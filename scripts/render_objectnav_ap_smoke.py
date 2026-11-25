#!/usr/bin/env python3
"""Embed an AP smoke payload in a self-contained local HTML report."""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path


def add_rssi_reference(manifest_path, row, source, radio, *, graph_mode):
    scene = row["scene"]
    suffix = "navmesh_graph" if graph_mode else "refined_routes"
    source_data = manifest_path.with_name(f"{scene}.{suffix}.json").read_bytes()
    severe_first_format = "wifinav-objectnav-rssi-graph-v4"
    formats = ("wifinav-objectnav-rssi-graph-v2", "wifinav-objectnav-rssi-graph-v3", severe_first_format) if graph_mode else (
        "wifinav-objectnav-rssi-reference-v1",)
    hash_field = "graph_sha256" if graph_mode else "proposals_sha256"
    payload = json.loads(manifest_path.with_name(f"{scene}.rssi_reference.json").read_bytes())
    if (payload["format"] not in formats or payload["source_ref"] != source["source_ref"]
            or payload["geometry_sha256"] != row["geometry_sha256"]
            or payload[hash_field] != hashlib.sha256(source_data).hexdigest()
            or payload["tasks"].keys() != {str(task["source_row"]) for task in source["tasks"]}):
        raise ValueError(f"RSSI references do not match the frozen sample: {scene}")
    ratio = payload["max_length_ratio"]
    objective_order = ["weak_length_m", "outage_length_m", "length_m"]
    if payload["format"] == severe_first_format:
        objective_order = ["outage_length_m", "weak_length_m", "length_m"]
        if payload["objective_order"] != objective_order:
            raise ValueError(f"Unexpected graph cost order: {scene}")
    for task in source["tasks"]:
        key = str(task["source_row"])
        candidates = radio["floors"][task["floor"]]["candidates"]
        references = payload["tasks"][key]
        if references.keys() != candidates.keys():
            raise ValueError(f"Missing AP-specific references: {scene}/{key}")
        for ap, reference in references.items():
            points = reference["route_xyz"]
            if (not points or len(points) != len(reference["profile"]["samples_dbm"])
                    or not 0 <= reference["selected"] <= reference.get("candidate_count", 1)
                    or (ratio is not None and reference["profile"]["length_m"] > ratio * task["reference_m"] + .001)
                    or any(math.dist(points[i], task["route_xyz"][i]) > .005 for i in (0, -1))):
                raise ValueError(f"Invalid route reference: {scene}/{key}/{ap}")
            if graph_mode and (reference["objective_um"] > reference["baseline_objective_um"]
                               or (ratio is not None and reference["objective_um"][2] > reference["budget_um"])):
                raise ValueError(f"Inconsistent graph optimum: {scene}/{key}/{ap}")
            candidates[ap].setdefault("reference_tasks", {})[key] = reference
    fields = ("execution_commit", "max_length_ratio", "sampling_steps_m")
    fields += ("graph_grid_m", "length_unit_m") if graph_mode else ("minimum_gain_m",)
    return {**{name: payload[name] for name in fields}, "objective_order": objective_order}


