from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_objectnav_train_route_pair import select_reference


def profile(weak, severe, length=2.0):
    return {"weak_length_m": weak, "outage_length_m": severe, "length_m": length}


class ReferenceSelectionTests(unittest.TestCase):
    def test_one_resolution_gain_does_not_replace_the_baseline(self):
        self.assertEqual(select_reference([[profile(1, .5)] * 2, [profile(1.1, .1), profile(.5, .1)]]), 0)

    def test_stable_weak_gain_takes_priority(self):
        self.assertEqual(select_reference([[profile(1, .5)] * 2, [profile(.8, .5)] * 2,
                                          [profile(.9, 0)] * 2]), 1)

    def test_stable_severe_gain_breaks_a_weak_tie(self):
        self.assertEqual(select_reference([[profile(1, .5)] * 2, [profile(1, .3, 2.1)] * 2]), 1)

    def test_negligible_gain_keeps_baseline(self):
        self.assertEqual(select_reference([[profile(1, .5)] * 2, [profile(.99, .3, 2.1)] * 2]), 0)
