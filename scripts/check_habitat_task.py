"""Real-scene/action acceptance run; this is not a language navigation result."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import habitat
import habitat_sim
import numpy as np
from PIL import Image
from connectivity_vln.navigation.task import PROJECT, prepare, pose

parser = argparse.ArgumentParser()
parser.add_argument("--config", type=Path)
args = parser.parse_args()
config, dataset, episode, metadata = prepare(args.config)
run = PROJECT / "runtime/runs" / ("habitat_acceptance_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
run.mkdir(parents=True)
(run / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
(run / "code_commit.txt").write_text(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True))

def gpu():
    return subprocess.check_output(["nvidia-smi", "--query-gpu=index,memory.used,memory.free", "--format=csv,noheader"], text=True)

before = gpu()
trace = []
with habitat.Env(config=config, dataset=dataset) as env:
    obs = env.reset()
    if set(obs) != {"rgb", "depth", "instruction"}:
        raise RuntimeError(f"Unexpected observations: {set(obs)}")
    if not env.sim.pathfinder.is_loaded:
        raise RuntimeError("Dataset navmesh not loaded")
    for index, action in enumerate([None, "turn_left", "turn_right", "move_forward", "stop"]):
        previous = pose(env)
        if action:
            obs = env.step(action)
        current = pose(env)
        Image.fromarray(obs["rgb"][..., :3]).save(run / f"{index:03d}_rgb.png")
        np.save(run / f"{index:03d}_depth.npy", obs["depth"])
        trace.append({"action": action or "reset", "pose_before": previous, "pose_after": current,
                      "rgb_shape": list(obs["rgb"].shape), "depth_shape": list(obs["depth"].shape),
                      "depth_min_m": float(np.min(obs["depth"])), "depth_max_m": float(np.max(obs["depth"])),
                      "depth_finite": bool(np.isfinite(obs["depth"]).all()),
                      "collision": bool(env.sim.previous_step_collided), "metrics": env.get_metrics(),
                      "episode_over": env.episode_over})
    summary = {"run_dir": str(run), "habitat_sim_version": habitat_sim.__version__,
               "navmesh_loaded": True, "start_navigable": bool(env.sim.pathfinder.is_navigable(episode["start_position"])),
               "start_position_error_m": float(np.linalg.norm(np.array(trace[0]["pose_after"]["position"]) - episode["start_position"])),
               "actions": trace, "gpu_before": before, "gpu_with_scene": gpu(),
               "purpose": "scene_and_action_acceptance_not_navigation_evaluation"}
(run / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2), flush=True)
