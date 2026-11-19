#!/usr/bin/env python3
"""Compare the Habitat RSS proxy with Sionna RT on frozen single-floor routes."""
import argparse
from importlib.metadata import version
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import drjit as dr
import mitsuba as mi
import numpy as np
import trimesh

mi.set_variant("llvm_ad_mono_polarized")
from sionna.rt import ITURadioMaterial, PlanarArray, RadioMapSolver, Scene, Transmitter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from connectivity_vln.benchmark.single_floor import route_metrics


def gltf_xyz(habitat_xyz, height_offset=0.0):
    """MP3D GLB uses Z up. Habitat applied a -90 degree rotation about X."""
    x, y, z = habitat_xyz
    return [x, -z, y + height_offset]


def create_mesh(source, output):
    gltf = trimesh.load_scene(source, skip_materials=True, process=False)
    mesh = gltf.to_geometry()
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError("Expected a nonempty triangular scene")
    mesh.export(output, include_attributes=False)
    return {"vertices": len(mesh.vertices), "faces": len(mesh.faces), "bounds_gltf_xyz": mesh.bounds.tolist()}


def add_transmitters(scene, config, placements):
    scene.frequency = config["carrier_hz"]
    scene.tx_array = PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")
    # Match the legacy 1 m free-space RSS anchor rather than assuming actual
    # device gains. This effective transmit power is a comparison convention.
    free_space_1m_db = 20 * math.log10(4 * math.pi * config["carrier_hz"] / 299792458)
    power = config["reference_rss_1m_dbm"] + free_space_1m_db
    for name, position in placements:
        scene.add(Transmitter(name=name, position=position, power_dbm=power))
    return power


def get_map(scene, config, center, size, seed, scene_depth=None):
    cell = config["cell_size_m"]
    radio_map = RadioMapSolver()(
        scene, center=center, size=size, orientation=[0, 0, 0], cell_size=[cell, cell],
        samples_per_tx=config["samples_per_tx"], seed=seed,
        max_depth=config["max_depth"] if scene_depth is None else scene_depth,
        los=True, specular_reflection=True, refraction=True, diffuse_reflection=False,
        diffraction=False,
    )
    return np.array(radio_map.rss, dtype=float), np.array(radio_map.cell_centers, dtype=float)


def watts_to_dbm(watts):
    out = np.full(watts.shape, np.nan)
    valid = np.isfinite(watts) & (watts > 0)
    out[valid] = 10 * np.log10(watts[valid]) + 30
    return out


def free_space_check(config):
    scene = Scene()
    power = add_transmitters(scene, config, [("calibration", [0.0, 0.0, 1.0])])
    watts, centers = get_map(scene, config, [0.0, 0.0, 0.0], [2.0, 2.0], config["seeds"][0], 0)
    expected = config["reference_rss_1m_dbm"] - 20 * np.log10(np.linalg.norm(centers - [0, 0, 1], axis=2))
    error = np.abs(watts_to_dbm(watts[0]) - expected)
    if not np.isfinite(error).all() or np.max(error) > config["free_space_error_max_db"]:
        raise RuntimeError(f"Free-space check failed: max error {np.max(error):.3f} dB")
    return {"tx_effective_power_dbm": power, "max_error_db": float(np.max(error)), "cells": int(error.size)}


def floor_check(scene, points, tolerance, labels):
    """Compare physical floor hits to known Habitat points after axis conversion."""
    transformed = np.array([gltf_xyz(p) for p in points])
    ray = mi.Ray3f(mi.Point3f(transformed[:, 0], transformed[:, 1], transformed[:, 2] + tolerance),
                     mi.Vector3f(0, 0, -1))
    hit = scene.mi_scene.ray_intersect(ray)
    errors = np.abs(np.asarray(hit.p.z) - transformed[:, 2])
    matched = np.asarray(hit.is_valid()) & (errors <= tolerance)
    count = int(np.count_nonzero(matched))
    ap_matched = [bool(m) for m, label in zip(matched, labels) if label.startswith("ap:")]
    if not all(ap_matched) or count < .90 * len(points):
        raise ValueError(f"Scene alignment failed: {count}/{len(points)} floor hits match, APs={ap_matched}")
    return {"matched": count, "checked": len(points), "all_ap_matched": all(ap_matched),
            "unmatched_labels": [label for label, ok in zip(labels, matched) if not ok]}


