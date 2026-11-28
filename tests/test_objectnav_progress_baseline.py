import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from objectnav_progress_baseline import EarlierStopBaseline, LevelRecoveryBaseline, ProgressBaseline
from objectnav_sensor_baseline import Observation


def observation(depth, *, yaw=0., x=0., z=0., target=False, height=0.):
    return Observation("chair", np.full((96, 128), depth), np.full((96, 128), target),
                       x, z, yaw, None, relative_height_m=height)


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

    def test_earlier_stop_only_changes_the_stop_trigger(self):
        earlier = EarlierStopBaseline()
        earlier.reset()
        target = observation(.65, target=True)
        self.assertEqual(self.policy.act(target), "move_forward")
        self.assertEqual(earlier.act(target), "stop")

    def test_level_recovery_leaves_direction_after_ascent_or_descent(self):
        policy = LevelRecoveryBaseline()
        for height in (-.04, .04):
            with self.subTest(height=height):
                policy.reset()
                self.assertEqual(policy.act(observation(1.)), "move_forward")
                self.assertEqual(policy.act(observation(1., z=-.25, height=height)), "turn_left")
                self.assertEqual(policy.act(observation(1., z=-.25, yaw=math.pi / 6, height=height)),
                                 "move_forward")

    def test_level_recovery_keeps_existing_stop_rule(self):
        policy = LevelRecoveryBaseline()
        policy.reset()
        self.assertEqual(policy.act(observation(1.)), "move_forward")
        self.assertEqual(policy.act(observation(.65, z=-.25, height=.04, target=True)), "stop")
