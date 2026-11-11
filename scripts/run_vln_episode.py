"""One frozen-model development rollout with explicit privileged-info isolation.

This is our provisional pixel-subgoal adapter, not an AgenticNav reproduction or
an accepted benchmark baseline. It uses a local navmesh geometry controller;
weighted signal-aware planning is a separate follow-up.
"""
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import habitat
import numpy as np
from PIL import Image, ImageDraw
from connectivity_vln.navigation.task import PROJECT, prepare, pose, load_json
from connectivity_vln.navigation.pixel_policy import (
    PixelPolicy,
    floor_candidates,
    heading_error,
    local_navmesh_waypoint,
    pixel_subgoal,
)
from connectivity_vln.evaluation.metrics import evaluate
from connectivity_vln.navigation.interface import ProgressGuard
from connectivity_vln.navigation.weighted_planner import NavmeshRiskPlanner
from connectivity_vln.signal_simulation.route_a import SignalField, communication_metrics

parser = argparse.ArgumentParser()
parser.add_argument("--config", type=Path)
parser.add_argument("--episode-id", type=str)
parser.add_argument("--output-dir", type=Path)
parser.add_argument("--interface-version", choices=["v0", "v1"], default="v0")
parser.add_argument("--stop-review", choices=["auto", "on", "off"], default="auto")
parser.add_argument("--planner", choices=["navmesh", "grid"], default="navmesh")
parser.add_argument("--risk-weight", type=float, default=0.0)
parser.add_argument("--wireless-instance", type=Path)
args = parser.parse_args()
if not 0 <= args.risk_weight < float('inf') or (args.planner != "grid" and args.risk_weight):
    parser.error("A finite nonnegative risk weight requires the shared grid planner")
config, dataset, episode, metadata = prepare(args.config, args.episode_id)
settings = metadata["settings"]
settings["interface_version"] = args.interface_version
settings["stop_review_enabled"] = (args.interface_version == "v1" if args.stop_review == "auto"
                                   else args.stop_review == "on")
model_config = load_json(PROJECT / "configs/model/qwen35b.json")
wireless_config = load_json(PROJECT / "configs/wireless/r2r_conn_v0.json")
wireless_instance = load_json(args.wireless_instance) if args.wireless_instance else None
if wireless_instance:
    if wireless_instance["scene_id"] != episode["scene_id"] or str(wireless_instance["episode_id"]) != str(episode["episode_id"]):
        raise ValueError("Wireless instance does not match selected task")
    wireless_config = wireless_instance["wireless_config"]