def sweep_bounds(points, locations, config, receive_z):
    xy = np.array([gltf_xyz(p)[:2] for p in points + locations])
    step = config["cell_size_m"]
    margin = config["map_margin_m"]
    low = np.floor((xy.min(axis=0) - margin) / step) * step
    high = np.ceil((xy.max(axis=0) + margin) / step) * step
    center = (low + high) / 2
    return [*center, receive_z], list(high - low)


def route_indexes(route, centers, step):
    x = centers[0, :, 0]
    y = centers[:, 0, 1]
    points = np.asarray([gltf_xyz(p)[:2] for p in route["points_xyz"]])
    cols = np.abs(points[:, 0, None] - x).argmin(axis=1)
    rows = np.abs(points[:, 1, None] - y).argmin(axis=1)
    offsets = np.abs(centers[rows, cols, :2] - points)
    if offsets.max() > step / 2 + 1e-4:
        raise ValueError("RSS sampling fell outside the matched radio grid")
    return rows, cols


def segments_below(values, lengths, threshold):
    if any(value is None for value in values):
        return None
    intervals = []
    position = 0.0
    start = None
    for a, b, length in zip(values, values[1:], lengths):
        if (a + b) / 2 < threshold:
            if start is None:
                start = position
        elif start is not None:
            intervals.append([start, position])
            start = None
        position += length
    if start is not None:
        intervals.append([start, position])
    return intervals


def summarize_profile(values, route, config):
    lengths = route["segment_lengths_m"]
    threshold = config["outage_threshold_dbm"]
    summary = route_metrics(values, lengths, weak=config["weak_threshold_dbm"], outage=threshold)
    runs = segments_below(values, lengths, threshold)
    return dict(summary, outage_intervals_m=runs,
                longest_outage_m=max((b-a for a,b in runs), default=0.0) if runs is not None else None,
                p10_dbm=float(np.quantile(values, .10)) if summary["available"] else None,
                missing_points=sum(value is None for value in values))


def preference(a, b, config):
    if not a["available"] or not b["available"]:
        return "unknown"
    gain = a["outage_length_m"] - b["outage_length_m"]
    if abs(gain) > config["ap_preference_exposure_tie_m"]:
        return "B" if gain > 0 else "A"
    gain = b["p10_dbm"] - a["p10_dbm"]
    if abs(gain) > config["ap_preference_p10_tie_db"]:
        return "B" if gain > 0 else "A"
    return "tie"


