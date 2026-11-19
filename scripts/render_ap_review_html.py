#!/usr/bin/env python3
"""Build the offline AP review report from a matched pair of audit files."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


def load_json(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def report_payload(audit, data):
    if audit["metadata"] != data["metadata"]:
        raise ValueError("Task and scope audit files are from different builds")
    selected = {
        row["episode_id"]
        for row in audit["episodes"]
        if row["selection_status"] == "selected"
    }
    task_ids = [task["episode_id"] for task in data["tasks"]]
    if len(task_ids) != len(selected) or set(task_ids) != selected:
        raise ValueError("Task IDs differ from the selected audit rows")
    return {"metadata": data["metadata"], "tasks": data["tasks"], "scope": audit["episodes"]}


def add_multiwall(payload, ap_data_hash, report_path, grids_path):
    report = load_json(report_path)
    grids = load_json(grids_path)
    report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
    if (report["config"]["rss_backend"] != "semantic_multiwall" or report["scene_review"]
            or report["input_sha256"] != ap_data_hash
            or grids["format"] != "wifinav-multiwall-ap-preview-v1"
            or grids["ap_data_sha256"] != ap_data_hash
            or grids["multiwall_report_sha256"] != report_hash):
        raise ValueError("The multi-wall profiles and grids must match the AP review batch")
    for task in payload["tasks"]:
        episode = task["episode_id"]
        coverage = report["scenes_with_profiles"][task["scene_id"]]["tasks"][episode]
        layer = grids["tasks"][episode]
        profiles, signals = coverage["assumptions"], layer["grid_rssi_dbm"]
        if (coverage["initial_ap_xyz"] != task["default_ap_position"]
                or layer["ap_xyz"] != task["default_ap_position"]
                or profiles.keys() != signals.keys()
                or any(len(values) != task["base_grid_nodes"] or not all(map(math.isfinite, values))
                       for values in signals.values())
                or any(not profile["available"] or len(profile["samples_dbm"]) != len(task["route_nodes"])
                       for profile in profiles.values())):
            raise ValueError(f"Mismatch in multi-wall AP data for {episode}")
        task["multiwall"] = {**coverage, "grid_rssi_dbm": signals}
    payload["multiwall"] = {
        "execution_commit": report["execution_commit"],
        "grid_commit": grids["execution_commit"],
        "summary": report["summary"],
        "config": report["config"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--topdown", type=Path, help="Native Habitat slices for this exact layout batch")
    parser.add_argument("--multiwall-report", type=Path)
    parser.add_argument("--multiwall-grids", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.multiwall_report) != bool(args.multiwall_grids):
        parser.error("Supply both the multi-wall report and its display grids")
    payload = report_payload(load_json(args.audit), load_json(args.data))
    data_hash = hashlib.sha256(args.data.read_bytes()).hexdigest()
    if args.topdown:
        topdown = load_json(args.topdown)
        task_ids = {str(task["episode_id"]) for task in payload["tasks"]}
        if (topdown["format"] != "wifinav-habitat-topdown-v1"
                or topdown["ap_data_sha256"] != data_hash
                or topdown["episodes"].keys() != task_ids
                or not set(topdown["episodes"].values()) <= topdown["maps"].keys()):
            raise ValueError("Habitat slices do not match the AP review batch")
        payload["topdown"] = topdown
    if args.multiwall_report:
        add_multiwall(payload, data_hash, args.multiwall_report, args.multiwall_grids)
    embedded_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    # Escape '<' so input text cannot terminate the JSON script element.
    embedded_json = embedded_json.replace("<", r"\u003c")
    template = Path(__file__).with_name("ap_review_report")
    page = (template / "page.html").read_text(encoding="utf-8")
    page = page.replace("__STYLE__", (template / "report.css").read_text(encoding="utf-8"))
    page = page.replace("__SCRIPT__", (template / "report.js").read_text(encoding="utf-8"))
    page = page.replace("__PAYLOAD__", embedded_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    print(f"{args.output.resolve()} · {len(payload['tasks'])} tasks · {len(payload['scope'])} audit rows")


if __name__ == "__main__":
    main()
