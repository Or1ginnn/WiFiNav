import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from objectnav_progress_baseline import ProgressBaseline
from objectnav_sensor_baseline import Observation


def observation(depth, *, yaw=0., x=0., z=0., target=False):
    return Observation("chair", np.full((96, 128), depth), np.full((96, 128), target),
                       x, z, yaw, None)


class ProgressBaselineTests(unittest.TestCase):
    def setUp(self):
        self.policy = ProgressBaseline()
        self.policy.reset()

    def test_blocked_forward_commits_to_open_direction(self):
        self.assertEqual(self.policy.act(observation(.42)), "move_forward")
        self.assertEqual(self.policy.act(observation(.42)), "turn_left")
        self.assertEqual(self.policy.act(observation(1., yaw=math.pi / 6)), "move_forward")
        advanced = observation(1., yaw=math.pi / 6, x=-.125, z=-.2165)
        self.assertEqual(self.policy.act(advanced), "move_forward")

    def test_recovery_preserves_semantic_stop_and_can_reset(self):
        for _ in range(10):
            self.policy.act(observation(.25))
        self.assertEqual(self.policy.act(observation(.42, target=True)), "stop")
        self.policy.reset()
        self.assertEqual(self.policy.act(observation(.42)), "move_forward")
