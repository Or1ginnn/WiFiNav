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
| 数据集路径 / 挂载 | 用户要求实际副本放 `~/WiFiNav/data/datasets/R2R_VLNCE_v1-3_preprocessed` 与 `~/WiFiNav/data/scene_datasets/mp3d`，不用链接；复制/盘点结果见DATASETS.md |
| checkpoints / outputs 路径 | `~/WiFiNav/models/Qwen3.5-35B-A3B`及`~/WiFiNav/runtime/{logs,manifests,hf-cache,vllm-cache}`；已完成迁移、分片SHA256复核和图文重启验收 |
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
| 服务器任务/场景数据 | 用户要求放checkout内data/datasets与data/scene_datasets，使用独立文件，不用链接；Git忽略 |
| 服务器模型/运行产物目录 | 统一使用checkout内models/和runtime/，实际文件且Git忽略 |

本机提交后push；服务器确认工作区干净再pull。服务器需要改代码时建立分支并提交后合并。大模型、数据、认证和完整运行产物不纳入Git。任务/场景的实际文件按用户要求置于checkout内被忽略的data目录，详见[数据说明](DATASETS.md)。不要双向rsync覆盖代码，也不要在已有非空目录强行clone。

## 当前部署配置（已通过基础图文验收）

- 模型：`Qwen/Qwen3.5-35B-A3B`；模型revision、引擎版本与精度在首次部署时登记。
- 首轮：四卡分片BF16、单请求、8K上下文、限制图片预算；仅权重粗算约70GB，不代表运行峰值，需实测与仿真共存。
- 显存不足时先缩短上下文/图像预算，再核验兼容量化方案；不承诺预先可用2卡或具体吞吐。
- 模型服务与Habitat分环境，通过网络接口连接；数据、模型和运行产物统一置于项目data/、models/和runtime/；共享环境继续复用。
- 当前服务：`http://127.0.0.1:8010/v1`，模型别名`wifinav-qwen35b`；四卡BF16/8K/单请求/85%显存预留。
- 2026-11-04文本、单图、双图请求通过；详细响应/延迟与启动兼容修复见 [现场记录](experiments/server_bootstrap_2026-11-04.md)。
- 最新任务顺序与验收以根目录 `plan.md` 的T0/E0–E8为准；已确认连通性感知VLN与R2R-Conn，B0正在进行。

## 接入检查清单

- [ ] 确认服务器允许的登录方式、账号、主机名/端口和使用范围。
- [ ] 配置 SSH 主机别名；认证材料留在本机受保护位置或 SSH agent，不提交到项目。
- [x] 记录服务器系统、GPU、驱动、CUDA、存储挂载与可用空间；配额如另有限制待补。
- [ ] 确认项目远端路径、数据路径、日志/模型输出路径及备份策略。
- [x] 决定源码同步方式，并建立仓库/分支和代码版本记录。
- [x] 复用现有环境并确认导入/设备可见性；Habitat0.3.0空场景GPU渲染通过。
- [x] 模型服务文本/单图/双图请求及日志保存通过；任务JSON已盘点，真实任务场景加载与导航验收待B0后续开展。
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

按用户最新决定，优先复用现有habitat0.3.0，sim/lab均为0.3.0，本轮重新import通过；其他环境保留作为必要时的兼容候选。真实MP3D/R2R-CE任务适配通过后冻结执行版本，不重装或升级共享包。habitat0.3.0已在scene=NONE完成GPU/EGL渲染，返回64×64×4；未运行任务场景或导航。现有vllm环境为共享环境，本次只读复用，不升级包。

2026-11-05已完成真实MP3D/R2R-CE验收与首条闭环：原navmesh、448×448 RGB-D、位姿及四动作正常；模型服务常驻时单场景在GPU0增加约304MiB显存。该Habitat-Sim没有Bullet支持，不能使用碰撞射线统计墙体；路线A暂以navmesh测地绕行量作为遮挡代理，物理保真验证后置。完整结果见[B1首条闭环](experiments/b1_first_episode_2026-11-05.md)。

### 已完成的模型下载与兼容处理