def finite_profile(values):
    return [float(v) if np.isfinite(v) else None for v in values]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    dr.set_thread_count(args.threads)
    out = args.output_dir.resolve()
    if (ROOT / "runtime") not in out.parents:
        raise ValueError("Output belongs under project runtime")
    out.mkdir(parents=True, exist_ok=False)
    raw = args.input.read_bytes()
    batch = json.loads(raw)
    config, routes, layouts = batch["config"], batch["routes"], batch["layouts"]
    if len(config["seeds"]) != 2 or len(layouts) != 2:
        raise ValueError("Pilot calls for two fixed seeds and two layouts")
    mesh = ROOT / batch["mesh"]
    if hashlib.sha256(mesh.read_bytes()).hexdigest() != batch["mesh_sha256"]:
        raise ValueError("Mesh changed after the Habitat pass")
    sanity = free_space_check(config)
    print("free_space", sanity, flush=True)
    mesh_ply = out / "pilot_scene.ply"
    geometry = create_mesh(mesh, mesh_ply)
    print("mesh", geometry, flush=True)
    positions = [layout["ap_floor_xyz"] for layout in layouts]
    points = [p for route in routes for p in route["points_xyz"]]
    labels = [f"{route['episode_id']}:{i}" for route in routes for i in range(len(route["points_xyz"]))]
    height = batch["floor_y"] + config["rx_height_above_floor_m"]
    center, size = sweep_bounds(points, positions, config, height)

    methods = {"route_a": {}}
    for route in routes:
        key = route["episode_id"]
        methods["route_a"][key] = []
        for layout in layouts:
            samples = layout["route_a_rssi_dbm"][key]
            methods["route_a"][key].append({"samples_dbm": samples, **summarize_profile(samples, route, config)})

    timings, convergence, alignment = {}, {}, None
    for setting in config["materials"]:
        name = setting["name"]
        material = ITURadioMaterial(name=f"pilot-{name}", itu_type=name, thickness=setting["thickness_m"])
        scene = Scene(mi_scene=mi.load_dict({
            "type": "scene",
            "pilot-mesh": {"type": "ply", "filename": str(mesh_ply), "bsdf": material},
        }))
        if alignment is None:
            alignment = floor_check(scene, points + positions, config["height_alignment_tolerance_m"],
                                    labels + [f"ap:{layout['id']}" for layout in layouts])
            print("alignment", alignment, flush=True)
        add_transmitters(scene, config, [
            (layout["id"], gltf_xyz(layout["ap_floor_xyz"], config["ap_height_above_floor_m"]))
            for layout in layouts
        ])
        maps = []
        for seed in config["seeds"]:
            t0 = time.monotonic()
            watts, centers = get_map(scene, config, center, size, seed)
            timings[f"{name}_{seed}"] = time.monotonic() - t0
            np.savez_compressed(out / f"rt_{name}_{seed}.npz", rss_watts=watts, centers_gltf_xyz=centers)
            print(name, seed, watts.shape, f"{timings[f'{name}_{seed}']:.2f}s", flush=True)
            maps.append(watts)
        # Average in power units across seeds. Treat unobserved cells as
        # unavailable until a larger ray budget can establish convergence.
        mean = np.where((maps[0] > 0) & (maps[1] > 0), (maps[0]+maps[1])/2, np.nan)
        dbm = watts_to_dbm(mean)
        delta = np.abs(watts_to_dbm(maps[0]) - watts_to_dbm(maps[1]))
        methods[f"rt_{name}"] = {}
        convergence[name] = {}
        for route in routes:
            key = route["episode_id"]
            rows, cols = route_indexes(route, centers, config["cell_size_m"])
            method_rows = []
            for i, layout in enumerate(layouts):
                samples = finite_profile(dbm[i, rows, cols])
                errors = delta[i, rows, cols]
                convergence[name][f"{key}:{layout['id']}"] = (
                    float(np.quantile(errors, .90)) if np.isfinite(errors).all() else None
                )
                method_rows.append({"samples_dbm": samples, **summarize_profile(samples, route, config)})
            methods[f"rt_{name}"][key] = method_rows

    resolved = all(value is not None and value <= config["max_repeat_p90_db"]
                   for entry in convergence.values() for value in entry.values())
    result = {
        "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "input_sha256": hashlib.sha256(raw).hexdigest(), "config_sha256": batch["config_sha256"],
        "config": config, "mesh_sha256": batch["mesh_sha256"], "navmesh_sha256": batch["navmesh_sha256"],
        "versions": {key: version(key) for key in ("sionna-rt", "mitsuba", "drjit", "trimesh", "numpy")},
        "mitsuba_variant": mi.variant(), "threads": args.threads, "models_called": 0,
        "free_space": sanity, "alignment": alignment, "geometry": geometry,
        "plane_center_gltf_xyz": center, "plane_size_m": size,
        "layouts": [{"label": label, "id": layout["id"], "ap_floor_xyz": layout["ap_floor_xyz"]}
                    for label, layout in zip("AB", layouts)],
        "timings_seconds": timings, "repeat_p90_delta_db": convergence, "repeat_gate_passed": resolved,
        "methods": methods,
        "ap_preference": {model: {key: preference(*summaries, config) for key, summaries in cases.items()}
                          for model, cases in methods.items()},
    }
    with (out / "report.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print("repeat gate", resolved, "AP preferences", result["ap_preference"], flush=True)


if __name__ == "__main__":
    main()
