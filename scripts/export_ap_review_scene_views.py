#!/usr/bin/env python3
"""Render textured Matterport floor cutaways for the offline AP report."""
import argparse
import base64
from collections import defaultdict
from functools import lru_cache
import hashlib
import io
import json
import mmap
from pathlib import Path
import struct
import subprocess
import time

import drjit as dr
import mitsuba as mi
import numpy as np
from PIL import Image
from scipy.ndimage import minimum_filter
import trimesh

ROOT = Path(__file__).resolve().parents[1]
CUT_ABOVE_NAVMESH_M = 1.65
FLOOR_MARGIN_BELOW_M = 0.36


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class Textures:
    def __init__(self, mapped_glb, decoder):
        self.glb = mapped_glb
        self.decoder = decoder
        magic, version, size, json_size, json_tag = struct.unpack_from("<4s4I", mapped_glb)
        if (magic, version, size, json_tag) != (b"glTF", 2, len(mapped_glb), 0x4E4F534A):
            raise ValueError("Expected a binary glTF 2.0 file")
        self.gltf = json.loads(mapped_glb[20:20 + json_size])
        self.bin_start = 28 + json_size
        _, tag = struct.unpack_from("<2I", mapped_glb, self.bin_start - 8)
        if tag != 0x004E4942:
            raise ValueError("Mesh buffer chunk missing")
        self.material = {row["name"]: row for row in self.gltf["materials"]}

    @lru_cache(maxsize=8)
    def decode(self, image_index):
        image = self.gltf["images"][image_index]
        view = self.gltf["bufferViews"][image["bufferView"]]
        if view["buffer"] != 0:
            raise ValueError("Expected the embedded glTF buffer")
        offset = self.bin_start + view.get("byteOffset", 0)
        image_data = self.glb[offset:offset + view["byteLength"]]
        if image.get("mimeType") == "image/x-basis":
            image_data = subprocess.run([self.decoder], input=image_data, stdout=subprocess.PIPE,
                                        check=True, timeout=20).stdout
        return np.asarray(Image.open(io.BytesIO(image_data)).convert("RGB"))

    def colors(self, material_name, uv):
        row = self.material[material_name]["pbrMetallicRoughness"]
        factor = np.array(row.get("baseColorFactor", [1, 1, 1, 1])[:3])
        tex = row.get("baseColorTexture")
        if tex is None:
            return np.broadcast_to(factor * 255, (len(uv), 3)), False
        texture = self.gltf["textures"][tex["index"]]
        index = texture["source"] if "source" in texture else texture["extensions"]["GOOGLE_texture_basis"]["source"]
        image = self.decode(index)
        # trimesh converts glTF V to an upward-pointing UV axis.
        u, v = uv[:, 0] % 1, (1 - uv[:, 1]) % 1
        row = np.minimum((v * image.shape[0]).astype(int), image.shape[0] - 1)
        col = np.minimum((u * image.shape[1]).astype(int), image.shape[1] - 1)
        return image[row, col] * factor, True


def physical_mesh(path):
    gltf = trimesh.load_scene(path, process=False)
    vertices, faces, uv = [], [], []
    assignments, materials = [], []
    offset = 0
    for node in gltf.graph.nodes_geometry:
        transform, name = gltf.graph[node]
        geometry = gltf.geometry[name]
        vertices.append(trimesh.transform_points(geometry.vertices, transform))
        faces.append(geometry.faces + offset)
        uv.append(geometry.visual.uv)
        assignments.append(np.full(len(geometry.faces), len(materials), dtype=np.int32))
        materials.append(geometry.visual.material.name)
        offset += len(geometry.vertices)
    vert = np.concatenate(vertices).astype(np.float32)
    tris = np.concatenate(faces).astype(np.uint32)
    mesh = mi.Mesh("matterport", len(vert), len(tris), has_vertex_texcoords=True)
    params = mi.traverse(mesh)
    params["vertex_positions"] = vert.ravel()
    params["faces"] = tris.ravel()
    params["vertex_texcoords"] = np.concatenate(uv).astype(np.float32).ravel()
    params.update()
    return mi.load_dict({"type": "scene", "mesh": mesh}), np.concatenate(assignments), materials


