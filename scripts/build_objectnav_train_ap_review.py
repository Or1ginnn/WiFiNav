#!/usr/bin/env python3
"""Freeze a bounded, geometry-only review sample from the installed official train split."""
import argparse
import hashlib
import json
from pathlib import Path

from build_objectnav_ap_smoke import ROOT, build


def write_json(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, separators=(",", ":"), allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--disjoint-from", type=Path, help="Exclude the scenes in a frozen train review manifest")
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / "runtime") not in output.parents or output.exists():
        parser.error("Expected a new run directory under runtime")
    raw_config = args.config.read_bytes()
    config = json.loads(raw_config)
    receipt = (ROOT / "data/_manifests/hm3d_objectnav_v2_episodes.json").read_bytes()
    scenes = json.loads(receipt)["splits"]["train"]["scene_refs"]
    order = sorted(scenes, key=lambda ref: hashlib.sha256(f"{config['selection_seed']}:{ref}".encode()).digest())
    excluded_refs = set()
    if args.disjoint_from:
        prior = args.disjoint_from.read_bytes()
        excluded_refs = {scene["source_ref"] for scene in json.loads(prior)["scenes"]}
        if not excluded_refs or not excluded_refs <= set(scenes):
            raise ValueError("The excluded review must cite installed official train scenes")
        order = [ref for ref in order if ref not in excluded_refs]
    output.mkdir(parents=True)
    config_hash = hashlib.sha256(raw_config).hexdigest()
    attempts, selected = [], []
    for ref in order:
        asset = ROOT / "data/scene_datasets" / ref
        scene = asset.name.removesuffix(".basis.glb")
        if Path(ref).parts[:2] != ("hm3d_v0.2", "train"):
            raise ValueError(f"Unexpected official train reference: {ref}")
        shard = ROOT / f"data/datasets/objectnav/hm3d/v2/train/content/{scene}.json.gz"
        geometry = build(shard, asset, config, config["task_count"], verify_sampled_routes=bool(excluded_refs))
        geometry["config_sha256"] = config_hash
        name = f"{scene}.geometry.json"
        write_json(output / name, geometry)
        complete = len(geometry["tasks"]) == config["task_count"]
        row = {"scene": scene, "source_ref": ref, "geometry": name, "selected": complete,
               "geometry_sha256": hashlib.sha256((output / name).read_bytes()).hexdigest(),
               "tasks": len(geometry["tasks"]), "floors": len(geometry["floors"]),
               "audited_rows": len(geometry["scope_audit"])}
        attempts.append(row)
        print(row, flush=True)
        if complete:
            selected.append(row)
        if len(selected) == config["scene_count"]:
            break
    manifest = {"config_sha256": config_hash, "config": config,
                "receipt_sha256": hashlib.sha256(receipt).hexdigest(), "scenes": selected, "attempts": attempts}
    if excluded_refs:
        manifest["excluded_scene_refs"] = sorted(excluded_refs)
        manifest["excluded_manifest_sha256"] = hashlib.sha256(prior).hexdigest()
    write_json(output / "manifest.json", manifest)
    if len(selected) != config["scene_count"]:
        raise SystemExit("Could not fill the frozen review sample")


if __name__ == "__main__":
    main()
