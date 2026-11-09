"""Use Habitat-Lab 0.3's native VLN task with an unchanged R2R-CE payload."""
import gzip
import hashlib
import json
from pathlib import Path

import habitat
from habitat.config import read_write
from omegaconf import OmegaConf

PROJECT = Path(__file__).resolve().parents[3]


def load_json(path):
    return json.loads(Path(path).read_text())


def prepare(config_path=None, episode_id=None):
    settings = load_json(config_path or PROJECT / "configs/navigation/r2r_dev.json")
    paths = load_json(PROJECT / "configs/data/server_paths.json")
    task_file = PROJECT / paths["task_dataset"] / settings["split"] / (settings["split"] + ".json.gz")
    with gzip.open(task_file, "rt") as stream:
        payload = json.load(stream)
    # Selection never depends on goal length, rendered observations or policy outcome.
    if episode_id is None:
        selected = min(payload["episodes"], key=lambda e: (e["scene_id"], int(e["episode_id"])))
    else:
        matches = [e for e in payload["episodes"] if str(e["episode_id"]) == str(episode_id)]
        if len(matches) != 1:
            raise ValueError("Explicit episode_id must identify exactly one source episode")
        selected = matches[0]
    config = habitat.get_config("benchmark/nav/vln_r2r.yaml")
    with read_write(config):
        h = config.habitat
        h.seed = settings["seed"]
        h.dataset.data_path = str(task_file)
        h.dataset.scenes_dir = str(PROJECT / paths["scene_dataset_root"])
        h.dataset.split = settings["split"]
        h.environment.max_episode_steps = settings["max_episode_steps"]
        h.environment.iterator_options.shuffle = False
        sim = h.simulator
        sim.forward_step_size = settings["forward_step_m"]
        sim.turn_angle = settings["turn_degrees"]
        sim.habitat_sim_v0.gpu_device_id = settings["gpu_device_id"]
        sim.habitat_sim_v0.allow_sliding = settings["allow_sliding"]
        # Keep the supplied dataset navmesh. Do not silently rebuild it.
        sim.default_agent_navmesh = False
        agent = sim.agents.main_agent
        agent.height = settings["agent_height_m"]
        agent.radius = settings["agent_radius_m"]
        for sensor in agent.sim_sensors.values():
            sensor.width = settings["width"]
            sensor.height = settings["height"]
            sensor.hfov = settings["hfov_degrees"]
            sensor.position = [0.0, settings["camera_height_m"], 0.0]
        depth = agent.sim_sensors.depth_sensor
        depth.normalize_depth = False
        depth.min_depth = settings["depth_min_m"]
        depth.max_depth = settings["depth_max_m"]
        h.task.measurements.success.success_distance = settings["success_distance_m"]
    dataset = habitat.make_dataset(config.habitat.dataset.type, config=config.habitat.dataset)
    dataset.episodes = [e for e in dataset.episodes if str(e.episode_id) == str(selected["episode_id"])]
    if len(dataset.episodes) != 1:
        raise RuntimeError("Selected episode ID was not unique")
    if set(config.habitat.task.lab_sensors) != {"instruction_sensor"}:
        raise RuntimeError("Unexpected task sensor; oracle observations are forbidden")
    metadata = {
        "split": settings["split"], "episode_id": str(selected["episode_id"]),
        "trajectory_id": str(selected["trajectory_id"]), "scene_id": selected["scene_id"],
        "selection": settings["selection"] if episode_id is None else "explicit_frozen_manifest_id",
        "task_sha256": hashlib.sha256(task_file.read_bytes()).hexdigest(),
        "settings": settings, "habitat_config": OmegaConf.to_container(config, resolve=True),
        "habitat_lab_version": habitat.__version__,
    }
    return config, dataset, selected, metadata


def pose(env):
    state = env.sim.get_agent_state()
    q = state.rotation
    return {"position": state.position.tolist(),
            "rotation_xyzw": [float(q.x), float(q.y), float(q.z), float(q.w)]}
