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


def build_graph(geometry):
    import habitat_sim
    import numpy as np
    from connectivity_vln.navigation.weighted_planner import NavmeshRiskPlanner

    asset = ROOT / "data/scene_datasets" / geometry["source_ref"]
    finder = habitat_sim.PathFinder()
    if not finder.load_nav_mesh(str(asset.with_suffix(".navmesh"))):
        raise ValueError(f"Cannot load navmesh for {asset}")
    tolerance = geometry["config"]["floor_tolerance_m"]
    floors = {key: NavmeshRiskPlanner(finder, floor["y"], resolution=GRID_M, floor_tolerance=tolerance)
              for key, floor in geometry["floors"].items()}
    task_graphs = {}
    for task in geometry["tasks"]:
        native = np.asarray(task["route_xyz"], dtype=float)
        graph = floors[task["floor"]]
        budget = MAX_RATIO * task["reference_m"]
        grid = graph.positions[:, [0, 2]]
        # No route within budget can leave the Euclidean start-to-goal ellipse.
        min_length = np.linalg.norm(grid - native[0, [0, 2]], axis=1) + np.linalg.norm(grid - native[-1, [0, 2]], axis=1)
        eligible = np.flatnonzero(min_length <= budget + 1e-6)
        indices = {int(old): i for i, old in enumerate(eligible)}
        points = graph.positions[eligible].astype(float).tolist() + native.tolist()
        native_ids = list(range(len(eligible), len(points)))
        edges = [(i, indices[neighbor]) for old, i in indices.items() for neighbor, _ in graph.edges[old]
                 if neighbor in indices and old < neighbor]
        edges.extend(zip(native_ids, native_ids[1:]))
        for node, point in zip(native_ids, native):
            edges.extend((node, indices[neighbor]) for neighbor, _ in graph._attach(point.astype(np.float32))
                         if neighbor in indices)
        task_graphs[str(task["source_row"])] = {"floor": task["floor"], "points": points, "edges": edges,
                                                "native_ids": native_ids}
    return {"format": "wifinav-objectnav-navmesh-graph-v1", "grid_m": GRID_M, "tasks": task_graphs}


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
    if built["format"] != "wifinav-objectnav-navmesh-graph-v1" or built["tasks"].keys() != by_key.keys():
        raise ValueError("Navigation graph does not cover the frozen tasks")
    results = {}
    for key, task in built["tasks"].items():
        nodes = np.asarray(task["points"], dtype=float)
        edges = np.asarray(task["edges"], dtype=int)
        baseline = task["native_ids"]
        start, goal = baseline[0], baseline[-1]
        max_length = math.floor(MAX_RATIO * by_key[key]["reference_m"] / LENGTH_UNIT_M)
        lengths = np.linalg.norm(nodes[edges[:, 1]] - nodes[edges[:, 0]], axis=1)
        intervals = np.maximum(1, np.ceil(lengths / STEP_M)).astype(int)
        # Interior samples are unique per edge; endpoints share the node cache.
        edge_index = np.repeat(np.arange(len(edges)), intervals - 1)
        offsets = np.cumsum(intervals - 1) - (intervals - 1)
        fractions = (np.arange(len(edge_index)) - offsets[edge_index] + 1) / intervals[edge_index]
        interior = nodes[edges[edge_index, 0]] + (nodes[edges[edge_index, 1]] - nodes[edges[edge_index, 0]]) * fractions[:, None]
        sample_points = np.concatenate([nodes, interior])
        receivers = habitat_to_glb(sample_points, config["rx_height_above_floor_m"])
        unit_lengths = np.ceil(lengths / intervals / LENGTH_UNIT_M).astype(int)
        adjacency = [[] for _ in nodes]
        length_graph = [[] for _ in nodes]
        sample_ids = []
        baseline_edges = {}
        for i, (a, b) in enumerate(edges.tolist()):
            interiors = range(len(nodes) + offsets[i], len(nodes) + offsets[i] + intervals[i] - 1)
            sample_ids.append([a, *interiors, b])
            edge_length = int(unit_lengths[i] * intervals[i])
            adjacency[a].append((b, i))
            adjacency[b].append((a, i))
            length_graph[a].append((b, edge_length))
            length_graph[b].append((a, edge_length))
            baseline_edges[a, b] = i
        lower_bounds = distances(length_graph, goal)
        native_path = [(a, b, baseline_edges[a, b]) for a, b in zip(baseline, baseline[1:])]
        flat_ids = np.asarray([i for ids in sample_ids for i in ids], dtype=int)
        point_offsets = np.cumsum(intervals + 1)
        seg_starts = np.delete(flat_ids[:-1], point_offsets[:-1] - 1)
        seg_ends = np.delete(flat_ids[1:], point_offsets[:-1] - 1)
        seg_lengths = np.repeat(unit_lengths, intervals)

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
            means = (signal[seg_starts] + signal[seg_ends]) / 2
            starts = np.cumsum(intervals) - intervals
            weak = np.add.reduceat(seg_lengths * (means < config["weak_threshold_dbm"]), starts)
            severe = np.add.reduceat(seg_lengths * (means < config["outage_threshold_dbm"]), starts)
            edge_costs = list(zip(weak.tolist(), severe.tolist(), (unit_lengths * intervals).tolist()))
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
    return {"format": "wifinav-objectnav-rssi-graph-v1", "source_ref": geometry["source_ref"],
            "max_length_ratio": MAX_RATIO, "sampling_steps_m": [STEP_M], "graph_grid_m": built["grid_m"],
            "length_unit_m": LENGTH_UNIT_M, "tasks": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", required=True, type=Path)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
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
        result = build_graph(geometry)
    result["geometry_sha256"] = digest
    result["execution_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), allow_nan=False)


if __name__ == "__main__":
    main()
