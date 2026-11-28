#!/usr/bin/env python3
"""Capture matched VLFM runs and score their actual poses on the same NavMesh."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import random
import subprocess
from types import SimpleNamespace

import habitat_sim

from objectnav_floor_protocol import ROOT, load_scene, prepare
from objectnav_vlfm_baseline import VLFM
from run_objectnav_dev import TRAIN_MANIFEST_SHA256, witness_task
from run_objectnav_eval import VLFM_OFFICIAL_PROFILE, execute, simulator, write


VERSIONS = ("0.2.4", "0.3.0")


def scene_inputs(frozen):
    for cohort in frozen["cohorts"]:
        path = ROOT / cohort["manifest"]
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != cohort["sha256"]:
            raise ValueError(f"Changed scene manifest: {path}")
        manifest = json.loads(raw)
        for scene in manifest["scenes"]:
            yield path, manifest["config"], scene, cohort["label"]


def capture(scene_rows, profile, frozen, out, names, gpu):
    camera = profile["camera"]
    current = VLFM.metadata(camera)
    if any(current[k] != frozen[k] for k in ("policy_revision", "model_receipt_sha256", "pointnav_sha256")):
        raise ValueError("Model receipt changed since the comparison was frozen")
    output = out / habitat_sim.__version__
    output.mkdir(exist_ok=True)
    for path, config, scene, cohort in scene_rows:
        name = scene["scene"]
        if name not in names:
            continue
        geometry, source, _ = load_scene(path, scene, config, split="train")
        with simulator(geometry, render=True, gpu_device=gpu, rgbd=True, profile=profile) as sim:
            for task in geometry["tasks"]:
                row = task["source_row"]
                target = output / f"{name}.{row}.json"
                identity = {"scene": name, "source_row": row, "category": task["category"], "cohort": cohort,
                            "version": habitat_sim.__version__, "run_id": frozen["run_id"],
                            "execution_commit": frozen["execution_commit"]}
                if target.exists():
                    prior = json.loads(target.read_bytes())
                    if any(prior[k] != v for k, v in identity.items()):
                        raise ValueError(f"Existing record has another identity: {target}")
                    continue
                episode = source["episodes"][row]
                floor_y = geometry["floors"][task["floor"]]["y"]
                # Give both simulators the same live termination condition. The
                # common scorer also checks the navigation surface after the run.
                live = SimpleNamespace(action_budget=profile["max_actions"], executed_pose_on_floor=lambda p:
                                       abs(p[1] - floor_y) <= config["floor_tolerance_m"] + 1e-5)
                policy = VLFM(camera=camera)
                try:
                    trace = execute(sim, episode, live, task, policy, trace_target=True)
                finally:
                    policy.close()
                partial = target.with_suffix(f".{os.getpid()}.partial")
                write(partial, {**identity, "trace": trace})
                partial.rename(target)
                print(f"{habitat_sim.__version__} {name}:{row} {len(trace['actions'])} actions", flush=True)


def reference_inputs(scene_rows, profile):
    if habitat_sim.__version__ != "0.3.0":
        raise ValueError("Use Habitat 0.3.0 to compute both sets of scores")
    for path, config, scene, cohort in scene_rows:
        geometry, source, _ = load_scene(path, scene, config, split="train")
        asset = ROOT / "data/scene_datasets" / scene["source_ref"]
        finder = habitat_sim.PathFinder()
        if not finder.load_nav_mesh(str(asset.with_suffix(".navmesh"))):
            raise ValueError(f"Unable to load {asset}")
        for task in geometry["tasks"]:
            row = task["source_row"]
            name = scene["scene"]
            witness = (witness_task(task, name, scene, ROOT / "runtime/diagnostics/objectnav_rssi_graph_20261125_v7")
                       if cohort == "original20" else task)
            episode, rule, views, bounds = prepare(finder, geometry, source, witness, action_budget=profile["max_actions"])
            result = {"scene": name, "source_row": row, "category": task["category"], "cohort": cohort}
            if not rule.executed_pose_on_floor(episode["start_position"]):
                raise ValueError(f"Invalid start in the common scorer: {name}:{row}")
            yield result, episode, rule, views, bounds


def score(scene_rows, profile, frozen, out):
    pairs = []
    expected_files = set()
    for result, episode, rule, views, bounds in reference_inputs(scene_rows, profile):
        name, row = result["scene"], result["source_row"]
        filename = f"{name}.{row}.json"
        expected_files.add(filename)
        for version in VERSIONS:
            item = json.loads((out / version / filename).read_bytes())
            if (item["run_id"] != frozen["run_id"] or item["execution_commit"] != frozen["execution_commit"]
                    or item["scene"] != name or item["source_row"] != row or item["version"] != version):
                raise ValueError(f"Mixed-version or mismatched record: {version} {name}:{row}")
            trace = item["trace"]
            if trace["observed_rssi_samples"] or trace["observed_rssi_missing"] or trace["labeled_frames"]:
                raise ValueError("Unexpected online observation")
            metrics = rule.score(episode["start_position"], views, bounds, trace)
            if metrics["termination"] == "incomplete":
                raise ValueError(f"Incomplete trace: {version} {name}:{row}")
            result[version] = {**metrics, "captured_actions": len(trace["actions"]), "captured_collisions": trace["collisions"]}
        pairs.append(result)
    for version in VERSIONS:
        if {p.name for p in (out / version).glob("*.json")} != expected_files:
            raise ValueError(f"Unexpected set of result files for {version}")
    if Counter(r["cohort"] for r in pairs) != {"original20": 20, "new80": 80}:
        raise ValueError("Expected exactly 100 pairs")
    write(out / "pairs.json", pairs)
    summary = {"all": summarize(pairs)}
    for cohort in ("original20", "new80"):
        summary[cohort] = summarize([p for p in pairs if p["cohort"] == cohort])
    write(out / "summary.json", summary)
    print(json.dumps(summary), flush=True)


def summarize(pairs):
    n = len(pairs)
    counts = Counter((p[VERSIONS[0]]["success"], p[VERSIONS[1]]["success"]) for p in pairs)
    cluster = {}
    for pair in pairs:
        cluster.setdefault(pair["scene"], []).append(pair[VERSIONS[1]]["success"] - pair[VERSIONS[0]]["success"])
    rng = random.Random(20261129)
    estimates = []
    samples = sorted(cluster)
    for _ in range(10000):
        draws = [cluster[key] for key in rng.choices(samples, k=len(samples))]
        estimates.append(sum(map(sum, draws)) / sum(map(len, draws)))
    estimates.sort()
    result = {"pairs": n, "scenes": len(samples), "both_success": counts[1, 1], "both_failure": counts[0, 0],
              "only_0.2.4": counts[1, 0], "only_0.3.0": counts[0, 1],
              "sr_delta_0.3.0_minus_0.2.4": (counts[0, 1] - counts[1, 0]) / n,
              "sr_delta_scene_bootstrap_95": [estimates[249], estimates[9749]]}
    for version in VERSIONS:
        rows = [p[version] for p in pairs]
        result[version] = {
            "sr": sum(r["success"] for r in rows) / n,
            "spl_lower": math.fsum(r["spl_lower_bound"] for r in rows) / n,
            "spl_upper": math.fsum(r["spl_upper_bound"] for r in rows) / n,
            "mean_path_m": math.fsum(r["length_m"] for r in rows) / n,
            "terminations": dict(Counter(r["termination"] for r in rows)),
            "captured_collisions": sum(r["captured_collisions"] for r in rows),
            "captured_actions": sum(r["captured_actions"] for r in rows),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--scene", action="append")
    mode.add_argument("--score", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    parser.add_argument("--egl-device", default=0, type=int)
    args = parser.parse_args()
    batch = args.batch.resolve()
    if ROOT / "runtime" not in batch.parents or habitat_sim.__version__ not in VERSIONS:
        parser.error("Expected a project runtime batch and a pinned Habitat version")
    frozen = json.loads((batch / "metadata.json").read_bytes())
    profile_raw = VLFM_OFFICIAL_PROFILE.read_bytes()
    if (sha256(profile_raw).hexdigest() != frozen["execution_profile_sha256"]
            or frozen["cohorts"][0]["sha256"] != TRAIN_MANIFEST_SHA256
            or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != frozen["execution_commit"]):
        raise ValueError("Execution profile, original sample or code changed")
    profile = json.loads(profile_raw)
    rows = list(scene_inputs(frozen))
    if len(rows) != 15 or sum(scene["tasks"] for _, _, scene, _ in rows) != 100:
        raise ValueError("Expected the frozen 15-scene, 100-task sample")
    if args.score:
        score(rows, profile, frozen, batch)
    elif args.preflight:
        cases = [result for result, _, _, _, _ in reference_inputs(rows, profile)]
        if len({(r["scene"], r["source_row"]) for r in cases}) != 100 or len({r["category"] for r in cases}) != 6:
            raise ValueError("Expected 100 distinct tasks covering the six categories")
        write(batch / "cases.json", cases)
    else:
        names = set(args.scene)
        if len(names) != len(args.scene) or names - {row[2]["scene"] for row in rows}:
            parser.error("Expected unique scenes from the frozen sample")
        capture(rows, profile, frozen, batch, names, args.egl_device)


if __name__ == "__main__":
    main()
