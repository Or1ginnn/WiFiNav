import argparse
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from score_objectnav_trace import (
    communication_success, parse_max_continuous_severe_m, summarize_communication_success,
)


class CommunicationSuccessTests(unittest.TestCase):
    def test_requires_a_legal_stop_and_an_inclusive_continuous_distance_limit(self):
        radio = {"available": True, "longest_outage_m": 1.0, "outage_length_m": 4.0}
        self.assertIs(communication_success({"success": 1}, radio, 1.0), True)
        self.assertIs(communication_success({"success": 1}, radio, 0.99), False)
        self.assertIs(communication_success({"success": 0}, radio, 1.0), False)

    def test_missing_rssi_leaves_only_navigation_successes_unresolved(self):
        radio = {"available": False}
        self.assertIsNone(communication_success({"success": 1}, radio, 1.0))
        self.assertIs(communication_success({"success": 0}, radio, 1.0), False)

    def test_summary_uses_all_tasks_and_leaves_the_rate_unknown_with_missing_results(self):
        rows = [{"communication_success": value} for value in (True, False, False)]
        self.assertEqual(summarize_communication_success(rows),
                         {"successes": 1, "failures": 2, "unknown": 0, "rate": 1 / 3})
        rows.append({"communication_success": None})
        self.assertEqual(summarize_communication_success(rows),
                         {"successes": 1, "failures": 2, "unknown": 1, "rate": None})

    def test_limit_must_be_a_finite_nonnegative_distance(self):
        self.assertEqual(parse_max_continuous_severe_m("0"), 0.0)
        for invalid in ("-1", "nan", "inf"):
            with self.subTest(invalid=invalid), self.assertRaises(argparse.ArgumentTypeError):
                parse_max_continuous_severe_m(invalid)
