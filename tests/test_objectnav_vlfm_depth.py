import unittest

import numpy as np

from scripts.objectnav_vlfm_baseline import normalize_depth


class VLFMDepthTests(unittest.TestCase):
    def test_official_depth_is_clipped_and_normalized_to_the_camera_range(self):
        depth = np.array([0., .5, 2.75, 5., 10., np.inf, -np.inf, np.nan], dtype=np.float32)
        np.testing.assert_array_equal(
            normalize_depth(depth, .5, 5.), np.array([0, 0, .5, 1, 1, 1, 0, 1], dtype=np.float32),
        )

    def test_original_profile_reproduces_existing_depth_values(self):
        depth = np.array([-.5, 0., .5, 5., 10., 15., np.nan], dtype=np.float32)
        original = np.clip(np.nan_to_num(depth, nan=10.) / 10., 0., 1.).astype(np.float32)
        np.testing.assert_array_equal(normalize_depth(depth, 0., 10.), original)
