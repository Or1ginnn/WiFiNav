# 服务器基础设施部署记录

> 下文保留首次部署时的目录和验收事实。此后用户要求资产移入项目，当前路径与重启记录以[项目内存储整理](project_storage_2026-11-04.md)为准；旧WiFiNav_runtime已实际迁移。

日期：2026-11-04（北京时间）。范围：目录盘点、Git同步、硬件/已有环境确认、Qwen3.5-35B-A3B模型服务。**不冻结导航任务，不运行benchmark。**

## 已完成的基础设施工作

- SSH可用；实际家目录为 `/mnt/data/suiqiuyi`，与用户名 `sunqiuyi` 拼写不同。
- 主机Ubuntu22.04.5，4×RTX4090（每卡24564MiB），驱动595.99.02，内存503GiB，盘点时磁盘可用约7.6T。GPU通过PCIe/SYS/NODE连接，无NVLink。
- 旧 `~/WiFiNav` 存在旧研究提交及已删除工作文件；完整归档与原目录均保存到 `~/WiFiNav_backups`，未reset、覆盖或删除旧历史。具体路径和哈希见 [环境记录](../LOCAL_ENVIRONMENT.md)。
- 在原约定路径重新克隆当前GitHub项目；以干净工作区的 `pull --ff-only` 同步后续变更。
- Habitat0.2.4和0.3.0导入通过；0.3.0完成scene=NONE的GPU/EGL空场景渲染，返回64×64×4。这不代表某数据集或导航任务已跑通。
- 复用现有vLLM环境（Python3.10.20、vLLM0.25.0、transformers5.13.1、torch2.11.0+cu130）；未安装、升级或删除共享环境包。

## 模型配置与文件来源

- 模型：`Qwen/Qwen3.5-35B-A3B`，固定revision `59d61f3ce65a6d9863b86d2e96597125219dc754`。
- 14个权重分片，总文件量71,903,878,016字节。
- 小文件从HF固定版本获取；官方ModelScope权重需逐项匹配HF固定版本的SHA256与大小，再下载并重新计算完整文件SHA256，全部通过才生成可用清单。
- Git已有代理配置失效，使用单次命令代理7890获取Git/HF元信息；ModelScope直连。未修改全局代理。
- SSH非登录会话缺少共享库路径，服务进程补充已有Conda环境的lib路径以加载FFmpeg/torchcodec；没有用重装包处理。

服务参数以 [配置](../../configs/model/qwen35b.json) 和 [启动脚本](../../scripts/serve_model.py) 为准。初始为四卡BF16、8K上下文、单请求、限制图片预算、关闭思考输出、eager执行；它是资源受限的部署配置，不等同于官方长上下文/长思考评测协议。

## 服务器目录与操作入口

```text
/mnt/data/suiqiuyi/
├── WiFiNav/                         # Git checkout，只放代码、配置、文档
├── WiFiNav_backups/                 # 原checkout与首次完整快照
└── WiFiNav_runtime/                 # 项目运行资产，不进入Git
    ├── models/Qwen3.5-35B-A3B/
    ├── hf-cache/
    ├── vllm-cache/
    ├── toolchains/cuda-13.0/         # 指向现有CUDA13的标准布局软链接
    ├── logs/
    │   ├── model_download.log
    │   └── model_service.log
    └── manifests/
        ├── model_download.json      # 仅下载/校验完成后产生
        ├── vllm_environment.txt
        ├── server_inventory.json
        ├── habitat_render.json
        └── service_probe.json       # 仅图文请求验收完成后产生
```

- 下载后启动：在checkout运行 `bash scripts/bootstrap_model.sh`；常驻运行需使用nohup并将日志保存到runtime。启动前检查已有进程/端口，避免重复实例。
- 服务仅监听服务器 `127.0.0.1:8010`；不直接对外开放。Mac访问可建立SSH隧道：`ssh -N -L 8010:127.0.0.1:8010 sunqiuyi@10.161.4.51`。
- 服务接口：`http://127.0.0.1:8010/v1`，模型名称 `wifinav-qwen35b`。
- 请求验收：在服务器运行 `/opt/anaconda3/envs/vllm/bin/python scripts/probe_model.py`，保存实际响应、usage、延迟和停止原因。合成图仅检验服务能否读图，不能作为导航性能结果。

## 第4步验收结果：已完成

部署代码版本：`81f00f9`；服务进程PID记录为71892（仅当次运行标识，重启后会改变）。模型revision见上文。当前通过nohup运行，未配置开机自启或自动重启。

- 14个分片均通过固定HF版本对应的SHA256验证。
- 四卡BF16、8K上下文、单请求、85%显存预留，TP0日志报告模型加载约16.52GiB，其他rank未单独计量。
- `/health`和`/v1/models`正常；模型别名为`wifinav-qwen35b`。

| 验收请求 | 实际响应摘要 | 请求耗时 | token（输入/输出） | 结果 |
|---|---|---|---|---|
| 文本 | READY | 5.570秒 | 17 / 2 | 通过 |
| 单图 | red square | 2.398秒 | 221 / 12 | 通过 |
| 双图 | 第一张red square；第二张blue circle | 2.250秒 | 424 / 18 | 通过 |

以上每项仅1次，文本首请求日志有Triton JIT；不能作为稳定吞吐、复杂图像准确率或导航性能结论。全部响应正常stop，未达到128输出token上限。

请求后的整卡显存快照依次为22155、22153、22769、20859MiB，**包含其他进程，不是模型独占显存或严格峰值**。当前模型服务和已有GPU工作并存，批量仿真前需重新安排资源。

### 本次启动问题与处理

1. SSH未激活动态库路径：服务进程补充现有Conda的lib路径，FFmpeg/torchcodec导入恢复。
2. 初始90%显存预留略超当时空闲量：降低到85%，保留其他进程。
3. 内核编译找不到ninja：服务进程PATH补入现有Conda bin。系统默认nvcc为11.5，与torch的CUDA13不匹配；复用已有 `~/CFRP/toolchains/cuda-13.0`，在runtime/toolchains下建立标准布局软链接并设置进程CUDA_HOME。未改共享包或原工具链。
4. 前两次失败日志分别保留为 `model_service_attempt1.log` 与 `model_service_attempt2.log`，当前正常服务日志为 `model_service.log`。

原环境、CFRP中的Habitat源码和CUDA工具链均未移动或重装；本项目依赖其路径，后续如需迁移应单独导出环境/工具链，不直接删除来源目录。

## 后续研究边界

任务选择与现有benchmark调整需先调研。比较输入/成功条件、路径选择空间、通信意义、代码/数据可获得性和工作量后，再确定VLN、ObjectNav或其他设置。原始任务、通信层与服务失败模型分别定义，详见 [任务调研单](../design/task_benchmark_research_plan.md)。
