"""Versioned offline latent-RSSI exposure on a declared motion-time grid.

This evaluator never supplies values to a navigation actor. Link failures,
forecasting, and physical wireless propagation are outside this implementation.
"""
import math


def evaluate_radio_v1(trajectory, truth_query, *, weak_dbm=-67.0, outage_dbm=-75.0,
                      integration_step_s=0.1, trajectory_status='complete'):
    if not all(math.isfinite(v) for v in (weak_dbm, outage_dbm, integration_step_s)):
        raise ValueError('Finite thresholds and integration step required')
    if outage_dbm >= weak_dbm or integration_step_s <= 0:
        raise ValueError('Require outage < weak and a positive integration step')
    if trajectory_status not in ('complete', 'error_prefix') or not trajectory:
        raise ValueError('Explicit trajectory status and nonempty trajectory required')
    previous_time = None
    for row in trajectory:
        t = row['motion_sim_time_seconds']; p = row['pose']['position']
        if not math.isfinite(t) or t < 0 or len(p) != 3 or not all(math.isfinite(v) for v in p):
            raise ValueError('Invalid time or 3D position')
        if previous_time is not None and t < previous_time:
            raise ValueError('Trajectory time decreased')
        previous_time = t
    if trajectory[0]['motion_sim_time_seconds'] != 0:
        raise ValueError('Trajectory must begin at motion time zero')
    weak = outage = longest = current = observed = 0.0
    events = queries = missing = 0
    was_outage = False
    for a, b in zip(trajectory, trajectory[1:]):
        start = a['motion_sim_time_seconds']; duration = b['motion_sim_time_seconds']-start
        if duration == 0:
            continue
        count = max(1, math.ceil(duration/integration_step_s))
        dt = duration/count
        for i in range(count):
            fraction = (i+0.5)/count
            position = [x+(y-x)*fraction for x,y in zip(a['pose']['position'], b['pose']['position'])]
            value = truth_query(position, start+duration*fraction)
            queries += 1
            if value is None or not math.isfinite(value):
                missing += 1
                # A missing interval prevents a complete exposure result.
                current = 0.0; was_outage = False
                continue
            observed += dt
            weak += dt*(value < weak_dbm)
            if value < outage_dbm:
                outage += dt; current += dt
                if not was_outage: events += 1
                was_outage = True; longest = max(longest, current)
            else:
                current = 0.0; was_outage = False
    total = trajectory[-1]['motion_sim_time_seconds']
    available = missing == 0
    return {'metric_version':'latent_motion_midpoint_v1',
            'trajectory_status':trajectory_status,
            'eligible_for_complete_trajectory_comparison':available and trajectory_status == 'complete' and total > 0,
            'integration_step_s':integration_step_s,'weak_threshold_dbm':weak_dbm,'outage_threshold_dbm':outage_dbm,
            'motion_time_seconds':total,'observed_time_seconds':observed,
            'query_count':queries,'missing_query_count':missing,
            'weak_seconds':weak if available else None,
            'outage_seconds':outage if available else None,
            'weak_ratio':weak/total if available and total else None,
            'outage_ratio':outage/total if available and total else None,
            'longest_outage_seconds':longest if available else None,
            'outage_events':events if available else None,
            'integration_assumption':'piecewise linear 3D positions; motion time includes turns, excludes inference waiting'}
