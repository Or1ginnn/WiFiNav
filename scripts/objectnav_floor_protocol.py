"""Strict single-floor ObjectNav scoring for the frozen v1 assets."""
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path

import habitat_sim
import numpy as np

from solve_objectnav_rssi_graph import ROOT, VERIFIED_FLOOR_STEP_M, edge_on_floor

ACTIONS = {"move_forward": .25, "turn_left": 30., "turn_right": 30.}
PROTOCOL = "wifinav-objectnav-single-floor-v1.1"
MAX_ACTIONS = 200
RSSI_STEP_M = .01875


def load_scene(manifest_path, scene, config):
    path = manifest_path.with_name(f'{scene["scene"]}.geometry.json')
    data = path.read_bytes()
    if sha256(data).hexdigest() != scene["files"][path.name]:
        raise ValueError(f"Changed evaluation input: {path}")
    geometry = json.loads(data)
    if geometry["source_ref"] != scene["source_ref"] or geometry["config"] != config or geometry["split"] != "val":
        raise ValueError("Mismatched scene, configuration or split")
    for name, fingerprint in geometry["source_sha256"].items():
        if sha256((ROOT / name).read_bytes()).hexdigest() != fingerprint:
            raise ValueError(f"Changed source asset: {name}")
    shard = ROOT / "data/datasets/objectnav/hm3d/v2/val/content" / f'{scene["scene"]}.json.gz'
    with gzip.open(shard, "rt", encoding="utf-8") as handle:
        source = json.load(handle)
    if len(source["episodes"]) != scene["source_episodes"]:
        raise ValueError("Official episode count changed")
    return geometry, source, path


class SingleFloor:
    def __init__(self, finder, floor, tolerance, radius):
        self.finder = finder
        self.floor = floor
        self.tolerance = tolerance
        self.radius = radius

    def in_band(self, point):
        return abs(point[1] - self.floor) <= self.tolerance + 1e-5

    def on_floor(self, points):
        # Check both the recorded height and actual NavMesh surface.
        if len(points) == 1:
            points = [points[0], points[0]]
        return all(map(self.in_band, points)) and edge_on_floor(
            points, lambda p: self.finder.snap_point(np.asarray(p, dtype=np.float32)),
            self.floor, self.tolerance, VERIFIED_FLOOR_STEP_M,
        )

    def shortest(self, start, ends):
        query = habitat_sim.MultiGoalShortestPath()
        query.requested_start = start
        query.requested_ends = np.asarray(ends, dtype=np.float32)
        return query if self.finder.find_path(query) else None

    def viewpoints(self, goals):
        points = {tuple(v["agent_state"]["position"]) for goal in goals for v in goal["view_points"]}
        return np.asarray(sorted(p for p in points if self.in_band(p) and self.finder.is_navigable(p)),
                          dtype=np.float32).reshape(-1, 3)

    def reference_bounds(self, start, views, witness, witness_distance):
        if not len(views):
            raise ValueError("No official navigable view on the starting floor")
        shortest = self.shortest(start, views)
        if shortest is None or not math.isfinite(shortest.geodesic_distance) or shortest.geodesic_distance <= 0:
            raise ValueError("No positive reference distance for a frozen task")
        lower = float(shortest.geodesic_distance)
        if self.on_floor(shortest.points):
            return lower, lower
        # The frozen native witness provides a certified upper bound. The
        # unconstrained path to an in-band view provides a lower bound.
        if (witness_distance <= 0 or lower > witness_distance + 1e-4
                or not self.on_floor(witness) or not self.is_stop(witness[-1], views)):
            raise ValueError("Cannot verify a bounded reference for a frozen task")
        return lower, max(lower, witness_distance)

    def is_stop(self, position, views):
        # Euclidean distance bounds the local path query and keeps the common
        # case cheap. Check all candidates within the official STOP radius.
        nearby = views[np.linalg.norm(views - position, axis=1) < self.radius]
        for view in nearby:
            if math.dist(position, view) <= 1e-5:
                return True
            path = self.shortest(position, [view])
            if path and path.geodesic_distance < self.radius and self.on_floor(path.points):
                return True
        return False

    def score(self, start, views, bounds, trace):
        positions = trace["positions"]
        actions = trace["actions"]
        if (len(positions) != len(actions) + 1 or len(actions) > MAX_ACTIONS
                or any(len(p) != 3 or not all(map(math.isfinite, p)) for p in positions)
                or math.dist(start, positions[0]) > 1e-4 or not self.on_floor([positions[0]])):
            raise ValueError("Invalid official start, trace shape or action budget")
        first_crossing = None
        for i, action in enumerate(actions):
            if action not in ACTIONS and action != "stop":
                raise ValueError(f"Unsupported action: {action}")
            if action == "stop" and (i != len(actions) - 1 or math.dist(*positions[i:i+2]) > 1e-5):
                raise ValueError("STOP must terminate the trace and keep the pose")
            if first_crossing is None and not self.on_floor(positions[i:i+2]):
                first_crossing = i + 1
        stop = bool(actions) and actions[-1] == "stop"
        prefix_end = len(positions) if first_crossing is None else first_crossing
        used = positions[:prefix_end]
        success = first_crossing is None and stop and self.is_stop(used[-1], views)
        length = sum(math.dist(a, b) for a, b in zip(used, used[1:]))
        lower, upper = bounds
        spl_low = lower / max(lower, length) if success else 0.
        spl_high = upper / max(upper, length) if success else 0.
        return {
            "success": int(success),
            "spl": spl_low if abs(spl_low - spl_high) <= 1e-8 else None,
            "spl_lower_bound": spl_low, "spl_upper_bound": spl_high,
            "reference_lower_m": lower, "reference_upper_m": upper,
            "length_m": length, "attempted_length_m": sum(math.dist(a, b) for a, b in zip(positions, positions[1:])),
            "first_floor_violation_action": first_crossing,
            "stop_called": stop and first_crossing is None,
            "termination": ("floor_violation" if first_crossing is not None else
                            ("success" if success else "invalid_stop") if stop else
                            "budget" if len(actions) == MAX_ACTIONS else "incomplete"),
            "scored_actions": len(used) - 1,
        }


def prepare(finder, geometry, source, task):
    row = task["source_row"]
    episode = source["episodes"][row]
    if (episode["scene_id"] != geometry["source_ref"] or
            episode["object_category"] != task["category"] or
            str(episode["episode_id"]) != str(task["source_episode_id"]) or
            episode["start_rotation"] != task["start_rotation"] or
            math.dist(episode["start_position"], task["route_xyz"][0]) > 1e-4):
        raise ValueError(f"Official inputs differ for source row {row}")
    cfg = geometry["config"]
    rules = SingleFloor(finder, geometry["floors"][task["floor"]]["y"],
                        cfg["floor_tolerance_m"], cfg["stop_radius_m"])
    goals = source["goals_by_category"][f'{Path(geometry["source_ref"]).name}_{task["category"]}']
    views = rules.viewpoints(goals)
    bounds = rules.reference_bounds(episode["start_position"], views, task["route_xyz"], task["reference_m"])
    return episode, rules, views, bounds
