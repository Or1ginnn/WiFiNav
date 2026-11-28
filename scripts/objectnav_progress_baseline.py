"""A progress watchdog for the egocentric ObjectNav engineering baseline."""
from collections import defaultdict
import math

import numpy as np

from objectnav_sensor_baseline import SensorBaseline


class ProgressBaseline(SensorBaseline):
    """Try an open heading when local turns or collisions prevent progress."""

    elevation_trigger_m = None

    def reset(self):
        super().reset()
        self.last_pose = None
        self.last_height = None
        self.last_action = None
        self.stationary = 0
        self.recovery_moves = 0
        self.blocked = defaultdict(set)

    def act(self, obs):
        pose = (obs.x, obs.z)
        cell = self.cell(*pose)
        heading = round(obs.yaw * 6 / math.pi) % 12
        blocked_now = False
        if self.last_pose is not None:
            moved = math.dist(self.last_pose, pose) >= .025
            self.stationary = 0 if moved else self.stationary + 1
            if self.last_action == "move_forward":
                elevation_change = abs(obs.relative_height_m - self.last_height)
                blocked_now = not moved or (self.elevation_trigger_m is not None
                                            and elevation_change >= self.elevation_trigger_m)
                if blocked_now:
                    self.blocked[cell].add(heading)
                else:
                    self.recovery_moves = max(0, self.recovery_moves - 1)

        nominal = super().act(obs)
        blocked = heading in self.blocked[cell]
        if nominal == "stop":
            action = nominal
        elif self.recovery_moves or self.stationary >= 8 or blocked_now or (nominal == "move_forward" and blocked):
            if not self.recovery_moves:
                self.recovery_moves = 4
            image = obs.depth_m
            h, w = image.shape
            window = image[h//3:3*h//4, 3*w//8:5*w//8]
            valid = window[np.isfinite(window) & (window > 0)]
            clear = len(valid) and float(np.quantile(valid, .25)) >= .37
            if clear and not blocked:
                action = "move_forward"
            else:
                # Retry from another view instead of alternating two turns.
                action = "turn_left"
                if len(self.blocked[cell]) == 12:
                    self.blocked[cell].clear()
        else:
            action = nominal

        self.last_pose, self.last_action = pose, action
        self.last_height = obs.relative_height_m
        return action


class EarlierStopBaseline(ProgressBaseline):
    """Development ablation that attempts STOP one forward step earlier."""

    stop_target_depth_m = .75


class LevelRecoveryBaseline(EarlierStopBaseline):
    """Change direction after a forward step with noticeable elevation change."""

    # 2.5 cm is one tenth of the nominal forward step. Use the measured
    # displacement only, with no map, floor anchor or scoring tolerance.
    elevation_trigger_m = .025
