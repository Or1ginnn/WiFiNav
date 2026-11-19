#!/usr/bin/env python3
"""Protected CPU audit of local route alternatives in the fixed AP review batch."""

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter
import hashlib
from itertools import accumulate
import json
from pathlib import Path
import subprocess
import sys

from render_ap_review_html import add_multiwall, report_payload


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from connectivity_vln.benchmark.single_floor import route_metrics
from connectivity_vln.navigation.weighted_planner import shortest_path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outage_windows(samples, threshold):
    start = None
    for index, (a, b) in enumerate(zip(samples, samples[1:])):
        if (a + b) / 2 < threshold:
            if start is None:
                start = index
        elif start is not None:
            yield start, index
            start = None
    if start is not None:
        yield start, len(samples) - 1


def candidate_window(task, samples, grid_rssi, window, distances, radio, settings):
    context = settings['anchor_context_m']
    first = max(0, bisect_right(distances, distances[window[0]] - context) - 1)
    last = min(len(samples) - 1, bisect_left(distances, distances[window[1]] + context))
    route = task['route_nodes']
    start, goal = route[first], route[last]
    weak, threshold = radio['weak_threshold_dbm'], radio['outage_threshold_dbm']
    baseline = route_metrics(samples[first:last + 1], task['route_lengths_m'][first:last], weak, threshold)
    signal = dict(enumerate(grid_rssi))
    signal.update({start: samples[first], goal: samples[last]})
    adjacency = [[] for _ in task['nodes']]
    edge_lengths = {}
    for a, b, length in task['edges']:
        if a in signal and b in signal:
            adjacency[a].append((b, length))
            adjacency[b].append((a, length))
            edge_lengths[a, b] = edge_lengths[b, a] = length
    budget = baseline['length_m'] * (1 + settings['local_detour_fraction'])
    candidates = {}
    error = None
    for weight in settings['risk_weights']:
        try:
            path, _ = shortest_path(adjacency, start, goal, lambda node: signal[node] < threshold, weight)
        except ValueError as exc:
            if str(exc) != 'No shared-grid route to selected local target':
                raise
            error = str(exc)
            break
        key = tuple(path)
        if key in candidates:
            candidates[key]['risk_weights'].append(weight)
            continue
        lengths = [edge_lengths[a, b] for a, b in zip(path, path[1:])]
        metrics = route_metrics([signal[node] for node in path], lengths, weak, threshold)
        reduction = baseline['outage_length_m'] - metrics['outage_length_m']
        candidates[key] = {
            'nodes': path, 'path_xyz': [task['nodes'][node] for node in path],
            'risk_weights': [weight], 'metrics': metrics, 'outage_reduction_m': reduction,
            'within_budget': metrics['length_m'] <= budget + 1e-6,
            'enough_improvement': reduction + 1e-6 >= settings['minimum_outage_reduction_m'],
        }
    witnesses = [candidate for candidate in candidates.values() if candidate['within_budget'] and candidate['enough_improvement']]
    best = min(witnesses, key=lambda c: (c['metrics']['outage_length_m'], c['metrics']['length_m'], c['nodes']), default=None)
    return {
        'weak_sample_interval': list(window), 'replaced_sample_interval': [first, last],
        'reference_xyz': [task['nodes'][node] for node in route[first:last + 1]],
        'reference_metrics': baseline, 'max_candidate_length_m': budget, 'candidates': list(candidates.values()),
        'best_witness_nodes': best['nodes'] if best else None, 'search_error': error,
    }


