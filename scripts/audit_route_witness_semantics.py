#!/usr/bin/env python3
"""Extract same-anchor route and MP3D landmark evidence for manual review."""

import argparse
import json
from pathlib import Path
import subprocess

import numpy as np

from run_rss_multiwall_pilot import ROOT, read_ply, sha


DOORS = {'door', 'doorframe', 'door#frame', 'doorway', 'archway'}
LANDMARKS = {'bed', 'refrigerator', 'kitchen#cabinet', 'kitchen#counter', 'kitchen#appliance'}


def object_categories(house_path):
    names, categories = {}, {}
    with house_path.open(encoding='utf-8') as handle:
        for line in handle:
            row = line.split()
            if not row:
                continue
            if row[0] == 'C':
                names[int(row[1])] = row[3]
            elif row[0] == 'O':
                categories[int(row[1])] = int(row[3])
    return {key: names[category] for key, category in categories.items() if names.get(category) in DOORS | LANDMARKS}


def first_box_hit(route, lower, upper):
    """First along-route position in a horizontal box, in metres."""
    travelled = 0.0
    for start, end in zip(route, route[1:]):
        delta = end - start
        length = float(np.linalg.norm(delta))
        enter, leave = 0.0, 1.0
        for axis, coordinate in enumerate((0, 2)):
            if delta[coordinate] == 0:
                if not lower[axis] <= start[coordinate] <= upper[axis]:
                    enter, leave = 1.0, 0.0
                continue
            a = (lower[axis] - start[coordinate]) / delta[coordinate]
            b = (upper[axis] - start[coordinate]) / delta[coordinate]
            enter, leave = max(enter, min(a, b)), min(leave, max(a, b))
        if enter <= leave:
            return travelled + length * enter
        travelled += length
    return None


def distance_to_box(point, lower, upper):
    return float(np.linalg.norm(np.maximum(np.maximum(lower - point, point - upper), 0)))


def landmark_boxes(house, ply, floor_y, windows, goal):
    labels = object_categories(house)
    vertices, faces = read_ply(ply)
    selected = faces[np.isin(faces['object'], list(labels))]
    nearby, refrigerators = [], []
    probe = np.vstack([*windows.values(), goal])[:, [0, 2]]
    for object_id, category in sorted(labels.items()):
        indices = selected['indices'][selected['object'] == object_id]
        if not len(indices):
            continue
        xyz = vertices[indices].reshape(-1, 3)
        if xyz[:, 2].max() < floor_y - .2 or xyz[:, 2].min() > floor_y + 1.8:
            continue
        xz = xyz[:, [0, 1]].copy()
        xz[:, 1] *= -1
        lower, upper = xz.min(axis=0), xz.max(axis=0)
        goal_distance = distance_to_box(goal[[0, 2]], lower, upper)
        if category == 'refrigerator':
            refrigerators.append({'object_id': object_id, 'distance_to_goal_xz_m': goal_distance})
        distances = [distance_to_box(point, lower, upper) for point in probe]
        if min(distances) > 1.5:
            continue
        nearby.append({'object_id': object_id, 'category': category, 'xz_min': lower.tolist(), 'xz_max': upper.tolist(),
                       'goal_distance_xz_m': goal_distance,
                       'first_window_overlap_m': {key: first_box_hit(route, lower, upper) for key, route in windows.items()}})
    return nearby, sorted(refrigerators, key=lambda row: row['distance_to_goal_xz_m'])[:3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('data', 'profiles', 'opportunities', 'output'):
        parser.add_argument(f'--{key}', required=True, type=Path)
    parser.add_argument('--episode', required=True)
    parser.add_argument('--assumption', required=True)
    parser.add_argument('--interval', nargs=2, type=int, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT / 'runtime' not in output.parents or output.exists():
        parser.error('Expected a new output file inside project runtime')
    report = json.loads(args.opportunities.read_text())
    hashes = {key: sha(getattr(args, key)) for key in ('data', 'profiles', 'opportunities')}
    if any(report['source_sha256'][key] != hashes[key] for key in ('data', 'profiles')):
        raise ValueError('Inputs differ from the original audit')
    task = next(t for t in json.loads(args.data.read_text())['tasks'] if t['episode_id'] == args.episode)
    case = next(t for t in report['tasks'] if t['episode_id'] == args.episode)['assumptions'][args.assumption]
    window = next(w for w in case['windows'] if w['replaced_sample_interval'] == args.interval)
    candidate = next(c for c in window['candidates'] if c['nodes'] == window['best_witness_nodes'])['path_xyz']
    first, last = args.interval
    reference = [task['nodes'][node] for node in task['route_nodes']]
    if (window['reference_xyz'] != reference[first:last + 1]
            or [candidate[0], candidate[-1]] != [reference[first], reference[last]]):
        raise ValueError('The saved witness has different reference anchors')
    scene = task['scene_id']
    profiles = json.loads(args.profiles.read_text())
    assets = profiles['scenes_with_profiles'][scene]['source_sha256']
    for path, digest in assets.items():
        if sha(ROOT / path) != digest:
            raise ValueError(f'Asset changed since computation: {path}')
    paths = json.loads((ROOT / 'configs/data/server_paths.json').read_text())
    mesh = ROOT / paths['scene_dataset_root'] / scene
    windows = {'reference': np.array(window['reference_xyz']), 'candidate': np.array(candidate)}
    boxes, refrigerators = landmark_boxes(mesh.with_suffix('.house'), mesh.with_name(mesh.stem + '_semantic.ply'),
                                          task['floor_y'], windows, np.array(task['goal_position']))
    evidence = {
        'format': 'wifinav-route-witness-semantics-v1', 'policy_access': 'evaluation_only', 'model_calls': 0,
        'execution_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256': hashes, 'asset_sha256': assets, 'episode_id': args.episode, 'scene_id': scene,
        'assumption': args.assumption, 'replaced_sample_interval': args.interval,
        'instruction_sha256': task['instruction_sha256'], 'goal_xyz': task['goal_position'],
        'prefix_edges_preserved': first, 'suffix_edges_preserved': len(reference) - 1 - last,
        'nearby_object_boxes': boxes, 'nearest_refrigerator_boxes_on_floor': refrigerators,
        'door_box_order': {key: [item['object_id'] for item in sorted(
            (item for item in boxes if item['category'] in DOORS and item['first_window_overlap_m'][key] is not None),
            key=lambda item: item['first_window_overlap_m'][key])] for key in windows},
        'semantic_review_status': 'visual_confirmation_pending',
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(evidence, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps({key: evidence[key] for key in ('episode_id', 'door_box_order', 'nearest_refrigerator_boxes_on_floor')},
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
