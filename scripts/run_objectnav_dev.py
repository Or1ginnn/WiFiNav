#!/usr/bin/env python3
"""Run NoSignal navigation on a frozen HM3D train development sample."""
import argparse
from collections import Counter
from hashlib import sha256
from importlib import import_module
import json
import math
from pathlib import Path
import subprocess

import habitat_sim

from objectnav_floor_protocol import MAX_ACTIONS, PROTOCOL, ROOT, load_scene, prepare
from run_objectnav_eval import DEFAULT_AGENT, SENSOR_LABELS, execute, simulator, write

TRAIN_MANIFEST_SHA256 = "3f3034ece428556e27134aa16363b39da052e724a03b88d5757dae2219a3c7f0"
TRAIN_WITNESS_SHA256 = "7f25f2331e46d00338e857b14150fba8b0c791b4ea6120238e94abdbe8b462ef"
DEV_DIAGNOSTIC = "wifinav-objectnav-train-dev-v1"
# Extend only the train vocabulary with category names verified in the
# official train goal annotations and the corresponding HM3D labels.
TRAIN_LABELS = {
    **SENSOR_LABELS,
    "bed": SENSOR_LABELS["bed"] | {"massage bed"},
    "chair": SENSOR_LABELS["chair"] | {"beanbag", "double armchair", "garden chair", "spa armchair"},
    "plant": SENSOR_LABELS["plant"] | {"grass", "tree"},
    "sofa": SENSOR_LABELS["sofa"] | {"chaise longue"},
}


def witness_task(task, scan, scene, witness_dir):
    if (scan, task["source_row"]) != ("g7hUFVNac26", 552):
        return task
    path = witness_dir / f"{scan}.rssi_reference.json"
    raw = path.read_bytes()
    witness = json.loads(raw)
    if sha256(raw).hexdigest() != TRAIN_WITNESS_SHA256 or witness["geometry_sha256"] != scene["geometry_sha256"]:
        raise ValueError("Development floor witness does not match frozen source")
    # The archived geometry baseline is a floor-certified length witness.
    # It stays with the scorer. Task identity and observable inputs are unchanged.
    route = witness["tasks"]["552"]["AP-01"]["baseline_route_xyz"]
    length = sum(math.dist(x, y) for x, y in zip(route, route[1:]))
    return {**task, "route_xyz": route, "reference_m": length}


def diagnostics(rule, views, trace, score):
    detections = [i for i, item in enumerate(trace["target_observations"], 1) if item["pixels"] >= 10]
    valid = trace["positions"][:score["scored_actions"] + 1]
    last = rule.shortest(valid[-1], views)
    distances = [math.dist(a, b) for a, b in zip(trace["positions"], trace["positions"][1:])]
    forwards = [d for d, a in zip(distances, trace["actions"]) if a == "move_forward"]
    return {
        "first_target_observation": detections[0] if detections else None,
        "detectable_target_frames": len(detections),
        "min_target_depth_p25_m": min((m["depth_p25_m"] for m in trace["target_observations"] if m["pixels"] >= 10),
                                    default=None),
        "last_legal_pose_to_view_geodesic_m": (float(last.geodesic_distance)
                                               if last is not None and math.isfinite(last.geodesic_distance) else None),
        "move_forward_count": len(forwards),
        "blocked_forward_count": sum(d < .025 for d in forwards),
        "category_stage": ("success" if score["success"] else
                           "seen_unsuccessful" if detections else "target_not_seen"),
    }


