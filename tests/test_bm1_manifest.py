import copy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from connectivity_vln.evaluation.manifest import validate_development_manifest


class ManifestChecks(unittest.TestCase):
    def setUp(self):
        self.actor={'case_id':'case1','instruction':'synthetic task','scene_id':'scene1',
                    'start_position':[0,0,0],'start_rotation':[0,0,0,1]}
        self.case={'case_id':'case1','episode_id':'1','scene_id':'scene1','group_id':'group1',
            'source_split':'train','assigned_split':'development','layout_id':'start','channel_seed':1,
            'instruction_sha256':hashlib.sha256(b'synthetic task').hexdigest(),
            'qualification':'unreviewed','protected_instance':{'wireless':{'ap':[0,0,0]}}}
        self.manifest={'schema_version':'bm1-dev-v1','stage':'development_schema_audit',
            'official_release':False,'source':{k:'a'*64 for k in ('task_sha256','gt_sha256','manifest_sha256')},
            'cases':[self.case]}
        self.actors=[self.actor]

    def check(self): return validate_development_manifest(self.manifest,self.actors)

    def test_valid_and_privileged_sidecar_stays_separate(self):
        self.assertEqual(self.check()['case_count'],1)

    def test_actor_rejects_privileged_fields(self):
        for key in ('goal','reference_path','ap','wireless','metrics','extra'):
            with self.subTest(key=key):
                self.actor[key]={}
                with self.assertRaises(ValueError): self.check()
                del self.actor[key]

    def test_duplicate_case_rejected(self):
        self.manifest['cases'].append(copy.deepcopy(self.case))
        self.actors.append(copy.deepcopy(self.actor))
        with self.assertRaises(ValueError): self.check()

    def test_source_group_and_scene_cannot_cross_splits(self):
        for identity in ('group_id','scene_id'):
            with self.subTest(identity=identity):
                case=copy.deepcopy(self.case); actor=copy.deepcopy(self.actor)
                case.update(case_id='case2',episode_id='2',source_split='val_unseen',assigned_split='held_out')
                if identity=='group_id': case['scene_id']='scene2';actor['scene_id']='scene2'
                else: case['group_id']='group2'
                actor['case_id']='case2'
                self.manifest['cases']=[self.case,case];self.actors=[self.actor,actor]
                with self.assertRaises(ValueError): self.check()

    def test_changed_instruction_and_missing_actor_rejected(self):
        self.actor['instruction']='changed'
        with self.assertRaises(ValueError): self.check()
        self.actors=[]
        with self.assertRaises(ValueError): self.check()

    def test_no_release_or_qualification_claim(self):
        self.manifest['official_release']=True
        with self.assertRaises(ValueError): self.check()
        self.manifest['official_release']=False;self.case['qualification']='eligible'
        with self.assertRaises(ValueError): self.check()


if __name__=='__main__': unittest.main()
