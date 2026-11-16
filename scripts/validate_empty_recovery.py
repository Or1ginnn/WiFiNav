"""Independent three-case engineering validation; does not replace full B3."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    spec_path = PROJECT/'configs/benchmark/empty_recovery_validation_v1.json'
    spec = read(spec_path)
    source = PROJECT/spec['source_batch']
    if sha(source/'manifest.json') != spec['manifest_sha256']:
        raise ValueError('Frozen manifest hash mismatch')
    manifest = read(source/'manifest.json')
    pilot = read(PROJECT/'configs/benchmark/pilot_v0.json')
    output = args.output_dir.resolve()
    if not output.is_relative_to((PROJECT/'runtime').resolve()):
        raise ValueError('Output must stay under runtime')
    output.mkdir(parents=True, exist_ok=False)
    model = read(PROJECT/pilot['model_config'])
    metadata = {'execution_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'started_at_utc':datetime.now(timezone.utc).isoformat(), 'spec':spec,
        'spec_sha256':sha(spec_path), 'manifest_sha256':sha(source/'manifest.json'),
        'model_config':model, 'source_batch_metadata':read(source/'batch_metadata.json'),
        'source_sha256':{name:sha(PROJECT/name) for name in [
            'scripts/validate_empty_recovery.py','scripts/run_vln_episode.py',
            'src/connectivity_vln/navigation/pixel_policy.py',
            'src/connectivity_vln/navigation/weighted_planner.py']}}
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    rows = []
    for case in spec['cases']:
        episode = next(e for e in manifest['episodes'] if e['episode_id'] == case['episode_id'])
        layout = next(a for a in episode['layouts'] if a['layout_id'] == case['layout_id'])
        name = f"episode_{case['episode_id']}_{case['layout_id']}_lambda{case['lambda']}"
        instance = output/(name+'_wireless.json')
        instance.write_text(json.dumps({'episode_id':episode['episode_id'],'scene_id':episode['scene_id'],**layout},indent=2)+'\n')
        command = [sys.executable,'-u',str(PROJECT/'scripts/run_vln_episode.py'),
            '--config',str(PROJECT/pilot['navigation_config']),'--episode-id',case['episode_id'],
            '--output-dir',str(output/name),'--interface-version','v1','--stop-review','off',
            '--planner','grid','--risk-weight',str(case['lambda']),'--wireless-instance',str(instance),
            '--empty-candidate-recovery']
        timed_out = False
        with (output/(name+'.log')).open('x') as log:
            process = subprocess.Popen(command,cwd=PROJECT,stdout=log,stderr=subprocess.STDOUT)
            try: code = process.wait(timeout=pilot['maximum_episode_wall_seconds'])
            except subprocess.TimeoutExpired:
                timed_out = True
                process.terminate()
                try: code = process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); code = process.wait()
        summary = output/name/'summary.json'
        rows.append({'case':case,'return_code':code,'timed_out':timed_out,
            'summary':read(summary) if summary.exists() else None,
            'scope':'complete only when no error or timeout; otherwise error prefix retained'})
        (output/'report.json').write_text(json.dumps({'rows':rows,'not_full_b3_acceptance':True},indent=2)+'\n')
    print(json.dumps(rows,indent=2),flush=True)


if __name__ == '__main__': main()
