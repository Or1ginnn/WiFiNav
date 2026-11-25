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
from connectivity_vln.benchmark.constrained_route import lexicographic_route


GRID_M = .15
STEP_M = .075
FLOOR_CHECK_STEP_M = STEP_M / 2
LENGTH_UNIT_M = 1e-6


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
    def connect(points, edges, a, b, floor_y, max_extra):
        path = shortest(finder, points[a], points[b], floor_y, tolerance)
        if path is None or max(math.dist(path[0], points[a]), math.dist(path[-1], points[b])) > .005:
            return False
        length = np.linalg.norm(np.diff(path, axis=0), axis=1).sum()
        if length > math.dist(points[a], points[b]) + max_extra:
            return False
        edges.append((a, b, path[1:-1].tolist()))
        return True

    floor_graphs = {}
    for key, graph in floors.items():
        points = graph.positions.astype(float).tolist()
        edges = []
        for a, neighbors in enumerate(graph.edges):
            for b, _ in neighbors:
                if a < b:
                    connect(points, edges, a, b, graph.floor_y, .08)
        floor_graphs[key] = {"points": points, "edges": edges}

    task_graphs = {}
    previous = {task["source_row"]: task["candidates"] for task in proposals["tasks"]} if proposals else {}
    for task in geometry["tasks"]:
        graph = floors[task["floor"]]
        start, stop = task["route_xyz"][0], task["route_xyz"][-1]
        native = shortest(finder, start, stop, graph.floor_y, tolerance)
        if native is None or abs(np.linalg.norm(np.diff(native, axis=0), axis=1).sum() - task["reference_m"]) > 1e-4:
            raise ValueError(f"Frozen native path changed for {task['source_row']}")
        floor_points = floor_graphs[task["floor"]]["points"]
        points = floor_points + native.tolist()
        native_ids = list(range(len(floor_points), len(points)))
        edges = []
        edges.extend((a, b, []) for a, b in zip(native_ids, native_ids[1:]))
        route_anchors = native_ids.copy()
        imported = 0
        for option in previous.get(task["source_row"], []):
            path = option["path_xyz"]
            mid_ids = list(range(len(points), len(points) + len(path) - 2))
            points.extend(path[1:-1])
            ids = [native_ids[0], *mid_ids, native_ids[-1]]
            before = len(edges)
            if all(connect(points, edges, a, b, graph.floor_y, .01) for a, b in zip(ids, ids[1:])):
                route_anchors.extend(mid_ids)
                imported += 1
            else:
                del edges[before:]
                del points[len(points) - len(mid_ids):]
        for node in route_anchors:
            for neighbor, _ in graph._attach(np.asarray(points[node], dtype=np.float32)):
                connect(points, edges, node, neighbor, graph.floor_y, .08)
        task_graphs[str(task["source_row"])] = {"floor": task["floor"], "points": points[len(floor_points):], "edges": edges,
                                                "native_ids": native_ids, "imported_paths": imported,
                                                "offered_paths": len(previous.get(task["source_row"], []))}
    return {"format": "wifinav-objectnav-navmesh-graph-v3", "grid_m": GRID_M, "floors": floor_graphs, "tasks": task_graphs}


def edge_on_floor(points, snap_point, floor_y, tolerance):
    """Check actual NavMesh surface height throughout each stored edge."""
    for a, b in zip(points, points[1:]):
        steps = max(1, math.ceil(math.dist(a, b) / FLOOR_CHECK_STEP_M))
        for i in range(steps + 1):
            point = [x + (y - x) * (i / steps) for x, y in zip(a, b)]
            x, y, z = snap_point(point)
            if (not all(map(math.isfinite, (x, y, z))) or abs(y - floor_y) > tolerance + 1e-5
                    or math.hypot(x - point[0], z - point[2]) > .025):
                return False
    return True