def assemble(manifest_path, with_routes=False, with_rssi_reference=False, with_rssi_graph=False):
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    config = manifest["config"]
    scenes = manifest["scenes"]
    if len(scenes) != config["scene_count"] or len({row["scene"] for row in scenes}) != len(scenes):
        raise ValueError("Expected a complete, distinct set of frozen scenes")
    geom = {"format": "wifinav-objectnav-ap-review-v1", "split": "train", "scope": config["scope"],
            "config": config, "config_sha256": manifest["config_sha256"], "scene_count": len(scenes),
            "requested": len(scenes) * config["task_count"], "tasks": [], "floors": {}, "scope_audit": [],
            "source_episode_count": 0, "scenes": [], "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest()}
    radio = {"floors": {}}
    route_checks = []
    reference_policy = None
    commits = set()
    for row in scenes:
        scene = row["scene"]
        raw = manifest_path.with_name(f"{scene}.radio.json").read_bytes()
        report = json.loads(raw)
        source = report["geometry"]
        if (report["geometry_sha256"] != row["geometry_sha256"] or source["source_ref"] != row["source_ref"]
                or source["config_sha256"] != geom["config_sha256"] or report["models_called"] != 0
                or source["split"] != "train" or len(source["tasks"]) != config["task_count"]):
            raise ValueError(f"Radio result does not match the frozen train sample: {scene}")
        commits.add(report["radio_commit"])
        geom["scenes"].append({**row, "source_sha256": source["source_sha256"],
                               "radio_sha256": hashlib.sha256(raw).hexdigest(),
                               "alignment": report["radio"]["alignment"], "mesh_faces": report["radio"]["mesh_faces"],
                               "execution_commit": source["execution_commit"]})
        geom["source_episode_count"] += source["source_episode_count"]
        for floor, spec in source["floors"].items():
            identifier = f"{scene}/{floor}"
            geom["floors"][identifier] = {**spec, "source_ref": source["source_ref"], "floor_id": floor}
            radio["floors"][identifier] = report["radio"]["floors"][floor]
        geom["tasks"].extend({**task, "scene": scene, "task_key": f"{scene}:{task['source_row']}",
                              "floor": f"{scene}/{task['floor']}"} for task in source["tasks"])
        geom["scope_audit"].extend({**item, "scene": scene} for item in source["scope_audit"])
        if with_rssi_reference or with_rssi_graph:
            policy = add_rssi_reference(manifest_path, row, source, report["radio"], graph_mode=with_rssi_graph)
            if reference_policy is not None and policy != reference_policy:
                raise ValueError("RSSI references mix policies or execution commits")
            reference_policy = policy
        if with_routes:
            proposals = manifest_path.with_name(f"{scene}.routes.json").read_bytes()
            checks = json.loads(manifest_path.with_name(f"{scene}.route_scores.json").read_bytes())
            geometry_keys = {row["geometry_sha256"], json.loads(proposals)["geometry_sha256"], checks["geometry_sha256"]}
            if len(geometry_keys) != 1 or checks["proposals_sha256"] != hashlib.sha256(proposals).hexdigest():
                raise ValueError(f"Route checks do not match frozen geometry: {scene}")
            route_checks.append((scene, checks, json.loads(proposals)))
    if len(commits) != 1:
        raise ValueError("Radio results mix execution commits")
    result = {"geometry": geom, "radio": radio, "radio_commit": commits.pop(), "models_called": 0}
    if reference_policy is not None:
        result["rssi_reference_policy"] = reference_policy
    if route_checks:
        proof = {"tasks": sum(checks["task_count"] for _, checks, _ in route_checks), "tested": 0, "passed": 0}
        for scene, checks, proposals in route_checks:
            proof["tested"] += len(checks["comparisons"])
            for pair in checks["comparisons"]:
                if not pair["passes"]:
                    continue
                proof["passed"] += 1
                if "example" not in proof:
                    task = next(t for t in proposals["tasks"] if t["source_row"] == pair["source_row"])
                    proof["example"] = {**pair, "task_key": f"{scene}:{pair['source_row']}",
                                        "path_xyz": task["candidates"][pair["candidate_index"]]["path_xyz"]}
        result["route_diagnostic"] = proof
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source_type = parser.add_mutually_exclusive_group(required=True)
    source_type.add_argument("--report", type=Path)
    source_type.add_argument("--manifest", type=Path)
    parser.add_argument("--with-routes", action="store_true")
    ref_mode = parser.add_mutually_exclusive_group()
    ref_mode.add_argument("--with-rssi-reference", action="store_true")
    ref_mode.add_argument("--with-rssi-graph", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.manifest and (args.with_routes or args.with_rssi_reference or args.with_rssi_graph):
        parser.error("Route overlays require --manifest")
    if args.manifest:
        report = assemble(args.manifest, args.with_routes, args.with_rssi_reference, args.with_rssi_graph)
        raw = json.dumps(report, separators=(",", ":"), allow_nan=False).encode()
    else:
        raw = args.report.read_bytes()
        report = json.loads(raw)
    geom = report["geometry"]
    if geom["format"] != "wifinav-objectnav-ap-review-v1" or len(geom["tasks"]) != geom["requested"]:
        raise ValueError("Expected a complete ObjectNav AP smoke report")
    for floor, spec in geom["floors"].items():
        grid = report["radio"]["floors"][floor]
        profiles = grid["candidates"]
        cells = grid["width"] * grid["height"]
        if set(profiles) != {item["id"] for item in spec["candidates"]}:
            raise ValueError(f"Incomplete AP candidates on {floor}")
        tasks = {str(t["source_row"]): t for t in geom["tasks"] if t["floor"] == floor}
        for ap, data in profiles.items():
            if (len(base64.b64decode(data["grid_int8"], validate=True)) != cells
                    or len(base64.b64decode(data["covered_bits"], validate=True)) != (cells + 7) // 8):
                raise ValueError(f"AP {floor}/{ap} has a misaligned heat map or boundary mask")
            if data["tasks"].keys() != tasks.keys() or any(
                len(data["tasks"][key]["samples_dbm"]) != len(task["route_xyz"])
                for key, task in tasks.items()
            ):
                raise ValueError(f"AP {floor}/{ap} is missing a task profile")
    report["report_sha256"] = hashlib.sha256(raw).hexdigest()
    payload = json.dumps(report, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    payload = payload.replace("<", r"\u003c")
    source = Path(__file__).with_name("objectnav_ap_report")
    page = (source / "index.html").read_text(encoding="utf-8")
    for marker, filename in (("__STYLE__", "style.css"), ("__SCRIPT__", "report.js")):
        page = page.replace(marker, (source / filename).read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(page.replace("__REPORT_JSON__", payload))
    print(args.output.resolve())


if __name__ == "__main__":
    main()
