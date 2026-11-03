#!/usr/bin/env bash
# Run under nohup; model files, PID and logs belong in WiFiNav_runtime.
set -euo pipefail
task_project_dir="$(cd "$(dirname "$0")/.." && pwd)"
task_runtime_dir="$HOME/WiFiNav_runtime"
task_python="/opt/anaconda3/envs/vllm/bin/python"
mkdir -p "$task_runtime_dir/logs" "$task_runtime_dir/manifests"
export HF_HOME="$task_runtime_dir/hf-cache"
export HF_HUB_DISABLE_XET=1
export WIFINAV_DOWNLOAD_WORKERS="${WIFINAV_DOWNLOAD_WORKERS:-16}"
# Use only the already running local proxy; no system proxy settings changed.
HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 \
  "$task_python" -u "$task_project_dir/scripts/download_model.py" \
  > "$task_runtime_dir/logs/model_download.log" 2>&1
exec "$task_python" -u "$task_project_dir/scripts/serve_model.py"
