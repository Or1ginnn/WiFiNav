"""Project-local, best-effort four-GPU wait queue; never stops foreign jobs."""
import argparse
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

PROJECT = Path(__file__).resolve().parents[1]
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def gpu_snapshot():
    def query(fields, kind):
        result = subprocess.run(['nvidia-smi', '--query-'+kind+'='+fields,
                                 '--format=csv,noheader,nounits'], check=True,
                                text=True, capture_output=True, timeout=15)
        return list(csv.reader(io.StringIO(result.stdout), skipinitialspace=True))
    devices = [{'index':int(i), 'uuid':u.strip(), 'memory_mib':int(m), 'utilization':int(v)}
               for i,u,m,v in query('index,uuid,memory.used,utilization.gpu','gpu')]
    processes = [{'uuid':u.strip(), 'pid':int(p)} for u,p in query('gpu_uuid,pid','compute-apps')]
    return {'devices':devices, 'processes':processes}


def idle(snapshot, config):
    selected = set(config['gpu_indices'])
    devices = [d for d in snapshot['devices'] if d['index'] in selected]
    if len(devices) != len(selected) or {d['index'] for d in devices} != selected:
        return False
    uuids = {d['uuid'] for d in devices}
    return (not any(p['uuid'] in uuids for p in snapshot['processes'])
            and all(d['memory_mib'] <= config['maximum_idle_memory_mib']
                    and d['utilization'] <= config['maximum_idle_utilization_percent'] for d in devices))


class IdleGate:
    def __init__(self, required):
        if required < 1:
            raise ValueError('stable_samples must be positive')
        self.required = required
        self.count = 0

    def observe(self, eligible):
        self.count = self.count+1 if eligible else 0
        return self.count >= self.required


def acquire_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError('Another project GPU waiter holds the lock')
    return handle


def pid_from(path):
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def own_service(pid, model):
    if pid is None:
        return False
    try:
        proc = Path('/proc')/str(pid)
        args = [v.decode(errors='replace') for v in (proc/'cmdline').read_bytes().split(b'\0') if v]
        expected={'--model':str(PROJECT/model['model_path']),
                  '--served-model-name':model['served_model_name'],
                  '--tensor-parallel-size':str(model['tensor_parallel_size'])}
        matches=all(flag in args and args.index(flag)+1<len(args) and args[args.index(flag)+1]==value
                    for flag,value in expected.items())
        return proc.stat().st_uid == os.getuid() and 'vllm.entrypoints.openai.api_server' in args and matches
    except OSError:
        return False


def service_ready(model):
    if not own_service(pid_from(PROJECT/'runtime/model_service.pid'), model):
        return False
    try:
        root=f"http://127.0.0.1:{model['port']}"
        with OPENER.open(root+'/health',timeout=3) as r:
            if r.status != 200:
                return False
        with OPENER.open(root+'/v1/models',timeout=3) as r:
            return model['served_model_name'] in [x['id'] for x in json.load(r)['data']]
    except (OSError, ValueError, KeyError):
        return False


def port_busy(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1):
            return True
    except OSError:
        return False


def belongs_to_service(pid, leader):
    try:
        if os.getpgid(pid) == leader:
            return True
        seen=set()
        while pid > 1 and pid not in seen:
            if pid == leader:
                return True
            seen.add(pid)
            status=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
            pid=int(status[1])
    except (OSError, ValueError):
        pass
    return False


def foreign_processes(snapshot, config, leader):
    uuids={d['uuid'] for d in snapshot['devices'] if d['index'] in config['gpu_indices']}
    return [p for p in snapshot['processes'] if p['uuid'] in uuids and not belongs_to_service(p['pid'],leader)]


def stop_own_group(process):
    # Only the new session created by this queue, never arbitrary GPU PIDs.
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


def probe_valid(results):
    if [r['case'] for r in results] != ['text','single_image','two_images']:
        return False
    if any(r.get('finish_reason') != 'stop' for r in results):
        return False
    a,b,c=[r['response']['content'].strip().lower() for r in results]
    return (a == 'ready' and 'red' in b and 'square' in b
            and all(s in c for s in ['red','square','blue','circle'])
            and c.index('red') < c.index('blue') and c.index('square') < c.index('circle'))


