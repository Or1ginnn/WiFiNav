"""CPU source audit of frozen train tasks; no filtering or policy outcomes."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    pilot = read(PROJECT/'configs/benchmark/pilot_v0.json')
    paths = read(PROJECT/'configs/data/server_paths.json')
    manifest_path = PROJECT/pilot['manifest_path']
    manifest = read(manifest_path)
    if pilot['split'] != 'train': raise ValueError('Audit is train development only')
    source = PROJECT/paths['task_dataset']/'train/train.json.gz'
    gt_path = source.with_name('train_gt.json.gz')
    if sha(source) != manifest['source_task_sha256']: raise ValueError('Source task changed')
    with gzip.open(source,'rt') as f: episodes = json.load(f)['episodes']
    with gzip.open(gt_path,'rt') as f: gt = json.load(f)
    rows = []
    for selected in manifest['episodes']:
        matches = [e for e in episodes if str(e['episode_id']) == selected['episode_id']]
        if len(matches) != 1: raise ValueError('Source ID not unique')
        e = matches[0]
        if str(e['trajectory_id']) != selected['trajectory_id'] or e['scene_id'] != selected['scene_id']:
            raise ValueError('Source group/scene mismatch')
        text = e['instruction']['instruction_text']
        ys = [p[1] for p in e['reference_path']]
        dense = [p[1] for p in gt[selected['episode_id']]['locations']]
        rows.append({'episode_id':selected['episode_id'],'scene_id':e['scene_id'],
            'trajectory_group':str(e['trajectory_id']),
            'instruction_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'source_reference_point_count':len(ys),'source_reference_y_range_m':max(ys)-min(ys),
            'dense_gt_point_count':len(dense),'dense_gt_y_range_m':max(dense)-min(dense),
            'goal_start_y_difference_m':e['goals'][0]['position'][1]-e['start_position'][1],
            'not_a_single_floor_qualification':True})
    out = args.output_dir.resolve()
    if not out.is_relative_to((PROJECT/'runtime').resolve()): raise ValueError('Use project runtime')
    out.mkdir(parents=True,exist_ok=False)
    result = {'execution_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=PROJECT,text=True).strip(),
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'source_sha256':{str(p.relative_to(PROJECT)):sha(p) for p in [source,gt_path,manifest_path,Path(__file__).resolve()]},
        'scope':'frozen ten train tasks; derived metadata only; no policy outcomes, filtering, semantic ground truth or held-out access',
        'rows':rows}
    (out/'source_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__ == '__main__': main()
