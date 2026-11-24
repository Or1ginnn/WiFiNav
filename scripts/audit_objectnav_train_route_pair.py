#!/usr/bin/env python3
"""Find and check a bounded same-endpoint route contrast without changing the task sample."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STEPS = (0.15, 0.075)
MAX_RATIO = 1.2
MIN_GAIN_M = 0.5
SPEED_MPS = 0.25
MAX_CANDIDATES = 12
MIN_REFERENCE_GAIN_M = .05


def length(points):
    import numpy as np

    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def propose(geometry, refine=False):
    import habitat_sim
    import numpy as np
    from build_objectnav_ap_smoke import sample_route, shortest

    finder = habitat_sim.PathFinder()
    asset = ROOT / "data/scene_datasets" / geometry["source_ref"]
    if not finder.load_nav_mesh(str(asset.with_suffix(".navmesh"))):
        raise ValueError(f"Cannot load navmesh for {asset}")
    result = {"source_ref": geometry["source_ref"], "tasks": [], "max_length_ratio": MAX_RATIO, "refine": refine}
    for task in geometry["tasks"]:
        floor = geometry["floors"][task["floor"]]
        tolerance = geometry["config"]["floor_tolerance_m"]
        route = np.asarray(task["route_xyz"])
        start, stop = route[0], route[-1]
        baseline = shortest(finder, start, stop, floor["y"], tolerance)
        if baseline is None or abs(length(baseline) - task["reference_m"]) > .01:
            raise ValueError(f"Frozen reference cannot be reproduced for row {task['source_row']}")
        m = floor["map"]
        mask = np.unpackbits(np.frombuffer(base64.b64decode(m["walkable_bits"]), dtype=np.uint8),
                             count=m["width"] * m["height"]).reshape(m["height"], m["width"])
        stride = max(1, round((.25 if refine else .75) / m["meters_per_pixel"]))
        rows, cols = np.nonzero(mask[::stride, ::stride])
        xy = np.asarray(m["first_center_xz"]) + np.column_stack((cols, rows)) * stride * m["meters_per_pixel"]
        offsets = np.linalg.norm(xy[:, None] - route[None, :, [0, 2]], axis=2).min(axis=1)
        budget = MAX_RATIO * length(baseline)
        best_case = np.linalg.norm(xy - start[[0, 2]], axis=1) + np.linalg.norm(xy - stop[[0, 2]], axis=1)
        indices = np.flatnonzero((offsets >= (.20 if refine else .60)) & (best_case <= budget))
        min_leg = min(.75, length(baseline) / 4) if refine else .75
        candidates = []
        for index in indices[np.argsort(-offsets[indices], kind="stable")]:
            x, z = xy[index]
            via = np.asarray(finder.snap_point([x, floor["y"], z]))
            if not np.isfinite(via).all() or np.linalg.norm(via - [x, floor["y"], z]) > .16:
                continue
            a = shortest(finder, start, via, floor["y"], tolerance)
            b = shortest(finder, via, stop, floor["y"], tolerance)
            if a is None or b is None or min(length(a), length(b)) < min_leg:
                continue
            if np.linalg.norm(a[-1] - b[0]) > .005 or not length(baseline) + .10 < length(a) + length(b) <= budget:
                continue
            # Discard paths that retrace or cross before or after the shared via point.
            left, right = (np.asarray(sample_route(path, .05))[:, [0, 2]] for path in (a, b))
            if min(len(left), len(right)) < 8:
                continue
            gaps = np.linalg.norm(left[:, None] - right[None, :], axis=2)
            gaps[-8:, :8] = np.inf
            if np.any(gaps < .075) or np.linalg.norm(left[-8] - right[7]) < .35:
                continue
            alternate = np.concatenate([a, b[1:]])
            if np.max(np.linalg.norm(alternate[[0, -1]] - baseline[[0, -1]], axis=1)) > .005:
                continue
            candidates.append({"via_xyz": via.tolist(), "path_xyz": alternate.tolist()})
            if len(candidates) == MAX_CANDIDATES:
                break
        result["tasks"].append({"source_row": task["source_row"], "floor": task["floor"],
                                "baseline_xyz": baseline.tolist(), "candidates": candidates})
    return result


def score(geometry, proposals):
    import drjit as dr
    from run_objectnav_ap_radio import habitat_to_glb, semantic_geometry, signal_for_anchor
    from run_rss_raytrace_pilot import summarize_profile
    import numpy as np

    dr.set_thread_count(4)
    asset = ROOT / "data/scene_datasets" / geometry["source_ref"]
    stem = asset.name.removesuffix(".basis.glb")
    scene, tags, _ = semantic_geometry(asset.with_name(stem + ".semantic.glb"), asset.with_name(stem + ".semantic.txt"))
    config = geometry["config"]

    def evaluate(points, ap, step):
        # Match the report's sampling policy without importing Habitat in this environment.
        samples = [points[0]]
        for start, stop in zip(points, points[1:]):
            n = max(1, int(np.ceil(np.linalg.norm(stop - start) / step)))
            samples.extend(start + (stop - start) * (i / n) for i in range(1, n + 1))
        rx = habitat_to_glb(samples, config["rx_height_above_floor_m"])
        signal, _ = signal_for_anchor(scene, tags, ap, rx, config)
        segment_lengths = np.linalg.norm(np.diff(samples, axis=0), axis=1).tolist()
        metrics = summarize_profile(signal.tolist(), {"segment_lengths_m": segment_lengths}, config)
        return {"step_m": step, "length_m": length(points), "weak_m": metrics["weak_length_m"],
                "weak_motion_s": metrics["weak_length_m"] / SPEED_MPS}

    comparisons = []
    for task in proposals["tasks"]:
        ap = geometry["floors"][task["floor"]]["candidates"][0]
        if not task["candidates"]:
            continue
        baseline = [evaluate(np.asarray(task["baseline_xyz"]), ap["xyz"], step) for step in STEPS]
        for i, candidate in enumerate(task["candidates"]):
            alternate = [evaluate(np.asarray(candidate["path_xyz"]), ap["xyz"], step) for step in STEPS]
            gain = min(a["weak_m"] - b["weak_m"] for a, b in zip(baseline, alternate))
            comparisons.append({"source_row": task["source_row"], "floor": task["floor"], "ap": ap["id"],
                                "candidate_index": i, "baseline": baseline, "alternate": alternate,
                                "min_weak_gain_m": gain, "passes": gain >= MIN_GAIN_M})
    return {"source_ref": proposals["source_ref"], "task_count": len(proposals["tasks"]),
            "max_length_ratio": MAX_RATIO, "min_weak_gain_m": MIN_GAIN_M,
            "speed_mps": SPEED_MPS, "comparisons": comparisons}


def select_reference(profiles):
    """Choose a candidate whose gain persists at both sampling resolutions."""
    baseline = profiles[0]
    ranked = [0]
    for i, candidate in enumerate(profiles[1:], 1):
        weak = [b["weak_length_m"] - a["weak_length_m"] for b, a in zip(baseline, candidate)]
        severe = [b["outage_length_m"] - a["outage_length_m"] for b, a in zip(baseline, candidate)]
        if min(weak) >= MIN_REFERENCE_GAIN_M or (max(map(abs, weak)) < 1e-5 and min(severe) >= MIN_REFERENCE_GAIN_M):
            ranked.append(i)
    return min(ranked, key=lambda i: (profiles[i][-1]["weak_length_m"],
                                     profiles[i][-1]["outage_length_m"], profiles[i][-1]["length_m"]))


def rssi_reference(geometry, proposals):
    import drjit as dr
    from run_objectnav_ap_radio import habitat_to_glb, semantic_geometry, signal_for_anchor
    from run_rss_raytrace_pilot import summarize_profile
    import numpy as np

    dr.set_thread_count(4)
    asset = ROOT / "data/scene_datasets" / geometry["source_ref"]
    stem = asset.name.removesuffix(".basis.glb")
    scene, tags, _ = semantic_geometry(asset.with_name(stem + ".semantic.glb"), asset.with_name(stem + ".semantic.txt"))
    config = geometry["config"]

    def sample(points, step):
        vertices = np.asarray(points, dtype=float)
        intervals = np.maximum(1, np.ceil(np.linalg.norm(np.diff(vertices, axis=0), axis=1) / step)).astype(int)
        return np.concatenate([np.linspace(a, b, n, endpoint=False) for a, b, n in
                               zip(vertices, vertices[1:], intervals)] + [vertices[-1:]])

    result = {}
    by_row = {row["source_row"]: row for row in geometry["tasks"]}
    if len(proposals["tasks"]) != len(by_row) or {t["source_row"] for t in proposals["tasks"]} != set(by_row):
        raise ValueError("Expected exactly one route proposal set per frozen task")
    for task in proposals["tasks"]:
        key = task["source_row"]
        baseline = task["baseline_xyz"]
        floor = geometry["floors"][by_row[key]["floor"]]
        if task["floor"] != by_row[key]["floor"] or abs(length(baseline) - by_row[key]["reference_m"]) > .01:
            raise ValueError(f"Invalid frozen route baseline for {key}")
        candidates = [row["path_xyz"] for row in task["candidates"]]
        for path in [baseline, *candidates]:
            points = np.asarray(path)
            if (np.max(np.abs(points[:, 1] - floor["y"])) > config["floor_tolerance_m"]
                    or length(points) > MAX_RATIO * length(baseline) + 1e-6
                    or np.max(np.linalg.norm(points[[0, -1]] - np.asarray(by_row[key]["route_xyz"])[[0, -1]], axis=1)) > .005):
                raise ValueError(f"Out-of-scope route candidate for {key}")
        samples = [[sample(route, step) for step in STEPS] for route in [baseline, *candidates]]
        flattened = [points for grouped in samples for points in grouped]
        receivers = habitat_to_glb(np.concatenate(flattened), config["rx_height_above_floor_m"])
        stops = np.cumsum([len(points) for points in flattened])[:-1]
        task_results = {}
        for ap in floor["candidates"]:
            signal, _ = signal_for_anchor(scene, tags, ap["xyz"], receivers, config)
            profiles = []
            for points, segment in zip(flattened, np.split(signal, stops)):
                rssi = segment.tolist()
                summary = summarize_profile(rssi, {"segment_lengths_m": np.linalg.norm(np.diff(points, axis=0), axis=1).tolist()}, config)
                profiles.append({**summary, "samples_dbm": rssi})
            grouped = [profiles[i:i + len(STEPS)] for i in range(0, len(profiles), len(STEPS))]
            choice = select_reference(grouped)
            task_results[ap["id"]] = {"candidate_count": len(candidates), "selected": choice,
                                      "route_xyz": samples[choice][-1].tolist(), "profile": grouped[choice][-1],
                                      "baseline_profile": grouped[0][-1],
                                      "weak_gain_m": [b["weak_length_m"] - a["weak_length_m"] for b, a in zip(grouped[0], grouped[choice])],
                                      "severe_gain_m": [b["outage_length_m"] - a["outage_length_m"] for b, a in zip(grouped[0], grouped[choice])]}
        result[str(key)] = task_results
    return {"format": "wifinav-objectnav-rssi-reference-v1", "source_ref": geometry["source_ref"],
            "max_length_ratio": MAX_RATIO, "minimum_gain_m": MIN_REFERENCE_GAIN_M, "sampling_steps_m": STEPS,
            "tasks": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", required=True, type=Path)
    parser.add_argument("--proposals", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--refine", action="store_true", help="Use a finer geometric via grid")
    mode.add_argument("--rssi-reference", action="store_true", help="Score same-endpoint options for every AP")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (args.rssi_reference and not args.proposals) or (args.refine and args.proposals):
        parser.error("--rssi-reference needs --proposals; --refine generates proposals")
    output = args.output.resolve()
    if (ROOT / "runtime") not in output.parents or output.exists():
        parser.error("Expected a new output file under runtime")
    raw = args.geometry.read_bytes()
    geometry = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    suffixes = (".semantic.glb", ".semantic.txt") if args.proposals else (".navmesh",)
    for name, expected in geometry["source_sha256"].items():
        if name.endswith(suffixes) and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen asset changed: {name}")
    if args.proposals:
        proposal_raw = args.proposals.read_bytes()
        proposals = json.loads(proposal_raw)
        if proposals["geometry_sha256"] != digest:
            raise ValueError("Route proposals do not match the frozen geometry")
        result = rssi_reference(geometry, proposals) if args.rssi_reference else score(geometry, proposals)
        result["proposals_sha256"] = hashlib.sha256(proposal_raw).hexdigest()
    else:
        result = propose(geometry, args.refine)
    result["geometry_sha256"] = digest
    result["execution_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), allow_nan=False)


if __name__ == "__main__":
    main()
