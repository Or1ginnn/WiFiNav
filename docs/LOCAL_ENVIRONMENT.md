# 本机环境与服务器接入记录

> 仅记录项目运行和后续连接服务器所需的信息。最近整理：2026-11-04（服务器信息由用户提供，本机软件版本沿用先前记录）。服务器已SSH连接并盘点，未核实字段明确留空待补；请勿在此文件填写密码、私钥内容或令牌。

## 本机信息

| 项目 | 当前记录 |
|---|---|
| 设备/架构 | Apple Silicon，`arm64` |
| 系统 | macOS 15.7.9；内核 Darwin 24.6.0 |
| 项目目录 | `/Users/sqysmac/Desktop/code/WIFI+Nav` |
| Git | Apple Git 2.50.1 (`/usr/bin/git`) |
| Python | `/usr/bin/python3`，Python 3.9.6 |
| Conda | 已安装：`/Users/sqysmac/miniconda3/bin/conda`；项目环境待建立/核实 |
| SSH 客户端 | OpenSSH 9.9p2，LibreSSL 3.3.6 |
| Git 仓库 | 2026-11-04 已初始化本地 Git，分支 `main`；托管为 `https://github.com/Or1ginnn/WiFiNav`（用户确认公开） |
| 项目代码/依赖 | 当前目录未发现；待选定 VLN 基线、Habitat 与信号仿真方案后确定 |

当前按 zero-shot 方案规划，不为新增连通性任务额外训练或微调导航模型。算力主要用于预训练模型推理、仿真渲染、覆盖图生成和批量评测；具体显存与耗时取决于最终基线和场景规模，待小样例实测。Sionna RT 官方支持 LLVM CPU 后端；本机能否顺利安装运行仍需验证，批量射线追踪可安排在 Linux GPU 服务器。

## 服务器登记表（2026-11-04已连接核实）

2026-11-03 最新信息：用户报告有4×RTX4090（每卡24GB，合计96GB）。已由用户确定部署 Qwen3.5-35B-A3B 多模态MoE进行冻结推理；首选vLLM，固定权重已下载校验，图文服务验收通过，旗舰API作为后续可选对照。模型服务、Habitat仿真、感知和信号场需分配显存；GPU同机、拓扑、显存和主机内存已核实，见下表。

| 项目 | 记录 |
|---|---|
| 服务器用途 / 负责人 | 待确认 |
| 操作系统 / 版本 | Ubuntu22.04.5 LTS / Linux6.8.0-138-generic x86_64 |
| GPU / 驱动 / CUDA | 4×4090，每卡24564MiB；驱动595.99.02；vLLM环境torch2.11.0+cu130；PCIe SYS/NODE，无NVLink；开始时各卡已用约1.3GiB，保留已有进程 |
| 内存 / 磁盘 | 内存503GiB；/dev/sda2约17T、可用7.6T（盘点时） |
| SSH 主机 / HostName | `10.161.4.51`（用户提供；属于内网地址，网络可达性待核实） |
| 用户名 / 端口 | `sunqiuyi` / `22` |
| 项目远端路径 | `/mnt/data/suiqiuyi/WiFiNav`；实际家目录 `/mnt/data/suiqiuyi`（与用户名拼写不同） |
| 数据集路径 / 挂载 | 待确认 |
| checkpoints / outputs 路径 | `/mnt/data/suiqiuyi/WiFiNav_runtime/{models,logs,manifests,hf-cache,vllm-cache}`；位于checkout外 |
| Python / Conda 环境 | /opt/anaconda3；复用现有vllm环境：Python3.10.20/vLLM0.25.0/transformers5.13.1/torch2.11.0+cu130；不改共享包 |
| 代码同步方式 | 本机提交并push至GitHub；服务器盘点后pull，服务器代码修改使用独立分支 |
| 任务提交与日志查看 | 待确认：交互式、作业调度器或容器 |
| 备份与权限 | 待确认 |

连接命令：`ssh -p 22 sunqiuyi@10.161.4.51`。用户提供的认证信息不写入项目、命令脚本或Git；SSH配置与认证保留在本机。现已登录并完成初始项目同步。旧工作目录已原样保留在下述备份目录，未覆盖旧文件。

