"""Build an isolated BM1 schema pilot from the OLD ten train tasks, no selection."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from connectivity_vln.evaluation.manifest import validate_development_manifest
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    pilot = read(PROJECT/'configs/benchmark/pilot_v0.json')
    if pilot['split'] != 'train': raise ValueError('Do not inspect held-out payloads')
    paths = read(PROJECT/'configs/data/server_paths.json')
    source = PROJECT/paths['task_dataset']/'train/train.json.gz'
    gt = source.with_name('train_gt.json.gz')
    old_manifest = PROJECT/pilot['manifest_path']
    frozen = read(old_manifest)
    if sha(source) != frozen['source_task_sha256']: raise ValueError('Source hash changed')
    with gzip.open(source,'rt') as f: episodes = json.load(f)['episodes']
    cases = []; actors = []
    for e in frozen['episodes']:
        matches = [r for r in episodes if str(r['episode_id']) == e['episode_id']]
        if len(matches) != 1: raise ValueError('Episode is not unique')
        raw = matches[0]
        if str(raw['trajectory_id']) != e['trajectory_id'] or raw['scene_id'] != e['scene_id']:
            raise ValueError('Source group changed')
        for layout in e['layouts']:
            seed = layout['wireless_config']['seed']
            case_id = f"r2rconn:train:{Path(e['scene_id']).stem}:{e['episode_id']}:{layout['layout_id']}:{seed}"
            actor = {'case_id':case_id,'instruction':raw['instruction']['instruction_text'],
                'scene_id':e['scene_id'],'start_position':raw['start_position'],
                'start_rotation':raw['start_rotation']}
            actors.append(actor)
            cases.append({'case_id':case_id,'episode_id':e['episode_id'],'scene_id':e['scene_id'],
                'group_id':e['scene_id']+'|'+e['trajectory_id'],'source_split':'train',
                'assigned_split':'development','layout_id':layout['layout_id'],'channel_seed':seed,
                'instruction_sha256':hashlib.sha256(actor['instruction'].encode()).hexdigest(),
                'qualification':'unreviewed','protected_instance':{
                    'source_task_ref':{'path':str(source.relative_to(PROJECT)),'episode_id':e['episode_id']},
                    'gt_ref':{'path':str(gt.relative_to(PROJECT)),'episode_id':e['episode_id']},
                    'wireless':layout}})
    manifest = {'schema_version':'bm1-dev-v1','stage':'development_schema_audit',
        'official_release':False,'source':{'declared_name':'R2R_VLNCE_v1-3_preprocessed',
            'official_bytes_verified':False,'task_sha256':sha(source),'gt_sha256':sha(gt),
            'manifest_sha256':sha(old_manifest)},'cases':cases}
    checks = validate_development_manifest(manifest,actors)
    checks.update({'execution_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=PROJECT,text=True).strip(),
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'all original ten train tasks/30 AP cases; no exclusion, policy result access or held-out access',
        'source_sha256':{str(p.relative_to(PROJECT)):sha(p) for p in [Path(__file__).resolve(),
            PROJECT/'src/connectivity_vln/evaluation/manifest.py',old_manifest,source,gt]}})
    out = args.output_dir.resolve()
    if not out.is_relative_to((PROJECT/'runtime').resolve()): raise ValueError('Use runtime')
    out.mkdir(parents=True,exist_ok=False)
    for name,value in [('protected_manifest.json',manifest),('actor_inputs.json',actors),('checks.json',checks)]:
        (out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps(checks,indent=2),flush=True)


if __name__ == '__main__': main()
