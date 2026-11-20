from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_route_witness_semantics import first_box_hit


class RouteBoxTests(unittest.TestCase):
    def setUp(self):
        self.route = np.array([[0, 0, 0], [2, 0, 0], [2, 0, 2]])

    def test_detects_crossing_between_samples(self):
        self.assertEqual(first_box_hit(self.route, [.5, -.5], [1, .5]), .5)
        self.assertEqual(first_box_hit(self.route, [1.9, 1], [2.1, 1.5]), 3)

    def test_parallel_path_outside_box_has_no_hit(self):
        self.assertIsNone(first_box_hit(self.route, [.5, 1], [1, 1.5]))


if __name__ == '__main__':
    unittest.main()
