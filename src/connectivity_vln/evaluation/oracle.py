"""Predeclared development gate; layouts are correlated, not independent tasks."""
import statistics


def complete(row):
    s = row.get('summary')
    status = row.get('status', {})
    return bool(s is not None and s.get('error') is None and status.get('return_code') == 0
                and not status.get('timed_out') and row.get('communication') is not None)


def metric(row, name):
    s = row.get('summary')
    return float(s.get('metrics', {}).get(name, 0)) if s else 0.


def success(row):
    return float(complete(row) and metric(row, 'success') > 0)


def assess(rows, spec, expected_keys):
    """All-task reporting plus a baseline-success subset fixed before variants."""
    weights = spec['lambda_values']
    policy = spec['acceptance']
    indexed = {}
    for r in rows:
        key = (r['episode_id'], r['layout_id'], r['lambda'])
        if key in indexed:
            raise ValueError('Duplicate case: ' + str(key))
        indexed[key] = r
    coverage = set(indexed) == {(e, l, w) for e, l in expected_keys for w in weights}
    base = {(e, l):indexed[e, l, 0.] for e, l in expected_keys if (e, l, 0.) in indexed}
    paired = [k for k, r in base.items() if success(r)]
    result = {'full_manifest_coverage':coverage,'baseline_success_subset':paired,
              'independent_language_tasks':len({e for e, l in expected_keys}),
              'aggregate':{},'decisions':{},'selected_lambda':None,
              'caveat':'development gate, no significance claim; layouts share source tasks; partial metrics retained and missing metrics zero-filled'}
    for w in weights:
        selected = [indexed[e,l,w] for e,l in expected_keys if (e,l,w) in indexed]
        if not selected:
            continue
        aggregate = {'case_count':len(selected),'complete_cases':sum(complete(r) for r in selected),
                     'missing_summaries':sum(r.get('summary') is None for r in selected),
                     'sr_all_selected':sum(success(r) for r in selected)/len(expected_keys),
                     'spl_all_selected':sum(metric(r,'spl') for r in selected)/len(expected_keys),
                     'ndtw_all_selected':sum(metric(r,'ndtw_exact_euclidean') for r in selected)/len(expected_keys)}
        for k in ['path_length_m','primitive_actions_including_stop','collision_actions']:
            aggregate['mean_'+k] = statistics.mean(metric(r,k) for r in selected)
        for k in ['outage_seconds','outage_ratio','longest_outage_seconds','weak_seconds','motion_time_seconds']:
            aggregate['mean_'+k] = statistics.mean((r.get('communication') or {}).get(k,0) for r in selected)
        unique = {r['run_dir']:r for r in selected}
        aggregate['actual_executions'] = len(unique)
        aggregate['actual_model_requests'] = sum((r.get('summary') or {}).get('model_request_attempts',0) for r in unique.values())
        aggregate['actual_wall_seconds'] = sum(r['status']['wall_seconds'] for r in unique.values())
        result['aggregate'][str(w)] = aggregate
        if not w:
            continue
        failed = []
        if not coverage: failed.append('incomplete_manifest_coverage')
        if not all(complete(r) for r in selected) or not all(complete(r) for r in base.values()):
            failed.append('partial_or_error_case')
        variants = {k:indexed[k[0],k[1],w] for k in paired if (k[0],k[1],w) in indexed}
        lost = [k for k in paired if k not in variants or not success(variants[k])]
        if lost: failed.append('lost_baseline_success')
        values = {}
        if not paired or len(variants) != len(paired):
            failed.append('no_complete_paired_subset')
        else:
            for name in ['spl','ndtw_exact_euclidean']:
                values[name+'_loss'] = statistics.mean(metric(base[k],name)-metric(variants[k],name) for k in paired)
            path0 = sum(metric(base[k],'path_length_m') for k in paired)
            path1 = sum(metric(variants[k],'path_length_m') for k in paired)
            values['path_increase'] = path1/path0-1 if path0 else (0. if not path1 else float('inf'))
            for name in ['outage_seconds','longest_outage_seconds']:
                values['baseline_total_'+name] = sum(base[k]['communication'][name] for k in paired)
                values['variant_total_'+name] = sum((variants[k].get('communication') or {}).get(name,0) for k in paired)
            outage0 = values['baseline_total_outage_seconds']
            values['outage_reduction'] = 1-values['variant_total_outage_seconds']/outage0 if outage0 else None
            if values['spl_loss'] > policy['maximum_paired_absolute_spl_loss']+1e-8: failed.append('SPL_loss')
            if values['ndtw_exact_euclidean_loss'] > policy['maximum_paired_absolute_ndtw_loss']+1e-8: failed.append('nDTW_loss')
            if values['path_increase'] > policy['maximum_paired_total_path_increase']+1e-8: failed.append('path_budget')
            if values['outage_reduction'] is None: failed.append('zero_baseline_outage')
            elif values['outage_reduction']+1e-8 < policy['minimum_paired_total_outage_reduction']: failed.append('insufficient_absolute_outage_reduction')
            if values['variant_total_longest_outage_seconds'] > values['baseline_total_longest_outage_seconds']*(1+policy['maximum_paired_total_longest_outage_increase'])+1e-8:
                failed.append('longest_outage_increase')
        result['decisions'][str(w)] = {'passed':not failed,'failures':failed,'lost_success_cases':lost,'paired':values}
    passed = [w for w in weights if w and result['decisions'].get(str(w),{}).get('passed')]
    if passed:
        result['selected_lambda'] = min(passed,key=lambda w:(result['decisions'][str(w)]['paired']['variant_total_outage_seconds'],w))
    return result