def render_floor(physical, floor, textures):
    scene, assignments, materials = physical
    original_step = floor["meters_per_pixel"]
    step = original_step / 2
    left, top = [v - original_step / 2 for v in floor["first_center_xz"]]
    width, height = floor["width"] * 2, floor["height"] * 2
    # World Habitat (X,Y,Z) transforms to raw MP3D (X,-Z,Y).
    base = floor["floor_y"]
    cut = base + CUT_ABOVE_NAVMESH_M
    world_x = left + (np.arange(width, dtype=np.float32) + .5) * step
    world_z = top + (np.arange(height, dtype=np.float32) + .5) * step
    depth = np.full((height, width), base - FLOOR_MARGIN_BELOW_M, dtype=np.float32)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    textured = 0
    for start in range(0, height, 96):
        end = min(height, start + 96)
        x, z = np.meshgrid(world_x, world_z[start:end])
        p = mi.Point3f(x.ravel(), -z.ravel(), cut)
        hit = scene.ray_intersect(mi.Ray3f(p, mi.Vector3f(0, 0, -1)))
        elevation = np.asarray(hit.p.z)
        visible = np.asarray(hit.is_valid()) & (elevation >= base - FLOOR_MARGIN_BELOW_M)
        if not visible.any():
            continue
        primitive = np.asarray(hit.prim_index)[visible]
        uvs = np.column_stack((np.asarray(hit.uv.x)[visible], np.asarray(hit.uv.y)[visible]))
        group = assignments[primitive]
        rgb = np.empty((len(primitive), 3), dtype=np.uint8)
        for material in np.unique(group):
            selection = group == material
            pixels, is_textured = textures.colors(materials[material], uvs[selection])
            rgb[selection] = np.clip(pixels, 0, 255)
            textured += int(selection.sum()) if is_textured else 0
        rgba[start:end, :, :3].reshape(-1, 3)[visible] = rgb
        rgba[start:end, :, 3].reshape(-1)[visible] = 255
        depth[start:end].reshape(-1)[visible] = elevation[visible]
    seen = rgba[:, :, 3] > 0
    if not seen.any() or not textured:
        raise RuntimeError("Cutaway did not render the scene textures")
    # Add mild shading at vertical jumps so furniture and wall edges read
    # at the scale of a top-down report. Keep exterior pixels transparent.
    relief = np.clip((depth - minimum_filter(depth, size=3)) * .15, 0, .16)
    rgb = rgba[:, :, :3].astype(float)
    rgba[:, :, :3] = np.clip((rgb * .88 + 24) * (1 - relief[:, :, None]), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="WEBP", quality=86, method=4)
    return {
        "width": width, "height": height, "meters_per_pixel": step,
        "top_left_xz": [left, top],
        "rgba_webp_base64": base64.b64encode(buf.getvalue()).decode("ascii"),
        "textured_pixels": textured, "visible_pixels": int(seen.sum()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--topdown", required=True, type=Path)
    parser.add_argument("--multiwall-report", required=True, type=Path)
    parser.add_argument("--basis-decoder", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    mi.set_variant("llvm_ad_mono_polarized")
    dr.set_thread_count(4)
    started = time.monotonic()
    out = args.output.resolve()
    if (ROOT / "runtime") not in out.parents or out.exists():
        raise ValueError("Expected a new output file inside runtime")
    ap_hash = sha(args.data)
    data = json.loads(args.data.read_text())
    topdown = json.loads(args.topdown.read_text())
    multiwall = json.loads(args.multiwall_report.read_text())
    if topdown["ap_data_sha256"] != ap_hash or multiwall["input_sha256"] != ap_hash:
        raise ValueError("Scene views must use the original AP layout batch")
    paths = json.loads((ROOT / "configs/data/server_paths.json").read_text())
    groups = defaultdict(set)
    for task in data["tasks"]:
        groups[task["scene_id"]].add(topdown["episodes"][task["episode_id"]])
    views = {}
    for scene, keys in sorted(groups.items()):
        mesh = ROOT / paths["scene_dataset_root"] / scene
        if sha(mesh) != multiwall["scenes_with_profiles"][scene]["source_sha256"][str(mesh.relative_to(ROOT))]:
            raise ValueError("GLB differs from the wireless review scene")
        physical = physical_mesh(mesh)
        with mesh.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as glb:
            textures = Textures(glb, str(args.basis_decoder.resolve()))
            for key in sorted(keys):
                views[key] = render_floor(physical, topdown["maps"][key], textures)
                print(key, views[key]["width"], views[key]["height"], views[key]["textured_pixels"], flush=True)
            textures.decode.cache_clear()
    result = {
        "format": "wifinav-textured-floor-v1",
        "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "ap_data_sha256": ap_hash, "topdown_sha256": sha(args.topdown),
        "decoder_sha256": sha(args.basis_decoder), "cut_above_navmesh_m": CUT_ABOVE_NAVMESH_M,
        "elapsed_seconds": time.monotonic() - started, "maps": views,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), allow_nan=False)


if __name__ == "__main__":
    main()
