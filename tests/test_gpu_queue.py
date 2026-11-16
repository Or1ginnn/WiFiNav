"""No real GPU/model launch: resource gating and daemon orchestration tests."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('gpu_queue',Path(__file__).resolve().parents[1]/'scripts/wait_for_gpus.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
CONFIG=json.loads((q.PROJECT/'configs/ops/four_gpu_queue.json').read_text())


def snapshot():
    return {'devices':[{'index':i,'uuid':str(i),'memory_mib':15,'utilization':0} for i in range(4)],'processes':[]}


def probes():
    return [{'case':n,'finish_reason':'stop','response':{'content':text}}
            for n,text in [('text','READY'),('single_image','A red square.'),('two_images','Red square. Blue circle.')]]


class QueueTest(unittest.TestCase):
    def test_low_memory_high_utilization_is_busy(self):
        s=snapshot();self.assertTrue(q.idle(s,CONFIG))
        s['devices'][1]['utilization']=98;self.assertFalse(q.idle(s,CONFIG))

    def test_any_compute_process_memory_or_missing_card_blocks(self):
        for kind in ['process','memory','missing','duplicate']:
            s=snapshot()
            if kind=='process':s['processes']=[{'uuid':'2','pid':999}]
            if kind=='memory':s['devices'][0]['memory_mib']=257
            if kind=='missing':s['devices'].pop()
            if kind=='duplicate':s['devices'].append(s['devices'][0])
            self.assertFalse(q.idle(s,CONFIG),kind)

    def test_busy_sample_resets_stability(self):
        gate=q.IdleGate(3)
        self.assertFalse(gate.observe(True));self.assertFalse(gate.observe(True))
        self.assertFalse(gate.observe(False));self.assertEqual(gate.count,0)
        self.assertFalse(gate.observe(True));self.assertFalse(gate.observe(True));self.assertTrue(gate.observe(True))

    def test_project_lock_prevents_duplicate_waiters(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lock';one=q.acquire_lock(p)
            try:
                with self.assertRaisesRegex(RuntimeError,'holds the lock'):q.acquire_lock(p)
            finally:one.close()
            q.acquire_lock(p).close()

    def test_probe_answers_and_order_are_validated(self):
        self.assertTrue(q.probe_valid(probes()))
        p=probes();p[2]['response']['content']='Blue circle. Red square.'
        self.assertFalse(q.probe_valid(p))
        p=probes();p[0]['finish_reason']='length';self.assertFalse(q.probe_valid(p))

    def test_foreign_pid_is_not_treated_as_service_child(self):
        s=snapshot();s['processes']=[{'uuid':'0','pid':10},{'uuid':'1','pid':20}]
        with patch.object(q,'belongs_to_service',side_effect=lambda pid,leader:pid==10):
            self.assertEqual(q.foreign_processes(s,CONFIG,10),[{'uuid':'1','pid':20}])

    def orchestration(self, *, race=False, startup_race=False, query_error=False, cancel=False, changed=False, reuse=False, bad_probe=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'runtime').mkdir();(root/'configs').mkdir()
            config=copy.deepcopy(CONFIG);config.update({'poll_seconds':1,'stable_samples':1 if race or startup_race else 3})
            config_path=root/'configs/queue.json';config_path.write_text(json.dumps(config))
            model={'tensor_parallel_size':4,'python':'unused','port':8010}
            model_path=root/config['model_config'];model_path.parent.mkdir(parents=True,exist_ok=True);model_path.write_text(json.dumps(model))
            run_dir=root/'runtime/queue/test';launches=[];stops=[];models=[]
            free=snapshot();busy=snapshot();busy['processes']=[{'uuid':'1','pid':99}]
            samples=([free,busy,free,free,free,free] if race else [busy,free,free,free,free,free,free])
            if startup_race:samples=[free,free,busy,free,free,free,free]
            if query_error:samples=[free,free,OSError('query failed'),free,free,free,free,free,free]
            scans=iter(samples)
            def scan():
                value=next(scans,free)
                if isinstance(value,Exception):raise value
                return copy.deepcopy(value)
            class Child:
                pid=99991;returncode=None
                def poll(self):return self.returncode
            def popen(command,**kwargs):
                child=Child()
                if any(str(x).endswith('serve_model.py') for x in command):launches.append('model');models.append(child)
                else:
                    launches.append('probe');child.returncode=0
                    out=probes()
                    if bad_probe:out[0]['response']['content']='wrong'
                    Path(command[command.index('--output')+1]).write_text(json.dumps(out))
                return child
            def sleep(_):
                if cancel:(run_dir/'CANCEL').touch()
            def stop(process):
                stops.append(process.pid);process.returncode=-15
            hashes=iter([{'version':'a'},{'version':'b'}]) if changed else None
            def digest(*_):return next(hashes,{'version':'b'}) if changed else {'version':'a'}
            with contextlib.ExitStack() as stack:
                for name,value in [('PROJECT',root),('gpu_snapshot',scan),('port_busy',lambda p:False),
                                   ('source_hashes',digest),('service_ready',lambda model:reuse or any(p.poll() is None for p in models)),
                                   ('stop_own_group',stop)]:
                    stack.enter_context(patch.object(q,name,value))
                stack.enter_context(patch.object(q.subprocess,'Popen',side_effect=popen))
                stack.enter_context(patch.object(q.subprocess,'check_output',return_value='testcommit\n'))
                stack.enter_context(patch.object(q.time,'sleep',side_effect=sleep))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                if cancel or changed or bad_probe:
                    with self.assertRaises((InterruptedError,RuntimeError)):q.run(config_path,run_dir)
                else:q.run(config_path,run_dir)
            status=json.loads((run_dir/'status.json').read_text())
            states=[json.loads(l)['state'] for l in (run_dir/'events.jsonl').read_text().splitlines()]
            return launches,stops,status,states

    def test_busy_then_stable_starts_exactly_once(self):
        launched,_,status,states=self.orchestration()
        self.assertEqual(launched,['model','probe']);self.assertEqual(status['state'],'ready')
        self.assertEqual(states.count('stabilizing'),3)

    def test_final_race_rechecks_instead_of_double_launch(self):
        launched,_,status,states=self.orchestration(race=True)
        self.assertIn('waiting_final_recheck',states);self.assertEqual(launched,['model','probe'])

    def test_cancel_or_changed_sources_never_start_model(self):
        for kwargs in [{'cancel':True},{'changed':True}]:
            launched,_,status,_=self.orchestration(**kwargs)
            self.assertEqual(launched,[]);self.assertIn(status['state'],['cancelled','failed'])

    def test_failed_probe_does_not_stop_preexisting_service(self):
        launched,stops,status,_=self.orchestration(reuse=True,bad_probe=True)
        self.assertEqual(launched,['probe']);self.assertEqual(stops,[]);self.assertEqual(status['state'],'failed')

    def test_startup_race_only_stops_own_model_and_waits_again(self):
        launched,stops,status,states=self.orchestration(startup_race=True)
        self.assertEqual(launched,['model','model','probe']);self.assertEqual(len(stops),1)
        self.assertIn('waiting_startup_race',states);self.assertEqual(status['state'],'ready')

    def test_query_failure_resets_gate_and_never_launches_early(self):
        launched,_,status,states=self.orchestration(query_error=True)
        self.assertIn('waiting_query_error',states);self.assertEqual(states.count('stabilizing'),5)
        self.assertEqual(launched,['model','probe']);self.assertEqual(status['state'],'ready')


if __name__=='__main__':unittest.main()
