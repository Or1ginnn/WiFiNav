#!/usr/bin/env python3
"""Build development RSS profiles with the selected single-floor multi-wall model."""
import argparse
from collections import Counter, defaultdict
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import time

import drjit as dr
import mitsuba as mi
import numpy as np
import trimesh

from run_rss_multiwall_pilot import ROOT, evaluate, sha
from run_rss_raytrace_pilot import floor_check


def make_batch(mesh, tasks, config):
    routes = [
        {
            "episode_id": task["episode_id"],
            "floor_y": task["floor_y"],
            "points_xyz": [task["nodes"][index] for index in task["route_nodes"]],
            "segment_lengths_m": task["route_lengths_m"],
        }
        for task in tasks
    ]
    layouts = [
        {"id": f"multiwall_dev_{task['episode_id']}", "target_episode_id": task["episode_id"],
         "ap_floor_xyz": task["default_ap_position"]}
        for task in tasks
    ]
    return {"mesh": str(mesh.relative_to(ROOT)), "routes": routes, "layouts": layouts, "config": config}


def check_mesh_alignment(mesh_path, batch):
    """Validate the Habitat→GLB frame on an independent physical floor mesh."""
    geometry = trimesh.load_scene(mesh_path, skip_materials=True, process=False).to_geometry()
    mesh = mi.Mesh("physical_floor_check", len(geometry.vertices), len(geometry.faces))
    parameters = mi.traverse(mesh)
    parameters["vertex_positions"] = np.asarray(geometry.vertices, dtype=np.float32).ravel()
    parameters["faces"] = np.asarray(geometry.faces, dtype=np.uint32).ravel()
    parameters.update()
    scene = mi.load_dict({"type": "scene", "physical": mesh})
    points, labels = [], []
    for route in batch["routes"]:
        points.extend(route["points_xyz"])
        labels.extend(f"{route['episode_id']}:{i}" for i in range(len(route["points_xyz"])))
    for layout in batch["layouts"]:
        points.append(layout["ap_floor_xyz"])
        labels.append(f"ap:{layout['target_episode_id']}")
    return floor_check(scene, points, batch["config"]["height_alignment_tolerance_m"], labels)


def run_scene(scene, tasks, asset_root, config):
    mesh = asset_root / scene
    navmesh = mesh.with_suffix(".navmesh")
    navmesh_hash = sha(navmesh)
    if any(task["navmesh_sha256"] != navmesh_hash for task in tasks):
        raise ValueError("Development tasks refer to another navmesh")
    batch = make_batch(mesh, tasks, config)
    alignment = check_mesh_alignment(mesh, batch)
    data = evaluate(batch, config)
    coverage = {}
    for task in tasks:
        episode = task["episode_id"]
        by_assumption = {key: variants[episode][0] for key, variants in data["coverage"].items()}
        if not all(row["available"] for row in by_assumption.values()):
            raise ValueError(f"Missing RSS profile for {episode}")
        flags = {row["outage_length_m"] > 0 for row in by_assumption.values()}
        state = "sensitive" if len(flags) > 1 else "outage_in_all" if True in flags else "connected_in_all"
        coverage[episode] = {
            "initial_ap_xyz": task["default_ap_position"],
            "trajectory_id": task["trajectory_id"],
            "coverage_status": state,
            "profile_samples": len(task["route_nodes"]),
            "navmesh_proxy_outage_length_m": task["initial_route_metrics"]["outage_length_m"],
            "assumptions": by_assumption,
        }
    return {
        "source_sha256": {**data["source_sha256"], str(mesh.relative_to(ROOT)): sha(mesh),
                          str(navmesh.relative_to(ROOT)): navmesh_hash},
        "geometry": data["geometry"], "alignment": alignment,
        "link_count": data["link_count"], "links_with_semantic_hits": data["links_with_semantic_hits"],
        "links": data["links"], "tasks": coverage,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dr.set_thread_count(4)
    start = time.monotonic()
    config = json.loads(args.config.read_text())
    if config["rss_backend"] != "semantic_multiwall":
        raise ValueError("Expected the selected semantic multi-wall backend")
    data_hash = sha(args.data)
    if data_hash != config["source_ap_review_sha256"]:
        raise ValueError("Expected the frozen AP review artifact")
    tasks = json.loads(args.data.read_text())["tasks"]
    scenes = defaultdict(list)
    for task in tasks:
        scenes[task["scene_id"]].append(task)
    if len(tasks) != config["task_count"] or len(scenes) != config["scene_count"]:
        raise ValueError("Unexpected development sample size")
    out = args.output.resolve()
    if (ROOT / "runtime") not in out.parents:
        raise ValueError("Output must be under project runtime")
    if out.exists():
        raise FileExistsError(out)
    paths = json.loads((ROOT / "configs/data/server_paths.json").read_text())
    assets = ROOT / paths["scene_dataset_root"]
    built, review = {}, {}
    for scene, scene_tasks in sorted(scenes.items()):
        try:
            built[scene] = run_scene(scene, scene_tasks, assets, config)
            print(scene, [item["coverage_status"] for item in built[scene]["tasks"].values()], flush=True)
        except (ValueError, RuntimeError, OSError) as exc:
            review[scene] = {"task_ids": [task["episode_id"] for task in scene_tasks],
                             "reason": str(exc)}
            print(scene, "review", str(exc), flush=True)
    status_counts = Counter(r["coverage_status"] for scene in built.values() for r in scene["tasks"].values())
    result = {
        "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "input_sha256": data_hash, "config_sha256": sha(args.config), "config": config,
        "versions": {k: version(k) for k in ("mitsuba", "drjit", "trimesh", "numpy", "sionna-rt")},
        "elapsed_seconds": time.monotonic() - start, "models_called": 0,
        "summary": {"scenes_with_profiles": len(built), "total_scenes": len(scenes),
                    "tasks_with_profiles": sum(status_counts.values()), "total_tasks": len(tasks),
                    "links": sum(item["link_count"] for item in built.values()),
                    "links_with_semantic_hits": sum(item["links_with_semantic_hits"] for item in built.values()),
                    "status_counts": dict(status_counts)},
        "scenes_with_profiles": built, "scene_review": review,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(result["summary"], flush=True)


if __name__ == "__main__":
    main()