- 固定HF revision：`59d61f3ce65a6d9863b86d2e96597125219dc754`。14个权重分片，文件总量71,903,878,016字节。
- 官方ModelScope同模型的全部权重SHA256与固定HF版本逐项匹配后，采用国内直连传输；每个分片落盘后再计算SHA256，核验成功才作为有效权重使用。配置、tokenizer等小文件仍来自固定HF版本。
- 下载与服务日志分别在runtime/logs；下载完成清单在runtime/manifests/model_download.json。仅目录或分片存在不代表部署完成。
- 复用vLLM0.25.0已确认注册Qwen3_5MoeForConditionalGeneration。SSH非登录会话需在服务进程设置vLLM环境的lib目录到LD_LIBRARY_PATH，才能加载已安装的FFmpeg/torchcodec；验证帮助入口可用，未安装或升级包。

### 服务运行状态与资源边界

- 14个分片下载及完整SHA256校验完成；文本/单图/双图均返回正确的验收响应。
- 服务以nohup常驻；PID记录在 `~/WiFiNav/runtime/model_service.pid`。未设置开机自启/自动重启，重启前先检查PID与端口，避免重复实例。
- CUDA13源路径为 `~/CFRP/toolchains/cuda-13.0`，服务使用runtime/toolchains/cuda-13.0软链接布局；原工具链未更改。PATH补入现有vLLM bin以找到ninja，动态库路径也仅对服务进程设置。
- GPU显存已主要用于该四卡服务并叠加其他已有进程；不是两卡空闲的部署。后续仿真并发需重新核实和安排，不能沿用部署前空闲量。

### 最终文档同步状态

新增运维记录曾被自动审批拦截，用户随后明确允许本次内网地址、用户名、实际目录/备份路径、硬件软件版本、服务端口和验收结果公开；不含密码、私钥或令牌。收尾提交af54d92现已成功推送GitHub并快进同步服务器，服务器工作区干净，服务/health返回200；授权状态记录随本次文档提交同步，无需重启服务。

## 项目内存储整理（2026-11-04）

原始资产372文件已独立复制至data/，模型14分片已实际移动至models/并重新通过SHA256核验；日志/缓存/清单和PID统一runtime/。无旧runtime兼容链接。共享环境与旧备份保持原处；日常命令与迁移验收见[整理记录](experiments/project_storage_2026-11-04.md)。

## B2执行现场（2026-11-09）

原模型服务日志显示11月7日已关闭；本轮确认没有本项目服务且GPU空闲后，按原配置恢复，PID1315140记录在runtime/model_service.pid，新日志为runtime/logs/model_service_20261109T233803.log。B2结束时health=200，共享Conda未改动。冻结清单在data/derived/r2r_conn/pilot_v0/manifest.json，批次在runtime/batches/pilot_20261109T154150Z，约726MiB；详情见[B2记录](experiments/b2_pilot_2026-11-09.md)。

本轮服务器7890代理访问GitHub连续TLS失败，直连也未响应；本机提交已正常推送GitHub，随后将同一提交制成Git bundle传输，服务器校验并仅快进合并，未改全局代理或覆盖工作区。最终同步应核对main和origin/main的commit与本机一致。

2026-11-10，导航接口 v1 继续通过 Git bundle 快进同步。复用现有 Habitat 环境与模型服务，验证数据存放于独立 `runtime/runs/interface_v1_*`，原B2 v0批次保持只读；结果见[导航接口复核](experiments/navigation_interface_v1_2026-11-10.md)。

2026-11-11完成接口v1固定10任务复跑与30AP回放：`runtime/batches/pilot_interface_v1`，执行提交`f6ff7b5`；完整日志为`runtime/logs/pilot_interface_v1.log`，配对指标为批次内`paired_comparison.json`。沿用原模型服务、Habitat和配置，未安装或升级共享环境；原v0批次未改。结果与下一步见[配对记录](experiments/b2_interface_v1_pair_2026-11-10.md)。

同日完成关闭STOP复核消融：执行提交`1c65cd6`，批次`runtime/batches/pilot_v1_no_review`，日志`runtime/logs/pilot_v1_no_review.log`，10任务/30回放，无运行异常。离线检查已验证v0/v1默认与显式on/off行为和恢复保护；消融结束后才通过bundle快进源码至`735f52b`。现有环境4项规划器单元测试通过，B3局部诊断在`runtime/batches/oracle_local_diagnostic_v0`，真实闭环在`runtime/batches/oracle_smoke_v0`；复用原模型与共享环境，未更改依赖。

