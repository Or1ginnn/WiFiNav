from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from connectivity_vln.benchmark.single_floor import scope_status,distances,preview_rssi,route_metrics


class ScopeTests(unittest.TestCase):
    def status(self,text,points=None):
        points=points or [[0,0,0],[1,0,0]]
        return scope_status(text,points[0],[points[-1]],points,points)

    def test_stairs_excluded_but_not_down_hallway(self):
        self.assertEqual(self.status('Go up the stairs into the gym')[0],'excluded')
        self.assertEqual(self.status('Go down the hallway')[0],'candidate')

    def test_same_height_endpoints_do_not_hide_midroute_height(self):
        self.assertEqual(self.status('Go to the room',[[0,0,0],[1,.6,0],[2,0,0]])[0],'review')

    def test_explicit_upstairs_is_excluded_but_preserved_for_audit(self):
        status,reasons,_=self.status('Go up the stairs into the gym')
        self.assertEqual(status,'excluded')
        self.assertIn('explicit_vertical_instruction',reasons)

    def test_nearby_stairs_and_floor_descriptors_are_not_vertical_commands(self):
        for text in (
            'Walk down the hallway, past the stairs.',
            'Walk around the upstairs hallway.',
            'Walk down two steps toward the table.',
            'Stop at the bottom of the stairs.',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.status(text)[0], 'review')

    def test_explicit_stair_and_elevator_movements(self):
        for text in (
            'Go straight down the hall and up the stairs.',
            'Head upstairs and stop.',
            'Descend the staircase.',
            'Take the elevator.',
        ):
            with self.subTest(text=text):
                status, _, evidence = self.status(text)
                self.assertEqual(status, 'excluded')
                self.assertTrue(evidence['vertical_phrase'])

    def test_ambiguous_and_negated_stairs_require_review(self):
        self.assertEqual(self.status('Stop near the stairs')[0],'review')
        self.assertEqual(self.status('Do not go up the stairs')[0],'review')

    def test_small_floor_variation_is_not_automatically_stairs(self):
        self.assertEqual(self.status('Go through the door',[[0,0,0],[1,.08,0]])[0],'candidate')

    def test_graph_obstruction_and_missing_are_explicit(self):
        ds=distances([[(1,2)],[(0,2)],[]],0)
        self.assertEqual(ds[1],2)
        config=dict(reference_rssi_dbm_at_1m=-48,path_loss_exponent=2.8,max_obstruction_penalty_db=25,obstruction_db_per_excess_meter=4)
        self.assertIsNone(preview_rssi([2,0,0],[0,0,0],ds[2],0,config))
        self.assertLess(preview_rssi([2,0,0],[0,0,0],4,0,config),preview_rssi([2,0,0],[0,0,0],2,0,config))
        self.assertFalse(route_metrics([-50,None],[1])['available'])


if __name__=='__main__':unittest.main()
