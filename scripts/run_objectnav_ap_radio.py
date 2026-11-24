#!/usr/bin/env python3
"""Precompute each vetted AP candidate on a HM3D semantic mesh using CPU rays."""
import argparse
import base64
from collections import Counter
import csv
import json
from pathlib import Path
import struct
import subprocess

import drjit as dr
import mitsuba as mi
import numpy as np

from export_ap_review_scene_views import Textures, physical_mesh, render_floor
from run_rss_multiwall_pilot import CATEGORIES, merge_hits, mesh_hits, sha
from run_rss_raytrace_pilot import floor_check, summarize_profile


ROOT = Path(__file__).resolve().parents[1]


def read_accessor(doc, buffer, index):
    attr = doc["accessors"][index]
    view = doc["bufferViews"][attr["bufferView"]]
    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
    types = {5121: "u1", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
    dtype = np.dtype(types[attr["componentType"]])
    width = widths[attr["type"]]
    if view["buffer"] != 0 or "sparse" in attr:
        raise ValueError("Expected a dense accessor in the embedded buffer")
    offset = view.get("byteOffset", 0) + attr.get("byteOffset", 0)
    stride = view.get("byteStride", width * dtype.itemsize)
    return np.ndarray((attr["count"], width), dtype=dtype, buffer=buffer,
                      offset=offset, strides=(stride, dtype.itemsize))


def semantic_geometry(mesh_path, annotations_path):
    with annotations_path.open(encoding="utf-8") as handle:
        if not next(handle).startswith("HM3D Semantic"):
            raise ValueError("Expected HM3D semantic annotations")
        names = {int(row[1], 16): row[2].strip().lower() for row in csv.reader(handle)}
    payload = mesh_path.read_bytes()
    magic, version, size, length, tag = struct.unpack_from("<4s4I", payload)
    if (magic, version, size, tag) != (b"glTF", 2, len(payload), 0x4E4F534A):
        raise ValueError("Expected a binary glTF 2.0 scene")
    doc = json.loads(payload[20:20 + length])
    bin_length, bin_tag = struct.unpack_from("<2I", payload, 20 + length)
    if bin_tag != 0x004E4942 or bin_length != len(payload) - 28 - length:
        raise ValueError("Missing glTF binary buffer")
    buffer = memoryview(payload)[28 + length:]
    nodes = [doc["nodes"][i] for i in doc["scenes"][doc.get("scene", 0)]["nodes"]]
    if any(set(node) & {"matrix", "rotation", "translation", "scale", "children"} for node in nodes):
        raise ValueError("This HM3D adapter expects untransformed root meshes")
    vertices, faces, categories = [], [], []
    metadata = Counter()
    offset = 0
    for node in nodes:
        for prim in doc["meshes"][node["mesh"]]["primitives"]:
            if prim.get("mode", 4) != 4:
                raise ValueError("Expected triangular HM3D geometry")
            attrs = prim["attributes"]
            positions = read_accessor(doc, buffer, attrs["POSITION"])
            linear = read_accessor(doc, buffer, attrs["COLOR_0"])[:, :3]
            if not np.issubdtype(linear.dtype, np.floating):
                attr = doc["accessors"][attrs["COLOR_0"]]
                if not attr.get("normalized"):
                    raise ValueError("Expected normalized semantic vertex colors")
                linear = linear.astype(np.float32) / np.iinfo(linear.dtype).max
            srgb = np.rint(np.where(linear <= .0031308, linear * 12.92,
                                    1.055 * linear ** (1 / 2.4) - .055) * 255).astype(np.uint32)
            rgb = (srgb[:, 0] << 16) | (srgb[:, 1] << 8) | srgb[:, 2]
            unique, inverse = np.unique(rgb, return_inverse=True)
            tags = [names.get(int(color)) for color in unique]
            label_indices = np.asarray([CATEGORIES.index(tag) if tag in CATEGORIES else -1 for tag in tags])
            tri = read_accessor(doc, buffer, prim["indices"]).reshape(-1, 3)
            by_vertex = label_indices[inverse][tri]
            metadata["faces"] += len(tri)
            matched = np.asarray([tag is not None for tag in tags])[inverse][tri]
            metadata["faces_with_known_colors"] += int(np.count_nonzero(np.all(matched, axis=1)))
            # A black vertex absent from the annotation table has no semantic label.
            # Keep it out of the structural mesh and report its extent separately.
            unannotated = (rgb[tri] == 0) & ~matched
            metadata["faces_with_unannotated_black"] += int(np.count_nonzero(np.any(unannotated, axis=1)))
            metadata["faces_with_unmatched_nonblack"] += int(np.count_nonzero(np.any(~(matched | unannotated), axis=1)))
            for idx, category in enumerate(CATEGORIES):
                selected = tri[np.count_nonzero(by_vertex == idx, axis=1) >= 2]
                if len(selected):
                    referenced, remapped = np.unique(selected, return_inverse=True)
                    vertices.append(positions[referenced])
                    faces.append(remapped.reshape(-1, 3) + offset)
                    categories.append(np.full(len(selected), idx, dtype=np.int8))
                    offset += len(referenced)
                    metadata[category] += len(selected)
    if not metadata["wall"] or metadata["faces_with_unmatched_nonblack"] > .05 * metadata["faces"]:
        raise ValueError(f"Semantic color mapping has insufficient support: {dict(metadata)}")
    coordinates = np.concatenate(vertices).astype(np.float32)
    triangles = np.concatenate(faces).astype(np.uint32)
    mesh = mi.Mesh("hm3d_structural", len(coordinates), len(triangles))
    params = mi.traverse(mesh)
    params["vertex_positions"] = coordinates.ravel()
    params["faces"] = triangles.ravel()
    params.update()
    return mi.load_dict({"type": "scene", "walls": mesh}), np.concatenate(categories), dict(metadata)


def habitat_to_glb(points, height):
    xyz = np.asarray(points, dtype=float)
    return np.column_stack((xyz[:, 0], -xyz[:, 2], xyz[:, 1] + height))


def floor_grid(floor_data, step):
    m = floor_data["map"]
    packed = np.frombuffer(base64.b64decode(m["walkable_bits"]), dtype=np.uint8)
    mask = np.unpackbits(packed, count=m["height"] * m["width"]).reshape(m["height"], m["width"])
    stride = max(1, round(step / m["meters_per_pixel"]))
    mask = mask[::stride, ::stride]
    cell_step = stride * m["meters_per_pixel"]
    rows, cols = np.nonzero(mask)
    origin_x, origin_z = m["first_center_xz"]
    points = np.column_stack((origin_x + cols * cell_step, np.full(len(rows), floor_data["y"]),
                              origin_z + rows * cell_step))
    return mask, cell_step, points


def signal_for_anchor(scene, tags, anchor, receivers, config):
    tx = habitat_to_glb([anchor], config["ap_height_above_floor_m"])
    repeated = np.broadcast_to(tx, receivers.shape)
    hits, distances = mesh_hits(scene, tags, repeated, receivers,
                                config["ray_epsilon_m"], config["max_hits_per_ray"])
    losses = config["loss_db_per_crossing"]
    penalties = [sum(max(losses[tag] for tag in labels) for _, labels in merge_hits(ray, config["merge_distance_m"]))
                 for ray in hits]
    free = config["reference_rss_1m_dbm"] - 20 * np.log10(np.maximum(distances, 1))
    return np.round(free - penalties, 2), sum(bool(ray) for ray in hits)


def build(geometry, asset, decoder):
    config = geometry["config"]
    stem = asset.name.removesuffix(".basis.glb")
    semantics = asset.with_name(stem + ".semantic.glb")
    annotations = asset.with_name(stem + ".semantic.txt")
    scene, tags, metadata = semantic_geometry(semantics, annotations)
    physical = physical_mesh(asset)
    anchors, stops, labels = [], [], []
    for fid, floor in geometry["floors"].items():
        anchors.extend(candidate["xyz"] for candidate in floor["candidates"])
        labels.extend(f"ap:{fid}/{candidate['id']}" for candidate in floor["candidates"])
    for task in geometry["tasks"]:
        stops.extend([task["route_xyz"][0], task["route_xyz"][-1]])
        labels.extend([f"start:{task['source_row']}", f"stop:{task['source_row']}"])
    alignment = floor_check(physical[0], anchors + stops, .30, labels)
    radio = {}
    glb = asset.read_bytes()
    textures = Textures(glb, decoder) if decoder else None
    for fid, floor in geometry["floors"].items():
        mask, grid_step, points = floor_grid(floor, config["rssi_grid_step_m"])
        floor_tasks = [task for task in geometry["tasks"] if task["floor"] == fid]
        receivers = points.tolist()
        slices = {}
        for task in floor_tasks:
            key = str(task["source_row"])
            route = np.asarray(task["route_xyz"])
            views = task["verified_viewpoints_xyz"]
            start_index = len(receivers)
            receivers.extend(route.tolist())
            receivers.extend(views)
            slices[key] = (start_index, start_index + len(route), len(receivers),
                           np.linalg.norm(np.diff(route, axis=0), axis=1).tolist())
        receivers = habitat_to_glb(receivers, config["rx_height_above_floor_m"])
        floor_radio = {"grid_step_m": grid_step, "width": int(mask.shape[1]), "height": int(mask.shape[0]),
                       "candidates": {}}
        if textures is not None:
            floor_radio["cutaway"] = render_floor(physical, floor["map"], textures)
        for candidate in floor["candidates"]:
            values, blocked = signal_for_anchor(scene, tags, candidate["xyz"], receivers, config)
            if not np.isfinite(values).all() or not 0 < blocked < len(values):
                raise ValueError(f"Unexpected structural ray results on {fid}/{candidate['id']}")
            grid = np.full(mask.shape, -128, dtype=np.int8)
            grid[mask > 0] = np.clip(np.rint(values[:len(points)]), -127, 0).astype(np.int8)
            covered = np.zeros(mask.shape, dtype=bool)
            covered[mask > 0] = values[:len(points)] >= config["weak_threshold_dbm"]
            profiles = {}
            for key, (start, end, views_end, lengths) in slices.items():
                samples, view_signals = values[start:end].tolist(), values[end:views_end]
                profiles[key] = {
                    "samples_dbm": samples,
                    **summarize_profile(samples, {"segment_lengths_m": lengths}, config),
                    "stop_viewpoints_sampled": int(len(view_signals)),
                    "stop_viewpoints_weak": int(np.count_nonzero(view_signals < config["weak_threshold_dbm"])),
                    "stop_viewpoints_min_dbm": float(view_signals.min()),
                    "stop_viewpoints_max_dbm": float(view_signals.max()),
                }
            floor_radio["candidates"][candidate["id"]] = {
                "coverage_above_weak": float(np.mean(values[:len(points)] >= config["weak_threshold_dbm"])),
                "grid_int8": base64.b64encode(grid.tobytes()).decode("ascii"),
                "covered_bits": base64.b64encode(np.packbits(covered, bitorder="big").tobytes()).decode("ascii"),
                "rays": len(values), "blocked_rays": blocked, "tasks": profiles,
            }
        radio[fid] = floor_radio
    return {"floors": radio, "mesh_faces": metadata, "alignment": alignment}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--basis-decoder", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / "runtime") not in output.parents or output.exists():
        parser.error("Expected a new output file inside project runtime")
    geom = json.loads(args.geometry.read_text())
    if geom["format"] != "wifinav-objectnav-ap-review-v1":
        raise ValueError("Unexpected AP geometry format")
    if len(geom["tasks"]) != geom["requested"]:
        raise ValueError("AP geometry did not reach the requested sample count")
    for name, digest in geom["source_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Source file changed after the geometry audit: {name}")
    dr.set_thread_count(4)
    asset = ROOT / "data/scene_datasets" / geom["source_ref"]
    radio = build(geom, asset, args.basis_decoder)
    result = {"geometry": geom, "geometry_sha256": sha(args.geometry), "radio": radio,
              "radio_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "models_called": 0}
    output.parent.mkdir(exist_ok=True, parents=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), allow_nan=False)
    print({fid: len(f["candidates"]) for fid, f in radio["floors"].items()}, radio["alignment"])


if __name__ == "__main__":
    main()
