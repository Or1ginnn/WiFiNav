#!/usr/bin/env python3
"""Build task, same-floor route and AP review inputs from one HM3D ObjectNav shard."""
import argparse
from collections import defaultdict
from functools import partial
import gzip
import hashlib
import json
from pathlib import Path
import random
import subprocess

import habitat_sim
import numpy as np

from export_ap_review_topdown import topdown_slice
from solve_objectnav_rssi_graph import VERIFIED_FLOOR_STEP_M, edge_on_floor, sample_route


ROOT = Path(__file__).resolve().parents[1]


def audit_pool(episodes, config, scene):
    if "episode_pool_per_category" not in config:
        return list(enumerate(episodes))
    categories = defaultdict(list)
    for index, episode in enumerate(episodes):
        categories[episode["object_category"]].append(index)
    rng = random.Random(f"{config['selection_seed']}:{scene}")
    indices = sorted(index for _, rows in sorted(categories.items())
                     for index in rng.sample(rows, min(len(rows), config["episode_pool_per_category"])))
    return [(index, episodes[index]) for index in indices]


def shortest(finder, start, end, floor, tolerance):
    query = habitat_sim.ShortestPath()
    query.requested_start = start
    query.requested_end = end
    if not finder.find_path(query):
        return None
    points = np.asarray(query.points, dtype=float)
    if np.max(np.abs(points[:, 1] - floor)) > tolerance:
        return None
    return points


def anchor_ap_candidates(finder, topdown, mask, floor, config, *, center_ranked=False):
    origin = np.asarray(topdown["first_center_xz"])
    pixels_m = topdown["meters_per_pixel"]
    stride = max(1, round(config["ap_search_step_m"] / pixels_m))
    rows, cols = np.nonzero(mask[::stride, ::stride])
    xz = origin + np.column_stack((cols, rows)) * (stride * pixels_m)
    center = xz.mean(axis=0)
    candidates = []
    for x, z in xz:
        point = np.array([x, floor, z], dtype=np.float32)
        snapped = np.asarray(finder.snap_point(point))
        if not np.all(np.isfinite(snapped)) or np.linalg.norm(snapped - point) > .16:
            continue
        if not finder.is_navigable(snapped):
            continue
        clearance = finder.distance_to_closest_obstacle(snapped, 1.0)
        if config["ap_min_clearance_m"] <= clearance <= config["ap_max_clearance_m"]:
            candidates.append((snapped.tolist(), clearance))
    if not candidates:
        raise ValueError("No wall-adjacent AP anchors fit this floor")
    locations = np.asarray([item[0] for item in candidates])[:, [0, 2]]
    distance_center = np.linalg.norm(locations - center, axis=1)
    if center_ranked:
        keep = np.argsort(distance_center, kind="stable")
    else:
        keep = [int(np.argmin(distance_center))]
        distances = np.linalg.norm(locations - locations[keep[0]], axis=1)
        while len(keep) < config["ap_candidates_per_floor"] and distances.max() >= config["ap_candidate_separation_m"]:
            index = int(np.argmax(distances))
            keep.append(index)
            distances = np.minimum(distances, np.linalg.norm(locations - locations[index], axis=1))
    return [
        {"id": f"AP-{i + 1:02d}", "xyz": [round(float(v), 5) for v in candidates[index][0]],
         "navmesh_clearance_m": round(float(candidates[index][1]), 3)}
        for i, index in enumerate(keep)
    ]