B3首轮14次执行/18case已完成，无运行异常或超时；`oracle_report.json`保存完整结果，`paired_summary.json`保存版本/清单/模型输入字段审计与汇总。原B2三版批次均保留，全部回放文件数核验通过，收尾模型服务health=200；文档继续经GitHub和bundle快进同步，收益与限制见[B3记录](experiments/b3_oracle_2026-11-11.md)。

## 2026-11-12 控制器诊断

本机与服务器HEAD均为`06ebac1`且干净，模型health=200，没有导航实验进程。历史六条near轨迹只读复核，诊断JSON放`runtime/diagnostics/b3_controller_20261112/`；已确认离散前进裁剪与越出单层高度导致的问题，见[修复记录](experiments/b3_controller_repair_2026-11-12.md)。修复先在本机提交、发布再同步；真实复跑使用新目录，不覆盖原smoke。

修复提交`1128cf1`已同步，原Habitat环境6项测试通过，`oracle_smoke_action_guard_v1`完成14执行/18case、0运行异常/超时、0单层高度越界；完整验证尚未运行。新验收器与完整协议在本机准备，累计11项单元测试通过。模型服务复核health=200，共享包和模型文件未改。

## 2026-11-13 完整B3收尾

完整批次`runtime/batches/oracle_full_action_guard_v1`使用`976bd10`，北京时间11月12日23:01至13日00:44完成70次执行/90case，实际请求636次。原始数据/模型未移动，共享环境未升级。执行器边界修复有效，所有实际位姿未越出单层；两个模型无候选输出错误作为前缀保留。验收No-Go，详见[完整结果](experiments/b3_full_2026-11-12.md)。

独立会话PID1750313已结束；只读SSH连接曾被远端关闭，重连确认批次完成，未重复启动。模型原PID1315140仍在线，4卡各约21031MiB，`curl --noproxy '*' --max-time 10 http://127.0.0.1:8010/health`返回200；未因通用curl查询失败而重启服务或更改全局代理。11项测试在正式运行前通过；70个worker的提交/模型/源码hash及636条请求输入字段审计均通过。完整CSV与审计在批次目录，本机核对副本统一在runtime/previews。

## 2026-11-16 GPU资源与等待器

只读盘点确认原四卡模型已停止；其他用户计算任务在卡间变化，显存少不等于空闲，不能沿用11月13日的在线状态。开始本轮操作时服务器main=`bf38427`且干净，未检测到`squeue`命令。按用户要求准备项目四卡等待器，全部状态/日志放runtime/queue和runtime/logs，负载仅恢复模型并验收；不更改共享依赖或其他任务。部署详情与实时入口见[排队记录](experiments/gpu_queue_2026-11-16.md)。

等待器实现提交`d07ccda`已同步，本机与复用Habitat环境23项测试通过，真实GPU检查不空闲。后台PID2400316已在独立会话启动，目录`runtime/queue/restore_qwen35b_20261116`，日志`runtime/logs/gpu_queue_20261116.log`。首次状态waiting、稳定计数0/3；仅CPU等待，模型尚未启动。排到资源后沿用原四卡BF16模型并独立图文验收，源码/配置hash冻结；后续状态以队列JSON为准。

### 2026-11-17 03:00验收

旧恢复队列在00:57四卡空闲后启动，但14分片仅加载8片即超过900秒上限，01:13失败并清理自建进程；健康与图文验收未通过。当前四卡均被其他计算负载占用。仅延长新队列冷启动上限至2400秒，沿用原模型revision、TP4/BF16/8K、共享vLLM/Habitat环境，不调整其他用户任务。独立队列与后续状态见`docs/experiments/gpu_queue_2026-11-16.md`；原B3保持No-Go，修订协议见`docs/experiments/empty_recovery_2026-11-17.md`。

03:14复核：独立新队列PID2773082 waiting/0/3，源码pin匹配、health直连拒绝；原始错误CPU回放及399条路径查询已完成，均无模型/GPU调用，真实Habitat环境29测试通过。源码8047932已push后bundle快进同步；未运行新的闭环导航。

