#!/usr/bin/env python3
"""Independently check a benchmark manifest, its sampled routes, and its coverage."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random

from install_hm3d_train import PROJECT, sha256


def physical_check(finder, route, floor_y, floor_tolerance):
    import habitat_sim
    import numpy as np

    for a, b in zip(route, route[1:]):
        a, b = sorted((a, b))
        length = math.dist(a, b)
        query = habitat_sim.ShortestPath()
        query.requested_start = np.asarray(a, dtype=np.float32)
        query.requested_end = np.asarray(b, dtype=np.float32)
        if not finder.find_path(query) or query.geodesic_distance > length + .025:
            raise ValueError("A route segment is inconsistent with native Habitat routing")
        for point in np.linspace(a, b, max(1, math.ceil(length / .009375)) + 1, dtype=np.float32):
            surface = finder.snap_point(point)
            if (not np.isfinite(surface).all() or abs(surface[1] - floor_y) > floor_tolerance + 1e-5
                    or math.hypot(surface[0] - point[0], surface[2] - point[2]) > .025):
                raise ValueError("A route segment leaves the verified floor or navigable surface")


def audit(manifest_path):
    import habitat_sim

    manifest = json.loads(manifest_path.read_bytes())
    config = manifest["config"]
    population = []
    totals = Counter()
    categories = Counter()
    difficulty = Counter()
    material_cases = 0
    for scene in manifest["scenes"]:
        scan = scene["scene"]
        for filename, expected in scene["files"].items():
            if sha256(manifest_path.with_name(filename)) != expected:
                raise ValueError(f"Changed artifact: {filename}")
        geometry = json.loads(manifest_path.with_name(f"{scan}.geometry.json").read_bytes())
        screened = {row["source_row"]: row["status"] for row in geometry["scope_audit"]}
        if len(geometry["scope_audit"]) != scene["source_episodes"] or set(screened) != set(range(scene["source_episodes"])):
            raise ValueError(f"Incomplete or duplicate source rows in {scan}")
        chosen = {key for key, status in screened.items() if status == "selected"}
        if chosen != {t["source_row"] for t in scene["tasks"]} or len(chosen) != len(scene["tasks"]):
            raise ValueError(f"Source eligibility and manifest disagree in {scan}")
        totals.update(screened.values())
        if not chosen:
            continue
        finder = habitat_sim.PathFinder()
        asset = PROJECT / "data/scene_datasets" / scene["source_ref"]
        if not finder.load_nav_mesh(str(asset.with_suffix(".navmesh"))):
            raise ValueError(f"Cannot verify navmesh for {scan}")
        for fid, floor in geometry["floors"].items():
            ap, = floor["candidates"]
            if not finder.is_navigable(ap["xyz"]) or abs(ap["xyz"][1] - floor["y"]) > config["floor_tolerance_m"]:
                raise ValueError(f"Invalid AP anchor in {scan}/{fid}")
        by_key = {str(task["source_row"]): task for task in geometry["tasks"]}
        for filename in (f"{scan}.rssi_reference.json", f"{scan}.cross_reference.json"):
            bundle = json.loads(manifest_path.with_name(filename).read_bytes())
            if not bundle["independent_solver_checked"] or set(bundle["tasks"]) != set(by_key):
                raise ValueError(f"Unverified or incomplete routes: {filename}")
            for key, result in bundle["tasks"].items():
                task = by_key[key]
                floor = geometry["floors"][task["floor"]]
                ap, = floor["candidates"]
                route = result[ap["id"]]
                if (route["objective_um"] > route["baseline_objective_um"]
                        or any(math.dist(route["route_xyz"][i], task["route_xyz"][i]) > .005 for i in (0, -1))):
                    raise ValueError(f"Invalid objective or route endpoint: {scan}:{key}")
                tolerance = config["floor_tolerance_m"]
                physical_check(finder, route["route_xyz"], floor["y"], tolerance)
                physical_check(finder, route.get("baseline_route_xyz", task["route_xyz"]), floor["y"], tolerance)
        for task in scene["tasks"]:
            categories[task["category"]] += 1
            difficulty[task["communication_difficulty"]] += 1
            material_cases += task["signal_changes_route_materially"]
            population.append((scan, task["source_row"]))
        print(f"Audited {scan}: {len(chosen)} tasks", flush=True)

    if (len(set(population)) != manifest["qualified_episodes"] or sum(totals.values()) != manifest["source_episodes"]
            or totals["selected"] != manifest["qualified_episodes"]):
        raise ValueError("Benchmark census and manifest disagree")
    review = [(row["scene"], row["source_row"]) for row in manifest["review_sample"]]
    expected = random.Random(manifest["rules"]["review_seed"]).sample(population, len(review))
    if review != expected or len(review) != min(manifest["rules"]["review_count"], len(population)):
        raise ValueError("Review subset is not the configured random sample")
    return {
        "passed": True, "scope": manifest["scope"], "manifest_sha256": sha256(manifest_path),
        "source_scenes": len(manifest["scenes"]), "source_episodes": manifest["source_episodes"],
        "qualified_episodes": len(population), "qualified_floors": sum(s["floors"] for s in manifest["scenes"]),
        "screening": dict(totals), "per_category": dict(categories), "communication_difficulty": dict(difficulty),
        "material_signal_route_differences": material_cases, "random_review_tasks": len(review),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (PROJECT / "runtime") not in args.output.resolve().parents or args.output.exists():
        parser.error("Expected a new audit file under runtime")
    result = audit(args.manifest)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(result, flush=True)


if __name__ == "__main__":
    main()
