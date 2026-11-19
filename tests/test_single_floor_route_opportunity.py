from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_single_floor_route_opportunities import candidate_window, outage_windows


class RouteOpportunityTests(unittest.TestCase):
    def test_windows_use_segment_midpoints_and_include_endpoints(self):
        self.assertEqual(list(outage_windows([-85, -85, -65, -65, -85], -75)), [(0, 1)])
        self.assertEqual(list(outage_windows([-65, -90, -65, -65, -90], -75)), [(0, 2), (3, 4)])

    def test_same_anchors_and_length_budget(self):
        task = {
            'nodes': [[1, 0, 0.4], [0, 0, 0], [1, 0, 0], [2, 0, 0]],
            'route_nodes': [1, 2, 3], 'route_lengths_m': [1, 1],
            'edges': [[1, 2, 1], [2, 3, 1], [0, 1, 1.08], [0, 3, 1.08]],
        }
        settings = dict(anchor_context_m=0.8, local_detour_fraction=0.2,
                        minimum_outage_reduction_m=0.1, risk_weights=[0, 1])
        radio = dict(weak_threshold_dbm=-67, outage_threshold_dbm=-75)
        args = (task, [-70, -90, -70], [-70], (0, 2), [0.0, 1.0, 2.0], radio)
        result = candidate_window(*args, settings)
        self.assertEqual(result['best_witness_nodes'], [1, 0, 3])
        self.assertEqual(result['reference_metrics']['outage_length_m'], 2)
        self.assertEqual(result['candidates'][0]['outage_reduction_m'], 2)
        rejected = candidate_window(*args, dict(settings, local_detour_fraction=0.05))
        self.assertIsNone(rejected['best_witness_nodes'])
        self.assertFalse(rejected['candidates'][0]['within_budget'])
        self.assertTrue(rejected['candidates'][0]['enough_improvement'])


if __name__ == '__main__':
    unittest.main()
