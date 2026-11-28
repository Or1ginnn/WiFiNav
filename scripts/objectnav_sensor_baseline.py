"""Deterministic ObjectNav reference agent using egocentric observations."""
from collections import Counter
from dataclasses import dataclass
import math
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class Observation:
    category: str
    depth_m: np.ndarray
    target_mask: np.ndarray
    x: float
    z: float
    yaw: float
    rssi_dbm: Optional[float]
    relative_height_m: float = 0.
    rgb: Optional[np.ndarray] = None


class SensorBaseline:
    """Use ground-truth semantic sensing for a lightweight engineering baseline."""

    stop_target_depth_m = .50

    def reset(self):
        self.departures = Counter()
        self.visits = Counter()
        self.signal = {}

    @staticmethod
    def cell(x, z):
        return (round(x * 4), round(z * 4))

    def act(self, obs):
        cell = self.cell(obs.x, obs.z)
        self.visits[cell] += 1
        if obs.rssi_dbm is not None:
            self.signal[cell] = obs.rssi_dbm

        image = obs.depth_m
        h, w = image.shape
        ys, xs = np.where(obs.target_mask & (image > 0))
        patch = image[h//3:2*h//3, 3*w//8:5*w//8]
        close_obstacle = float(np.quantile(patch[patch > 0], .2)) if np.any(patch > 0) else 5.
        if len(xs) >= 10:
            x = float(np.median(xs)) / w
            if x < .30:
                return "turn_left"
            if x > .70:
                return "turn_right"
            if float(np.quantile(image[ys, xs], .25)) < self.stop_target_depth_m:
                return "stop"
            if close_obstacle > .28:
                return "move_forward"

        def priority(turn):
            yaw = obs.yaw + turn * math.pi / 6
            target = self.cell(obs.x - .50 * math.sin(yaw), obs.z - .50 * math.cos(yaw))
            # Penalize known weak cells using earlier observations only. An
            # unseen cell has no risk estimate and uses the exploration score.
            rssi = self.signal.get(target)
            risk = max(0., (-67. - rssi) / 8.) if rssi is not None else 0.
            key = (*cell, round(yaw * 6 / math.pi) % 12)
            penalty = 5. * (turn == 0 and close_obstacle < .38) + .18 * abs(turn)
            return self.departures[key] + .12 * min(35, self.visits[target]) + penalty + risk

        turn = min((0, 1, -1), key=priority)
        if turn:
            # Count an attempted direction before moving so blocked positions
            # eventually try another branch even if the robot has not advanced.
            key = (*cell, round((obs.yaw + turn * math.pi / 6) * 6 / math.pi) % 12)
            self.departures[key] += .35
            return "turn_left" if turn > 0 else "turn_right"
        key = (*cell, round(obs.yaw * 6 / math.pi) % 12)
        self.departures[key] += 1
        return "move_forward"
