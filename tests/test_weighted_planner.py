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

    def test_discrete_heading_avoids_clipping_without_turn_oscillation(self):
        class Floor:
            def get_bounds(self):
                return np.array([0.,0.,0.]),np.array([3.,0.,3.])
            def snap_point(self,p): return np.asarray(p,dtype=np.float32)
            def try_step(self,a,b):
                reached=np.asarray(b).copy()
                if b[0]>a[0] and abs(b[2]-a[2])<.001: reached[0]-=.02
                return reached
        planner=NavmeshRiskPlanner(Floor(),0.)
        start=np.array([1.,0.,1.]);target=np.array([2.,0.,1.])
        action,record=planner.discrete_action(start,[1.,0.,0.],target,step_m=.25,turn_degrees=15)
        self.assertIn(action,['turn_left','turn_right'])
        self.assertGreater(record['rejected_headings']['clipping'],0)
        theta=np.radians(record['selected_heading_offset_degrees'])
        forward=[np.cos(theta),0.,-np.sin(theta)]
        action,_=planner.discrete_action(start,forward,target,step_m=.25,turn_degrees=15)
        self.assertEqual(action,'move_forward')

    def test_discrete_step_cannot_leave_supported_floor(self):
        class Floor:
            def get_bounds(self): return np.array([0.,0.,0.]),np.array([3.,0.,3.])
            def snap_point(self,p): return np.asarray(p,dtype=np.float32)
            def try_step(self,a,b): return np.asarray(b).copy()
        planner=NavmeshRiskPlanner(Floor(),0.)
        class Drop(Floor):
            def try_step(self,a,b):
                p=np.asarray(b).copy();p[1]=-.254
                return p
        planner.pathfinder=Drop()
        with self.assertRaisesRegex(ValueError,'floor'):
            planner.discrete_action([1.,0.,1.],[1.,0.,0.],[2.,0.,1.],step_m=.25,turn_degrees=15)


if __name__ == '__main__':
    unittest.main()