def audit_floor_graph(geometry, graph):
    import habitat_sim
    import numpy as np

    if graph["format"] != "wifinav-objectnav-navmesh-graph-v3":
        raise ValueError("Expected an unaudited ObjectNav floor graph")
    navmesh = (ROOT / "data/scene_datasets" / geometry["source_ref"]).with_suffix(".navmesh")
    finder = habitat_sim.PathFinder()
    if not finder.load_nav_mesh(str(navmesh)):
        raise ValueError(f"Cannot load navmesh for {navmesh}")
    tolerance = geometry["config"]["floor_tolerance_m"]

    def snap(point):
        return finder.snap_point(np.asarray(point, dtype=np.float32))

    def filter_edges(points, edges, floor):
        y = geometry["floors"][floor]["y"]
        return [(a, b, bends) for a, b, bends in edges if edge_on_floor([points[a], *bends, points[b]], snap, y, tolerance)]

    for floor, spec in graph["floors"].items():
        edges = filter_edges(spec["points"], spec["edges"], floor)
        spec["removed_edges"] = len(spec["edges"]) - len(edges)
        spec["edges"] = edges
    for task in graph["tasks"].values():
        floor = graph["floors"][task["floor"]]
        edges = filter_edges(floor["points"] + task["points"], task["edges"], task["floor"])
        task["removed_edges"] = len(task["edges"]) - len(edges)
        task["edges"] = edges
    graph["format"] = "wifinav-objectnav-navmesh-graph-v4"
    graph["floor_check_step_m"] = FLOOR_CHECK_STEP_M
    return graph


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
    if built["format"] != "wifinav-objectnav-navmesh-graph-v4" or built["tasks"].keys() != by_key.keys():
        raise ValueError("Navigation graph does not cover the frozen tasks")
    results = {}
    floor_signals = {}
    for key, task in built["tasks"].items():
        floor_id = task["floor"]
        floor = built["floors"][floor_id]
        nodes = np.asarray(floor["points"] + task["points"], dtype=float)
        edges = floor["edges"] + task["edges"]
        floor_nodes = len(floor["points"])
        floor_edges = len(floor["edges"])
        baseline = task["native_ids"]
        start, goal = baseline[0], baseline[-1]
        adjacency = [[] for _ in nodes]
        sample_points = nodes.tolist()
        sample_ids = []
        segment_start_ids, segment_end_ids, seg_lengths = [], [], []
        segment_offsets = []
        edge_lengths = []
        baseline_edges = {}
        floor_interiors_end = len(nodes)
        for i, (a, b, midpoints) in enumerate(edges):
            points = np.asarray([nodes[a], *midpoints, nodes[b]])
            pieces = np.linalg.norm(np.diff(points, axis=0), axis=1)
            steps = np.maximum(1, np.ceil(pieces / STEP_M)).astype(int)
            intermediate = [point for x, y, n in zip(points, points[1:], steps)
                            for point in np.linspace(x, y, n, endpoint=False).tolist()][1:]
            ids = [a, *range(len(sample_points), len(sample_points) + len(intermediate)), b]
            sample_points.extend(intermediate)
            if i + 1 == floor_edges:
                floor_interiors_end = len(sample_points)
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
            baseline_edges[a, b] = i
        native_pairs = list(zip(baseline, baseline[1:]))
        replaced_baseline = any(pair not in baseline_edges for pair in native_pairs)
        if replaced_baseline:
            try:
                native_path, _ = lexicographic_route(adjacency, [(0, 0, length) for length in edge_lengths], start, goal)
            except ValueError as exc:
                raise ValueError(f"No same-floor route to the frozen STOP for row {key}") from exc
        else:
            native_path = [(a, b, baseline_edges[a, b]) for a, b in native_pairs]
        sample_points = np.asarray(sample_points)
        receivers = habitat_to_glb(sample_points, config["rx_height_above_floor_m"])
        seg_lengths = np.asarray(seg_lengths)
        floor_indices = np.r_[0:floor_nodes, len(nodes):floor_interiors_end]
        task_indices = np.r_[floor_nodes:len(nodes), floor_interiors_end:len(receivers)]

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
        for ap in geometry["floors"][floor_id]["candidates"]:
            cache_key = floor_id, ap["id"]
            if cache_key not in floor_signals:
                floor_signals[cache_key], _ = signal_for_anchor(scene, tags, ap["xyz"], receivers[floor_indices], config)
            signal = np.empty(len(receivers))
            signal[floor_indices] = floor_signals[cache_key]
            signal[task_indices], _ = signal_for_anchor(scene, tags, ap["xyz"], receivers[task_indices], config)
            # Use the same midpoint classification rule as route_metrics.
            means = (signal[segment_start_ids] + signal[segment_end_ids]) / 2
            weak = np.add.reduceat(seg_lengths * (means < config["weak_threshold_dbm"]), segment_offsets)
            severe = np.add.reduceat(seg_lengths * (means < config["outage_threshold_dbm"]), segment_offsets)
            edge_costs = list(zip(severe.tolist(), weak.tolist(), edge_lengths))
            path, cost = lexicographic_route(adjacency, edge_costs, start, goal)
            native_cost = tuple(sum(edge_costs[i][j] for _, _, i in native_path) for j in range(3))
            if cost > native_cost:
                raise AssertionError(f"Graph optimization failed to match the included baseline: {key}/{ap['id']}")
            baseline_route, baseline_profile = profile(native_path, signal)
            # For equal objectives keep the original trace as the visual tie breaker.
            changed = cost < native_cost
            route, route_profile = profile(path if changed else native_path, signal)
            references[ap["id"]] = {"selected": int(changed), "route_xyz": route, "profile": route_profile,
                                     "baseline_profile": baseline_profile, "objective_um": cost,
                                     "baseline_objective_um": native_cost}
            if replaced_baseline:
                references[ap["id"]]["baseline_route_xyz"] = baseline_route
        results[key] = references
        print(f"{key}: {len(nodes)} nodes, {len(edges)} edges, {len(references)} APs", flush=True)
    return {"format": "wifinav-objectnav-rssi-graph-v5", "source_ref": geometry["source_ref"],
            "objective_order": ["outage_length_m", "weak_length_m", "length_m"],
            "max_length_ratio": None, "sampling_steps_m": [STEP_M], "graph_grid_m": built["grid_m"],
            "floor_check_step_m": built["floor_check_step_m"], "length_unit_m": LENGTH_UNIT_M, "tasks": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--graph", type=Path)
    mode.add_argument("--audit-graph", type=Path, help="Check the actual surface heights of an existing graph")
    parser.add_argument("--proposals", type=Path, help="Include the audited paths from the earlier review")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (args.graph or args.audit_graph) and args.proposals:
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
    if args.graph or args.audit_graph:
        graph_raw = (args.graph or args.audit_graph).read_bytes()
        graph = json.loads(graph_raw)
        if graph["geometry_sha256"] != digest:
            raise ValueError("Navigation graph does not match the frozen geometry")
        if args.audit_graph:
            result = audit_floor_graph(geometry, graph)
            result["original_graph_sha256"] = hashlib.sha256(graph_raw).hexdigest()
        else:
            result = score_graph(geometry, graph)
            result["graph_sha256"] = hashlib.sha256(graph_raw).hexdigest()
    else:
        proposal_raw = args.proposals.read_bytes() if args.proposals else None
        proposals = json.loads(proposal_raw) if proposal_raw else None
        if proposals and proposals["geometry_sha256"] != digest:
            raise ValueError("Previous routes do not match the frozen geometry")
        result = audit_floor_graph(geometry, build_graph(geometry, proposals))
        if proposal_raw:
            result["proposals_sha256"] = hashlib.sha256(proposal_raw).hexdigest()
    result["geometry_sha256"] = digest
    result["execution_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), allow_nan=False)


if __name__ == "__main__":
    main()
