#!/usr/bin/env python3
"""Evaluate the existing Habitat RSS proxy at fixed pilot route points."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import habitat_sim
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from connectivity_vln.signal_simulation.route_a import SignalField


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--ap-review-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config_bytes = args.config.read_bytes()
    config = json.loads(config_bytes)
    source = args.ap_review_data.read_bytes()
    if hashlib.sha256(source).hexdigest() != config["source_ap_review_sha256"]:
        raise ValueError("Expected the frozen AP review artifact")

    tasks = {t["episode_id"]: t for t in json.loads(source)["tasks"]}
    selected = [tasks[key] for key in config["task_ids"]]
    ap_sources = [tasks[key] for key in config["ap_source_task_ids"]]
    scene = config["scene_id"]
    floor = selected[0]["floor_y"]
    for task in selected + ap_sources:
        if task["scene_id"] != scene or abs(task["floor_y"] - floor) > 1e-4:
            raise ValueError("Pilot inputs must share the same scene and floor")

    paths = json.loads((ROOT / "configs/data/server_paths.json").read_text())
    mesh = ROOT / paths["scene_dataset_root"] / scene
    navmesh = mesh.with_suffix(".navmesh")
    navmesh_hash = hashlib.sha256(navmesh.read_bytes()).hexdigest()
    if any(t["navmesh_sha256"] != navmesh_hash for t in selected + ap_sources):
        raise ValueError("Pilot inputs refer to a different navmesh")

    finder = habitat_sim.PathFinder()
    if not finder.load_nav_mesh(str(navmesh)):
        raise RuntimeError(f"Habitat failed to load {navmesh}")
    routes = []
    for task in selected:
        routes.append({
            "episode_id": task["episode_id"],
            "trajectory_id": task["trajectory_id"],
            "points_xyz": [task["nodes"][index] for index in task["route_nodes"]],
            "segment_lengths_m": task["route_lengths_m"],
        })
    layouts = []
    route_a = selected[0]["wireless_config"].copy()
    route_a.update(reference_rssi_dbm_at_1m=config["reference_rss_1m_dbm"],
                   weak_threshold_dbm=config["weak_threshold_dbm"],
                   outage_threshold_dbm=config["outage_threshold_dbm"])
    for source_task in ap_sources:
        ap = source_task["default_ap_position"]
        layout_id = f"rss_pilot_ap_{source_task['episode_id']}"
        route_a_config = dict(route_a, layout_id=layout_id, ap_floor_position=ap)
        field = SignalField(finder, scene, ap, route_a_config)
        values = {}
        for route in routes:
            samples = [field.query(np.array(p), i) for i, p in enumerate(route["points_xyz"])]
            values[route["episode_id"]] = [s["rssi_truth_dbm"] for s in samples]
        layouts.append({"id": layout_id, "ap_floor_xyz": ap, "route_a_config": route_a_config,
                        "route_a_rssi_dbm": values})

    out = args.output.resolve()
    if (ROOT / "runtime") not in out.parents:
        raise ValueError("Output belongs under project runtime")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        json.dump({
            "config": config, "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "habitat_sim_version": habitat_sim.__version__, "floor_y": floor,
            "mesh": str(mesh.relative_to(ROOT)), "mesh_sha256": hashlib.sha256(mesh.read_bytes()).hexdigest(),
            "navmesh_sha256": navmesh_hash, "layouts": layouts, "routes": routes,
        }, handle, indent=2, allow_nan=False)
    print(f"{len(routes)} routes x {len(layouts)} AP placements: {out}")


if __name__ == "__main__":
    main()
