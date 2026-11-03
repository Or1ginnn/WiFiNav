"""Launch the project model service without changing shared Conda packages."""
import json
import os
from pathlib import Path

project = Path(__file__).resolve().parents[1]
config = json.loads((project / "configs/model/qwen35b.json").read_text())
runtime = Path(config["runtime_root"]).expanduser()
if not (runtime / "manifests/model_download.json").exists():
    raise SystemExit("Download manifest missing; run download_model.py first")
model = runtime / "models/Qwen3.5-35B-A3B"
args = [
    config["python"], "-m", "vllm.entrypoints.openai.api_server",
    "--model", str(model),
    "--served-model-name", config["served_model_name"],
    "--host", config["host"], "--port", str(config["port"]),
    "--dtype", config["precision"],
    "--tensor-parallel-size", str(config["tensor_parallel_size"]),
    "--max-model-len", str(config["max_model_len"]),
    "--max-num-seqs", str(config["max_num_seqs"]),
    "--max-num-batched-tokens", str(config["max_model_len"]),
    "--gpu-memory-utilization", str(config["gpu_memory_utilization"]),
    "--limit-mm-per-prompt", json.dumps({"image": config["max_images_per_request"], "video": 0}),
    "--mm-processor-kwargs", json.dumps({"max_pixels": config["max_image_pixels"]}),
    "--reasoning-parser", "qwen3",
    "--default-chat-template-kwargs", '{"enable_thinking":false}',
    "--enforce-eager",
    "--disable-custom-all-reduce",
]
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0,1,2,3")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HOME", str(runtime / "hf-cache"))
os.environ.setdefault("VLLM_CACHE_ROOT", str(runtime / "vllm-cache"))
# SSH non-login shells do not activate Conda's shared-library search path.
library_dir = str(Path(config["python"]).parents[1] / "lib")
os.environ["LD_LIBRARY_PATH"] = library_dir + (
    ":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else ""
)
print("Starting model service", json.dumps(args), flush=True)
os.execv(config["python"], args)
