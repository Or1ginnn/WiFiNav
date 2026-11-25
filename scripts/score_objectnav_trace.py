#!/usr/bin/env python3
"""Score executed ObjectNav poses with native Habitat measures and an RSSI replay."""
import argparse
import gzip
import json
import math
from pathlib import Path
from types import SimpleNamespace

from solve_objectnav_rssi_graph import ROOT, sample_route


def score_navigation(finder, episode, trace, radius):
    import habitat_sim
    import numpy as np
    from habitat.config.default_structured_configs import (
        DistanceToGoalMeasurementConfig, SPLMeasurementConfig, SuccessMeasurementConfig,
    )
    from habitat.core.embodied_task import Measurements
    from habitat.tasks.nav.nav import DistanceToGoal, SPL, Success

    positions = np.asarray(trace["positions"], dtype=np.float32)
    actions = trace["actions"]
    if (positions.shape != (len(actions) + 1, 3) or not np.isfinite(positions).all()
            or math.dist(positions[0], episode.start_position) > 1e-4
            or "stop" in actions[:-1]):
        raise ValueError("A trace must begin at the official start and end at its first STOP")

    class Replay:
        position = positions[0]

        def get_agent_state(self):
            return SimpleNamespace(position=self.position)

        def geodesic_distance(self, position, goals, episode=None):
            del episode
            query = habitat_sim.MultiGoalShortestPath()
            query.requested_start = position
            query.requested_ends = np.asarray(goals, dtype=np.float32)
            return float(query.geodesic_distance) if finder.find_path(query) else math.inf

    replay = Replay()
    distance = DistanceToGoal(replay, DistanceToGoalMeasurementConfig(distance_to="VIEW_POINTS"))
    success = Success(replay, SuccessMeasurementConfig(success_distance=radius))
    spl = SPL(replay, SPLMeasurementConfig())
    task = SimpleNamespace(measurements=Measurements([distance, success, spl]), is_stop_called=False)
    measures = (distance, success, spl)
    for metric in measures:
        metric.reset_metric(episode=episode, task=task)
    reference = distance.get_metric()
    if not math.isfinite(reference) or reference <= 0:
        raise ValueError("Expected a positive, finite official reference distance")
    for position, action in zip(positions[1:], actions):
        replay.position = position
        task.is_stop_called = action == "stop"
        for metric in measures:
            metric.update_metric(episode=episode, task=task)
    final_distance = distance.get_metric()
    return {
        "success": float(success.get_metric()), "spl": float(spl.get_metric()),
        "official_reference_m": reference,
        "final_distance_m": final_distance if math.isfinite(final_distance) else None,
        "length_m": float(np.linalg.norm(np.diff(positions, axis=0), axis=1).sum()),
        "stop_called": task.is_stop_called,
    }


