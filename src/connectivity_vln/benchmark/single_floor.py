"""CPU-only preliminary scope rules and layout preview helpers."""
import heapq
import math
import re

VERTICAL = re.compile(r'\b(?:up|down|ascend\w*|descend\w*|climb\w*)\b.{0,35}\b(?:stairs?|staircase|steps?|flight)\b|\b(?:upstairs|downstairs|up-stairs|down-stairs)\b|\b(?:take|use|enter)\b.{0,20}\b(?:elevator|lift)\b', re.I)
AMBIGUOUS = re.compile(r'\b(?:stairs?|staircase|steps?|elevator|lift|landing|upper|lower|second floor|third floor|next floor)\b', re.I)
NEGATION = re.compile(r"\b(?:not|never|avoid|don't|without)\b", re.I)


def scope_status(text, start, goals, reference, dense_gt, tolerance=.2, epsilon=1e-4):
    points = [start] + list(goals) + list(reference) + list(dense_gt)
    if not points or any(len(p)!=3 or any(not math.isfinite(float(v)) for v in p) for p in points):
        return 'excluded', ['invalid_source_positions'], {}
    ys = [float(p[1]) for p in points]
    info = {'height_range_m':max(ys)-min(ys),
            'max_height_from_start_m':max(abs(y-start[1]) for y in ys)}
    reasons = []
    vertical = VERTICAL.search(text)
    if vertical and not NEGATION.search(text):
        reasons.append('explicit_vertical_instruction')
    if reasons:
        return 'excluded', reasons, info
    if info['height_range_m'] > tolerance+epsilon or info['max_height_from_start_m'] > tolerance+epsilon:
        reasons.append('height_variation_requires_single_floor_review')
    if AMBIGUOUS.search(text) or (vertical and NEGATION.search(text)):
        reasons.append('ambiguous_vertical_language_requires_review')
    if reasons:
        return 'review', reasons, info
    return 'candidate', [], info


def distances(adjacency, start):
    result = [math.inf]*len(adjacency); result[start] = 0.
    queue = [(0., start)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != result[node]: continue
        for other, length in adjacency[node]:
            new = cost+length
            if new < result[other]:
                result[other]=new;heapq.heappush(queue,(new,other))
    return result


def preview_rssi(position, ap, geodesic, shadow, config):
    if not math.isfinite(geodesic): return None
    horizontal=max(math.hypot(position[0]-ap[0],position[2]-ap[2]),1.)
    excess=max(0.,geodesic-horizontal)
    return (config['reference_rssi_dbm_at_1m']-10*config['path_loss_exponent']*math.log10(horizontal)
            -min(config['max_obstruction_penalty_db'],excess*config['obstruction_db_per_excess_meter'])+shadow)


def route_metrics(values, lengths, weak=-67., outage=-75.):
    total = sum(lengths); weak_m=outage_m=0.
    if len(lengths)!=max(0,len(values)-1): raise ValueError('Route dimensions do not match')
    if any(v is None for v in values): return {'available':False,'length_m':total}
    for i,length in enumerate(lengths):
        value=(values[i]+values[i+1])/2
        weak_m+=length*(value<weak);outage_m+=length*(value<outage)
    return {'available':True,'length_m':total,'weak_length_m':weak_m,'outage_length_m':outage_m,
            'outage_length_ratio':outage_m/total if total else None,
            'minimum_dbm':min(values) if values else None}
