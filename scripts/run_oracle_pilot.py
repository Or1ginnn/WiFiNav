"""Predeclared two-scene B3 closed-loop smoke; all attempted cases retained."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT/'src'))
import habitat_sim
from connectivity_vln.signal_simulation.route_a import SignalField, communication_metrics

read = lambda p: json.loads(Path(p).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-dir', type=Path, required=True)
    args = parser.parse_args()
    spec_path = PROJECT/'configs/benchmark/oracle_smoke_v0.json'
    spec = read(spec_path)
    pilot = read(PROJECT/spec['pilot_spec'])
    manifest_path = PROJECT/pilot['manifest_path']
    manifest = read(manifest_path)
    for filename, sha in manifest['config_hashes'].items():
        assert hashlib.sha256((PROJECT/filename).read_bytes()).hexdigest() == sha, filename
    paths = read(PROJECT/'configs/data/server_paths.json')
    source = PROJECT/paths['task_dataset']/pilot['split']/(pilot['split']+'.json.gz')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['source_task_sha256']
    episodes = []; scenes = set()
    for e in manifest['episodes']:
        if e['scene_id'] not in scenes:
            episodes.append(e); scenes.add(e['scene_id'])
    assert len(episodes) == 2
    batch = args.batch_dir.resolve()
    if not batch.is_relative_to((PROJECT/'runtime').resolve()):
        raise ValueError('Output must stay under runtime')
    # No mixed-code resume: a new batch is mandatory for this small smoke.
    batch.mkdir(parents=True, exist_ok=False)
    (batch/'manifest.json').write_bytes(manifest_path.read_bytes())
    (batch/'batch_metadata.json').write_text(json.dumps({
        'execution_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'started_at_utc':datetime.now(timezone.utc).isoformat(), 'spec':spec,
        'spec_sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest(),
        'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'selected_episodes':[e['episode_id'] for e in episodes],
        'not_full_b3_acceptance':True},indent=2)+'\n')
    rows = []
    for e in episodes:
        navmesh = (PROJECT/paths['scene_dataset_root']/e['scene_id']).with_suffix('.navmesh')
        assert hashlib.sha256(navmesh.read_bytes()).hexdigest() == e['navmesh_sha256']
        pf = habitat_sim.PathFinder(); assert pf.load_nav_mesh(str(navmesh))
        for weight in spec['lambda_values']:
            # NoSignal does not read radio truth; share one trajectory across APs.
            layouts = e['layouts'] if weight else e['layouts'][:1]
            for layout in layouts:
                name = f"episode_{e['episode_id']}_{layout['layout_id']}_lambda{weight:g}"
                instance = {'episode_id':e['episode_id'],'scene_id':e['scene_id'], **layout}
                instance_file = batch/(name+'_wireless.json')
                instance_file.write_text(json.dumps(instance,indent=2)+'\n')
                directory = batch/name
                command = [sys.executable,'-u',str(PROJECT/'scripts/run_vln_episode.py'),
                           '--config',str(PROJECT/pilot['navigation_config']), '--episode-id',e['episode_id'],
                           '--output-dir',str(directory), '--interface-version',spec['interface_version'],
                           '--stop-review',spec['stop_review'], '--planner',spec['planner'],
                           '--risk-weight',str(weight),'--wireless-instance',str(instance_file)]
                print('Starting',name,flush=True)
                started = time.perf_counter(); timed_out = False
                with (batch/(name+'.log')).open('x') as log:
                    process = subprocess.Popen(command,cwd=PROJECT,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
                    try:
                        code = process.wait(timeout=pilot['maximum_episode_wall_seconds'])
                    except subprocess.TimeoutExpired:
                        timed_out = True; process.terminate()
                        try: code = process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill(); code = process.wait()
                summary = read(directory/'summary.json') if (directory/'summary.json').exists() else None
                trajectory = ([json.loads(l) for l in (directory/'trajectory.jsonl').read_text().splitlines()]
                              if (directory/'trajectory.jsonl').exists() else [])
                status = {'name':name,'return_code':code,'timed_out':timed_out,
                          'wall_seconds':time.perf_counter()-started,'summary_present':summary is not None}
                (batch/(name+'_status.json')).write_text(json.dumps(status,indent=2)+'\n')
                for ap in (e['layouts'] if not weight else [layout]):
                    field = SignalField(pf,e['scene_id'],ap['ap_floor_position'],ap['wireless_config'])
                    replay = [{**step,'wireless':field.query(step['pose']['position'],i)} for i,step in enumerate(trajectory)]
                    row = {'episode_id':e['episode_id'],'layout_id':ap['layout_id'],'lambda':weight,
                           'run_dir':str(directory),'status':status,'summary':summary,
                           'trajectory_sha256':hashlib.sha256((directory/'trajectory.jsonl').read_bytes()).hexdigest() if trajectory else None,
                           'communication':communication_metrics(replay,ap['wireless_config']) if replay else None}
                    rows.append(row)
                    with (directory/('b3_replay_'+ap['layout_id']+'.jsonl')).open('x') as f:
                        for step in replay:
                            f.write(json.dumps({'step':step['step'],'pose':step['pose'],
                                                'motion_sim_time_seconds':step['motion_sim_time_seconds'],
                                                'wireless':step['wireless']})+'\n')
                (batch/'progress.json').write_text(json.dumps({'case_rows':len(rows),'rows':rows},indent=2)+'\n')
                print(json.dumps({**status,'success':summary['metrics']['success'] if summary else 0,
                                  'exit':summary['exit_reason'] if summary else 'missing_summary'}),flush=True)
    (batch/'oracle_report.json').write_text(json.dumps({'scope':'two-scene closed-loop smoke, not full B3 acceptance',
                                                       'rows':rows},indent=2)+'\n')
    print('Completed',len(rows),'case rows from 14 executions',flush=True)


if __name__ == '__main__':
    main()
