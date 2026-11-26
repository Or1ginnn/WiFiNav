#!/usr/bin/env python3
"""Build the single-AP HM3D ObjectNav benchmark from frozen source shards."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys

from build_objectnav_ap_smoke import ROOT, build
from build_objectnav_train_ap_review import write_json
from install_hm3d_train import EPISODES, sha256
from connectivity_vln.benchmark.single_floor import route_metrics


CONFIG = ROOT / "configs/benchmark/objectnav_val_v1.json"
OPERATIONAL_FILES = (
    "scripts/build_objectnav_benchmark.py", "scripts/build_objectnav_ap_smoke.py",
    "scripts/score_objectnav_trace.py", "scripts/run_objectnav_ap_radio.py",
    "scripts/run_rss_raytrace_pilot.py", "scripts/solve_objectnav_rssi_graph.py", "scripts/check_objectnav_graph_optimum.py",
    "src/connectivity_vln/benchmark/single_floor.py",
)
RENDER_ENV = ROOT / "runtime/envs/sionna_rt_2_2_0_py311/bin/python"
DECODER = ROOT / "runtime/tools/basisu_v1_60/decode_basis_ppm"
LLVM = "/opt/anaconda3/pkgs/libllvm19-19.1.2-ha7bfdaf_0/lib/libLLVM-19.so"


def load(path):
    return json.loads(path.read_bytes())


def run(python, script, log, *args):
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4"}
    env.setdefault("DRJIT_LIBLLVM_PATH", LLVM)
    command = [str(python), str(ROOT / "scripts" / script), *map(str, args)]
    with log.open("x") as handle:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"{script} failed (exit {result.returncode}). See {log}")


def files_for_scene(ref):
    asset = ROOT / "data/scene_datasets" / ref
    scan = asset.name.removesuffix(".basis.glb")
    shard = ROOT / "data/datasets/objectnav/hm3d/v2/val/content" / (scan + ".json.gz")
    return scan, shard, (
        asset, asset.with_suffix(".navmesh"), asset.with_name(scan + ".semantic.glb"),
        asset.with_name(scan + ".semantic.txt"),
    )


def unavailable(ref):
    _, shard, files = files_for_scene(ref)
    return [str(path.relative_to(ROOT)) for path in (shard, *files)
            if path.is_symlink() or not path.is_file() or not path.stat().st_size]


def classify(task, final, cross, minimum):
    before, after = final["baseline_profile"], final["profile"]
    shortfall = [row["baseline_profile"]["weak_length_m"] - row["profile"]["weak_length_m"] for row in (final, cross)]
    severe = [row["baseline_profile"]["outage_length_m"] - row["profile"]["outage_length_m"] for row in (final, cross)]
    impactful = (min(severe) >= minimum or
                  (min(shortfall) >= minimum and min(severe) >= -1e-8))
    if before["weak_length_m"] == 0:
        difficulty = "geometric_route_covered"
    elif after["weak_length_m"] == 0:
        difficulty = "covered_alternative"
    else:
        difficulty = "residual_weak_coverage"
    direct = math.dist(task["route_xyz"][0], task["route_xyz"][-1])
    return {
        "source_row": task["source_row"], "source_episode_id": task["source_episode_id"], "category": task["category"],
        "floor": task["floor"], "signal_changes_route_materially": impactful,
        "communication_difficulty": difficulty, "geometric_length_m": before["length_m"],
        "geodesic_to_direct_ratio": before["length_m"] / direct if direct else None,
        "oracle_length_m": after["length_m"],
        "geometric_start_dbm": before["samples_dbm"][0], "reference_stop_dbm": before["samples_dbm"][-1],
        "geometric_weak_m": before["weak_length_m"], "oracle_weak_m": after["weak_length_m"],
        "geometric_severe_m": before["outage_length_m"], "oracle_severe_m": after["outage_length_m"],
        "weak_reduction_m_at_both_steps": shortfall, "severe_reduction_m_at_both_steps": severe,
    }


def build_scene(ref, config, rules, identity, output, radio_python, decoder):
    scan, shard, (scene, _, _, _) = files_for_scene(ref)
    geometry_path = output / f"{scan}.geometry.json"
    geometry = build(shard, scene, config, count=None)
    geometry["config_sha256"] = identity["config_sha256"]
    if geometry["source_episode_count"] != len(geometry["scope_audit"]):
        raise RuntimeError(f"Unaccounted official rows in {scan}")
    if any(len(floor["candidates"]) != 1 for floor in geometry["floors"].values()):
        raise RuntimeError(f"Expected one frozen AP per floor in {scan}")
    write_json(geometry_path, geometry)
    record = {
        "scene": scan, "source_ref": ref, "geometry_sha256": sha256(geometry_path),
        "source_episodes": geometry["source_episode_count"], "tasks": [],
        "screening": dict(Counter(row["status"] for row in geometry["scope_audit"])),
        "floors": len(geometry["floors"]), "files": {geometry_path.name: sha256(geometry_path)},
    }
    if not geometry["tasks"]:
        print(f"{scan}: 0 qualifying rows out of {record['source_episodes']}", flush=True)
        return record

    def product(label, python, script, *arguments):
        result = output / f"{scan}.{label}.json"
        run(python, script, output / f"{scan}.{label}.log",
            "--geometry", geometry_path, "--output", result, *arguments)
        record["files"][result.name] = sha256(result)
        return result

    product("radio", radio_python, "run_objectnav_ap_radio.py", "--basis-decoder", decoder)
    graph = product("base_graph", sys.executable, "solve_objectnav_rssi_graph.py")
    previous = product("base_reference", radio_python, "solve_objectnav_rssi_graph.py", "--graph", graph)
    augmented = product("augmented_graph", sys.executable, "solve_objectnav_rssi_graph.py",
                        "--augment-graph", graph, "--previous-routes", previous)
    graph = product("first_navmesh_graph", sys.executable, "solve_objectnav_rssi_graph.py", "--validate-graph", augmented)
    steps = rules["route_rssi_steps_m"]
    first_reference = product("first_fine_reference", radio_python, "solve_objectnav_rssi_graph.py",
                              "--graph", graph, "--verify-optimum", "--rssi-step-m", steps[0])
    # The fine solution can use different turns than the coarse route that
    # seeded the first pass. Recheck its straight links before freezing it.
    refined = product("refined_graph", sys.executable, "solve_objectnav_rssi_graph.py",
                      "--augment-graph", graph, "--previous-routes", first_reference)
    graph = product("navmesh_graph", sys.executable, "solve_objectnav_rssi_graph.py", "--validate-graph", refined)
    final = load(product("rssi_reference", radio_python, "solve_objectnav_rssi_graph.py",
                         "--graph", graph, "--verify-optimum", "--rssi-step-m", steps[0]))
    cross = load(product("cross_reference", radio_python, "solve_objectnav_rssi_graph.py",
                         "--graph", graph, "--verify-optimum", "--rssi-step-m", steps[1]))
    for task in geometry["tasks"]:
        key = str(task["source_row"])
        ap, = geometry["floors"][task["floor"]]["candidates"]
        metrics = classify(task, final["tasks"][key][ap["id"]], cross["tasks"][key][ap["id"]],
                           rules["material_improvement_m"])
        record["tasks"].append(metrics)
    print(f"{scan}: {len(record['tasks'])}/{record['source_episodes']} qualifying rows, {record['floors']} floors", flush=True)
    return record


def verify_small(output, record, rules, radio_python):
    scan = record["scene"]
    if not record["tasks"]:
        raise RuntimeError("The small batch has no qualified tasks")
    geometry = output / f"{scan}.geometry.json"
    nav_path = output / "probe_navigation.json"
    joint_path = output / "probe_scores.json"
    run(sys.executable, "score_objectnav_trace.py", output / "probe_navigation.log",
        "--geometry", geometry, "--output", nav_path, "--probe")
    run(radio_python, "score_objectnav_trace.py", output / "probe_scores.log",
        "--geometry", geometry, "--output", joint_path, "--navigation", nav_path,
        "--rssi-step-m", rules["route_rssi_steps_m"][0])
    success, early = load(joint_path)
    for result, expected in ((success, 1), (early, 0)):
        if result["navigation"]["success"] != expected or not result["communication"]["available"]:
            raise ValueError("Habitat and RSSI integration probe failed")
        if not math.isclose(result["navigation"]["length_m"], result["communication"]["length_m"], abs_tol=.001):
            raise ValueError("Navigation and RSSI received unequal trajectory lengths")
    if success["navigation"]["spl"] <= 0 or early["navigation"]["spl"] != 0:
        raise ValueError("The successful and early-stop probes have incorrect SPL")
    clear = route_metrics([-60.0, -60.0], [1.0])
    missing = route_metrics([-60.0, None], [1.0])
    if clear["signal_deficit_db_m"] != 0 or clear["weak_mean_dbm"] is not None or missing["available"]:
        raise ValueError("Missing or full-coverage signal handling failed")
    return {"probe_scores_sha256": sha256(joint_path), "event_checks": {"complete": 1, "early_stop": 1}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--radio-python", type=Path, default=RENDER_ENV)
    parser.add_argument("--basis-decoder", type=Path, default=DECODER)
    parser.add_argument("--workers", type=int, default=1)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--small", action="store_true")
    mode.add_argument("--full-after", type=Path, metavar="PASSED_SMALL_MANIFEST")
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT / "runtime" not in output.parents or output.exists() or args.workers < 1:
        parser.error("Provide a new run directory inside runtime and at least one worker")
    rules = load(CONFIG)
    config_path = ROOT / rules["radio_config"]
    config = load(config_path)
    for name in ("selection_seed", "episode_pool_per_category", "scene_count", "task_count"):
        del config[name]
    config.update(scope=rules["scope"], ap_candidates_per_floor=1)
    refs = sorted(load(EPISODES)["splits"]["val"]["scene_refs"])
    if len(refs) != len(set(refs)) or any(Path(ref).parts[:2] != ("hm3d_v0.2", "val") for ref in refs):
        raise ValueError("Invalid or duplicate scene paths in the official val manifest")
    if args.small:
        refs = [ref for ref in refs if files_for_scene(ref)[0] == rules["small_scene"]]
        if len(refs) != 1:
            raise ValueError("The predeclared small scene is absent or ambiguous")
    identity = {"execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip(),
                "config_sha256": hashlib.sha256(config_path.read_bytes() + CONFIG.read_bytes()).hexdigest(),
                "workflow_sha256": hashlib.sha256("".join(sha256(ROOT / file) for file in OPERATIONAL_FILES).encode()).hexdigest(),
                "source_receipt_sha256": sha256(EPISODES)}
    if args.full_after:
        small = load(args.full_after)
        if small["scope"] != "small" or not small["validation"]["passed"] or any(
            small["identity"][name] != identity[name] for name in ("config_sha256", "workflow_sha256", "source_receipt_sha256")
        ):
            raise ValueError("Full construction needs a successful small batch with the same rules and source")
    missing = {ref: files for ref in refs if (files := unavailable(ref))}
    if missing:
        parser.exit(2, f"Missing {len(missing)} required official scene assets. First missing set: {next(iter(missing.values()))}\n")
    if not (args.radio_python.is_file() and args.basis_decoder.is_file()):
        parser.error("The existing CPU ray environment and Basis decoder are required")
    output.mkdir(parents=True)
    write_json(output / "inputs.json", {"identity": identity, "config": config, "rules": rules, "scene_refs": refs})
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        scenes = list(pool.map(lambda ref: build_scene(ref, config, rules, identity, output,
                                                      args.radio_python, args.basis_decoder), refs))
    checks = verify_small(output, scenes[0], rules, args.radio_python) if args.small else {
        "small_manifest_sha256": sha256(args.full_after)
    }
    population = [(scene["scene"], task["source_row"]) for scene in scenes for task in scene["tasks"]]
    requested = min(rules["review_count"], len(population)) if args.small else rules["review_count"]
    review = random.Random(rules["review_seed"]).sample(population, requested)
    source_rows = sum(row["source_episodes"] for row in scenes)
    if not args.small and source_rows != 1000:
        raise RuntimeError(f"Full official val source must account for 1000 rows, got {source_rows}")
    write_json(output / "manifest.json", {
        "format": "wifinav-objectnav-benchmark-v1",
        "scope": "small" if args.small else "full", "identity": identity, "config": config, "rules": rules,
        "validation": {"passed": True, **checks}, "source_episodes": source_rows, "qualified_episodes": len(population),
        "scenes": scenes, "review_sample": [{"scene": scan, "source_row": row} for scan, row in review],
    })
    print(f"Validated {len(population)}/{source_rows} rows and selected {len(review)} review tasks", flush=True)


if __name__ == "__main__":
    main()
