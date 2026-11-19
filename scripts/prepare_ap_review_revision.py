#!/usr/bin/env python3
"""Validate an HTML AP draft and prepare a separate CPU re-evaluation batch."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def same_xyz(actual, expected):
    return isinstance(actual, list) and len(actual) == 3 and all(
        type(value) in (int, float) and abs(value - reference) <= 1e-5
        for value, reference in zip(actual, expected)
    )


def selected_nodes(data, draft):
    metadata = data['metadata']
    tasks = {task['episode_id']: task for task in data['tasks']}
    rows = draft.get('changes')
    if (draft.get('format') != 'wifinav-ap-review-edits-v1'
            or any(draft.get(key) != metadata[key] for key in ('execution_commit', 'source_sha256', 'specification'))
            or not isinstance(rows, list) or len(rows) != len(tasks)):
        raise ValueError('Draft was exported from a different AP review batch')
    selected = {}
    for row in rows:
        episode = row['episode_id']
        task = tasks.get(episode)
        if task is None or episode in selected:
            raise ValueError(f'Unknown or repeated episode {episode}')
        if any(row.get(key) != task[key] for key in ('trajectory_id', 'scene_id', 'navmesh_sha256')):
            raise ValueError(f'Task or navmesh mismatch for episode {episode}')
        initial = task['default_ap_node']
        node = row.get('selected_ap_node')
        if (type(node) is not int or node not in task['ap_candidate_nodes']
                or type(row.get('initial_ap_node')) is not int or row['initial_ap_node'] != initial
                or not same_xyz(row.get('initial_ap_position'), task['default_ap_position'])):
            raise ValueError(f'Invalid initial or selected AP node for episode {episode}')
        changed = node != initial
        position = task['nodes'][node] if changed else task['default_ap_position']
        if (not same_xyz(row.get('selected_ap_position'), position)
                or row.get('changed') is not changed or row.get('native_revalidation_required') is not changed):
            raise ValueError(f'Invalid AP position or edit flags for episode {episode}')
        selected[episode] = node
    return selected


def native_check(finder, task, points, node, tolerance, habitat_sim):
    ap = points[node]
    floor = task['floor_y']
    episode = task['episode_id']
    if abs(float(ap[1]) - floor) > tolerance or not finder.is_navigable(ap):
        raise ValueError(f'Episode {episode} AP {node} is outside the navigable floor scope')
    longest = 0.0
    for index in task['route_nodes']:
        path = habitat_sim.ShortestPath()
        path.requested_start, path.requested_end = ap, points[index]
        if (not finder.find_path(path) or not math.isfinite(path.geodesic_distance) or not path.points
                or any(abs(float(point[1]) - floor) > tolerance for point in path.points)):
            raise ValueError(f'Episode {episode} AP {node} has no accepted native single-floor path to route node {index}')
        longest = max(longest, float(path.geodesic_distance))
    return {'route_points_checked': len(task['route_nodes']), 'max_geodesic_to_route_m': longest}


def apply_draft(data, selected):
    import habitat_sim
    import numpy as np
    from build_single_floor_ap_review import wireless_preview

    assets = ROOT / json.loads((ROOT / 'configs/data/server_paths.json').read_text())['scene_dataset_root']
    spec = data['metadata']['specification']
    tolerance = spec['height_tolerance_m'] + spec['height_epsilon_m']
    finders, changes = {}, {}
    for task in data['tasks']:
        episode = task['episode_id']
        node = selected[episode]
        old_node = task['default_ap_node']
        if node == old_node:
            continue
        scene = task['scene_id']
        if scene not in finders:
            mesh = (assets / scene).with_suffix('.navmesh')
            digest = sha256(mesh.read_bytes())
            finder = habitat_sim.PathFinder()
            if not finder.load_nav_mesh(str(mesh)):
                raise ValueError(f'Could not load {mesh}')
            finders[scene] = finder, digest
        finder, digest = finders[scene]
        if digest != task['navmesh_sha256']:
            raise ValueError(f'Episode {episode} source navmesh hash mismatch')
        points = np.asarray(task['nodes'], dtype=np.float32)
        evidence = native_check(finder, task, points, node, tolerance, habitat_sim)
        adjacency = [[] for point in points]
        for a, b, length in task['edges']:
            adjacency[a].append((b, length))
            adjacency[b].append((a, length))
        position = task['nodes'][node]
        config = dict(task['wireless_config'], ap_floor_position=position)
        task.update(wireless_preview(finder, scene, points, adjacency, task['route_nodes'],
                                     task['route_lengths_m'], node, config))
        changes[episode] = {'initial_ap_node': old_node, 'initial_ap_position': task['default_ap_position'],
                            'selected_ap_node': node, 'selected_ap_position': position, **evidence}
        task.update(default_ap_node=node, default_ap_position=position)
    return habitat_sim.__version__, changes


def encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--draft', type=Path, required=True)
    parser.add_argument('--multiwall-config', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if ROOT / 'runtime' not in out.parents or out.exists():
        parser.error('Expected a new output directory inside project runtime')
    data_raw, audit_raw, draft_raw = (path.read_bytes() for path in (args.data, args.audit, args.draft))
    data, audit, draft = (json.loads(raw) for raw in (data_raw, audit_raw, draft_raw))
    config_raw = args.multiwall_config.read_bytes()
    config = json.loads(config_raw)
    if config.get('rss_backend') != 'semantic_multiwall' or config.get('source_ap_review_sha256') != sha256(data_raw):
        raise ValueError('Multi-wall config must be pinned to the input AP batch')
    if audit['metadata'] != data['metadata']:
        raise ValueError('Source scope audit differs from the AP batch')
    selected = selected_nodes(data, draft)
    habitat_version, changes = apply_draft(data, selected)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    revision = {
        'format': 'wifinav-ap-review-revision-v1',
        'execution_commit': commit, 'habitat_sim_version': habitat_version,
        'base_data_sha256': sha256(data_raw), 'base_audit_sha256': sha256(audit_raw),
        'base_config_sha256': sha256(config_raw), 'draft_sha256': sha256(draft_raw),
        'changed_tasks': changes, 'model_calls': 0,
    }
    metadata = data['metadata']
    data['metadata'] = audit['metadata'] = dict(
        metadata, created_at_utc=datetime.now(timezone.utc).isoformat(),
        execution_commit=commit, ap_layout_revision=revision,
        field_note='Changed AP positions were revalidated with native Habitat and the route_a proxy. Use the separate multi-wall report for semantic RSSI.',
    )
    data_bytes = encode(data)
    config['source_ap_review_sha256'] = sha256(data_bytes)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'ap_review_data.json').write_bytes(data_bytes)
    (out / 'source_scope_audit.json').write_bytes(encode(audit))
    (out / 'multiwall_config.json').write_bytes(encode(config))
    (out / 'revision.json').write_bytes(encode({**revision, 'data_sha256': sha256(data_bytes)}))
    print(f'{len(changes)}/{len(selected)} AP positions revised by native Habitat · {out}', flush=True)


if __name__ == '__main__':
    main()
