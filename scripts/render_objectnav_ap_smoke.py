#!/usr/bin/env python3
"""Embed an AP smoke payload in a self-contained local HTML report."""
import argparse
import base64
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
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
