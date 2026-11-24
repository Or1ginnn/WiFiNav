#!/usr/bin/env python3
"""Build the known-map ObjectNav graph in Habitat, then solve it for each AP on CPU."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from connectivity_vln.benchmark.constrained_route import optimal_route
from connectivity_vln.benchmark.single_floor import distances


GRID_M = .15
STEP_M = .075
LENGTH_UNIT_M = 1e-6
MAX_RATIO = 1.2


def build_graph(geometry, proposals=None):
    import habitat_sim
    import numpy as np
    from build_objectnav_ap_smoke import shortest
    from connectivity_vln.navigation.weighted_planner import NavmeshRiskPlanner

    asset = ROOT / "data/scene_datasets" / geometry["source_ref"]
    finder = habitat_sim.PathFinder()
    if not finder.load_nav_mesh(str(asset.with_suffix(".navmesh"))):
        raise ValueError(f"Cannot load navmesh for {asset}")
    tolerance = geometry["config"]["floor_tolerance_m"]
    floors = {key: NavmeshRiskPlanner(finder, floor["y"], resolution=GRID_M, floor_tolerance=tolerance)
              for key, floor in geometry["floors"].items()}
    task_graphs = {}
    previous = {task["source_row"]: task["candidates"] for task in proposals["tasks"]} if proposals else {}
    for task in geometry["tasks"]:
        graph = floors[task["floor"]]
        budget = MAX_RATIO * task["reference_m"]
        start, stop = task["route_xyz"][0], task["route_xyz"][-1]
        native = shortest(finder, start, stop, graph.floor_y, tolerance)
        if native is None or abs(np.linalg.norm(np.diff(native, axis=0), axis=1).sum() - task["reference_m"]) > 1e-4:
            raise ValueError(f"Frozen native path changed for {task['source_row']}")
        grid = graph.positions[:, [0, 2]]
        # No route within budget can leave the Euclidean start-to-goal ellipse.
        min_length = np.linalg.norm(grid - native[0, [0, 2]], axis=1) + np.linalg.norm(grid - native[-1, [0, 2]], axis=1)
        eligible = np.flatnonzero(min_length <= budget + 1e-6)
        indices = {int(old): i for i, old in enumerate(eligible)}
        points = graph.positions[eligible].astype(float).tolist() + native.tolist()
        native_ids = list(range(len(eligible), len(points)))
        edges = []

        def connect(a, b, max_extra):
            path = shortest(finder, points[a], points[b], graph.floor_y, tolerance)
            if path is None or max(math.dist(path[0], points[a]), math.dist(path[-1], points[b])) > .005:
                return False
            length = np.linalg.norm(np.diff(path, axis=0), axis=1).sum()
            if length > math.dist(points[a], points[b]) + max_extra:
                return False
            edges.append((a, b, path[1:-1].tolist()))
            return True

        for old, i in indices.items():
            for neighbor, _ in graph.edges[old]:
                if neighbor in indices and old < neighbor:
                    connect(i, indices[neighbor], .08)
        edges.extend((a, b, []) for a, b in zip(native_ids, native_ids[1:]))
        route_anchors = native_ids.copy()
        imported = 0
        for option in previous.get(task["source_row"], []):
            path = option["path_xyz"]
            mid_ids = list(range(len(points), len(points) + len(path) - 2))
            points.extend(path[1:-1])
            ids = [native_ids[0], *mid_ids, native_ids[-1]]
            before = len(edges)
            if all(connect(a, b, .01) for a, b in zip(ids, ids[1:])):
                route_anchors.extend(mid_ids)
                imported += 1
            else:
                del edges[before:]
                del points[len(points) - len(mid_ids):]
        for node in route_anchors:
            for neighbor, _ in graph._attach(np.asarray(points[node], dtype=np.float32)):
                if neighbor in indices:
                    connect(node, indices[neighbor], .08)
        task_graphs[str(task["source_row"])] = {"floor": task["floor"], "points": points, "edges": edges,
                                                "native_ids": native_ids, "imported_paths": imported,
                                                "offered_paths": len(previous.get(task["source_row"], []))}
    return {"format": "wifinav-objectnav-navmesh-graph-v2", "grid_m": GRID_M, "tasks": task_graphs}


def score_graph(geometry, built):
    import drjit as dr
    from run_objectnav_ap_radio import habitat_to_glb, semantic_geometry, signal_for_anchor
    from run_rss_raytrace_pilot import summarize_profile
    import numpy as np

    dr.set_thread_count(4)
    asset = ROOT / "data/scene_datasets" / geometry["source_ref"]
    stem = asset.name.removesuffix(".basis.glb")
    scene, tags, _ = semantic_geometry(asset.with_name(stem + ".semantic.glb"), asset.with_name(stem + ".semantic.txt"))
    config = geometry["config"]
    by_key = {str(task["source_row"]): task for task in geometry["tasks"]}
    if built["format"] != "wifinav-objectnav-navmesh-graph-v2" or built["tasks"].keys() != by_key.keys():
        raise ValueError("Navigation graph does not cover the frozen tasks")
    results = {}
    for key, task in built["tasks"].items():
        nodes = np.asarray(task["points"], dtype=float)
        edges = task["edges"]
        baseline = task["native_ids"]
        start, goal = baseline[0], baseline[-1]
        max_length = math.floor(MAX_RATIO * by_key[key]["reference_m"] / LENGTH_UNIT_M)
        adjacency = [[] for _ in nodes]
        length_graph = [[] for _ in nodes]
        sample_points = nodes.tolist()
        sample_ids = []
        segment_start_ids, segment_end_ids, seg_lengths = [], [], []
        segment_offsets = []
        edge_lengths = []
        baseline_edges = {}
        for i, (a, b, midpoints) in enumerate(edges):
            points = np.asarray([nodes[a], *midpoints, nodes[b]])
            pieces = np.linalg.norm(np.diff(points, axis=0), axis=1)
            steps = np.maximum(1, np.ceil(pieces / STEP_M)).astype(int)
            intermediate = [point for x, y, n in zip(points, points[1:], steps)
                            for point in np.linspace(x, y, n, endpoint=False).tolist()][1:]
            ids = [a, *range(len(sample_points), len(sample_points) + len(intermediate)), b]
            sample_points.extend(intermediate)
            sample_ids.append(ids)
            sub_lengths = np.repeat(np.ceil(pieces / steps / LENGTH_UNIT_M).astype(int), steps).tolist()
            edge_length = sum(sub_lengths)
            segment_offsets.append(len(seg_lengths))
            edge_lengths.append(edge_length)
            seg_lengths.extend(sub_lengths)
            segment_start_ids.extend(ids[:-1])
            segment_end_ids.extend(ids[1:])
            adjacency[a].append((b, i))
            adjacency[b].append((a, i))
            length_graph[a].append((b, edge_length))
            length_graph[b].append((a, edge_length))
            baseline_edges[a, b] = i
        lower_bounds = distances(length_graph, goal)
        native_path = [(a, b, baseline_edges[a, b]) for a, b in zip(baseline, baseline[1:])]
        sample_points = np.asarray(sample_points)
        receivers = habitat_to_glb(sample_points, config["rx_height_above_floor_m"])
        seg_lengths = np.asarray(seg_lengths)

        def profile(path, signal):
            route_ids = [start]
            for origin, _, edge in path:
                ids = sample_ids[edge]
                route_ids.extend((ids if ids[0] == origin else ids[::-1])[1:])
            route = sample_points[route_ids]
            rssi = signal[route_ids].tolist()
            route_lengths = np.linalg.norm(np.diff(route, axis=0), axis=1).tolist()
            summary = summarize_profile(rssi, {"segment_lengths_m": route_lengths}, config)
            return route.tolist(), {**summary, "samples_dbm": rssi}

        references = {}
        for ap in geometry["floors"][task["floor"]]["candidates"]:
            signal, _ = signal_for_anchor(scene, tags, ap["xyz"], receivers, config)
            # Use the same midpoint classification rule as route_metrics.
            means = (signal[segment_start_ids] + signal[segment_end_ids]) / 2
            weak = np.add.reduceat(seg_lengths * (means < config["weak_threshold_dbm"]), segment_offsets)
            severe = np.add.reduceat(seg_lengths * (means < config["outage_threshold_dbm"]), segment_offsets)
            edge_costs = list(zip(weak.tolist(), severe.tolist(), edge_lengths))
            path, cost = optimal_route(adjacency, edge_costs, start, goal, max_length, lower_bounds)
            native_cost = tuple(sum(edge_costs[i][j] for _, _, i in native_path) for j in range(3))
            if native_cost[2] > max_length or cost > native_cost:
                raise AssertionError(f"Graph optimization failed to match the included baseline: {key}/{ap['id']}")
            baseline_profile = profile(native_path, signal)[1]
            # For equal objectives keep the original trace as the visual tie breaker.
            changed = cost < native_cost
            route, route_profile = profile(path if changed else native_path, signal)
            references[ap["id"]] = {"selected": int(changed), "route_xyz": route, "profile": route_profile,
                                     "baseline_profile": baseline_profile, "objective_um": cost,
                                     "baseline_objective_um": native_cost, "budget_um": max_length}
        results[key] = references
        print(f"{key}: {len(nodes)} nodes, {len(edges)} edges, {len(references)} APs", flush=True)
    return {"format": "wifinav-objectnav-rssi-graph-v2", "source_ref": geometry["source_ref"],
            "max_length_ratio": MAX_RATIO, "sampling_steps_m": [STEP_M], "graph_grid_m": built["grid_m"],
            "length_unit_m": LENGTH_UNIT_M, "tasks": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", required=True, type=Path)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--proposals", type=Path, help="Include the audited paths from the earlier review")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.graph and args.proposals:
        parser.error("--proposals is only used during graph construction")
    output = args.output.resolve()
    if (ROOT / "runtime") not in output.parents or output.exists():
        parser.error("Expected a new output file in project runtime")
    raw = args.geometry.read_bytes()
    geometry = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    suffixes = (".semantic.glb", ".semantic.txt") if args.graph else (".navmesh",)
    for name, expected in geometry["source_sha256"].items():
        if name.endswith(suffixes) and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen asset changed: {name}")
    if args.graph:
        graph_raw = args.graph.read_bytes()
        graph = json.loads(graph_raw)
        if graph["geometry_sha256"] != digest:
            raise ValueError("Navigation graph does not match the frozen geometry")
        result = score_graph(geometry, graph)
        result["graph_sha256"] = hashlib.sha256(graph_raw).hexdigest()
    else:
        proposal_raw = args.proposals.read_bytes() if args.proposals else None
        proposals = json.loads(proposal_raw) if proposal_raw else None
        if proposals and proposals["geometry_sha256"] != digest:
            raise ValueError("Previous routes do not match the frozen geometry")
        result = build_graph(geometry, proposals)
        if proposal_raw:
            result["proposals_sha256"] = hashlib.sha256(proposal_raw).hexdigest()
    result["geometry_sha256"] = digest
    result["execution_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), allow_nan=False)


if __name__ == "__main__":
    main()
