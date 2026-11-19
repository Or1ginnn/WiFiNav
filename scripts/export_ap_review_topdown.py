#!/usr/bin/env python3
"""Export Habitat's native top-down navmesh slices for the AP review report."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess

import habitat_sim
import numpy as np


PROJECT = Path(__file__).resolve().parents[1]
METERS_PER_PIXEL = float(np.float32(0.05))


def topdown_slice(pathfinder, height, tolerance):
    lower, _ = pathfinder.get_bounds()
    view = pathfinder.get_topdown_view(METERS_PER_PIXEL, height, tolerance)
    rows, cols = np.nonzero(view)
    if not rows.size:
        raise ValueError(f"Habitat returned an empty slice at Y={height}")
    r0, r1 = max(0, int(rows.min()) - 1), int(rows.max()) + 2
    c0, c1 = max(0, int(cols.min()) - 1), int(cols.max()) + 2
    cropped = view[r0:r1, c0:c1]
    height_px, width_px = cropped.shape
    # Habitat samples the first cell at the navmesh lower bound. Anchor the
    # exported cell centers there, so col/row advance along world +X/+Z.
    origin = [float(lower[0]) + c0 * METERS_PER_PIXEL,
              float(lower[2]) + r0 * METERS_PER_PIXEL]
    encoded = base64.b64encode(np.packbits(cropped.ravel(), bitorder="big")).decode("ascii")
    return {
        "width": width_px, "height": height_px,
        "first_center_xz": origin, "floor_y": height,
        "meters_per_pixel": METERS_PER_PIXEL, "walkable_bits": encoded,
    }, cropped


def confirm_alignment(task, data, walkable):
    """Allow a small raster margin for points lying along a navmesh edge."""
    origin = np.asarray(data["first_center_xz"])
    step = data["meters_per_pixel"]
    points = np.array([task["start_position"], task["goal_position"], task["default_ap_position"],
                       *[task["nodes"][i] for i in task["route_nodes"]],
                       *[task["nodes"][i] for i in task["ap_candidate_nodes"]]])
    cells = np.rint((points[:, [0, 2]] - origin) / step).astype(int)
    for col, row in cells:
        if not (0 <= col < data["width"] and 0 <= row < data["height"]):
            raise ValueError(f"Episode {task['episode_id']} has a marker outside its Habitat slice")
        nearby = walkable[max(0, row-2):row+3, max(0, col-2):col+3]
        if not nearby.any():
            raise ValueError(f"Episode {task['episode_id']} has a marker off its Habitat slice at {col}, {row}")
    return len(points)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if (PROJECT / "runtime") not in output.parents:
        parser.error("--output must be under project runtime")
    raw = args.data.read_bytes()
    data = json.loads(raw)
    tolerance = data["metadata"]["specification"]["height_tolerance_m"]
    paths = json.loads((PROJECT / "configs/data/server_paths.json").read_text())
    root = PROJECT / paths["scene_dataset_root"]
    scenes, slices, by_episode = {}, {}, {}
    checked = 0
    for task in data["tasks"]:
        scene, floor = task["scene_id"], task["floor_y"]
        if scene not in scenes:
            navmesh = (root / scene).with_suffix(".navmesh")
            digest = hashlib.sha256(navmesh.read_bytes()).hexdigest()
            finder = habitat_sim.PathFinder()
            if not finder.load_nav_mesh(str(navmesh)):
                raise ValueError(f"Cannot load {navmesh}")
            scenes[scene] = finder, digest
        finder, digest = scenes[scene]
        if digest != task["navmesh_sha256"]:
            raise ValueError(f"Navmesh differs from AP review source for {scene}")
        slice_key = f"{scene}@{floor}"
        if slice_key not in slices:
            slices[slice_key] = topdown_slice(finder, floor, tolerance)
        image, mask = slices[slice_key]
        checked += confirm_alignment(task, image, mask)
        by_episode[task["episode_id"]] = slice_key
    result = {
        "format": "wifinav-habitat-topdown-v1",
        "generator_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip(),
        "habitat_sim_version": habitat_sim.__version__,
        "ap_data_sha256": hashlib.sha256(raw).hexdigest(),
        "height_tolerance_m": tolerance,
        "maps": {key: value[0] for key, value in slices.items()},
        "episodes": by_episode,
        "alignment_points_checked": checked,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), allow_nan=False)
        handle.write("\n")
    print(f"{len(by_episode)} tasks / {len(slices)} distinct Habitat slices / {checked} alignment checks")


if __name__ == "__main__":
    main()
