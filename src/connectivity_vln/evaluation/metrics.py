"""Offline R2R-CE diagnostics. GT locations never enter the policy input."""
import gzip
import math

import numpy as np


def exact_ndtw(positions, reference, success_distance):
    # Same Euclidean local cost/normalization as VLN-CE NDTW; exact DP, not fastdtw.
    previous = np.full(len(reference) + 1, np.inf)
    previous[0] = 0
    for point in positions:
        current = np.full(len(reference) + 1, np.inf)
        for j, other in enumerate(reference, 1):
            current[j] = np.linalg.norm(np.array(point) - other) + min(previous[j], current[j-1], previous[j-1])
        previous = current
    return math.exp(-float(previous[-1]) / (len(reference) * success_distance))


def evaluate(env, trajectory, gt_locations, settings):
    positions = [trajectory[0]["pose"]["position"]]
    for step in trajectory[1:]:
        point = step["pose"]["position"]
        if point != positions[-1]:
            positions.append(point)
    result = dict(env.get_metrics())
    result["path_length_m"] = sum(float(np.linalg.norm(np.array(b)-a)) for a,b in zip(positions, positions[1:]))
    result["ndtw_exact_euclidean"] = exact_ndtw(positions, gt_locations, settings["success_distance_m"])
    result["sdtw_exact_euclidean"] = result["success"] * result["ndtw_exact_euclidean"]
    result["primitive_actions_including_stop"] = len(trajectory) - 1
    result["collision_actions"] = sum(step.get("collision", False) for step in trajectory[1:])
    result["start_to_goal_geodesic_m"] = trajectory[0]["evaluation_only_metrics"]["distance_to_goal"]
    return result