def score_habitat(geometry, probes=False, traces=None):
    import habitat
    import habitat_sim
    import numpy as np
    import quaternion
    from habitat.config.default_structured_configs import DatasetConfig

    source = Path(geometry["source_ref"])
    scan = source.name.removesuffix(".basis.glb")
    split = geometry["split"]
    cfg = DatasetConfig(type="ObjectNav-v1", split=split,
                        data_path="data/datasets/objectnav/hm3d/v2/{split}/{split}.json.gz",
                        scenes_dir="data/scene_datasets", content_scenes=[scan])
    dataset = habitat.make_dataset(cfg.type, config=cfg)
    episode_path = ROOT / cfg.data_path.format(split=split)
    shard = episode_path.parent / "content" / f"{scan}.json.gz"
    with gzip.open(shard, "rt", encoding="utf-8") as handle:
        source_rows = json.load(handle)["episodes"]
    if len(dataset.episodes) != len(source_rows) or len(source_rows) != geometry["source_episode_count"]:
        raise ValueError("Official source count and loaded Habitat episodes differ")
    sim = habitat_sim.SimulatorConfiguration()
    sim.scene_id = str(ROOT / "data/scene_datasets" / source)
    sim.scene_dataset_config_file = str(ROOT / "data/scene_datasets/hm3d_v0.2/hm3d_annotated_basis.scene_dataset_config.json")
    sim.create_renderer = False
    agent = habitat_sim.agent.AgentConfiguration()
    agent.action_space = {
        key: habitat_sim.agent.ActionSpec(key, habitat_sim.agent.ActuationSpec(amount))
        for key, amount in (("move_forward", .25), ("turn_left", 30.), ("turn_right", 30.))
    }
    by_key = {str(row["source_row"]): row for row in geometry["tasks"]}

    def episode_at(key):
        row = int(key)
        original = source_rows[row]
        episode = dataset.episodes[row]
        # Habitat renumbers episode IDs when loading each shard. Check the raw
        # identity from the shard and match the loaded episode's actual inputs.
        if (str(original["episode_id"]) != str(by_key[key]["source_episode_id"])
                or str(episode.episode_id) != key
                or episode.object_category != by_key[key]["category"]
                or not np.allclose(episode.start_position, original["start_position"], atol=1e-6, rtol=0)
                or not np.allclose(episode.start_rotation, original["start_rotation"], atol=1e-6, rtol=0)
                or str(episode.scene_id) != "data/scene_datasets/" + str(source)):
            raise ValueError(f"Official episode identity differs for source row {key}")
        return episode

    radius = geometry["config"]["stop_radius_m"]
    with habitat_sim.Simulator(habitat_sim.Configuration(sim, [agent])) as simulator:
        navmesh = simulator.pathfinder
        if probes:
            for key, task in by_key.items():
                episode = episode_at(key)
                state = habitat_sim.AgentState()
                state.position = np.asarray(episode.start_position, dtype=np.float32)
                state.rotation = quaternion.quaternion(episode.start_rotation[3], *episode.start_rotation[:3])
                simulator.get_agent(0).set_state(state)
                follower = simulator.make_greedy_follower(goal_radius=radius, forward_key="move_forward",
                                                           left_key="turn_left", right_key="turn_right")
                try:
                    commands = follower.find_path(np.asarray(task["route_xyz"][-1], dtype=np.float32))
                except habitat_sim.errors.GreedyFollowerError:
                    continue
                start = state.position.tolist()
                positions = [start]
                actions = []
                for command in commands:
                    if command is None:
                        break
                    simulator.step(command)
                    actions.append(command)
                    positions.append(simulator.get_agent(0).get_state().position.tolist())
                arrival = {"source_row": int(key), "actions": actions + ["stop"],
                           "positions": positions + [positions[-1]], "termination": "stop"}
                early = {"source_row": int(key), "actions": ["stop"], "positions": [start, start],
                         "termination": "early_stop"}
                if (score_navigation(navmesh, episode, arrival, radius)["success"] == 1
                        and score_navigation(navmesh, episode, early, radius)["success"] == 0):
                    traces = [arrival, early]
                    break
            else:
                raise RuntimeError("The fixed small batch produced no successful Habitat action probe")
        return [{"trace": trace, "navigation": score_navigation(navmesh, episode_at(str(trace["source_row"])), trace, radius)}
                for trace in traces]


def score_radio(geometry, navigation, step):
    import drjit as dr
    import numpy as np
    from run_objectnav_ap_radio import habitat_to_glb, semantic_geometry, signal_for_anchor
    from run_rss_raytrace_pilot import summarize_profile

    dr.set_thread_count(4)
    asset = ROOT / "data/scene_datasets" / geometry["source_ref"]
    scan = asset.name.removesuffix(".basis.glb")
    scene, tags, _ = semantic_geometry(asset.with_name(scan + ".semantic.glb"), asset.with_name(scan + ".semantic.txt"))
    by_key = {row["source_row"]: row for row in geometry["tasks"]}
    config = geometry["config"]
    for row in navigation:
        trace = row["trace"]
        task = by_key[trace["source_row"]]
        anchor, = geometry["floors"][task["floor"]]["candidates"]
        positions = np.asarray(trace["positions"], dtype=float)
        points = np.asarray(sample_route(positions, step))
        receivers = habitat_to_glb(points, config["rx_height_above_floor_m"])
        signals, _ = signal_for_anchor(scene, tags, anchor["xyz"], receivers, config)
        values = [float(value) if math.isfinite(value) else None for value in signals]
        lengths = np.linalg.norm(np.diff(points, axis=0), axis=1).tolist()
        row["communication"] = summarize_profile(values, {"segment_lengths_m": lengths}, config)
    return navigation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--traces", type=Path)
    mode.add_argument("--navigation", type=Path)
    parser.add_argument("--rssi-step-m", type=float, default=.01875)
    args = parser.parse_args()
    if ROOT / "runtime" not in args.output.resolve().parents or args.output.exists():
        parser.error("Output must be a new file below project runtime")
    geometry = json.loads(args.geometry.read_bytes())
    if args.navigation:
        rows = score_radio(geometry, json.loads(args.navigation.read_bytes()), args.rssi_step_m)
    else:
        traces = json.loads(args.traces.read_bytes()) if args.traces else None
        rows = score_habitat(geometry, probes=args.probe, traces=traces)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(rows, handle, allow_nan=False)


if __name__ == "__main__":
    main()
