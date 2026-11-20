#!/usr/bin/env python3
"""Evaluate a direct-path multi-wall model on the frozen RSS pilot routes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import time

import drjit as dr
import mitsuba as mi
import numpy as np

from mp3d_semantic_ply import read_ply
from run_rss_raytrace_pilot import ROOT, gltf_xyz, preference, summarize_profile


CATEGORIES = ("wall", "door", "window")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def object_labels(house):
    labels = {}
    objects = {}
    with house.open(encoding="utf-8") as handle:
        for line in handle:
            record = line.split()
            if not record:
                continue
            if record[0] == "C":
                labels[int(record[1])] = (record[3], record[5])
            elif record[0] == "O":
                objects[int(record[1])] = int(record[3])
    result = {}
    for index, category in objects.items():
        raw, mapped = labels.get(category, ("", ""))
        # Door frames, curtains and blinds can share a superclass. In this
        # pilot only explicit doors and windows are treated as closed sheets.
        name = raw if raw in ("door", "window") else "wall" if mapped == "wall" else None
        if name is not None:
            result[index] = name
    return result, objects.keys()


def make_scene(ply, house, lower, upper):
    xyz, faces = read_ply(ply)
    labels, known = object_labels(house)
    face_ids = faces["object"]
    identifiers = {int(value) for value in np.unique(face_ids)}
    unknown = sorted(identifiers - set(known) - {-1})
    if unknown:
        raise ValueError(f"Semantic file has unrecognized IDs: {unknown[:10]}")
    lut = np.full(max(known) + 1, -1, dtype=np.int8)
    for obj, tag in labels.items():
        lut[obj] = CATEGORIES.index(tag)
    # Keep triangles whose bounds intersect the convex box around every
    # pilot link. All retained coordinates remain in the MP3D GLB frame.
    positive = np.flatnonzero(face_ids >= 0)
    tag = lut[face_ids[positive]]
    selected = positive[tag >= 0]
    tri = faces["indices"][selected]
    if tri.min() < 0 or tri.max() >= len(xyz):
        raise ValueError("Semantic face indices are outside vertex bounds")
    points = xyz[tri]
    in_box = np.all((points.max(axis=1) >= lower) & (points.min(axis=1) <= upper), axis=1)
    selected = selected[in_box]
    tri = tri[in_box]
    unique, remapped = np.unique(tri, return_inverse=True)
    mesh = mi.Mesh("structural", len(unique), len(tri))
    parameters = mi.traverse(mesh)
    parameters["vertex_positions"] = np.ascontiguousarray(xyz[unique]).ravel()
    parameters["faces"] = remapped.astype(np.uint32).ravel()
    parameters.update()
    scene = mi.load_dict({"type": "scene", "structural": mesh})
    metadata = {
        "semantic_vertices": len(xyz), "semantic_faces": len(faces),
        "unlabelled_faces": int(np.count_nonzero(face_ids < 0)),
        "structural_faces_in_link_bounds": dict(zip(CATEGORIES, np.bincount(lut[face_ids[selected]], minlength=len(CATEGORIES)).tolist())),
        "structural_object_counts": dict(Counter(labels.values())),
    }
    return scene, lut[face_ids[selected]], metadata


def component(points):
    return mi.Point3f(points[:, 0], points[:, 1], points[:, 2])


def mesh_hits(scene, triangles, txs, rxs, epsilon, max_hits):
    difference = rxs - txs
    ranges = np.linalg.norm(difference, axis=1)
    directions = difference / ranges[:, None]
    direction = mi.Vector3f(directions[:, 0], directions[:, 1], directions[:, 2])
    progress = np.full(len(txs), epsilon)
    live = np.ones(len(txs), dtype=bool)
    hits = [[] for _ in txs]
    for _ in range(max_hits):
        origins = txs + directions * progress[:, None]
        ray = mi.Ray3f(component(origins), direction)
        ray.maxt = mi.Float(np.maximum(ranges - progress - epsilon, 0))
        detail = scene.ray_intersect(ray, active=mi.Bool(live))
        valid = live & np.asarray(detail.is_valid())
        if not valid.any():
            return hits, ranges
        distances = np.asarray(detail.t)
        indexes = np.asarray(detail.prim_index)
        for idx in np.flatnonzero(valid):
            hits[idx].append([float(progress[idx] + distances[idx]), CATEGORIES[triangles[indexes[idx]]]])
        progress[valid] += distances[valid] + epsilon
        live = valid & (progress < ranges - epsilon)
    raise RuntimeError("Exceeded geometric hit limit; geometry needs review")


def merge_hits(hits, spacing):
    groups = []
    for distance, label in hits:
        if groups and distance - groups[-1][0] <= spacing:
            groups[-1][1].add(label)
        else:
            groups.append((distance, {label}))
    return groups


def evaluate(batch, config):
    mesh = ROOT / batch["mesh"]
    ply, house = mesh.with_name(mesh.stem + "_semantic.ply"), mesh.with_suffix(".house")
    routes, layouts = batch["routes"], batch["layouts"]
    ap_height = batch["config"]["ap_height_above_floor_m"]
    antennas = [gltf_xyz(layout["ap_floor_xyz"], ap_height) for layout in layouts]
    rx_height = batch["config"]["rx_height_above_floor_m"]
    pairs = {route["episode_id"]: [] for route in routes}
    links = []
    for layout_index, antenna in enumerate(antennas):
        target = layouts[layout_index].get("target_episode_id")
        for route in routes:
            if target is not None and target != route["episode_id"]:
                continue
            pairs[route["episode_id"]].append(layout_index)
            receive_z = route.get("floor_y", batch.get("floor_y")) + rx_height
            for idx, point in enumerate(route["points_xyz"]):
                rx = gltf_xyz(point)
                rx[2] = receive_z
                links.append((layout_index, route["episode_id"], idx, antenna, rx))
    txs = np.array([link[3] for link in links])
    rxs = np.array([link[4] for link in links])
    lower = np.minimum(txs.min(axis=0), rxs.min(axis=0)) - 0.01
    upper = np.maximum(txs.max(axis=0), rxs.max(axis=0)) + 0.01
    scene, triangles, metadata = make_scene(ply, house, lower, upper)
    hits, lengths = mesh_hits(scene, triangles, txs, rxs, config["ray_epsilon_m"], config["max_hits_per_ray"])
    if config.get("require_mixed_links", True) and (not any(hits) or all(hits)):
        raise ValueError("No mix of blocked and unobstructed pilot links; review semantic geometry")
    ref = batch["config"]["reference_rss_1m_dbm"]
    free_space = ref - 20 * np.log10(np.maximum(lengths, 1.0))
    results, preferences = {}, {}
    for distance in config["merge_distance_m"]:
        intersections = [merge_hits(line, distance) for line in hits]
        for label, by_type in config["loss_db_per_crossing"].items():
            name = f"{label}_{distance:.2f}"
            values = {}
            for link, groups, reference in zip(links, intersections, free_space):
                key = link[0], link[1]
                # A cluster can have both a wall face and a frame/window
                # boundary. Take the largest assumed loss once.
                loss = sum(max(by_type[tag] for tag in tags) for _, tags in groups)
                values.setdefault(key, []).append(float(reference - loss))
            results[name] = {}
            for route in routes:
                eid = route["episode_id"]
                rows = [values[i, eid] for i in pairs[eid]]
                if not rows:
                    raise ValueError(f"No AP layout assigned to {eid}")
                results[name][eid] = [
                    {"samples_dbm": row, **summarize_profile(row, route, batch["config"])} for row in rows
                ]
            preferences[name] = {
                eid: preference(*rows, batch["config"])
                for eid, rows in results[name].items() if len(rows) == 2
            }
    return {
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in (ply, house)},
        "geometry": metadata, "link_count": len(links), "links_with_semantic_hits": sum(map(bool, hits)),
        "hit_histogram": dict(Counter(len(h) for h in hits)), "coverage": results, "ap_preference": preferences,
        "links": [
            {"layout_index": link[0], "episode_id": link[1], "sample_index": link[2],
             "direct_distance_m": float(length), "hits": h}
            for link, length, h in zip(links, lengths, hits)
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dr.set_thread_count(4)
    started = time.monotonic()
    config = json.loads(args.config.read_text())
    input_hash = sha(args.input)
    if input_hash != config["paired_input_sha256"]:
        raise ValueError("Expected exact paired pilot input")
    out = args.output.resolve()
    if (ROOT / "runtime") not in out.parents:
        raise ValueError("Output must be under project runtime")
    if out.exists():
        raise FileExistsError(out)
    result = evaluate(json.loads(args.input.read_text()), config)
    result.update(config=config, config_sha256=sha(args.config), input_sha256=input_hash,
                  execution_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  elapsed_seconds=time.monotonic() - started)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(result["geometry"], result["link_count"], result["links_with_semantic_hits"], flush=True)
    print(result["ap_preference"], result["elapsed_seconds"], flush=True)


if __name__ == "__main__":
    main()
