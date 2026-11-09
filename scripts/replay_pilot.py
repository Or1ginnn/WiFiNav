"""Replay fixed NoSignal trajectories against all frozen AP layouts.

No policy weights, prompts, AP positions or parameters are selected from outcomes.
This does not execute an Oracle policy or establish an Oracle benefit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import habitat_sim
from connectivity_vln.navigation.task import PROJECT, load_json
from connectivity_vln.signal_simulation.route_a import SignalField, communication_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch_dir.resolve()
    manifest = load_json(batch / "manifest.json")
    paths = load_json(PROJECT / "configs/data/server_paths.json")
    results = []
    episodes = []
    for episode in manifest["episodes"]:
        directory = batch / ("episode_" + episode["episode_id"])
        status = load_json(batch / ("episode_" + episode["episode_id"] + "_status.json"))
        summary = load_json(directory / "summary.json") if (directory / "summary.json").exists() else None
        trajectory_path = directory / "trajectory.jsonl"
        trajectory = [json.loads(line) for line in trajectory_path.read_text().splitlines()] if trajectory_path.exists() else []
        sha = hashlib.sha256(trajectory_path.read_bytes()).hexdigest() if trajectory else None
        navmesh = (PROJECT / paths["scene_dataset_root"] / episode["scene_id"]).with_suffix(".navmesh")
        if hashlib.sha256(navmesh.read_bytes()).hexdigest() != episode["navmesh_sha256"]:
            raise RuntimeError("Navmesh changed after manifest freeze")
        pathfinder = habitat_sim.PathFinder()
        if not pathfinder.load_nav_mesh(str(navmesh)):
            raise RuntimeError("Could not load navmesh for replay")
        episode_result = {"episode_id": episode["episode_id"], "scene_id": episode["scene_id"],
                          "trajectory_id": episode["trajectory_id"], "exit_reason": status["exit_reason"],
                          "success": status["success"], "summary_complete": summary is not None,
                          "runtime_error": summary.get("error") if summary else "missing_summary",
                          "spl": summary["metrics"]["spl"] if summary else 0.0,
                          "ndtw": summary["metrics"]["ndtw_exact_euclidean"] if summary else None,
                          "path_length_m": summary["metrics"]["path_length_m"] if summary else None}
        episodes.append(episode_result)
        for layout in episode["layouts"]:
            config = layout["wireless_config"]
            field = SignalField(pathfinder, episode["scene_id"], layout["ap_floor_position"], config)
            replay = []
            for index, step in enumerate(trajectory):
                replay.append({"step": step["step"], "pose": step["pose"], "action": step["action"],
                               "motion_sim_time_seconds": step["motion_sim_time_seconds"],
                               "wireless": field.query(step["pose"]["position"], index)})
            target = directory / ("replay_" + layout["layout_id"] + ".jsonl")
            with target.open("x") as stream:
                for item in replay:
                    stream.write(json.dumps(item) + "\n")
            communication = communication_metrics(replay, config) if replay else None
            results.append({**episode_result, "layout_id": layout["layout_id"],
                            "trajectory_sha256": sha, "sample_count": len(replay),
                            "full_rollout": summary is not None and summary.get("error") is None,
                            "communication": communication})
    complete = [r for r in results if r["full_rollout"] and r["communication"]]
    aggregate = {
        "episode_count": len(episodes), "scene_count": len({e["scene_id"] for e in episodes}),
        "case_count": len(results), "completed_rollouts": sum(e["summary_complete"] for e in episodes),
        "runtime_error_episodes": sum(e["runtime_error"] is not None for e in episodes),
        "missing_summary_episodes": sum(not e["summary_complete"] for e in episodes),
        "successful_episodes": sum(e["success"] for e in episodes),
        "sr_all_selected": statistics.mean(e["success"] for e in episodes),
        "spl_all_selected": statistics.mean(e["spl"] for e in episodes),
        "ndtw_available_trajectories_including_error_prefixes": statistics.mean(
            e["ndtw"] for e in episodes if e["ndtw"] is not None),
        "complete_cases": len(complete),
        "partial_cases": len(results)-len(complete),
        "cases_with_outage": sum(r["communication"]["outage_seconds"] > 0 for r in complete),
        "cases_with_weak_signal": sum(r["communication"]["weak_seconds"] > 0 for r in complete),
        "cases_with_outage_including_partial": sum(
            r["communication"] is not None and r["communication"]["outage_seconds"] > 0 for r in results),
        "cases_with_weak_signal_including_partial": sum(
            r["communication"] is not None and r["communication"]["weak_seconds"] > 0 for r in results),
        "oracle_benefit_verified": False,
        "failed_episodes_retained": True,
        "case_counts_do_not_multiply_independent_navigation_samples": True,
    }
    report = {"aggregate": aggregate, "episodes": episodes, "cases": results,
              "manifest_sha256": hashlib.sha256((batch/"manifest.json").read_bytes()).hexdigest()}
    (batch / "pilot_report.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(aggregate, indent=2), flush=True)


if __name__ == "__main__":
    main()