首次同步状态：本机已合并远端初始历史（`0f6ade2`），未强制覆盖。首次push曾被自动审批拒绝；用户随后明确授权研究计划、历史文档、两份参考PDF和全部现有历史公开。现已成功推送至GitHub（首轮推送HEAD为 `d406195`），main跟踪origin/main。服务器已克隆当前main；后续按干净工作区fast-forward同步。

## 目录与同步约定

| 位置 | 用途与维护方式 |
|---|---|
| 本机 `/Users/sqysmac/Desktop/code/WIFI+Nav` | 默认编辑、文档与提交入口 |
| GitHub `Or1ginnn/WiFiNav` | 用户确认公开托管；主分支main，作为两机同步来源 |
| 服务器 `~/WiFiNav` | 运行checkout；首次同步前盘点，不覆盖已有文件 |
| 服务器模型/数据/运行产物目录 | 规划放在项目外；尚未创建，结合已有磁盘布局确定后记录 |

本机提交后push；服务器确认工作区干净再pull。服务器需要改代码时建立分支并提交后合并。大模型、数据、认证和完整运行产物不纳入Git。不要双向rsync覆盖代码，也不要在已有非空目录强行clone。

## 当前部署配置（已通过基础图文验收）

- 模型：`Qwen/Qwen3.5-35B-A3B`；模型revision、引擎版本与精度在首次部署时登记。
- 首轮：四卡分片BF16、单请求、8K上下文、限制图片预算；仅权重粗算约70GB，不代表运行峰值，需实测与仿真共存。
- 显存不足时先缩短上下文/图像预算，再核验兼容量化方案；不承诺预先可用2卡或具体吞吐。
- 模型服务与Habitat分环境，通过网络接口连接；数据、模型和输出实际目录待接入后填写。
- 当前服务：`http://127.0.0.1:8010/v1`，模型别名`wifinav-qwen35b`；四卡BF16/8K/单请求/85%显存预留。
- 2026-11-04文本、单图、双图请求通过；详细响应/延迟与启动兼容修复见 [现场记录](experiments/server_bootstrap_2026-11-04.md)。
- 最新任务顺序与验收以根目录 `plan.md` 的T0/E0–E8为准；具体任务及benchmark尚未确定。

## 接入检查清单

- [ ] 确认服务器允许的登录方式、账号、主机名/端口和使用范围。
- [ ] 配置 SSH 主机别名；认证材料留在本机受保护位置或 SSH agent，不提交到项目。
- [x] 记录服务器系统、GPU、驱动、CUDA、存储挂载与可用空间；配额如另有限制待补。
- [ ] 确认项目远端路径、数据路径、日志/模型输出路径及备份策略。
- [x] 决定源码同步方式，并建立仓库/分支和代码版本记录。
- [x] 复用现有环境并确认导入/设备可见性；Habitat0.3.0空场景GPU渲染通过。
- [x] 模型服务文本/单图/双图请求及日志保存通过；任务数据读取与导航验收待T0确定任务后开展。
- [x] 将实际命令、结果和限制补到本文件、部署现场记录及 `plan.md`。

## 更新记录

### 2026-11-04

- 登记用户提供的SSH主机、用户名、端口和远端 `~/WiFiNav` 路径；尚未验证连接。
- 初始化当前电脑项目的本地Git（main），新增忽略规则；远端托管为 `https://github.com/Or1ginnn/WiFiNav`（用户确认公开）。

### 2026-11-03

- 同步用户已确定的Qwen3.5-35B-A3B模型与初始部署预算，明确尚未接入或运行。

- 登记用户提供的4×4090硬件信息，明确未经服务器实测；部署方案重新评估本地开放模型，不再默认只能使用付费API。

### 2026-11-02

- 记录本机系统、架构、Git、Python、Conda 和 SSH 客户端版本。
- 确认项目目录尚无 Git 元数据、代码和依赖清单。
- 服务器字段保持待确认，避免把未核实配置写成事实。
- 检查后移除旧 X-NavDP 主线描述，环境需求改为根据当前 VLN 方案确定。