run = args.output_dir or PROJECT / "runtime/runs" / ("nosignal_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
run = run.resolve()
if not run.is_relative_to((PROJECT / "runtime").resolve()):
    raise ValueError("Rollout output must remain under project runtime/")
run.mkdir(parents=True, exist_ok=False)
(run / "frames").mkdir()
metadata.update({"mode": "StaticMap" if args.risk_weight else "NoSignal", "implementation_status": "provisional_depth_candidate_subgoal_navmesh_controller",
                 "model": model_config, "wireless": wireless_config,
                 "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip(),
                 "policy_privileged_inputs": [], "evaluation_uses_gt": True,
                 "policy_uses_wireless": False,
                 "controller_uses_wireless_truth": bool(args.risk_weight),
                 "planner": args.planner, "risk_weight": args.risk_weight,
                 "wireless_instance": wireless_instance,
                 "not_official_benchmark_result": True})
(run / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
policy = PixelPolicy(model_config, settings)
trajectory = []
decisions = []
sim_time = 0.0
started = time.perf_counter()
print("RUN_DIR", run, flush=True)


def save_state(env, obs, action, decision=None, latency=0.0):
    global sim_time
    index = len(trajectory)
    if action == "move_forward":
        sim_time += settings["forward_step_m"] / settings["motion_forward_speed_mps"]
    elif action in {"turn_left", "turn_right"}:
        sim_time += settings["turn_degrees"] / settings["motion_turn_speed_degrees_per_second"]
    filename = f"{index:04d}"
    Image.fromarray(obs["rgb"][..., :3]).save(run / "frames" / (filename + ".png"))
    np.save(run / "frames" / (filename + "_depth.npy"), obs["depth"])
    item = {"step": index, "decision": decision, "action": action, "pose": pose(env),
            "rgb": "frames/" + filename + ".png", "depth": "frames/" + filename + "_depth.npy",
            "motion_sim_time_seconds": sim_time, "wall_elapsed_seconds": time.perf_counter() - started,
            "action_wall_seconds": latency, "collision": bool(env.sim.previous_step_collided) if action != "reset" else False,
            "wireless": signal.query(env.sim.get_agent_state().position, index),
            "evaluation_only_metrics": dict(env.get_metrics())}
    trajectory.append(item)
    with (run / "trajectory.jsonl").open("a") as stream:
        stream.write(json.dumps(item) + "\n")
    return item


def act(env, action, decision):
    stamp = time.perf_counter()
    obs = env.step(action)
    return obs, save_state(env, obs, action, decision, time.perf_counter() - stamp)


exit_reason = "uninitialized"
error = None
with habitat.Env(config=config, dataset=dataset) as env:
    obs = env.reset()
    signal = SignalField(
        env.sim.pathfinder,
        episode["scene_id"],
        wireless_instance["ap_floor_position"] if wireless_instance else episode["start_position"],
        wireless_config,
    )
    save_state(env, obs, "reset")
    progress_guard = ProgressGuard(trajectory[0]["pose"], settings["turn_degrees"])
    no_progress = 0
    try:
        grid_planner = (NavmeshRiskPlanner(env.sim.pathfinder, float(episode["start_position"][1]))
                        if args.planner == "grid" else None)
        for index in range(settings["max_decisions"]):
            directory = run / f"decision_{index:03d}"
            directory.mkdir()
            frame = directory / "policy_view.png"
            candidates = floor_candidates(env, obs["depth"], settings, obs["rgb"], frame)
            (directory / "candidates.json").write_text(json.dumps(candidates, indent=2)+"\n")
            # Only instruction, RGB history, model memory and controller feedback.
            choice, request_record = policy.decide(
                episode["instruction"]["instruction_text"], frame, candidates, directory,
                raw_frame=run / trajectory[-1]["rgb"],
            )
            feedback = {"tool": choice["tool"], "executed_actions": [], "collision": False}
            record = {"index": index, "choice": choice, "request": request_record, "feedback": feedback}
            decisions.append(record)
            decision_start = np.asarray(pose(env)["position"])
            if choice["tool"] == "stop":
                obs, step = act(env, "stop", index)
                feedback["executed_actions"].append("stop")
                exit_reason = "model_stop"
            elif choice["tool"] == "look":
                action = "turn_left" if choice["degrees"] > 0 else "turn_right"
                for _ in range(round(abs(choice["degrees"]) / settings["turn_degrees"])):
                    if env.episode_over:
                        break
                    obs, step = act(env, action, index)
                    feedback["executed_actions"].append(action)
            else:
                try:
                    candidate = next(c for c in candidates if c["id"] == choice["candidate_id"])
                    target, projection = pixel_subgoal(env, obs["depth"], candidate, settings)
                    record.update({"subgoal_world": target, "depth_projection": projection})
                    forward_count = 0
                    # Bounded geometry controller. The navmesh query is local to
                    # the VLM-selected target and never receives the task goal.
                    planner_trace = []
                    record["local_planner"] = planner_trace
                    for _ in range(settings["max_local_controller_actions"]):
                        if env.episode_over:
                            break
                        delta = np.array(target) - np.array(pose(env)["position"])
                        delta[1] = 0
                        if float(np.linalg.norm(delta)) < settings["forward_step_m"] * 0.6:
                            break
                        if grid_planner is None:
                            next_point, planner_state = local_navmesh_waypoint(env, target)
                        else:
                            position = env.sim.get_agent_state().position
                            route, planner_state = grid_planner.plan(
                                position, target, weight=args.risk_weight,
                                field=signal if args.risk_weight else None,
                            )
                            next_point = next((p for p in route[1:]
                                               if np.linalg.norm((np.asarray(p)-position)[[0, 2]]) > 0.12),
                                              route[-1])
                        planner_trace.append(planner_state)
                        angle = heading_error(env, next_point)
                        if abs(angle) > settings["turn_degrees"] / 2:
                            action = "turn_left" if angle > 0 else "turn_right"
                        else:
                            if forward_count >= settings["max_forward_actions_per_subgoal"]:
                                break
                            action = "move_forward"
                            forward_count += 1
                        obs, step = act(env, action, index)
                        feedback["executed_actions"].append(action)
                        if step["collision"]:
                            feedback["collision"] = True
                            break
                except ValueError as failure:
                    feedback["rejected_subgoal"] = str(failure)
            feedback["displacement_m"] = float(
                np.linalg.norm((np.asarray(pose(env)["position"]) - decision_start)[[0, 2]])
            )
            feedback["made_progress"] = feedback["displacement_m"] >= 0.05
            if args.interface_version == "v1":
                feedback["progress_kind"] = (
                    "stop" if choice["tool"] == "stop"
                    else progress_guard.update(pose(env), feedback)
                )
                if feedback["progress_kind"] == "new_view":
                    feedback["made_progress"] = True
                no_progress = progress_guard.stalled
                feedback["consecutive_stalled"] = no_progress
            else:
                no_progress = no_progress + 1 if not feedback["made_progress"] else 0
            # Keep diagnostic counters out of the VLM's normal feedback format.
            policy.observe_feedback({
                key: value for key, value in feedback.items()
                if key not in ("progress_kind", "consecutive_stalled")
            })
            (directory / "decision.json").write_text(json.dumps(record, indent=2) + "\n")
            with (run / "decisions.jsonl").open("a") as stream:
                stream.write(json.dumps(record) + "\n")
            print(json.dumps({"decision": index, "tool": choice, "feedback": feedback,
                              "primitive_steps": len(trajectory)-1}), flush=True)
            if args.interface_version == "v1" and env.episode_over:
                exit_reason = "model_stop" if choice["tool"] == "stop" else "primitive_step_limit"
                break
            if no_progress >= settings["max_consecutive_no_progress"]:
                exit_reason = "consecutive_no_progress_limit"
                break
            if env.episode_over:
                exit_reason = "model_stop" if choice["tool"] == "stop" else "primitive_step_limit"
                break
        else:
            exit_reason = "decision_limit"
    except Exception as failure:
        exit_reason = "runtime_error"
        error = repr(failure)
        (run / "error.txt").write_text(traceback.format_exc())
    # Privileged GT is loaded only now, for offline diagnostics.
    paths = load_json(PROJECT / "configs/data/server_paths.json")
    gt_file = PROJECT / paths["task_dataset"] / settings["split"] / (settings["split"] + "_gt.json.gz")
    with gzip.open(gt_file, "rt") as stream:
        gt = json.load(stream)[str(episode["episode_id"])]["locations"]
    metrics = evaluate(env, trajectory, gt, settings)
    metrics["communication"] = communication_metrics(trajectory, wireless_config)
    # Offline diagnostic plot. Neither GT nor this plot is fed to the policy.
    points = np.array([x["pose"]["position"] for x in trajectory])[:, [0,2]]
    ref = np.array(gt)[:, [0,2]]
    low = np.minimum(points.min(axis=0), ref.min(axis=0)) - 1
    high = np.maximum(points.max(axis=0), ref.max(axis=0)) + 1
    scale = 650 / max(high-low)
    def xy(v):
        return tuple(((v-low)*scale + 25).astype(int))
    image = Image.new("RGB", (720, 760), "white")
    draw = ImageDraw.Draw(image)
    draw.line([xy(v) for v in ref], fill="gray", width=4)
    if len(points)>1:
        draw.line([xy(v) for v in points], fill="blue", width=3)
    for v, color in ((points[0], "green"), (points[-1], "blue"), (ref[-1], "red")):
        x,y = xy(v); draw.ellipse((x-5,y-5,x+5,y+5), fill=color)
    draw.text((15,720), "Offline only: GT gray; executed blue; start green; goal red. X/Z plane.", fill="black")
    image.save(run / "trajectory_offline.png")
summary = {"run_dir": str(run), "episode_id": str(episode["episode_id"]), "scene_id": episode["scene_id"],
           "interface_version": args.interface_version,
           "exit_reason": exit_reason, "error": error, "metrics": metrics,
           "decisions": len(decisions), "motion_sim_time_seconds": sim_time,
           "wall_seconds": time.perf_counter()-started,
           "model_request_attempts": sum(len(list(d.rglob('request_*.json'))) for d in run.glob('decision_*')),
           "status": "development_rollout_only_not_paper_result"}
(run / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2), flush=True)
if error:
    raise SystemExit(1)
