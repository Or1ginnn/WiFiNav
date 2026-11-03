"""Download a fixed public checkpoint into the external runtime directory."""
import json
from pathlib import Path

from huggingface_hub import snapshot_download

project = Path(__file__).resolve().parents[1]
config = json.loads((project / "configs/model/qwen35b.json").read_text())
runtime = Path(config["runtime_root"]).expanduser()
target = runtime / "models" / "Qwen3.5-35B-A3B"
manifest_dir = runtime / "manifests"
manifest_dir.mkdir(parents=True, exist_ok=True)
snapshot_download(
    repo_id=config["model_id"],
    revision=config["revision"],
    local_dir=str(target),
    max_workers=4,
    allow_patterns=["*.json", "*.safetensors", "*.jinja", "*.txt", "*.model", "LICENSE*", "README.md"],
)
index = json.loads((target / "model.safetensors.index.json").read_text())
shards = sorted(set(index["weight_map"].values()))
for shard in shards:
    if not (target / shard).is_file():
        raise RuntimeError(f"Missing model shard: {shard}")
manifest = {
    "model_id": config["model_id"],
    "revision": config["revision"],
    "path": str(target),
    "shards": [{"name": name, "bytes": (target / name).stat().st_size} for name in shards],
}
(manifest_dir / "model_download.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2), flush=True)
