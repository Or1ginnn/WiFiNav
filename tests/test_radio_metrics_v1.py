from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from connectivity_vln.evaluation.radio_metrics_v1 import evaluate_radio_v1


def row(t,x=0,y=0): return {'motion_sim_time_seconds':t,'pose':{'position':[x,y,0]}}


class RadioMetricsTests(unittest.TestCase):
    def test_midpoint_detects_crossed_weak_region_with_good_endpoints(self):
        result=evaluate_radio_v1([row(0),row(1,1)],lambda p,t:-80 if .2<p[0]<.8 else -50)
        self.assertAlmostEqual(result['outage_seconds'],.6)
        self.assertEqual(result['outage_events'],1)

    def test_turn_time_and_zero_duration_stop(self):
        result=evaluate_radio_v1([row(0),row(.5),row(.5)],lambda p,t:-80)
        self.assertAlmostEqual(result['outage_seconds'],.5)
        self.assertEqual(result['outage_events'],1)

    def test_events_and_longest_are_contiguous_across_actions(self):
        result=evaluate_radio_v1([row(0),row(1),row(2),row(3)],lambda p,t:-80 if t<2 else -50)
        self.assertAlmostEqual(result['outage_seconds'],2)
        self.assertAlmostEqual(result['longest_outage_seconds'],2)
        self.assertEqual(result['outage_events'],1)

    def test_missing_is_not_zero_or_partial_benefit(self):
        result=evaluate_radio_v1([row(0),row(1)],lambda p,t:None if t>.5 else -80)
        self.assertIsNone(result['outage_seconds'])
        self.assertFalse(result['eligible_for_complete_trajectory_comparison'])
        self.assertGreater(result['observed_time_seconds'],0)

    def test_zero_duration_ratio_undefined(self):
        result=evaluate_radio_v1([row(0),row(0)],lambda p,t:-80)
        self.assertIsNone(result['outage_ratio'])
        self.assertEqual(result['query_count'],0)
        self.assertFalse(result['eligible_for_complete_trajectory_comparison'])

    def test_missing_signal_is_not_zero_exposure(self):
        result=evaluate_radio_v1([row(0),row(1)],lambda p,t:None)
        self.assertIsNone(result['outage_seconds'])
        self.assertIsNone(result['longest_outage_seconds'])
        self.assertEqual(result['missing_query_count'],10)

    def test_error_prefix_never_complete_comparison(self):
        result=evaluate_radio_v1([row(0),row(1)],lambda p,t:-50,trajectory_status='error_prefix')
        self.assertEqual(result['outage_seconds'],0)
        self.assertFalse(result['eligible_for_complete_trajectory_comparison'])

    def test_height_is_passed_to_signal_query(self):
        result=evaluate_radio_v1([row(0,y=0),row(1,y=1)],lambda p,t:-80 if p[1]>.5 else -50)
        self.assertAlmostEqual(result['outage_seconds'],.5)

    def test_strict_threshold_and_invalid_parameters(self):
        result=evaluate_radio_v1([row(0),row(1)],lambda p,t:-75)
        self.assertEqual(result['outage_seconds'],0)
        self.assertAlmostEqual(result['weak_seconds'],1)
        with self.assertRaises(ValueError): evaluate_radio_v1([row(0)],lambda p,t:0,integration_step_s=0)
        with self.assertRaises(ValueError): evaluate_radio_v1([row(1),row(0)],lambda p,t:0)


if __name__=='__main__':unittest.main()