def build(shard, asset, config, count, *, center_ranked_aps=False, verify_sampled_routes=False):
    complete_shard = count is None
    if complete_shard and "episode_pool_per_category" in config:
        raise ValueError("Full-shard screening requires all source episodes")
    with gzip.open(shard, "rt", encoding="utf-8") as handle:
        source = json.load(handle)
    episodes = source["episodes"]
    expected_ref = str(asset.relative_to(ROOT / "data/scene_datasets"))
    if {row["scene_id"] for row in episodes} != {expected_ref}:
        raise ValueError("Scene asset does not match this exact official shard")
    navmesh = asset.with_suffix(".navmesh")
    finder = habitat_sim.PathFinder()
    if not finder.load_nav_mesh(str(navmesh)):
        raise ValueError(f"Unable to open {navmesh}")
    floor_tol = config["floor_tolerance_m"]
    sampled_pool = "episode_pool_per_category" in config
    elevations = [round(row["start_position"][1], 2) for row in episodes]
    starts = sorted(elevations if sampled_pool else set(elevations))
    floor_groups = [[]]
    for y in starts:
        if floor_groups[-1] and y - floor_groups[-1][0 if sampled_pool or complete_shard else -1] > floor_tol:
            floor_groups.append([])
        floor_groups[-1].append(y)
    anchors = [round(float(np.median(group)), 3) for group in floor_groups]
    floors, by_group, audit = {}, defaultdict(list), []
    def snap(point):
        return finder.snap_point(np.asarray(point, dtype=np.float32))

    for row_index, episode in audit_pool(episodes, config, expected_ref):
        start = episode["start_position"]
        floor_index = int(np.argmin(np.abs(np.asarray(anchors) - start[1])))
        floor = anchors[floor_index]
        category = episode["object_category"]
        ids = {"source_row": row_index, "source_episode_id": episode["episode_id"], "category": category}
        if abs(floor - start[1]) > floor_tol or not finder.is_navigable(start):
            audit.append({**ids, "status": "start_outside_floor"})
            continue
        route_for = partial(shortest, finder, start, floor=floor, tolerance=floor_tol)
        goals = source["goals_by_category"][f"{asset.name}_{category}"]
        witnesses = []
        for goal in goals:
            for view in goal["view_points"]:
                position = view["agent_state"]["position"]
                if abs(position[1] - floor) > floor_tol or not finder.is_navigable(position):
                    continue
                path = route_for(position)
                if path is not None and np.linalg.norm(path[-1] - position) < config["stop_radius_m"]:
                    length = float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum())
                    witnesses.append((length, goal["object_id"], position, path))
        if (complete_shard or verify_sampled_routes) and witnesses:
            # The reference must follow the actual surface, even when a native
            # shortest path interpolates across a stair or a raised threshold.
            verified = next((item for item in sorted(witnesses, key=lambda item: item[0])
                             if edge_on_floor(item[3], snap, floor, floor_tol, VERIFIED_FLOOR_STEP_M)), None)
            witnesses = [verified] if verified is not None else []
        if not witnesses:
            audit.append({**ids, "status": "no_verified_same_floor_viewpoint"})
            continue
        length, object_id, _, route = min(witnesses, key=lambda item: item[0])
        floor_id = f"L{floor_index + 1}"
        route_points = sample_route(route, config["route_step_m"])
        audit.append({**ids, "floor": floor_id, "status": "eligible"})
        by_group[floor_id, category].append({
            **ids, "floor": floor_id, "route_xyz": route_points,
            "start_rotation": episode["start_rotation"],
            "reference_m": round(length, 5), "stop_object_id": object_id,
            "verified_viewpoints_xyz": [list(map(float, item[3][-1])) for item in witnesses],
            "max_height_from_floor_m": round(float(np.max(np.abs(route[:, 1] - floor))), 5),
        })
    if complete_shard:
        tasks = sorted((task for group in by_group.values() for task in group), key=lambda task: task["source_row"])
        count = len(tasks)
    else:
        # Round robin by floor and goal category, before reading any RF values.
        tasks = []
        while len(tasks) < count and any(by_group.values()):
            for _, group in sorted(by_group.items()):
                if group and len(tasks) < count:
                    tasks.append(group.pop(0))
    selected = {row["source_row"] for row in tasks}
    for row in audit:
        if row["source_row"] in selected:
            row["status"] = "selected"
    for floor_id in sorted({task["floor"] for task in tasks}):
        floor = anchors[int(floor_id[1:]) - 1]
        topdown, mask = topdown_slice(finder, floor, floor_tol)
        floors[floor_id] = {"y": floor, "map": topdown,
                            "candidates": anchor_ap_candidates(finder, topdown, mask, floor, config,
                                                               center_ranked=center_ranked_aps)}
    stem = asset.name.removesuffix(".basis.glb")
    source_paths = [shard, asset, navmesh, asset.with_name(stem + ".semantic.glb"), asset.with_name(stem + ".semantic.txt")]
    return {
        "format": "wifinav-objectnav-ap-review-v1",
        "source_ref": expected_ref,
        "split": shard.parent.parent.name,
        "scope": config["scope"],
        "habitat_sim_version": habitat_sim.__version__,
        "source_episode_count": len(episodes),
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths},
        "requested": count, "tasks": tasks, "scope_audit": audit, "floors": floors, "config": config,
        "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--shard", type=Path, required=True)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / "runtime") not in output.parents or output.exists():
        parser.error("Expected a new output file in project runtime")
    config = json.loads(args.config.read_text())
    result = build(args.shard.resolve(), args.scene.resolve(), config, config["task_count"])
    result["config_sha256"] = hashlib.sha256(args.config.read_bytes()).hexdigest()
    output.parent.mkdir(exist_ok=True, parents=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), allow_nan=False)
    print(f"{len(result['tasks'])}/{result['requested']} tasks, {len(result['floors'])} single-floor slices")
    if len(result["tasks"]) != result["requested"]:
        raise SystemExit("Insufficient eligible episodes. The audit is retained.")


if __name__ == "__main__":
    main()