def summarize(rows):
    n = len(rows)
    stage = Counter(r["diagnostics"]["category_stage"] for r in rows)
    seen = sum(r["diagnostics"]["detectable_target_frames"] > 0 for r in rows)
    successes = stage["success"]
    return {
        "episodes": n, "successes": successes, "sr": successes / n,
        "successful_scenes": len({r["scene"] for r in rows if r["navigation"]["success"]}),
        "spl_lower_bound": sum(r["navigation"]["spl_lower_bound"] for r in rows) / n,
        "spl_upper_bound": sum(r["navigation"]["spl_upper_bound"] for r in rows) / n,
        "target_detected": seen, "success_given_target_detected": (
            sum(r["navigation"]["success"] and r["diagnostics"]["detectable_target_frames"] > 0
                for r in rows) / seen if seen else None),
        "stages": dict(stage), "terminations": dict(Counter(r["navigation"]["termination"] for r in rows)),
        "failure_by_stage_and_termination": [
            {"stage": s, "termination": t, "episodes": count}
            for (s, t), count in sorted(Counter((r["diagnostics"]["category_stage"], r["navigation"]["termination"])
                                              for r in rows if not r["navigation"]["success"]).items())
        ],
        "action_budget": MAX_ACTIONS, "total_actions": sum(len(r["trace"]["actions"]) for r in rows),
        "total_collisions": sum(r["trace"]["collisions"] for r in rows),
        "blocked_forwards": sum(r["diagnostics"]["blocked_forward_count"] for r in rows),
        "total_forwards": sum(r["diagnostics"]["move_forward_count"] for r in rows),
        "mean_path_m": sum(r["navigation"]["length_m"] for r in rows) / n,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-sha256", default=TRAIN_MANIFEST_SHA256,
                        help="SHA-256 of the train manifest, recorded before execution")
    parser.add_argument("--witness-dir", type=Path,
                        default=ROOT / "runtime/diagnostics/objectnav_rssi_graph_20261125_v7")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--agent", default=DEFAULT_AGENT)
    parser.add_argument("--egl-device", type=int, default=0)
    args = parser.parse_args()
    if ROOT / "runtime" not in args.output.resolve().parents or args.output.exists():
        parser.error("Output must be a new directory under runtime")
    raw = args.manifest.read_bytes()
    if sha256(raw).hexdigest() != args.manifest_sha256:
        parser.error("Train manifest does not match the recorded SHA-256")
    manifest = json.loads(raw)
    if not manifest.get("scenes") or manifest["config"]["scope"] != "official_train_development_review":
        parser.error("Expected an official train development review")
    original = args.manifest_sha256 == TRAIN_MANIFEST_SHA256
    module, name = args.agent.split(":", 1)
    agent = getattr(import_module(module), name)
    args.output.mkdir(parents=True)
    write(args.output / "metadata.json", {
        "diagnostic": DEV_DIAGNOSTIC, "protocol": PROTOCOL, "split": "train", "track": "no_signal",
        "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "manifest_sha256": args.manifest_sha256, "train_witness_sha256": TRAIN_WITNESS_SHA256 if original else None,
        "config_sha256": manifest["config_sha256"], "habitat_sim_version": habitat_sim.__version__,
        "agent": args.agent, "egl_device": args.egl_device, "action_budget": MAX_ACTIONS,
        "model_requests": 0,
    })

    records = []
    for scene in manifest["scenes"]:
        scan = scene["scene"]
        geometry, source, _ = load_scene(args.manifest, scene, manifest["config"], split="train")
        rows = []
        with simulator(geometry, render=True, gpu_device=args.egl_device) as sim:
            objects = sim.semantic_scene.objects
            for task in geometry["tasks"]:
                witness = witness_task(task, scan, scene, args.witness_dir) if original else task
                episode, rules, views, bounds = prepare(sim.pathfinder, geometry, source, witness)
                names = TRAIN_LABELS[task["category"]]
                ids = [obj.semantic_id for obj in objects if obj and obj.category
                       and obj.category.name().strip().lower() in names]
                if not ids:
                    raise ValueError(f"No semantic sensor target label for {scan}:{task['source_row']}")
                trace = execute(sim, episode, rules, task, agent(), ids, trace_target=True)
                score = rules.score(episode["start_position"], views, bounds, trace)
                rows.append({"scene": scan, "floor": task["floor"], "category": task["category"],
                             "reference_witness": "audited_geometric_route" if witness is not task else "original",
                             "trace": trace, "navigation": score, "diagnostics": diagnostics(rules, views, trace, score)})
        if len(rows) != scene["tasks"] or not any(r["trace"]["labeled_frames"] for r in rows):
            raise ValueError(f"Incomplete executions or missing semantics in {scan}")
        write(args.output / f"{scan}.json", rows)
        print(f"{scan}: {sum(r['navigation']['success'] for r in rows)}/{len(rows)}", flush=True)
        records.extend(rows)
    keys = {(r["scene"], r["trace"]["source_row"]) for r in records}
    if len(keys) != len(records) or len(keys) != manifest["config"]["scene_count"] * manifest["config"]["task_count"]:
        raise ValueError("Incomplete or duplicate development cases")
    summary = summarize(records)
    write(args.output / "results.json", records)
    write(args.output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
