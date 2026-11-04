"""Download a fixed public checkpoint into the project models directory."""
import json
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor
import subprocess
import urllib.request
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

project = Path(__file__).resolve().parents[1]
config = json.loads((project / "configs/model/qwen35b.json").read_text())
runtime = (project / Path(config["runtime_root"]).expanduser()).resolve()
target = (project / Path(config["model_path"]).expanduser()).resolve()
manifest_dir = runtime / "manifests"
manifest_dir.mkdir(parents=True, exist_ok=True)
source = os.environ.get("WIFINAV_DOWNLOAD_SOURCE", "huggingface")
patterns = ["*.json", "*.jinja", "*.txt", "*.model", "LICENSE*", "README.md"]
if source == "huggingface":
    patterns.append("*.safetensors")
snapshot_download(
    repo_id=config["model_id"],
    revision=config["revision"],
    local_dir=str(target),
    max_workers=int(os.environ.get("WIFINAV_DOWNLOAD_WORKERS", "8")),
    allow_patterns=patterns,
)
verified = {}
if source == "modelscope":
    # HF revision remains authoritative; the alternate transport must match its
    # size and SHA256 for every weight shard before it is used.
    info = HfApi().model_info(config["model_id"], revision=config["revision"], files_metadata=True)
    weights = [item for item in info.siblings if item.rfilename.endswith(".safetensors")]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("https://modelscope.cn/api/v1/models/Qwen/Qwen3.5-35B-A3B/repo/files?Recursive=true", timeout=30) as response:
        mirror = json.load(response)
    mirror_files = {item["Path"]: item for item in mirror["Data"]["Files"]}
    for item in weights:
        other = mirror_files[item.rfilename]
        if not item.lfs or other["Sha256"] != item.lfs.sha256 or other["Size"] != item.size:
            raise RuntimeError(f"Mirror does not match pinned HF revision: {item.rfilename}")

    def download_weight(item):
        name = item.rfilename
        output = target / name
        partial = target / (name + ".part")
        expected = item.lfs.sha256
        if not output.exists():
            url = f'https://modelscope.cn/models/{config["model_id"]}/resolve/master/{name}'
            subprocess.run(["curl", "--noproxy", "*", "--fail", "--location", "--silent", "--show-error",
                            "--retry", "5", "--retry-delay", "2", "--connect-timeout", "20",
                            "--speed-limit", "1024", "--speed-time", "90", "--continue-at", "-",
                            "--output", str(partial), url], check=True)
            candidate = partial
        else:
            candidate = output
        if candidate.stat().st_size != item.size:
            raise RuntimeError(f"Wrong weight size: {name}")
        digest = hashlib.sha256()
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError(f"Weight SHA256 mismatch: {name}")
        if candidate == partial:
            partial.rename(output)
        print(f"Verified {name}: {item.size} bytes sha256={expected}", flush=True)
        return name, expected

    with ThreadPoolExecutor(max_workers=8) as pool:
        verified = dict(pool.map(download_weight, weights))
index = json.loads((target / "model.safetensors.index.json").read_text())
shards = sorted(set(index["weight_map"].values()))
for shard in shards:
    if not (target / shard).is_file():
        raise RuntimeError(f"Missing model shard: {shard}")
manifest = {
    "model_id": config["model_id"],
    "revision": config["revision"],
    "path": str(target),
    "source": source,
    "shards": [{"name": name, "bytes": (target / name).stat().st_size, "sha256": verified.get(name)} for name in shards],
}
(manifest_dir / "model_download.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2), flush=True)
