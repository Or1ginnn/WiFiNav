#!/usr/bin/env python3
"""Re-evaluate a recorded pair of local paths with equal multi-wall sampling density."""

import argparse
import json
import math
from pathlib import Path
import subprocess

import drjit as dr
import numpy as np

from run_rss_multiwall_pilot import ROOT, evaluate, sha


def sampled_route(label, path, floor, max_spacing):
    points = [path[0]]
    lengths = []
    for a, b in zip(path, path[1:]):
        a, b = np.asarray(a), np.asarray(b)
        distance = float(np.linalg.norm(b - a))
        if not distance:
            continue
        count = math.ceil(distance / max_spacing)
        for index in range(1, count + 1):
            points.append((a + (b - a) * (index / count)).tolist())
            lengths.append(distance / count)
    return {'episode_id': label, 'floor_y': floor, 'points_xyz': points, 'segment_lengths_m': lengths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data', 'profiles', 'opportunities', 'output'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    parser.add_argument('--episode', required=True)
    parser.add_argument('--assumption', required=True)
    parser.add_argument('--interval', type=int, nargs=2, required=True)
    parser.add_argument('--spacing', type=float, nargs='+', required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT / 'runtime' not in output.parents or output.exists():
        parser.error('Expected a new diagnostic file inside project runtime')
    if any(not math.isfinite(step) or step <= 0 for step in args.spacing):
        parser.error('Sampling spacings must be finite and positive')
    dr.set_thread_count(4)
    opportunities = json.loads(args.opportunities.read_text())
    hashes = {key: sha(getattr(args, key)) for key in ('data', 'profiles', 'opportunities')}
    if any(opportunities['source_sha256'][key] != hashes[key] for key in ('data', 'profiles')):
        raise ValueError('Recheck inputs differ from the diagnosed layouts')
    profiles = json.loads(args.profiles.read_text())
    task = next(t for t in json.loads(args.data.read_text())['tasks'] if t['episode_id'] == args.episode)
    diag = next(t for t in opportunities['tasks'] if t['episode_id'] == args.episode)
    window = next(w for w in diag['assumptions'][args.assumption]['windows'] if w['replaced_sample_interval'] == args.interval)
    reference = window['reference_xyz']
    candidate = next(c['path_xyz'] for c in window['candidates'] if c['nodes'] == window['best_witness_nodes'])
    if (candidate[0], candidate[-1]) != (reference[0], reference[-1]):
        raise ValueError('Candidate and reference anchors differ')
    scene = task['scene_id']
    asset_hashes = profiles['scenes_with_profiles'][scene]['source_sha256']
    for path, digest in asset_hashes.items():
        if sha(ROOT / path) != digest:
            raise ValueError(f'Scene asset differs from the audited data: {path}')
    paths = json.loads((ROOT / 'configs/data/server_paths.json').read_text())
    mesh = Path(paths['scene_dataset_root']) / scene
    results = []
    for step in args.spacing:
        routes = [sampled_route(label, path, task['floor_y'], step)
                  for label, path in (('reference', reference), ('candidate', candidate))]
        config = profiles['config']
        batch = {'mesh': str(mesh), 'routes': routes, 'layouts': [{'id': 'fixed_ap', 'ap_floor_xyz': task['default_ap_position']}],
                 'config': config}
        coverage = evaluate(batch, config)['coverage']
        comparisons = {}
        for key, profiles_by_route in coverage.items():
            metrics = {route: {k: v for k, v in report[0].items() if k != 'samples_dbm'}
                       for route, report in profiles_by_route.items()}
            comparisons[key] = {**metrics, 'outage_reduction_m': metrics['reference']['outage_length_m'] -
                                metrics['candidate']['outage_length_m']}
        results.append({'max_sample_spacing_m': step, 'assumptions': comparisons})
        row = comparisons[args.assumption]
        print(f'{step:g} m: {row["reference"]["outage_length_m"]:.3f} → {row["candidate"]["outage_length_m"]:.3f} m', flush=True)
    report = {
        'format': 'wifinav-single-floor-route-recheck-v1', 'policy_access': 'evaluation_only', 'model_calls': 0,
        'execution_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256': hashes, 'asset_sha256': asset_hashes, 'episode_id': args.episode,
        'selected_assumption': args.assumption, 'replaced_sample_interval': args.interval,
        'semantic_review_status': 'pending', 'results': results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write('\n')


if __name__ == '__main__':
    main()
