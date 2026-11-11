"""Offline local-subgoal route-space diagnostic, never an online VLN score."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import habitat_sim
import numpy as np
from connectivity_vln.navigation.weighted_planner import NavmeshRiskPlanner
from connectivity_vln.signal_simulation.route_a import SignalField

PROJECT = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(Path(p).read_text())


def exposure(path, field):
    length = weak = outage = 0.
    for start, end in zip(path, path[1:]):
        start, end = np.asarray(start), np.asarray(end)
        distance = float(np.linalg.norm(end-start))
        count = max(1, int(np.ceil(distance/.1)))
        for t in (np.arange(count)+.5)/count:
            truth = field.query(start+t*(end-start), 0)['rssi_truth_dbm']
            length += distance/count
            weak += distance/count * (truth < field.config['weak_threshold_dbm'])
            outage += distance/count * (truth < field.config['outage_threshold_dbm'])
    return {'length_m': length, 'weak_m': weak, 'outage_m': outage,
            'outage_length_ratio': outage/length if length else 0.}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-batch', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to((PROJECT/'runtime').resolve()):
        raise ValueError('Output must stay under runtime')
    output.mkdir(parents=True, exist_ok=False)
    spec = read(PROJECT/'configs/benchmark/oracle_smoke_v0.json')
    manifest = read(args.source_batch/'manifest.json')
    paths = read(PROJECT/'configs/data/server_paths.json')
    rows = []
    graphs = {}
    for e in manifest['episodes']:
        directory = args.source_batch/('episode_'+e['episode_id'])
        decisions = [json.loads(l) for l in (directory/'decisions.jsonl').read_text().splitlines()]
        trajectory = [json.loads(l) for l in (directory/'trajectory.jsonl').read_text().splitlines()]
        before = {}; previous = trajectory[0]['pose']['position']
        for step in trajectory[1:]:
            before.setdefault(step['decision'], previous)
            previous = step['pose']['position']
        navmesh = (PROJECT/paths['scene_dataset_root']/e['scene_id']).with_suffix('.navmesh')
        assert hashlib.sha256(navmesh.read_bytes()).hexdigest() == e['navmesh_sha256']
        floor = trajectory[0]['pose']['position'][1]
        key = (e['scene_id'], round(floor, 2))
        if key not in graphs:
            pf = habitat_sim.PathFinder(); assert pf.load_nav_mesh(str(navmesh))
            graphs[key] = NavmeshRiskPlanner(pf, floor)
        planner = graphs[key]
        selected = [d for d in decisions if 'subgoal_world' in d][:spec['diagnostic_subgoals_per_episode']]
        for d in selected:
            # A rejected subgoal may execute no actions and have no own pose row.
            start = trajectory[0]['pose']['position']
            for step in trajectory[1:]:
                if step['decision'] is not None and step['decision'] >= d['index']:
                    break
                start = step['pose']['position']
            for layout in e['layouts']:
                field = SignalField(planner.pathfinder, e['scene_id'], layout['ap_floor_position'], layout['wireless_config'])
                for weight in spec['lambda_values']:
                    row = {'episode_id':e['episode_id'], 'decision':d['index'], 'layout_id':layout['layout_id'], 'lambda':weight}
                    try:
                        route, state = planner.plan(start, d['subgoal_world'], weight=weight, field=field if weight else None)
                        row.update({'path':route, 'planner':state, 'exposure':exposure(route, field), 'error':None})
                    except ValueError as error:
                        row['error'] = str(error)
                    rows.append(row)
        print('diagnosed',e['episode_id'],len(selected),'subgoals',flush=True)
    result = {'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'manifest_sha256':hashlib.sha256((args.source_batch/'manifest.json').read_bytes()).hexdigest(),
              'selection':'first two logged local subgoals per episode, all 10 frozen episodes; no success filtering',
              'scope':'offline frozen subgoal endpoints, latent static field, no VLN success or executed motion claim', 'rows':rows}
    (output/'diagnostic.json').write_text(json.dumps(result,indent=2)+'\n')
    print('saved',output/'diagnostic.json',flush=True)


if __name__ == '__main__':
    main()
