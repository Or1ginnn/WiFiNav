#!/usr/bin/env python3
"""Run or verify the frozen single-floor ObjectNav benchmark on Habitat."""
import argparse
from base64 import b64decode
from collections import Counter
from hashlib import sha256
from importlib import import_module
import json
import math
import os
from pathlib import Path
import subprocess

import habitat_sim
import numpy as np
import quaternion

from objectnav_floor_protocol import ACTIONS, MAX_ACTIONS, PROTOCOL, ROOT, RSSI_STEP_M, load_scene, prepare
from objectnav_sensor_baseline import Observation
from score_objectnav_trace import parse_max_continuous_severe_m, summarize_communication_success

DEFAULT_AGENT = "objectnav_sensor_baseline:SensorBaseline"
RADIO_PYTHON = ROOT / "runtime/envs/sionna_rt_2_2_0_py311/bin/python"
LLVM = Path("/opt/anaconda3/pkgs/libllvm19-19.1.2-ha7bfdaf_0/lib/libLLVM-19.so")
TRACKS = ("no_signal", "observed_rssi")
# Frozen vocabulary of HM3D v2 val semantic classes mapped to ObjectNav
# categories. This is a class mapping, independent of scene and object ID.
SENSOR_LABELS = {
    "bed": {"bed", "bed sheet", "bedframe", "dog bed", "headboard"},
    "chair": {"armchair", "bar chair", "bean bag chair", "chair", "computer chair", "desk chair",
              "dining chair", "folded chair", "folding chair", "highchair", "lounge chair", "office chair",
              "patio chair", "recliner", "rocking chair", "sofa chair"},
    "plant": {"decorative plant", "dried flowers", "flower", "flower stand", "flower vase", "flowerpot", "plant"},
    "sofa": {"circular sofa", "couch", "l-shaped sofa", "sofa", "sofa set"},
    "toilet": {"toilet", "toilet seat"},
    "tv_monitor": {"bulletin board", "display", "monitor", "tv", "tv_monitor", "tv/monitor"},
}


