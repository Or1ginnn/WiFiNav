#!/usr/bin/env python3
"""Export display grids for the already computed AP layouts in the multi-wall report."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess

import drjit as dr
import numpy as np

from run_rss_multiwall_pilot import ROOT, gltf_xyz, make_scene, merge_hits, mesh_hits, sha


def export_scene(tasks, mesh, config):
    slices = {}
    positions, receivers = [], []
    for task in tasks:
        transmit = gltf_xyz(task["default_ap_position"], config["ap_height_above_floor_m"])
        height = task["floor_y"] + config["rx_height_above_floor_m"]
        points = [[x, -z, height] for x, _, z in task["nodes"][:task["base_grid_nodes"]]]
        start = len(receivers)
        receivers.extend(points)
        positions.extend([transmit] * len(points))
        slices[task["episode_id"]] = slice(start, len(receivers))
    tx, rx = np.array(positions), np.array(receivers)
    lower = np.minimum(tx.min(axis=0), rx.min(axis=0)) - 0.01
    upper = np.maximum(tx.max(axis=0), rx.max(axis=0)) + 0.01
    geometry, tags, _ = make_scene(mesh.with_name(mesh.stem + "_semantic.ply"), mesh.with_suffix(".house"), lower, upper)
    hits, lengths = mesh_hits(geometry, tags, tx, rx, config["ray_epsilon_m"], config["max_hits_per_ray"])
    reference = config["reference_rss_1m_dbm"] - 20 * np.log10(np.maximum(lengths, 1.0))
    signals = {}
    for spacing in config["merge_distance_m"]:
        grouped = [merge_hits(ray, spacing) for ray in hits]
        for band, loss in config["loss_db_per_crossing"].items():
            penalties = [sum(max(loss[tag] for tag in tags) for _, tags in cluster) for cluster in grouped]
            signals[f"{band}_{spacing:.2f}"] = np.round(reference - penalties, 3)
    return {
        task["episode_id"]: {"ap_xyz": task["default_ap_position"],
                             "grid_rssi_dbm": {key: value[slices[task["episode_id"]]].tolist()
                                               for key, value in signals.items()}}
        for task in tasks
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--multiwall-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dr.set_thread_count(4)
    output = args.output.resolve()
    if (ROOT / "runtime") not in output.parents:
        raise ValueError("Output must be under project runtime")
    if output.exists():
        raise FileExistsError(output)
    report = json.loads(args.multiwall_report.read_text())
    input_hash = sha(args.data)
    if report["input_sha256"] != input_hash or report["scene_review"]:
        raise ValueError("Expected complete multi-wall profiles for the same AP batch")
    config = report["config"]
    groups = defaultdict(list)
    for task in json.loads(args.data.read_text())["tasks"]:
        groups[task["scene_id"]].append(task)
    paths = json.loads((ROOT / "configs/data/server_paths.json").read_text())
    tasks = {}
    for scene, group in sorted(groups.items()):
        reviewed = report["scenes_with_profiles"][scene]
        for task in group:
            if reviewed["tasks"][task["episode_id"]]["initial_ap_xyz"] != task["default_ap_position"]:
                raise ValueError(f"AP differs from the multi-wall profiles: {task['episode_id']}")
        for relative, checksum in reviewed["source_sha256"].items():
            if sha(ROOT / relative) != checksum:
                raise ValueError(f"Scene source changed after the validated run: {relative}")
        maps = export_scene(group, ROOT / paths["scene_dataset_root"] / scene, config)
        tasks.update(maps)
        print(scene, len(maps), "AP display grids", flush=True)
    result = {
        "format": "wifinav-multiwall-ap-preview-v1",
        "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "ap_data_sha256": input_hash, "multiwall_report_sha256": sha(args.multiwall_report), "tasks": tasks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), allow_nan=False)


if __name__ == "__main__":
    main()
