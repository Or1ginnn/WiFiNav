#!/usr/bin/env python3
"""Replay failures on Habitat and audit STOP and floor decisions offline."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess

import habitat_sim
import numpy as np

from objectnav_floor_protocol import MAX_ACTIONS, PROTOCOL, ROOT, load_scene, prepare
from run_objectnav_dev import TRAIN_MANIFEST_SHA256, witness_task
from run_objectnav_eval import execute, simulator, write


def floor_evidence(rules, trace, action_number):
    evidence = []
    positions = trace["positions"]
    for index in range(max(0, action_number - 6), action_number):
        start, end = positions[index:index + 2]
        snapped = rules.finder.snap_point(np.asarray(end, dtype=np.float32))
        evidence.append({
            "step": index + 1, "action": trace["actions"][index],
            "before_xyz": start, "after_xyz": end,
            "vertical_move_m": end[1] - start[1],
            "height_from_floor_m": end[1] - rules.floor,
            "navmesh_y_m": float(snapped[1]),
            "target_pixels_before_move": trace["target_observations"][index]["pixels"],
        })
    return evidence


def stop_evidence(sim, rules, views, trace):
    pose = trace["positions"][-1]
    offsets = np.linalg.norm(views - pose, axis=1)
    nearest = int(np.argmin(offsets))
    path = rules.shortest(pose, views)
    response = sim.step("move_forward")
    next_pose = sim.get_agent(0).get_state().position.tolist()
    next_path = rules.shortest(next_pose, views)
    return {
        "target_observation": trace["target_observations"][-1],
        "floor_valid": rules.executed_pose_on_floor(pose),
        "nearest_view_euclidean_m": float(offsets[nearest]),
        "nearest_view_vertical_diff_m": abs(float(views[nearest, 1]) - pose[1]),
        "nearest_view_geodesic_m": float(path.geodesic_distance) if path else None,
        "legal_stop_steps": [i for i, p in enumerate(trace["positions"][:-1]) if rules.is_stop(p, views)],
        "one_more_forward": {
            "pose": next_pose, "collided": bool(response.get("collided", False)),
            "displacement_m": math.dist(pose, next_pose),
            "nearest_view_geodesic_m": float(next_path.geodesic_distance) if next_path else None,
            "legal_stop": rules.executed_pose_on_floor(next_pose) and rules.is_stop(next_pose, views),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if ROOT / "runtime" not in args.output.resolve().parents or args.output.exists():
        parser.error("Expected a new output JSON under project runtime")
    manifest_raw = args.manifest.read_bytes()
    run_raw = (args.run / "results.json").read_bytes()
    metadata = json.loads((args.run / "metadata.json").read_bytes())
    profile = metadata.get("execution_profile")
    action_budget = metadata.get("action_budget", MAX_ACTIONS)
    fingerprint = sha256(manifest_raw).hexdigest()
    if fingerprint != metadata["manifest_sha256"] or metadata["protocol"] != PROTOCOL:
        parser.error("Run manifest or scoring protocol did not match")
    manifest = json.loads(manifest_raw)
    failures = {(row["scene"], row["trace"]["source_row"]): row for row in json.loads(run_raw)
                if row["navigation"]["termination"] in ("floor_violation", "invalid_stop")}
    records = []
    for scene in manifest["scenes"]:
        scan = scene["scene"]
        if not any(key[0] == scan for key in failures):
            continue
        geometry, source, _ = load_scene(args.manifest, scene, manifest["config"], split="train")
        with simulator(geometry, render=False, gpu_device=0, profile=profile) as sim:
            for task in geometry["tasks"]:
                record = failures.get((scan, task["source_row"]))
                if record is None:
                    continue
                witness = (witness_task(task, scan, scene, ROOT / "runtime/diagnostics/objectnav_rssi_graph_20261125_v7")
                           if fingerprint == TRAIN_MANIFEST_SHA256 else task)
                episode, rules, views, bounds = prepare(sim.pathfinder, geometry, source, witness,
                                                        action_budget=action_budget)
                original = record["trace"]
                replay = execute(sim, episode, rules, task, actions=original["actions"])
                score = rules.score(episode["start_position"], views, bounds, replay)
                if replay["positions"] != original["positions"] or score != record["navigation"]:
                    raise ValueError(f"Failure replay differs for {scan}:{task['source_row']}")
                crossing = score["first_floor_violation_action"]
                records.append({
                    "scene": scan, "source_row": task["source_row"], "category": task["category"],
                    "termination": score["termination"], "steps": len(original["actions"]),
                    "floor_y_m": rules.floor, "floor_tolerance_m": rules.tolerance,
                    "start_height_from_floor_m": original["positions"][0][1] - rules.floor,
                    "stop_radius_m": rules.radius,
                    "evidence": (floor_evidence(rules, original, crossing) if crossing is not None
                                 else stop_evidence(sim, rules, views, original)),
                })
    if len(records) != len(failures):
        raise ValueError("Failure audit did not cover all cases")
    write(args.output, {"protocol": PROTOCOL, "manifest_sha256": fingerprint,
                        "execution_commit": subprocess.check_output(
                            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                        "source_execution_commit": metadata["execution_commit"], "source_results_sha256": sha256(run_raw).hexdigest(),
                        "cases": records})
    print(f"Replayed and audited {len(records)} failures", flush=True)


if __name__ == "__main__":
    main()