def audit_task(task, radio, settings):
    points, route = task['nodes'], task['route_nodes']
    distances = [0.0, *accumulate(task['route_lengths_m'])]
    if len(distances) != len(route) or not all(0 <= node < len(points) for node in route):
        raise ValueError(f'Invalid reference route for episode {task["episode_id"]}')
    coverage = task['multiwall']
    rows = {}
    for key, profile in coverage['assumptions'].items():
        samples, grid = profile['samples_dbm'], coverage['grid_rssi_dbm'][key]
        threshold = radio['outage_threshold_dbm']
        baseline = route_metrics(samples, task['route_lengths_m'], radio['weak_threshold_dbm'], threshold)
        if abs(baseline['outage_length_m'] - profile['outage_length_m']) > 1e-7:
            raise ValueError(f'Reference coverage mismatch: {task["episode_id"]} {key}')
        windows = [candidate_window(task, samples, grid, interval, distances, radio, settings)
                   for interval in outage_windows(samples, threshold)]
        if not windows:
            status = 'no_reference_outage_segment'
        elif any(window['best_witness_nodes'] is not None for window in windows):
            status = 'geometric_candidate_pending_semantic_review'
        else:
            status = 'no_witness_in_fixed_scan'
        rows[key] = {
            'status': status, 'reference_metrics': baseline, 'reference_samples_below': sum(v < threshold for v in samples),
            'windows': windows,
        }
    return {
        'episode_id': task['episode_id'], 'scene_id': task['scene_id'], 'trajectory_id': task['trajectory_id'],
        'source_split': 'train', 'instruction_sha256': task['instruction_sha256'],
        'navmesh_sha256': task['navmesh_sha256'], 'ap_node': task['default_ap_node'],
        'ap_review_status': 'pending_human_review', 'assumptions': rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('data', 'audit', 'profiles', 'grids', 'output'):
        parser.add_argument(f'--{key}', required=True, type=Path)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/benchmark/single_floor_route_opportunity_v1.json')
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT / 'runtime' not in output.parents or output.exists():
        parser.error('Expected a new diagnostic file inside project runtime')
    settings = json.loads(args.config.read_text())
    hashes = {key: sha256(getattr(args, key)) for key in ('data', 'audit', 'profiles', 'grids')}
    if hashes != settings['source_sha256']:
        raise ValueError('Inputs differ from the fixed AP review batch')
    source_audit = json.loads(args.audit.read_text())
    data = json.loads(args.data.read_text())
    payload = report_payload(source_audit, data)
    add_multiwall(payload, hashes['data'], args.profiles, args.grids)
    tasks = payload['tasks']
    audit = {row['episode_id']: row for row in payload['scope']}
    groups = {(task['scene_id'], task['trajectory_id']) for task in tasks}
    scenes = {scene for scene, _ in groups}
    if (data['metadata']['specification']['source_split'] != 'train' or len(tasks) != settings['expected_tasks']
            or len(scenes) != settings['expected_scenes'] or len(groups) != len(tasks)):
        raise ValueError('Unexpected train-only scene or source-path grouping')
    for task in tasks:
        row = audit[task['episode_id']]
        instruction_hash = hashlib.sha256(task['instruction'].encode()).hexdigest()
        if (row['native_geometry_check'] != 'passed' or row['scope_status'] != 'candidate'
                or any(row[key] != task[key] for key in ('scene_id', 'trajectory_id', 'instruction'))
                or instruction_hash != task['instruction_sha256']
                or len(task['multiwall']['assumptions']) != settings['expected_assumptions_per_task']):
            raise ValueError(f'Unexpected source task evidence for episode {task["episode_id"]}')
    radio = payload['multiwall']['config']
    rows = [audit_task(task, radio, settings) for task in tasks]
    statuses = Counter(case['status'] for row in rows for case in row['assumptions'].values())
    witnesses = [row['episode_id'] for row in rows if any(
        case['status'] == 'geometric_candidate_pending_semantic_review' for case in row['assumptions'].values())]
    result = {
        'format': 'wifinav-single-floor-route-opportunity-v1', 'policy_access': 'evaluation_only',
        'official_release': False, 'model_calls': 0,
        'execution_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'config_sha256': sha256(args.config), 'config': settings, 'source_sha256': hashes,
        'source_profiles_commit': payload['multiwall']['execution_commit'], 'source_grids_commit': payload['multiwall']['grid_commit'],
        'summary': {'language_tasks': len(rows), 'source_path_groups': len(groups), 'scenes': len(scenes),
                    'assumption_cases': sum(statuses.values()), 'statuses': dict(statuses), 'tasks_with_witness': witnesses,
                    'diagnosed_windows': sum(len(case['windows']) for row in rows for case in row['assumptions'].values())},
        'tasks': rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps(result['summary'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