def write(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def load_radio(manifest_path, scene, geometry):
    path = manifest_path.with_name(f'{scene["scene"]}.radio.json')
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != scene["files"][path.name]:
        raise ValueError("Changed radio data")
    floors = {}
    for key, data in json.loads(raw)["radio"]["floors"].items():
        ap, = data["candidates"].values()
        grid = np.frombuffer(b64decode(ap["grid_int8"]), dtype=np.int8).reshape(data["height"], data["width"])
        origin = geometry["floors"][key]["map"]["first_center_xz"]
        floors[key] = (grid, origin, data["grid_step_m"])
    return floors


def current_rssi(mapping, pose):
    grid, (x0, z0), step = mapping
    x, z = round((pose[0] - x0) / step), round((pose[2] - z0) / step)
    if 0 <= z < grid.shape[0] and 0 <= x < grid.shape[1] and grid[z, x] != -128:
        return int(grid[z, x])
    return None


def simulator(geometry, *, render, gpu_device, rgbd=False):
    options = habitat_sim.SimulatorConfiguration()
    options.scene_id = str(ROOT / "data/scene_datasets" / geometry["source_ref"])
    options.scene_dataset_config_file = str(ROOT / "data/scene_datasets/hm3d_v0.2/hm3d_annotated_basis.scene_dataset_config.json")
    options.create_renderer = render
    options.load_semantic_mesh = render and not rgbd
    # HM3D .semantic.glb carries IDs in vertex colors. The texture mode
    # defaults to True in Habitat 0.3.0 and produces an all-zero sensor here.
    options.use_semantic_textures = False
    options.gpu_device_id = gpu_device
    agent = habitat_sim.agent.AgentConfiguration()
    agent.action_space = {name: habitat_sim.agent.ActionSpec(name, habitat_sim.agent.ActuationSpec(amount))
                          for name, amount in ACTIONS.items()}
    if render:
        image_sensor = ("rgb", habitat_sim.SensorType.COLOR) if rgbd else ("semantic", habitat_sim.SensorType.SEMANTIC)
        for name, kind in (("depth", habitat_sim.SensorType.DEPTH), image_sensor):
            spec = habitat_sim.CameraSensorSpec()
            spec.uuid, spec.sensor_type = name, kind
            spec.resolution, spec.hfov, spec.position = [480, 640] if rgbd else [96, 128], 90., [0., .88, 0.]
            agent.sensor_specifications.append(spec)
    return habitat_sim.Simulator(habitat_sim.Configuration(options, [agent]))


def reset(sim, episode):
    state = habitat_sim.AgentState()
    state.position = np.asarray(episode["start_position"], dtype=np.float32)
    x, y, z, w = episode["start_rotation"]
    state.rotation = quaternion.quaternion(w, x, y, z)
    sim.get_agent(0).set_state(state)


def execute(sim, episode, rules, task, policy=None, target_ids=(), mapping=None, actions=None, *,
            trace_target=False, observe_elevation=False):
    reset(sim, episode)
    start = sim.get_agent(0).get_state()
    if policy is not None:
        policy.reset()
    trace = {"source_row": task["source_row"], "positions": [start.position.tolist()], "actions": [], "collisions": 0,
             "observed_rssi_samples": 0, "observed_rssi_missing": 0, "labeled_frames": 0, "target_visible_frames": 0,
             "action_budget": MAX_ACTIONS}
    commands = iter(actions) if actions is not None else None
    state = start
    frames = sim.get_sensor_observations() if policy is not None else None
    if trace_target:
        trace["target_observations"] = []
    a = float(quaternion.as_rotation_vector(start.rotation)[1])
    for _ in range(MAX_ACTIONS):
        if commands is not None:
            action = next(commands, None)
            if action is None:
                break
        else:
            theta = float(quaternion.as_rotation_vector(state.rotation * start.rotation.inverse())[1])
            delta = state.position - start.position
            # Transform position into the frame of the official start heading.
            x, z = math.cos(a) * delta[0] - math.sin(a) * delta[2], math.sin(a) * delta[0] + math.cos(a) * delta[2]
            rssi = current_rssi(mapping, state.position) if mapping is not None else None
            if mapping is not None:
                trace["observed_rssi_samples" if rssi is not None else "observed_rssi_missing"] += 1
            semantic = frames.get("semantic")
            target_mask = (np.isin(semantic, target_ids) if semantic is not None
                           else np.zeros(frames["depth"].shape, dtype=bool))
            trace["labeled_frames"] += int(semantic is not None and np.any(semantic > 0))
            trace["target_visible_frames"] += int(np.any(target_mask))
            if trace_target and semantic is not None:
                # Use the same positive-depth pixels as the engineering policy.
                depth = frames["depth"]
                valid = depth[target_mask & np.isfinite(depth) & (depth > 0)]
                trace["target_observations"].append({
                    "pixels": len(valid),
                    "depth_p25_m": float(np.quantile(valid, .25)) if len(valid) else None,
                })
            elevation = float(delta[1]) if observe_elevation else 0.
            action = policy.act(Observation(task["category"], frames["depth"], target_mask,
                                            float(x), float(z), theta, rssi, relative_height_m=elevation,
                                            rgb=frames.get("rgb")))
            if trace_target and semantic is None:
                # Visual policies report their own detections rather than
                # observing the simulator's labels.
                trace["target_observations"].append(policy.target_observation)
                trace["target_visible_frames"] += int(policy.target_observation["pixels"] > 0)
        trace["actions"].append(action)
        if action == "stop":
            trace["positions"].append(state.position.tolist())
            break
        if action not in ACTIONS:
            raise ValueError(f"Agent returned unsupported action {action!r}")
        response = sim.step(action)
        frames = response
        trace["collisions"] += int(bool(response.get("collided", False)))
        state = sim.get_agent(0).get_state()
        trace["positions"].append(state.position.tolist())
        if not rules.executed_pose_on_floor(state.position):
            break
    return trace


def summarize(rows):
    count = len(rows)
    success = sum(r["navigation"]["success"] for r in rows)
    valid = [r["communication"] for r in rows if r["communication"]["available"]]
    summary = {
        "episodes": count, "successes": success, "sr": success / count,
        "spl_lower_bound": sum(r["navigation"]["spl_lower_bound"] for r in rows) / count,
        "spl_upper_bound": sum(r["navigation"]["spl_upper_bound"] for r in rows) / count,
        "terminations": dict(Counter(r["navigation"]["termination"] for r in rows)),
        "radio_available": len(valid),
        "mean_path_m": sum(r["navigation"]["length_m"] for r in rows) / count,
        "mean_weak_m": sum(r["weak_length_m"] for r in valid) / len(valid) if valid else None,
        "mean_severe_m": sum(r["outage_length_m"] for r in valid) / len(valid) if valid else None,
        "mean_longest_severe_m": sum(r["longest_outage_m"] for r in valid) / len(valid) if valid else None,
        "mean_deficit_db_m": sum(r["signal_deficit_db_m"] for r in valid) / len(valid) if valid else None,
        "actions": sum(len(r["trace"]["actions"]) for r in rows),
        "collisions": sum(r["trace"]["collisions"] for r in rows),
        "online_rssi_samples": sum(r["trace"]["observed_rssi_samples"] for r in rows),
        "online_rssi_missing": sum(r["trace"]["observed_rssi_missing"] for r in rows),
        "episodes_with_target_seen": sum(r["trace"]["target_visible_frames"] > 0 for r in rows),
    }
    if "communication_success" in rows[0]:
        summary["communication_success"] = summarize_communication_success(rows)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--population", choices=("review20", "all"), default="review20")
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="module:factory with reset() and act(observation)")
    parser.add_argument("--radio-python", type=Path, default=RADIO_PYTHON)
    parser.add_argument("--max-continuous-severe-m", type=parse_max_continuous_severe_m,
                        help="Maximum continuous severe weak-signal distance for communication success")
    parser.add_argument("--egl-device", type=int, default=0, help="GPU used only for Habitat sensor rendering")
    parser.add_argument("--audit-references", action="store_true")
    parser.add_argument("--cross-floor-probe", type=Path)
    args = parser.parse_args()
    if ROOT / "runtime" not in args.output.resolve().parents or args.output.exists():
        parser.error("Output must be a new directory under runtime")
    if args.audit_references and args.cross_floor_probe:
        parser.error("Reference audit and regression replay are separate runs")
    limit = args.max_continuous_severe_m
    if limit is not None and (args.audit_references or args.cross_floor_probe):
        parser.error("Communication success requires RSSI scoring of closed-loop runs")
    manifest_raw = args.manifest.read_bytes()
    manifest = json.loads(manifest_raw)
    server_audit = json.loads(args.manifest.with_name("audit.json").read_bytes())
    manifest_hash = sha256(manifest_raw).hexdigest()
    if (manifest["scope"] != "full" or not server_audit["passed"]
            or server_audit["manifest_sha256"] != manifest_hash):
        parser.error("Expected an independently audited full manifest")
    selected = {(r["scene"], r["source_row"]) for r in manifest["review_sample"]}
    probe = json.loads(args.cross_floor_probe.read_bytes())["probe"] if args.cross_floor_probe else None
    if args.cross_floor_probe and not probe:
        parser.error("The regression needs a previously executed cross-floor probe")
    if probe:
        selected = {("GLAQ4DNUx5U", 0), (probe["scene"], probe["source_row"])}
    all_tasks = args.audit_references or (not probe and args.population == "all")
    if not args.audit_references and not probe and not args.radio_python.is_file():
        parser.error("Existing CPU radio environment is needed")
    module, factory = args.agent.split(":", 1)
    agent_factory = getattr(import_module(module), factory) if not args.audit_references and not probe else None
    args.output.mkdir(parents=True)
    metadata = {
        "protocol": PROTOCOL, "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "manifest_sha256": manifest_hash, "source_identity": manifest["identity"],
        "agent": args.agent if agent_factory else None, "mode": "references" if args.audit_references else "regression" if probe else args.population,
        "probe_sha256": sha256(args.cross_floor_probe.read_bytes()).hexdigest() if probe else None,
        "action_budget": MAX_ACTIONS, "rssi_step_m": RSSI_STEP_M, "habitat_sim_version": habitat_sim.__version__,
        "egl_device": args.egl_device if agent_factory else None,
        "tracks": list(TRACKS) if agent_factory else [],
    }
    if limit is not None:
        metadata["communication_success"] = {"max_continuous_severe_m": limit,
                                              "severe_threshold_dbm": manifest["config"]["outage_threshold_dbm"]}
    write(args.output / "metadata.json", metadata)
    result = []
    for scene in manifest["scenes"]:
        name = scene["scene"]
        tasks = {t["source_row"] for t in scene["tasks"] if all_tasks or (name, t["source_row"]) in selected}
        if not tasks:
            continue
        geometry, source, path = load_scene(args.manifest, scene, manifest["config"])
        if args.audit_references:
            finder = habitat_sim.PathFinder()
            asset = ROOT / "data/scene_datasets" / scene["source_ref"]
            if not finder.load_nav_mesh(str(asset.with_suffix(".navmesh"))):
                raise ValueError(f"No navigable mesh for {name}")
            for task in geometry["tasks"]:
                _, _, views, (lower, upper) = prepare(finder, geometry, source, task)
                result.append({"scene": name, "source_row": task["source_row"], "same_floor_views": len(views),
                               "reference_lower_m": lower, "reference_upper_m": upper})
            print(f"{name}: verified {len(tasks)} references", flush=True)
            continue
        rows = []
        floors = load_radio(args.manifest, scene, geometry) if not probe else None
        with simulator(geometry, render=not probe, gpu_device=args.egl_device) as sim:
            objects = sim.semantic_scene.objects if not probe else []
            for task in geometry["tasks"]:
                row = task["source_row"]
                if row not in tasks:
                    continue
                episode, rule, views, bounds = prepare(sim.pathfinder, geometry, source, task)
                if probe:
                    a = probe["trace"]["actions"]
                    if name != probe["scene"]:
                        reset(sim, episode)
                        follower = sim.make_greedy_follower(goal_radius=rule.radius, forward_key="move_forward",
                                                           left_key="turn_left", right_key="turn_right")
                        a = [x for x in follower.find_path(task["route_xyz"][-1]) if x is not None] + ["stop"]
                    variants = (("cross_floor", a),) if name == probe["scene"] else (("same_floor", a), ("early_stop", ["stop"]))
                    for track, actions in variants:
                        trace = execute(sim, episode, rule, task, actions=actions)
                        rows.append({"scene": name, "track": track, "trace": trace,
                                     "navigation": rule.score(episode["start_position"], views, bounds, trace)})
                    continue
                # Only convert currently visible semantic pixels into the
                # category mask. No object positions or IDs go to the agent.
                names = SENSOR_LABELS[task["category"]]
                ids = [obj.semantic_id for obj in objects if obj and obj.category
                       and obj.category.name().strip().lower() in names]
                if not ids:
                    raise ValueError(f"No semantic sensor target label for {name}:{row}")
                for track in TRACKS:
                    mapping = floors[task["floor"]] if track == "observed_rssi" else None
                    trace = execute(sim, episode, rule, task, agent_factory(), ids, mapping)
                    navigation = rule.score(episode["start_position"], views, bounds, trace)
                    rows.append({"scene": name, "track": track, "navigation": navigation, "trace": trace})
        write(args.output / f"{name}.navigation.json", rows)
        if probe:
            result.extend(rows)
        else:
            if not any(r["trace"]["labeled_frames"] for r in rows):
                raise ValueError(f"All semantic frames are empty in {name}")
            inputs = [{**r, "trace": {**r["trace"], "positions": r["trace"]["positions"][:r["navigation"]["scored_actions"] + 1],
                                    "actions": r["trace"]["actions"][:r["navigation"]["scored_actions"]]}} for r in rows]
            prefix_file = args.output / f"{name}.prefixes.json"
            radio_output = args.output / f"{name}.scored.json"
            write(prefix_file, inputs)
            env = {**os.environ, "CUDA_VISIBLE_DEVICES": ""}
            if LLVM.is_file():
                env.setdefault("DRJIT_LIBLLVM_PATH", str(LLVM))
            command = [str(args.radio_python), str(ROOT / "scripts/score_objectnav_trace.py"),
                       "--geometry", str(path), "--navigation", str(prefix_file), "--output", str(radio_output),
                       "--rssi-step-m", str(RSSI_STEP_M)]
            if limit is not None:
                command.extend(("--max-continuous-severe-m", str(limit)))
            subprocess.run(command, check=True, cwd=ROOT, env=env)
            scored = json.loads(radio_output.read_bytes())
            if (len(scored) != len(rows) or any((r["track"], r["trace"]["source_row"]) !=
                (s["track"], s["trace"]["source_row"]) or s["communication"]["available"] and
                abs(s["communication"]["length_m"] - r["navigation"]["length_m"]) > .002
                for r, s in zip(rows, scored))):
                raise ValueError("Communication results do not match the navigation prefixes")
            for row, replay in zip(rows, scored):
                row["communication"] = replay["communication"]
                if limit is not None:
                    row["communication_success"] = replay["communication_success"]
            result.extend(rows)
        print(f"{name}: finished {len(rows)} trace executions", flush=True)

    if args.audit_references:
        if len(result) != manifest["qualified_episodes"]:
            raise ValueError("Reference audit did not cover the full benchmark")
        bounded = [r for r in result if r["reference_lower_m"] < r["reference_upper_m"] - 1e-5]
        summary = {"episodes": len(result), "exact": len(result) - len(bounded), "bounded": bounded}
    elif probe:
        summary = {r["track"]: r["navigation"] for r in result}
        if (set(summary) != {"same_floor", "early_stop", "cross_floor"} or summary["same_floor"]["success"] != 1
                or summary["early_stop"]["success"] != 0 or summary["cross_floor"]["termination"] != "floor_violation"):
            raise ValueError("Expected legal success, premature STOP failure and cross-floor rejection")
    else:
        by_track = {track: {(r["scene"], r["trace"]["source_row"]): r for r in result if r["track"] == track}
                    for track in TRACKS}
        first, second = (by_track[track] for track in TRACKS)
        expected = manifest["qualified_episodes"] if all_tasks else len(selected)
        if (len(result) != expected * 2 or len(first) != expected or first.keys() != second.keys()
                or (not all_tasks and first.keys() != selected)):
            raise ValueError("Incomplete or unpaired benchmark results")
        common = [k for k in first if all(by_track[t][k]["navigation"]["success"] for t in TRACKS)]
        summary = {
            "all": {t: summarize(list(by_track[t].values())) for t in TRACKS},
            "common_success": {t: summarize([by_track[t][k] for k in common]) if common else None for t in TRACKS},
            "common_success_pairs": len(common),
            "different_action_sequences": sum(first[k]["trace"]["actions"] != second[k]["trace"]["actions"] for k in first),
        }
    write(args.output / "results.json", result)
    write(args.output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
