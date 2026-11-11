"""Compare frozen pilot interface batches, keeping every selected episode."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

PROJECT = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(Path(p).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', action='append', required=True, help='label=directory')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    batches = dict(item.split('=', 1) for item in args.batch)
    output = args.output.resolve()
    if not output.is_relative_to((PROJECT/'runtime').resolve()):
        raise ValueError('Output must stay under runtime')
    snapshots = [Path(b)/'manifest.json' for b in batches.values()]
    snapshot = snapshots[0].read_bytes()
    assert all(p.read_bytes() == snapshot for p in snapshots), 'Manifest changed'
    episodes = json.loads(snapshot)['episodes']
    rows = []; references = {}
    for e in episodes:
        row = {'episode_id':e['episode_id']}
        for label, batch in batches.items():
            d = Path(batch)/('episode_'+e['episode_id'])
            meta = read(d/'metadata.json')
            settings = dict(meta['settings'])
            settings.pop('interface_version', None); settings.pop('stop_review_enabled', None)
            immutable = (meta['model'], settings, meta['task_sha256'], meta['scene_id'], meta['trajectory_id'])
            references.setdefault(e['episode_id'], immutable)
            assert immutable == references[e['episode_id']], (label, e['episode_id'], 'Non-interface config changed')
            s = read(d/'summary.json'); metrics = s['metrics']
            row[label] = {k:metrics[k] for k in ['success','spl','ndtw_exact_euclidean','distance_to_goal','path_length_m']}
            row[label].update({k:s[k] for k in ['exit_reason','error','decisions','model_request_attempts']})
            row[label]['wall_seconds'] = read(Path(batch)/('episode_'+e['episode_id']+'_status.json'))['wall_seconds']
        rows.append(row)
    aggregate = {}
    for label in batches:
        aggregate[label] = {k:statistics.mean(row[label][k] for row in rows) for k in
                            ['success','spl','ndtw_exact_euclidean','path_length_m','model_request_attempts','wall_seconds']}
        aggregate[label]['runtime_error_episodes'] = sum(row[label]['error'] is not None for row in rows)
    result = {'manifest_sha256':hashlib.sha256(snapshot).hexdigest(), 'batches':batches,
              'checked':'identical manifest bytes; task/model/scene/trajectory/settings except interface flags',
              'caveat':'all selected tasks; metrics include any error prefixes; development set only',
              'aggregate':aggregate, 'episodes':rows}
    with output.open('x') as f:
        json.dump(result,f,indent=2); f.write('\n')
    print(json.dumps(aggregate,indent=2))


if __name__ == '__main__':
    main()
