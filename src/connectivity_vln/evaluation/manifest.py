"""BM1 development contract checks; no policy outcomes or qualification filter."""
import hashlib
import json
import re

ACTOR_KEYS = {'case_id', 'instruction', 'scene_id', 'start_position', 'start_rotation'}
CASE_KEYS = {'case_id', 'episode_id', 'scene_id', 'group_id', 'source_split',
             'assigned_split', 'layout_id', 'channel_seed', 'instruction_sha256',
             'qualification', 'protected_instance'}


def validate_development_manifest(manifest, actors):
    """Check this draft contract, not arbitrary JSON Schema or sandbox security."""
    if manifest.get('schema_version') != 'bm1-dev-v1' or manifest.get('official_release') is not False:
        raise ValueError('Development version only; not an official release')
    if manifest.get('stage') != 'development_schema_audit':
        raise ValueError('Unexpected construction stage')
    for key in ('task_sha256', 'gt_sha256', 'manifest_sha256'):
        if not re.fullmatch('[0-9a-f]{64}', manifest['source'][key]):
            raise ValueError('Missing source hash')
    cases = manifest['cases']
    if not cases or len(cases) != len(actors):
        raise ValueError('Every case requires exactly one actor record')
    actor_by_id = {}
    for actor in actors:
        if set(actor) != ACTOR_KEYS:
            raise ValueError('Actor field allowlist violated; privileged fields forbidden')
        if actor['case_id'] in actor_by_id:
            raise ValueError('Duplicate actor case')
        if not isinstance(actor['instruction'], str):
            raise ValueError('Instruction must be text')
        for key, length in (('start_position', 3), ('start_rotation', 4)):
            if len(actor[key]) != length or any(type(v) not in (int, float) for v in actor[key]):
                raise ValueError('Invalid start pose')
        actor_by_id[actor['case_id']] = actor
    seen = set(); group_splits = {}; scene_splits = {}; task_splits = {}
    for case in cases:
        if set(case) != CASE_KEYS or case['case_id'] in seen:
            raise ValueError('Invalid or duplicate case')
        seen.add(case['case_id'])
        if case['qualification'] != 'unreviewed':
            raise ValueError('This schema audit cannot decide formal qualification')
        expected = {'train':'development', 'val_unseen':'held_out'}.get(case['source_split'])
        if expected is None or case['assigned_split'] != expected:
            raise ValueError('Source split mapping violated')
        if type(case['channel_seed']) is not int or case['channel_seed'] < 0:
            raise ValueError('Invalid channel seed')
        for table, identity in ((group_splits, case['group_id']),
                                (scene_splits, case['scene_id']),
                                (task_splits, (case['scene_id'], case['episode_id']))):
            if identity in table and table[identity] != case['assigned_split']:
                raise ValueError('Scene or source-path group split leakage')
            table[identity] = case['assigned_split']
        actor = actor_by_id.get(case['case_id'])
        if actor is None or actor['scene_id'] != case['scene_id']:
            raise ValueError('Actor/case identity mismatch')
        if hashlib.sha256(actor['instruction'].encode()).hexdigest() != case['instruction_sha256']:
            raise ValueError('Actor instruction changed')
        if not isinstance(case['protected_instance'], dict):
            raise ValueError('Protected evaluator instance missing')
        # Reject non-finite numeric payloads, including the protected sidecar.
        json.dumps(case, allow_nan=False)
        json.dumps(actor, allow_nan=False)
    if seen != set(actor_by_id):
        raise ValueError('Unexpected actor case')
    return {'case_count':len(cases), 'language_tasks':len(task_splits),
            'source_groups':len(group_splits), 'scenes':len(scene_splits),
            'assigned_splits':sorted(set(group_splits.values())),
            'actor_privileged_fields_absent':True,
            'not_a_formal_qualification_or_release':True}