## 2026-11-18 22:47模型恢复现场核实

新队列`runtime/queue/restore_qwen35b_20261117`于北京时间11月18日03:36:27启动模型1436455，03:41:55达到ready；`attempt_001/service_probe.json`确认文本READY、单图红方形、双图红方形/蓝圆形顺序，三项finish_reason均stop。22:47直连localhost:8010的health和v1/models均200，别名wifinav-qwen35b、root为项目models/Qwen3.5-35B-A3B、8K上下文。引擎1437485、四卡worker1437772–1437775均属sunqiuyi，每卡约20857MiB，利用率0%，无其他计算PID。四卡由本项目模型常驻待命，资源恢复阻塞已解除；本轮只核查状态，未启动导航小验证，B3 No-Go不变。

11月18日23:51审查前复核：服务器HEAD1910198、工作区干净；队列负载源码hash匹配、模型固定revision未变，health/models直连200、四卡约20857MiB/0%，历史文本/单图/双图probe真实通过。既定三次闭环目录不存在，本轮仅审核，不运行新导航或更改共享依赖。详见`experiments/benchmark_plan_review_2026-11-18.md`。

## 2026-11-19 BM0与BM4启动

从干净9245a8b开始，四卡仅本项目TP4 worker；health200、独立probe `runtime/manifests/service_probe_20261119_prevalidation.json`文本/单图/双图真实通过，既有Habitat环境29测试通过，未升级依赖。无导航重复进程后，以flock项目锁和独立会话启动三次回归PID2323871，批次`runtime/batches/empty_recovery_v1_20261119`，日志`runtime/logs/empty_recovery_v1_20261119.log`，PID清单`runtime/manifests/empty_recovery_v1_20261119.pid`。运行期间保持服务器9245a8b不变，后续文档同步等批次结束；前两次成功、第三次尚执行，最终结论另记。

11月19日04:31复核：服务器64b3901且干净，模型health/models200、仅本项目四卡worker（各约21000MiB），无导航进程；3次BM4已结束且源hash匹配。BM0源CPU审计已在64b3901生成，BM4 worker保持9245a8b不混版。BM1开发schema本机测试35通过，待安全同步后执行CPU审计，不动原资产或保留评估集。

11月19日04:35 BM1 CPU审计完成：代码6180a8d经GitHub推送后bundle快进服务器，真实Habitat环境35测试通过；原10任务/30case的开发manifest、actor输入与checks在`runtime/diagnostics/bm1_schema_dev_20261119/`，原数据hash不变，没有模型/保留集调用。04:30一次性唤醒已执行并删除；当前没有新导航批次，模型保留在线。

11月19日本轮BM3规范更新：f522403已push并在服务器干净工作区bundle快进同步，沿用原Habitat环境44测试通过（35既有+9新无线积分测试），未安装包、重启模型或运行导航。新增离线latent暴露模块不替换原route_a/旧评分；多层规划/传播和在线拒绝尚未实现或验收。

## 2026-11-19 单层20任务 AP 布局审阅

项目代码从`07037c2`到`bcb2159`均经GitHub发布后由bundle快进同步到服务器。服务器复用`/opt/anaconda3/envs/habitat0.3.0/bin/python`及Habitat-Sim 0.3.0 PathFinder，在CPU上读取项目`data/datasets`和5个MP3D navmesh；没有调用Qwen、GPU渲染、导航推理或更改共享环境。筛选/布局原始开发数据保存在服务器`runtime/diagnostics/single_floor_ap_review_20261119_retry02/`，日志`runtime/logs/single_floor_ap_review_20261119_retry02.log`；首次失败日志保留在同目录前缀无`retry01`的日志中。服务器HEAD、工作区和构建结果记录见[本轮实验记录](experiments/single_floor_ap_review_2026-11-19.md)。

保留初版与 v2 本机报告。复审改用服务器 CPU 独立产物 `runtime/diagnostics/single_floor_ap_review_20261119_reaudit/`，日志 `runtime/logs/single_floor_ap_review_20261119_reaudit.log`，执行提交 `666cc3e`。本机离线报告位于 `runtime/reports/single_floor_ap_review_20261119_v3/index.html`，已用隔离的本机 Chrome 打开并检查地图点击、覆盖和曲线更新、撤销、导入导出、审计搜索以及窄屏显示。报告和本地草稿留在本机；服务器保存 CPU 构造数据。

