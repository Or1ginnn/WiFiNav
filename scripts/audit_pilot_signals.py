"""Check frozen AP fields at seeded navigable probes outside policy execution."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import habitat_sim
import numpy as np
from connectivity_vln.navigation.task import PROJECT, load_json
from connectivity_vln.signal_simulation.route_a import SignalField


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch_dir.resolve()
    manifest = load_json(batch / "manifest.json")
    paths = load_json(PROJECT / "configs/data/server_paths.json")
    audits = []
    for episode in manifest["episodes"]:
        pf = habitat_sim.PathFinder()
        navmesh = (PROJECT / paths["scene_dataset_root"] / episode["scene_id"]).with_suffix(".navmesh")
        if not pf.load_nav_mesh(str(navmesh)):
            raise RuntimeError("Could not load probe navmesh")
        pf.seed(902026 + int(episode["episode_id"]))
        points = [pf.get_random_navigable_point() for _ in range(256)]
        floor = episode["layouts"][0]["ap_floor_position"][1]
        points = [np.asarray(point) for point in points if np.isfinite(point).all() and abs(point[1]-floor) <= 0.25][:32]
        if not points:
            raise RuntimeError("No valid same-floor probes")
        for layout in episode["layouts"]:
            field = SignalField(pf, episode["scene_id"], layout["ap_floor_position"], layout["wireless_config"])
            samples = []
            for index, point in enumerate(points):
                query = habitat_sim.ShortestPath()
                query.requested_start = np.asarray(layout["ap_floor_position"])
                query.requested_end = point
                if not pf.find_path(query) or not np.isfinite(query.geodesic_distance):
                    continue
                first = field.query(point, index)
                second = field.query(point, index)
                if first != second or not np.isfinite(first["rssi_measured_dbm"]):
                    raise RuntimeError("Signal field was not finite and reproducible")
                samples.append({"position": point.tolist(), **first})
            audits.append({"episode_id": episode["episode_id"], "layout_id": layout["layout_id"],
                           "probe_count": len(samples), "repeated_queries_identical": True,
                           "weak_fraction": sum(s["weak"] for s in samples)/len(samples) if samples else None,
                           "outage_fraction": sum(s["outage"] for s in samples)/len(samples) if samples else None,
                           "samples": samples})
    report = {"purpose": "fixed_field_probe_audit_not_policy_evaluation_or_layout_selection",
              "case_count": len(audits), "query_count": sum(r["probe_count"] for r in audits),
              "all_repeated_queries_identical": True, "cases": audits}
    (batch / "signal_probe_audit.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    main()
