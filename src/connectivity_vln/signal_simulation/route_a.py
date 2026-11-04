"""First-loop RSSI field with explicit, reproducible approximation limits."""
import hashlib
import math

import habitat_sim
import numpy as np


class SignalField:
    def __init__(self, pathfinder, scene_id, ap_floor_position, config):
        self.pathfinder = pathfinder
        self.scene_id = scene_id
        self.ap = np.asarray(ap_floor_position, dtype=np.float64)
        self.config = config

    def _normal(self, *parts):
        material = "|".join(map(str, parts)).encode()
        digest = hashlib.sha256(material).digest()
        seed = int.from_bytes(digest[:8], "big", signed=False)
        return float(np.random.default_rng(seed).normal())

    def _shadow(self, position):
        cell = self.config["spatial_shadow_cell_m"]
        grid = tuple(int(round(float(value) / cell)) for value in position[[0, 2]])
        return self.config["spatial_shadow_sigma_db"] * self._normal(
            self.config["seed"], self.scene_id, self.config["layout_id"], "shadow", *grid
        )

    def _geodesic(self, position):
        query = habitat_sim.ShortestPath()
        query.requested_start = self.ap.astype(np.float32)
        query.requested_end = np.asarray(position, dtype=np.float32)
        if not self.pathfinder.find_path(query) or not math.isfinite(query.geodesic_distance):
            return math.inf
        return float(query.geodesic_distance)

    def query(self, position, sample_index):
        position = np.asarray(position, dtype=np.float64)
        distance = max(float(np.linalg.norm((position - self.ap)[[0, 2]])), 1.0)
        geodesic = self._geodesic(position)
        excess = max(0.0, geodesic - distance) if math.isfinite(geodesic) else math.inf
        obstruction = (
            self.config["max_obstruction_penalty_db"]
            if not math.isfinite(excess)
            else min(
                self.config["max_obstruction_penalty_db"],
                excess * self.config["obstruction_db_per_excess_meter"],
            )
        )
        truth = (
            self.config["reference_rssi_dbm_at_1m"]
            - 10.0 * self.config["path_loss_exponent"] * math.log10(distance)
            - obstruction
            + self._shadow(position)
        )
        noise = self.config["observation_noise_sigma_db"] * self._normal(
            self.config["seed"], self.scene_id, self.config["layout_id"], "observation", sample_index
        )
        measured = truth + noise
        return {
            "sample_index": sample_index,
            "rssi_truth_dbm": truth,
            "rssi_measured_dbm": measured,
            "horizontal_distance_to_ap_m": distance,
            "navmesh_geodesic_to_ap_m": geodesic,
            "geodesic_excess_m": excess,
            "obstruction_proxy_penalty_db": obstruction,
            "weak": measured < self.config["weak_threshold_dbm"],
            "outage": measured < self.config["outage_threshold_dbm"],
        }


def communication_metrics(trajectory, config):
    weak_seconds = 0.0
    outage_seconds = 0.0
    longest_outage = 0.0
    current_outage = 0.0
    outage_events = 0
    was_outage = False
    for previous, current in zip(trajectory, trajectory[1:]):
        duration = max(0.0, current["motion_sim_time_seconds"] - previous["motion_sim_time_seconds"])
        sample = current["wireless"]
        if sample["weak"]:
            weak_seconds += duration
        if sample["outage"]:
            outage_seconds += duration
            current_outage += duration
            if not was_outage:
                outage_events += 1
            was_outage = True
            longest_outage = max(longest_outage, current_outage)
        else:
            current_outage = 0.0
            was_outage = False
    total = trajectory[-1]["motion_sim_time_seconds"] if trajectory else 0.0
    values = [item["wireless"]["rssi_measured_dbm"] for item in trajectory]
    return {
        "motion_time_seconds": total,
        "weak_seconds": weak_seconds,
        "weak_ratio": weak_seconds / total if total else 0.0,
        "outage_seconds": outage_seconds,
        "outage_ratio": outage_seconds / total if total else 0.0,
        "outage_events": outage_events,
        "longest_outage_seconds": longest_outage,
        "rssi_min_dbm": min(values),
        "rssi_mean_dbm": float(np.mean(values)),
        "rssi_max_dbm": max(values),
        "weak_threshold_dbm": config["weak_threshold_dbm"],
        "outage_threshold_dbm": config["outage_threshold_dbm"],
    }
