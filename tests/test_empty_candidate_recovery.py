"""Exercise the real policy retry/recovery code without a model or renderer.

Mac fallback loads the actual class AST without simulator-only module imports;
server Habitat tests import the complete production module.
"""
import ast
import base64
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from connectivity_vln.navigation.interface import ProgressGuard, validate_tool, stop_review
try:
    from connectivity_vln.navigation.pixel_policy import PixelPolicy, ToolParseError
except ModuleNotFoundError as error:
    if error.name not in ('habitat_sim', 'habitat', 'numpy', 'PIL'):
        raise
    source = ROOT / 'src/connectivity_vln/navigation/pixel_policy.py'
    tree = ast.parse(source.read_text())
    tree.body = [node for node in tree.body if
                 isinstance(node, ast.ClassDef) and node.name in ('PixelPolicy', 'ToolParseError')
                 or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SYSTEM' for t in node.targets)]
    import urllib.request
    namespace = dict(base64=base64, json=json, Path=Path, urllib=urllib,
                     validate_tool=validate_tool, stop_review=stop_review)
    exec(compile(tree, str(source), 'exec'), namespace)
    PixelPolicy, ToolParseError = namespace['PixelPolicy'], namespace['ToolParseError']


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.frame = self.directory / 'frame.png'
        self.frame.write_bytes(b'mocked image; no API')
        self.policy = PixelPolicy({}, {'interface_version':'v1', 'stop_review_enabled':False,
            'max_parse_attempts':2, 'max_history_images':2, 'empty_candidate_recovery':True})
        self.policy.memory = 'previous valid observation'

    def responses(self, values):
        raws = [{'choices':[{'finish_reason':'stop','message':{'content':json.dumps(v)}}],
                 'wall_seconds':0.1} for v in values]
        self.policy._chat = Mock(side_effect=raws)

    def decide(self, candidates=None):
        return self.policy.decide('navigate', self.frame, candidates or [], self.directory)

    def invalid(self):
        self.responses([{'tool':'waypoint','candidate_id':4,'memory':'invented'},
                        {'tool':'waypoint','candidate_id':3}])

    def test_empty_recovery_after_exact_original_retry_bound(self):
        self.invalid()
        choice, record = self.decide()
        self.assertEqual(choice['tool'], 'look')
        self.assertEqual(choice['degrees'], 45)
        self.assertEqual(choice['memory'], 'previous valid observation')
        self.assertEqual(validate_tool(json.dumps(choice), [], version='v1'), choice)
        self.assertEqual(record['attempts'], 2)
        self.assertEqual(record['fallback'], 'empty_candidates_after_parse_retries')
        self.assertEqual(self.policy._chat.call_count, 2)
        self.assertEqual(len(list(self.directory.glob('parse_error_*.txt'))), 2)
        self.assertEqual(self.policy.history, [str(self.frame)])

    def test_disabled_preserves_original_error(self):
        self.policy.settings['empty_candidate_recovery'] = False
        self.invalid()
        with self.assertRaises(ToolParseError): self.decide()

    def test_nonempty_preserves_original_error(self):
        self.invalid()
        with self.assertRaises(ToolParseError): self.decide([{'id':0}])

    def test_legal_stop_and_look_remain_model_choices(self):
        for item in ({'tool':'stop'}, {'tool':'look','degrees':-60}):
            self.responses([item])
            choice, record = self.decide()
            self.assertEqual(choice['tool'], item['tool'])
            self.assertNotIn('fallback', record)
            self.assertEqual(self.policy._chat.call_count, 1)
        self.assertEqual(len(self.policy.history), 2)

    def test_invalid_action_parameters_still_rejected(self):
        self.responses([{'tool':'look','degrees':True}, {'tool':'look','degrees':46}])
        choice, _ = self.decide()
        self.assertEqual(choice['degrees'], 45)
        self.assertEqual(self.policy._chat.call_count, 2)
        self.assertIn('Look angle', (self.directory/'parse_error_0.txt').read_text())

    def test_observation_cycle_is_still_bounded_by_existing_guard(self):
        pose = {'position':[0,0,0], 'rotation_xyzw':[0,0,0,1]}
        guard = ProgressGuard(pose, 15)
        decisions = 0
        while guard.stalled < 4 and decisions < 80:
            decisions += 1
            half = math.radians(decisions * 45) / 2
            pose['rotation_xyzw'] = [0,math.sin(half),0,math.cos(half)]
            guard.update(pose, {'tool':'look','executed_actions':3,'collision':False})
        self.assertEqual(decisions, 11)
        self.assertEqual(guard.stalled, 4)
        self.assertLess(decisions*3, 500)


if __name__ == '__main__': unittest.main()
