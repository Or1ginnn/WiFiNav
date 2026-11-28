from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render_objectnav_ap_smoke import REVIEW_GROUPS, stratified_review


class ObjectNavReviewTests(unittest.TestCase):
    def test_rare_group_and_floors_are_preserved(self):
        scenes = []
        for i in range(3):
            tasks = [
                {
                    "source_row": j,
                    "floor": "L1" if j < 3 else "L2",
                    "category": "chair" if j % 2 else "bed",
                    "communication_difficulty": REVIEW_GROUPS[0] if j % 3 == 0 else "residual_weak_coverage",
                    "signal_changes_route_materially": j % 3 == 1,
                }
                for j in range(6)
            ]
            if i == 0:
                tasks[1]["communication_difficulty"] = REVIEW_GROUPS[1]
            scenes.append({"scene": f"scene{i}", "tasks": tasks})
        manifest = {"scope": "full", "rules": {"review_seed": "test"}, "scenes": scenes,
                    "qualified_episodes": 18, "review_sample": [{"scene": "scene0", "source_row": 5}]}

        chosen, details = stratified_review(manifest, 10)

        self.assertEqual((chosen, details), stratified_review(manifest, 10))
        self.assertEqual(len(set(chosen)), 10)
        self.assertIn(("scene0", 1), chosen)
        self.assertEqual(details["sample_groups"], dict(zip(REVIEW_GROUPS, [3, 1, 3, 3])))
        self.assertEqual(len({(scene, row // 3) for scene, row in chosen}), 6)
        self.assertEqual({key for key, _ in chosen}, {"scene0", "scene1", "scene2"})
        self.assertEqual(manifest["review_sample"], [{"scene": "scene0", "source_row": 5}])

    def test_override_requires_full_qualified_population(self):
        for scope, count in [("small", 1), ("full", 0), ("full", 2)]:
            with self.subTest(scope=scope, count=count), self.assertRaises(ValueError):
                stratified_review({"scope": scope, "qualified_episodes": 1}, count)
