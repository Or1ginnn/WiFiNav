"""Serial frozen-manifest NoSignal rollouts with resumable, explicit outcomes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

PROJECT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", type=Path)
    parser.add_argument("--interface-version", choices=["v0", "v1"], default="v0")
    args = parser.parse_args()
    spec = read(PROJECT / "configs/benchmark/pilot_v0.json")
    manifest_path = PROJECT / spec["manifest_path"]
    manifest = read(manifest_path)
    for name, expected in manifest["config_hashes"].items():
        if hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Frozen config changed: {name}")
    paths = read(PROJECT / "configs/data/server_paths.json")
    source = PROJECT / paths["task_dataset"] / spec["split"] / (spec["split"] + ".json.gz")
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["source_task_sha256"]:
        raise RuntimeError("Source task payload changed after freezing")
    model = read(PROJECT / spec["model_config"])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(f'http://127.0.0.1:{model["port"]}/health', timeout=10) as response:
        if response.status != 200:
            raise RuntimeError("Model service is not healthy")
    batch = args.batch_dir or PROJECT / "runtime/batches" / ("pilot_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    batch = batch.resolve()
    if not batch.is_relative_to((PROJECT / "runtime").resolve()):
        raise ValueError("Batch path must stay under project runtime/")
    batch.mkdir(parents=True, exist_ok=True)
    metadata_path = batch / "batch_metadata.json"
    if metadata_path.exists():
        if read(metadata_path).get("interface_version", "v0") != args.interface_version:
            raise RuntimeError("Resume interface version differs; use a new batch directory")
    elif any(batch.glob("episode_*")):
        raise RuntimeError("Cannot resume existing episodes without batch metadata")
    (PROJECT / "runtime/manifests/b2_active_batch.json").write_text(json.dumps({"batch_dir": str(batch)}) + "\n")
    snapshot = batch / "manifest.json"
    if snapshot.exists() and snapshot.read_bytes() != manifest_path.read_bytes():
        raise RuntimeError("Resume manifest differs from frozen batch")
    if not snapshot.exists():
        snapshot.write_bytes(manifest_path.read_bytes())
    if not metadata_path.exists():
        metadata_path.write_text(json.dumps({
            "manifest_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            "execution_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip(),
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "interface_version": args.interface_version,
            "no_signal_wireless_does_not_influence_policy": True,
        }, indent=2) + "\n")
    outcomes = []
    for episode in manifest["episodes"]:
        episode_id = episode["episode_id"]
        directory = batch / ("episode_" + episode_id)
        status_file = batch / ("episode_" + episode_id + "_status.json")
        if status_file.exists():
            outcomes.append(read(status_file))
            continue
        if directory.exists():
            raise RuntimeError(f"Unfinished attempt exists; inspect and record failure before resuming: {directory}")
        command = [sys.executable, "-u", str(PROJECT / "scripts/run_vln_episode.py"),
                   "--config", str(PROJECT / spec["navigation_config"]),
                   "--episode-id", episode_id, "--output-dir", str(directory),
                   "--interface-version", args.interface_version]
        print(f"Starting episode {episode_id} ({len(outcomes)+1}/{len(manifest['episodes'])})", flush=True)
        start = time.perf_counter()
        timed_out = False
        with (batch / ("episode_" + episode_id + ".log")).open("a") as log:
            process = subprocess.Popen(command, cwd=PROJECT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            try:
                code = process.wait(timeout=spec["maximum_episode_wall_seconds"])
            except subprocess.TimeoutExpired:
                timed_out = True
                process.terminate()
                try:
                    code = process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    code = process.wait()
        summary_path = directory / "summary.json"
        summary = read(summary_path) if summary_path.exists() else None
        status = {"episode_id": episode_id, "scene_id": episode["scene_id"], "run_dir": str(directory),
                  "return_code": code, "timed_out": timed_out, "wall_seconds": time.perf_counter()-start,
                  "summary_present": summary is not None,
                  "exit_reason": summary["exit_reason"] if summary else ("wall_time_limit" if timed_out else "missing_summary"),
                  "success": summary["metrics"]["success"] if summary else 0.0}
        status_file.write_text(json.dumps(status, indent=2) + "\n")
        outcomes.append(status)
        (batch / "progress.json").write_text(json.dumps({"completed": len(outcomes), "total": len(manifest["episodes"]), "outcomes": outcomes}, indent=2)+"\n")
        print(json.dumps(status), flush=True)
    (batch / "rollouts_complete.json").write_text(json.dumps(outcomes, indent=2)+"\n")
    print("Finished NoSignal rollouts:", batch, flush=True)


if __name__ == "__main__":
    main()