def source_hashes(config_path, config):
    files=[config_path, PROJECT/config['model_config'], Path(__file__).resolve(),
           PROJECT/'scripts/serve_model.py',PROJECT/'scripts/probe_model.py']
    return {str(p.relative_to(PROJECT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def run(config_path, directory, check_only=False):
    config=json.loads(config_path.read_text())
    if (any(type(i) is not int for i in config['gpu_indices']) or config['gpu_indices'] != [0,1,2,3]
            or config['payload'] != 'restore_existing_model_and_text_single_two_image_probe'):
        raise ValueError('This validated queue supports four GPUs and the model restore/probe job only')
    if config['poll_seconds'] < 1 or config['startup_poll_seconds'] < 1:
        raise ValueError('Polling intervals must be positive')
    model=json.loads((PROJECT/config['model_config']).read_text())
    if model['tensor_parallel_size'] != 4:
        raise ValueError('Model configuration must retain tested TP=4')
    if check_only:
        snapshot=gpu_snapshot()
        print(json.dumps({'idle_now':idle(snapshot,config),'snapshot':snapshot},indent=2))
        return
    lock=acquire_lock(PROJECT/'runtime/queue/four_gpu.lock')
    directory.mkdir(parents=True,exist_ok=False)
    (directory/'queue.pid').write_text(str(os.getpid())+'\n')
    sources=source_hashes(config_path,config)
    stamp=lambda:datetime.now(timezone.utc).isoformat()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=PROJECT,text=True).strip()
    (directory/'metadata.json').write_text(json.dumps({'queued_at_utc':stamp(),'commit':commit,
          'config':config,'model':model,'source_sha256':sources},indent=2)+'\n')
    def record(state, **values):
        row={'state':state,'at_utc':stamp(),'queue_pid':os.getpid(),**values}
        temp=directory/'status.tmp';temp.write_text(json.dumps(row,indent=2)+'\n');temp.replace(directory/'status.json')
        with (directory/'events.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    def cancelled():
        if (directory/'CANCEL').exists():
            raise InterruptedError('Queue cancellation requested')
    gate=IdleGate(config['stable_samples']);service=None;attempt=0
    try:
        while True:
            cancelled()
            if source_hashes(config_path,config) != sources:
                raise RuntimeError('Queued source/config changed; requeue a reviewed version')
            reused=service_ready(model)
            if not reused:
                try:
                    snapshot=gpu_snapshot()
                except (OSError,ValueError,subprocess.SubprocessError) as error:
                    gate.observe(False);record('waiting_query_error',error=str(error));time.sleep(config['poll_seconds']);continue
                eligible=idle(snapshot,config) and not port_busy(model['port'])
                ready=gate.observe(eligible)
                record('stabilizing' if eligible else 'waiting',stable_samples=gate.count,
                       required_samples=gate.required,snapshot=snapshot)
                if not ready:
                    time.sleep(config['poll_seconds']);continue
                # Fresh independent sample immediately before allocating the GPUs.
                try:
                    final_snapshot=gpu_snapshot()
                except (OSError,ValueError,subprocess.SubprocessError) as error:
                    gate.observe(False);record('waiting_query_error',phase='final_recheck',error=str(error))
                    time.sleep(config['poll_seconds']);continue
                if not idle(final_snapshot,config) or port_busy(model['port']):
                    gate.observe(False);record('waiting_final_recheck');time.sleep(config['poll_seconds']);continue
                cancelled()
            attempt+=1;work=directory/f'attempt_{attempt:03d}';work.mkdir()
            if not reused:
                env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']='0,1,2,3'
                with (work/'model_service.log').open('x') as out:
                    service=subprocess.Popen([model['python'],'-u',str(PROJECT/'scripts/serve_model.py')],
                        cwd=PROJECT,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
                (PROJECT/'runtime/model_service.pid').write_text(str(service.pid)+'\n')
                record('starting_model',model_pid=service.pid,attempt=attempt)
                deadline=time.monotonic()+config['startup_timeout_seconds'];raced=False
                while time.monotonic()<deadline:
                    cancelled()
                    if foreign_processes(gpu_snapshot(),config,service.pid):
                        stop_own_group(service);service=None;gate.observe(False);raced=True
                        record('waiting_startup_race',attempt=attempt);break
                    if service.poll() is not None:
                        raise RuntimeError('Model startup exited; inspect attempt model_service.log')
                    if service_ready(model):break
                    time.sleep(config['startup_poll_seconds'])
                if raced:
                    time.sleep(config['poll_seconds']);continue
                if not service_ready(model):raise TimeoutError('Model startup health timeout')
            if source_hashes(config_path,config) != sources:
                raise RuntimeError('Queued source/config changed before probe')
            record('probing',model_pid=pid_from(PROJECT/'runtime/model_service.pid'),reused_existing_service=reused)
            with (work/'probe.log').open('x') as out:
                probe=subprocess.Popen([model['python'],'-u',str(PROJECT/'scripts/probe_model.py'),
                    '--output',str(work/'service_probe.json')],cwd=PROJECT,stdin=subprocess.DEVNULL,
                    stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
                deadline=time.monotonic()+config['probe_timeout_seconds']
                try:
                    while probe.poll() is None and time.monotonic()<deadline:
                        cancelled();time.sleep(1)
                    if probe.poll() is None:raise TimeoutError('Probe timeout')
                    if probe.returncode != 0:raise RuntimeError('Model probe failed; inspect attempt probe.log')
                except BaseException:
                    stop_own_group(probe);raise
            if not probe_valid(json.loads((work/'service_probe.json').read_text())):
                raise RuntimeError('Probe HTTP succeeded but expected text/image answers were not verified')
            if source_hashes(config_path,config) != sources:
                raise RuntimeError('Queued source/config changed during probe')
            if service is not None and foreign_processes(gpu_snapshot(),config,service.pid):
                stop_own_group(service);service=None;gate.observe(False)
                record('waiting_probe_race',attempt=attempt);time.sleep(config['poll_seconds']);continue
            record('ready',model_pid=pid_from(PROJECT/'runtime/model_service.pid'),
                   reused_existing_service=reused,probe=str(work/'service_probe.json'),
                   next_research_step='empty-candidate recovery and candidate-route diagnostics; B3 No-Go retained')
            return
    except BaseException as error:
        if service is not None:stop_own_group(service)
        record('cancelled' if isinstance(error,(InterruptedError,KeyboardInterrupt)) else 'failed',error=str(error))
        raise
    finally:
        lock.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=PROJECT/'configs/ops/four_gpu_queue.json')
    parser.add_argument('--run-dir',type=Path)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    directory=(args.run_dir or PROJECT/'runtime/queue'/('restore_qwen35b_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).resolve()
    if not directory.is_relative_to((PROJECT/'runtime/queue').resolve()):
        raise ValueError('Queue directory must stay under project runtime/queue')
    def interrupt(signum, frame):
        raise KeyboardInterrupt('Queue terminated')
    signal.signal(signal.SIGTERM,interrupt)
    run(args.config.resolve(),directory,args.check_only)


if __name__=='__main__':main()