本机 v4 报告加入 Habitat 原生俯视图，路径为 `runtime/reports/single_floor_ap_review_20261119_v4/index.html`。服务器复用 Habitat-Sim 0.3.0 的 CPU PathFinder，独立导出 `runtime/diagnostics/single_floor_ap_review_20261119_topdown/habitat_topdown.json`。地图与 HTML 成品不入 Git；HTML 仅在本机生成。

射线追踪试点资产预查：当前五个审阅场景都有 GLB 和 navmesh。`2n8kARJN3HM` 另有 `.house` 与语义 PLY，GLB 的 148 个渲染材料条目无附加射频参数。Habitat 0.3.0 Python 当前无 Sionna、Mitsuba 和 Dr.Jit。已在独立环境 `runtime/envs/sionna_rt_2_2_0_py311` 用 Sionna RT 2.2.0 / LLVM 19.1.2 完成两批 CPU 射线追踪，试点定义见 [BM3 无线协议](design/bm3_radio_and_refusal_v0.md#5-成熟传播模型与-ap-选点试点)。

五场景多墙 RSSI 验收复用同一 Python 3.11 / LLVM 19 CPU 环境，运行在 4 个 CPU 核。结果 `runtime/diagnostics/single_floor_multiwall_dev_20261119/report.json`，日志 `runtime/logs/single_floor_multiwall_dev_20261119.log`。

本机 v5 AP 审阅报告位于 `runtime/reports/single_floor_ap_review_20261119_v5/index.html`。服务器 CPU 只导出 `runtime/diagnostics/multiwall_ap_preview_20261119/grids.json`，本机将多墙网格和曲线嵌入离线 HTML。动态切换图层直接在浏览器完成。

本机 v6 报告 `runtime/reports/single_floor_ap_review_20261119_v6/index.html`。服务器四核 CPU 从已校验的 GLB 生成纹理切片，结果为 `runtime/diagnostics/ap_scene_views_20261119_v3/views.json`，源色彩通过项目内 Basis Universal v1_60 解码器读取。浏览器直接加载嵌入图，无需服务。

2026-11-20 草稿重算验收复用 Habitat 0.3.0 与 `runtime/envs/sionna_rt_2_2_0_py311`。CPU 产物在 `runtime/diagnostics/single_floor_ap_revision_smoke_20261120/`，本机生成测试 HTML 后用 Chrome 检查。用户审阅入口仍是本机 v12。见[草稿验收及命令](experiments/single_floor_ap_review_2026-11-19.md#ap-草稿验收与重算)。

同日 BM1/BM2 单层诊断复用 Habitat 0.3.0 环境的 Python，在 CPU 读取已生成的导航图和多墙数据。执行提交 `2f337e7`，服务器结果与本机逐字节一致，见[诊断记录](experiments/single_floor_route_opportunity_2026-11-20.md#独立验证结果)。

北京时间 2026-11-20 09:12，按用户要求在 benchmark 批次完成后释放 GPU。确认等待器和导航锁空闲，向本项目服务 PID 1436455 发送 TERM。端口 8010 关闭，原四个计算 PID 均退出，复查四卡各 15 MiB、利用率 0%、无 CUDA 计算进程。前后快照和归档 PID 位于 `runtime/manifests/gpu_release_20261120_091239/`。队列的 `ready` 是历史验收，当前服务保持关闭，夜间使用由用户安排。

同日一次性唤醒执行 493 门框与地标审阅，使用 Habitat 0.3.0 环境的 NumPy 直接读取语义 PLY，模型调用 0，代码执行提交 `48aff81`。移除了本步骤对射线追踪运行时的导入依赖，见[语义审阅记录](experiments/single_floor_route_opportunity_2026-11-20.md#493-门与地标复查)。

## 2026-11-22 HM3D ObjectNav 数据接入

服务器项目路径复核为 `/mnt/data/suiqiuyi/WiFiNav`，安装前工作区干净，提交为 `e81aa0c`。服务器直连官方 episode CDN 时 DNS 超时，通过本机从同一官方地址转传到项目 `runtime/data_imports/`，校验后以实际文件放入 `data/datasets/objectnav/hm3d/v2/`。原 R2R-CE 任务资产和 90 处 MP3D 场景仍可供旧实验复现。

复用 `/opt/anaconda3/envs/habitat0.3.0/bin/python` 验证官方任务加载，以 CPU 和无渲染模拟器加载一个与官方任务匹配的公开 HM3D 场景。既有环境及模型服务未变更。其余授权场景尚未到位。产物路径、验收范围与剩余资源见 [数据记录](DATASETS.md)。

2026-11-24 三个授权的 HM3D `train` tar 从本机项目 `data/` 上传至服务器项目 `runtime/data_imports/hm3d_train_v0.2/`，逐包核对 SHA256 后导入 `data/scene_datasets/hm3d_v0.2/train/`。复用既有 Habitat 0.3.0 进行 145 个导航网格和一个带语义场景的 CPU 验收。安装产物继续由服务器管理，见 [数据记录](DATASETS.md)。

同日完成首批官方 `train` 的 20 条任务和 7 个 AP 布局。几何核验复用 Habitat 0.3.0，多墙射线和切片纹理复用项目已有的 `runtime/envs/sionna_rt_2_2_0_py311` 与 `runtime/tools/basisu_v1_60/decode_basis_ppm`。关闭 CUDA 可见设备，模型调用为 0。生成 HTML 需要从服务器取回审阅 JSON，本机生成页面。复现入口、版本和产物见 [首批 AP 审阅](experiments/objectnav_train_ap_review_2026-11-24.md)。

RSSI 优先参考在同一环境的 CPU 上完成，使用冻结几何及 AP 数据，独立产物目录为 `runtime/diagnostics/objectnav_rssi_reference_20261124_v1/`。结果用于本机离线页面。

2026-11-25 在既有 Habitat 和多墙射线环境中复算全图最优路线。最终 CPU 产物位于 `runtime/diagnostics/objectnav_rssi_graph_20261125_v2/`，见 [全图求解记录](experiments/objectnav_rssi_graph_2026-11-25.md)。

取消长度上限后的 CPU 批次位于 `runtime/diagnostics/objectnav_rssi_graph_20261125_v3/`。保留带预算版及其原始报告。新版离线 HTML 在本机验证地图点选和下拉的 AP 路线联动。

严重弱信号优先批次复用 v3 导航图与 CPU 环境，结果位于 `runtime/diagnostics/objectnav_rssi_graph_20261125_v4/`，模型调用为 0。渲染后的 HTML 留在本机。

单层边修正使用 Habitat 0.3.0 核查实际导航表面，并在原 CPU 射线环境重算结果。产物位于 `runtime/diagnostics/objectnav_rssi_graph_20261125_v5/`，原批次保留。

全量 Oracle 审计复用这两个 CPU 环境。局部补边的中间产物及异常记录保留在 `runtime/diagnostics/objectnav_rssi_graph_20261125_v6/`，加密几何检查与三档信号采样结果位于 `runtime/diagnostics/objectnav_rssi_graph_20261125_v7/`。两批均关闭 CUDA 可见设备，无模型调用。HTML 从验收产物在本机渲染，使用原本机审阅入口。[全量 Oracle 审计](experiments/objectnav_rssi_graph_2026-11-25.md#全量-oracle-审计)

2026-11-26 复用上述已有 CPU 环境完成官方 `val` 单场景工程小批。产物和复跑位于 `runtime/diagnostics/objectnav_val_small_20261126_v2/` 及其 `_replay` 副本，未启动模型服务。正式全量入口按官方分片检查资产，返回缺 35 个场景。授权档案到齐后暂存于 `runtime/data_imports/hm3d_val_v0.2/` 并用项目安装入口核验。[小批与全量状态](experiments/objectnav_val_small_2026-11-26.md)

2026-11-27 沿用同一 CPU 环境验收路径直连修复。后续全量入口使用新版小批清单 `runtime/diagnostics/objectnav_val_small_20261127_v3/manifest.json`。服务器保留两版批次及独立复跑，本机保留新旧 HTML。[新版验收](experiments/objectnav_val_small_2026-11-26.md#2026-11-27-新版验收)

2026-11-28，同一 CPU 环境验收固定直连规则和输出采样表面检查。初次放量入口使用 `runtime/diagnostics/objectnav_val_small_20261128_v5_parallel/manifest.json`。保留独立验收拒绝的 v4 小批及对应证据。[v5 小批验收](experiments/objectnav_val_small_2026-11-26.md#2026-11-28-确定性复核与最终直连修复)

2026-11-28，三个官方 `val` tar 从本机项目上传至 `runtime/data_imports/hm3d_val_v0.2/`，在已有 Habitat 0.3.0 CPU 环境安装及核验 36 个场景。放量预检记录在同目录 `full_readiness_20261128.json`。[数据安装](DATASETS.md#当前主线hm3d-objectnav-v2)

2026-11-28，执行提交 `5655f9a` 完成修复版小批和全量独立审计。服务器正式产物位于 `runtime/diagnostics/objectnav_val_full_20261128_v3_checkpoint/`，使用同提交的 `runtime/diagnostics/objectnav_val_small_anchor_ray_20261128/manifest.json` 解锁放量。过程复用现有 CPU Habitat、射线环境和项目依赖，GPU 用量及模型请求均为 0。全量 HTML 及浏览器证据位于本机 `runtime/reports/objectnav_val_full_review_20261128/`。[全量验收与哈希](experiments/objectnav_val_small_2026-11-26.md#2026-11-28-全量验收)

2026-11-28，单层评测 v1.1 复用 Habitat 0.3.0 和项目现有 CPU 射线解释器。参考审计和跨层回归用 CPU，小批闭环使用 GPU 0 的 EGL 渲染深度和语义。模型调用为 0。正式执行提交、服务器证据与复跑命令见 [v1.1 验收](experiments/objectnav_benchmark_v11_acceptance_2026-11-28.md)。

2026-11-28，NoSignal 开发首轮同样使用 Habitat 0.3.0 和 GPU 0 的 EGL 深度语义渲染。四次运行共执行 80 条轨迹，模型请求为 0，运行结束退出渲染进程。记录在服务器 `runtime/diagnostics/objectnav_train_dev_20261128_*`。[开发执行版本、产物和复跑](experiments/objectnav_train_nosignal_2026-11-28.md)

2026-11-28，NoSignal 复核在同一 Habitat 环境用 CPU 重放失败动作并核验正式判分探针，闭环配对仅使用 GPU 0 渲染，模型请求为 0。开发样本冻结件、首跑加载失败日志及第二轮轨迹在 `runtime/diagnostics/objectnav_train_dev_followup_20261128*`。[执行与证据](experiments/objectnav_train_nosignal_followup_2026-11-28.md)

2026-11-28，VLFM 冻结源码和额外运行依赖位于项目 `runtime/vendor` 与 `runtime/envs/vlfm_py39_*`，权重在 `models/vlfm`。复用现有 Torch 2.6.0+cu124，模型服务绑定 localhost 12382、12383、12384，仅使用 GPU 0。0.2.4 首场景和 0.3.0 全部 20 条均完成。确认本次服务退出、端口释放，四卡无计算进程。可复跑环境和权重指纹位于 `runtime/diagnostics/vlfm_setup_20261128/`。[评测与复跑](experiments/objectnav_vlfm_2026-11-28.md)

2026-11-28，通信达标评分复用项目 CPU 射线环境及 Habitat 0.3.0，回放保存的 20 条 VLFM 轨迹并核对原导航判分探针。GPU 与模型调用为 0。服务器默认 GitHub 代理端口拒绝连接，本轮在单条 Git 命令中关闭代理后直连成功，按原分支快进同步。[配置与回放证据](experiments/objectnav_benchmark_v11_acceptance_2026-11-28.md#通信达标成功率)

2026-11-28 21:10，正式 VLFM NoSignal 基线启动在物理 GPU 1–3。每组仅向其进程暴露一张卡，Habitat 使用对应的逻辑 EGL 设备 0，GPU 1 已通过真实 RGB-D 渲染和显卡进程核验。三组各用一套 localhost 感知服务。批次保存在 `runtime/diagnostics/objectnav_vlfm_20261128_val961/`，执行期间服务器固定在 `23b2c7b`。[执行证据和完成条件](experiments/objectnav_vlfm_2026-11-28.md#正式集-nosignal-基线)
