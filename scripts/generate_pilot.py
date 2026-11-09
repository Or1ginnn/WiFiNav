"""Freeze ten task IDs and AP placements before observing policy outcomes."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import habitat_sim
import numpy as np
from connectivity_vln.navigation.task import PROJECT, load_json


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate():
    specification = load_json(PROJECT / "configs/benchmark/pilot_v0.json")
    destination = PROJECT / specification["manifest_path"]
    if destination.exists():
        raise SystemExit(f"Manifest already frozen; refusing to replace {destination}")
    paths = load_json(PROJECT / "configs/data/server_paths.json")
    split = specification["split"]
    source = PROJECT / paths["task_dataset"] / split / (split + ".json.gz")
    with gzip.open(source, "rt") as stream:
        episodes = json.load(stream)["episodes"]
    scenes = sorted({e["scene_id"] for e in episodes})[:specification["scene_count"]]
    wireless = load_json(PROJECT / specification["wireless_base_config"])
    wireless.update(specification["wireless_overrides"])
    rows = []
    for scene_index, scene in enumerate(scenes):
        pathfinder = habitat_sim.PathFinder()
        scene_path = PROJECT / paths["scene_dataset_root"] / scene
        navmesh = scene_path.with_suffix(".navmesh")
        if not pathfinder.load_nav_mesh(str(navmesh)):
            raise RuntimeError(f"Navmesh not loaded: {navmesh}")
        pathfinder.seed(specification["scene_seed"] + scene_index)
        points = [np.asarray(pathfinder.get_random_navigable_point())
                  for _ in range(specification["ap_candidates_per_scene"])]
        distinct = set()
        chosen = []
        for episode in sorted((e for e in episodes if e["scene_id"] == scene), key=lambda e: int(e["episode_id"])):
            if str(episode["trajectory_id"]) in distinct:
                continue
            distinct.add(str(episode["trajectory_id"]))
            chosen.append(episode)
            if len(chosen) == specification["episodes_per_scene"]:
                break
        if len(chosen) != specification["episodes_per_scene"]:
            raise RuntimeError("Not enough distinct source paths; no outcome-based replacement allowed")
        for episode in chosen:
            start = np.asarray(episode["start_position"])
            candidates = []
            for candidate in points:
                if not np.isfinite(candidate).all() or abs(candidate[1] - start[1]) > specification["ap_floor_tolerance_m"]:
                    continue
                query = habitat_sim.ShortestPath()
                query.requested_start = start
                query.requested_end = candidate
                if pathfinder.find_path(query) and np.isfinite(query.geodesic_distance):
                    candidates.append(candidate)
            if not candidates:
                raise RuntimeError(f"No same-floor AP points for episode {episode['episode_id']}")
            layouts = []
            for layout in specification["layouts"]:
                if layout["ap_rule"] == "episode_start":
                    ap = start
                else:
                    target = layout["target_radius_m"]
                    ap = min(candidates, key=lambda point: abs(np.linalg.norm((point-start)[[0, 2]])-target))
                actual_radius = float(np.linalg.norm((ap-start)[[0, 2]]))
                config = dict(wireless)
                config.update(layout_id=layout["layout_id"], ap_floor_position=ap.tolist())
                layouts.append({"layout_id": layout["layout_id"], "ap_floor_position": ap.tolist(),
                                "actual_horizontal_radius_m": actual_radius, "wireless_config": config})
            rows.append({"episode_id": str(episode["episode_id"]), "trajectory_id": str(episode["trajectory_id"]),
                         "scene_id": scene, "split": split,
                         "scene_sha256": sha(scene_path), "navmesh_sha256": sha(navmesh), "layouts": layouts})
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "specification": specification,
                "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip(),
                "source_task_sha256": sha(source), "habitat_sim_version": habitat_sim.__version__,
                "config_hashes": {name: sha(PROJECT / name) for name in [
                    "configs/benchmark/pilot_v0.json", specification["navigation_config"],
                    specification["model_config"], specification["wireless_base_config"]]},
                "episodes": rows, "episode_count": len(rows), "case_count": sum(len(e["layouts"]) for e in rows)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as stream:
        stream.write(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"manifest": str(destination), "sha256": sha(destination),
                      "episode_count": len(rows), "case_count": manifest["case_count"],
                      "episode_ids": [e["episode_id"] for e in rows], "scenes": scenes}, indent=2), flush=True)


if __name__ == "__main__":
    generate()
