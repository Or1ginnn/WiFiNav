# 项目内资产整理（2026-11-04）

用户要求主要操作集中于服务器项目目录，任务、场景、模型均使用实际文件。项目根目录为 `/mnt/data/suiqiuyi/WiFiNav`。

## 目录约定

```text
WiFiNav/
├── configs/、scripts/、docs/、plan.md   # Git维护
├── data/                             # Git忽略，原始资产副本
│   ├── datasets/R2R_VLNCE_v1-3_preprocessed/
│   ├── scene_datasets/mp3d/
│   └── _manifests/raw_assets_copy.json
├── models/Qwen3.5-35B-A3B/            # Git忽略，实际权重与配置
└── runtime/                          # Git忽略
    ├── logs/
    ├── manifests/
    ├── hf-cache/
    ├── vllm-cache/
    ├── toolchains/cuda-13.0/
    └── model_service.pid
```

- 原始数据372个文件、22,604,101,582字节全部复制并与来源SHA256/大小比对，通过独立inode与无链接检查。来源未修改，详细规模与限制见[数据说明](../DATASETS.md)。
- 模型和runtime由原 `~/WiFiNav_runtime` 在同一文件系统直接重命名移入项目，未重复下载或创建兼容软链接；旧runtime路径不再使用。模型14个权重分片共71,903,878,016字节，迁移后重新计算SHA256，全部与固定revision下载清单一致；模型目录无软链接。
- 模型revision保持 `59d61f3ce65a6d9863b86d2e96597125219dc754`，服务参数保持四卡BF16/8K/单请求/85%显存预留，API `http://127.0.0.1:8010/v1`。
- 仅停止经PID、命令行与旧模型路径核实的本项目服务71892；新服务PID250364。历史验收保留为 `runtime/manifests/service_probe.before_relocation.json`。
- 迁移清单：`runtime/manifests/project_storage_migration.json`；新日志：`runtime/logs/model_service_after_relocation.log`；下载清单中的模型path已更新为项目内实际路径。
- 共享Conda环境、Habitat editable源码、FlashInfer共享编译缓存（~/.cache/flashinfer）与原CUDA工具链继续复用，不移动共享依赖。runtime/toolchains仅是编译器布局适配，含指向已有CUDA工具链的链接；任务/场景/模型本身均为实际文件。旧项目备份保持 `~/WiFiNav_backups`。

## 日常操作

登录后先 `cd ~/WiFiNav`，从项目根目录使用配置与脚本。源码修改先本机提交，经GitHub快进同步；data/models/runtime不上传GitHub，也不将72GB权重复制到Mac。

服务未运行时启动（先核查PID与端口，避免重复启动）：

```bash
cd ~/WiFiNav
mkdir -p runtime/logs
nohup /opt/anaconda3/envs/vllm/bin/python -u scripts/serve_model.py \
  > runtime/logs/model_service.log 2>&1 < /dev/null &
echo $! > runtime/model_service.pid
```

查看日志：`tail -n 80 runtime/logs/model_service.log`（本次迁移启动日志使用after_relocation文件名）。服务验收：`/opt/anaconda3/envs/vllm/bin/python scripts/probe_model.py`，结果写入 `runtime/manifests/service_probe.json`。

## 迁移后验收

健康端点HTTP200；`/v1/models`返回的root为 `/mnt/data/suiqiuyi/WiFiNav/models/Qwen3.5-35B-A3B`。文本返回READY（2.394秒）；单图正确识别红色方形（1.897秒）；双图按顺序正确识别红色方形、蓝色圆形（2.106秒）。三项finish_reason均为stop。完整响应与usage保存在 `runtime/manifests/service_probe.json`。这些是单次验收耗时，不代表稳定吞吐。资产整理不等于真实场景加载、导航或R2R-Conn生成已完成；下一步继续B0导航实现与Habitat场景适配。
