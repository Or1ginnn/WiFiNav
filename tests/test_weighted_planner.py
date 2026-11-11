"""Small two-route test: isolate tradeoff, lambda=0 access and disconnection."""
import unittest
import numpy as np

from connectivity_vln.navigation.weighted_planner import shortest_path, NavmeshRiskPlanner


class WeightedPlannerTest(unittest.TestCase):
    def setUp(self):
        # Short route 0-1-3; longer safe route 0-2-3.
        self.graph = [[(1, 1.), (2, 1.5)], [(0, 1.), (3, 1.)],
                      [(0, 1.5), (3, 1.5)], [(1, 1.), (2, 1.5)]]

    def test_zero_weight_never_reads_field(self):
        def forbidden(_):
            raise AssertionError("NoSignal accessed radio truth")
        self.assertEqual(shortest_path(self.graph, 0, 3, forbidden, 0), ([0, 1, 3], 2.))

    def test_risk_changes_route_with_cost_accounted(self):
        path, cost = shortest_path(self.graph, 0, 3, lambda n: float(n == 1), 4)
        self.assertEqual(path, [0, 2, 3])
        self.assertEqual(cost, 3.)

    def test_disconnected_and_invalid_weight(self):
        with self.assertRaises(ValueError):
            shortest_path([[], []], 0, 1, lambda n: 0, 0)
        for value in [-1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                shortest_path(self.graph, 0, 3, lambda n: 0, value)

    def test_grid_integration_and_risk_cache_isolation(self):
        class OpenFloor:
            def get_bounds(self):
                return np.array([0., 0., 0.]), np.array([3., 0., 2.])
            def snap_point(self, p):
                return np.asarray(p, dtype=np.float32)
            def try_step(self, a, b):
                return np.asarray(b)
        class Field:
            config = {'weak_threshold_dbm': -67., 'outage_threshold_dbm': -75.}
            def __init__(self, weak):
                self.weak = weak
            def query(self, point, index):
                return {'rssi_truth_dbm': -80. if self.weak and point[2] < .75 and .5 < point[0] < 2.5 else -60.}
        planner = NavmeshRiskPlanner(OpenFloor(), 0.)
        start, goal = [0., 0., 0.], [3., 0., 0.]
        _, base = planner.plan(start, goal)
        path, weighted = planner.plan(start, goal, weight=4., field=Field(True))
        self.assertAlmostEqual(base['path_length_m'], 3., places=5)
        self.assertGreater(max(p[2] for p in path), .5)
        self.assertGreater(weighted['path_length_m'], base['path_length_m'])
        _, safe = planner.plan(start, goal, weight=4., field=Field(False))
        self.assertAlmostEqual(safe['path_length_m'], 3., places=5)


if __name__ == '__main__':
    unittest.main()