## 2026-11-04 现场盘点与备份

- 主机：ubuntu-MZF2-AC0-00；SSH现有认证可用，无需将密码写入脚本。
- 旧checkout：main=2820826，存在旧研究提交和全部tracked工作文件被删除的状态。**这些状态未被reset或合并进新研究主线。**
- 完整快照：`/mnt/data/suiqiuyi/WiFiNav_backups/pre_sync_20261103T161055Z.tar.gz`（文件名为服务器UTC时间）。SHA256：`37e9ec6d0c878c42a0fc34c5edd1c88f3d2acf82756ded6a6f05baa64874a2a7`。
- 原目录移存：`/mnt/data/suiqiuyi/WiFiNav_backups/original_checkout_20261103T161055Z`，包括.git和原工作区状态。
- 新checkout：在约定的 `~/WiFiNav` 从托管仓库重新克隆，初始HEAD=fc63bfa。
- Git原配置代理指向未监听的127.0.0.1:7894。仅本次Git命令使用 `-c http.proxy=http://127.0.0.1:7890`，未改全局配置。模型下载也需使用已存在的7890代理，HuggingFace直连超时。

### 可复用Habitat环境

| 环境 | Python | 已知版本 / 状态 |
|---|---|---|
| /opt/anaconda3/envs/habitat0.3.0 | 3.9.23 | sim/lab0.3.0；import通过；lab源码来自CFRP/third_party，不移动该来源 |
| /opt/anaconda3/envs/habitat0.2.4 | 3.9.23 | sim0.2.4/lab0.2.420230405；import通过 |
| /opt/anaconda3/envs/habitat0.1.7 | 3.10.20 | sim0.1.7已安装；完整任务兼容性未验证 |
| /opt/anaconda3/envs/habitat0.1.7_fixed | 3.8.20 | 环境存在；包与功能待核实 |

先保留这些环境，任务确定后选对应版本；本次不重装Habitat。habitat0.3.0已在scene=NONE完成GPU/EGL渲染，返回64×64×4；未运行任务场景或导航。现有vllm环境为共享环境，本次只读复用，不升级包。

### 已完成的模型下载与兼容处理

- 固定HF revision：`59d61f3ce65a6d9863b86d2e96597125219dc754`。14个权重分片，文件总量71,903,878,016字节。
- 官方ModelScope同模型的全部权重SHA256与固定HF版本逐项匹配后，采用国内直连传输；每个分片落盘后再计算SHA256，核验成功才作为有效权重使用。配置、tokenizer等小文件仍来自固定HF版本。
- 下载与服务日志分别在runtime/logs；下载完成清单在runtime/manifests/model_download.json。仅目录或分片存在不代表部署完成。
- 复用vLLM0.25.0已确认注册Qwen3_5MoeForConditionalGeneration。SSH非登录会话需在服务进程设置vLLM环境的lib目录到LD_LIBRARY_PATH，才能加载已安装的FFmpeg/torchcodec；验证帮助入口可用，未安装或升级包。

### 服务运行状态与资源边界

- 14个分片下载及完整SHA256校验完成；文本/单图/双图均返回正确的验收响应。
- 服务以nohup常驻；PID记录在 `~/WiFiNav_runtime/model_service.pid`。未设置开机自启/自动重启，重启前先检查PID与端口，避免重复实例。
- CUDA13源路径为 `~/CFRP/toolchains/cuda-13.0`，服务使用runtime/toolchains/cuda-13.0软链接布局；原工具链未更改。PATH补入现有vLLM bin以找到ninja，动态库路径也仅对服务进程设置。
- GPU显存已主要用于该四卡服务并叠加其他已有进程；不是两卡空闲的部署。后续仿真并发需重新核实和安排，不能沿用部署前空闲量。

### 最终文档同步状态

部署代码81f00f9已在GitHub与服务器同步，服务器工作区干净，服务/health返回200。最终运维验收文档的公开push被自动审批拒绝，等待用户确认新增运维信息可公开；当前详细收尾记录仅在本机Git中，未将其记作GitHub/服务器已同步。
