# 项目目录结构与文档索引

> 最近整理：2026-11-05。B1首条导航+RSSI闭环已完成，当前准备B2开发pilot与Oracle验收。根目录 `plan.md` 是进度入口；提案与调研 PDF 保存在项目内，旧方向归档以便追溯。

## 当前目录

```text
WIFI+Nav/
├── README.md                                    # 仓库入口、当前状态和执行顺序
├── .gitignore                                   # 本机状态、认证、模型/数据和运行产物忽略规则
├── AGENTS.md                                    # 新聊天读取计划与维护进度的项目约定
├── plan.md                                      # 当前项目计划、进度、里程碑、待办
├── configs/data/server_paths.json               # 项目内数据路径及副本策略
├── configs/model/qwen35b.json                    # 固定模型revision与服务初值
├── configs/navigation/r2r_dev.json               # 固定首条任务、观察/动作和控制预算
├── configs/wireless/r2r_conn_v0.json             # 路线A信号、阈值与确定性seed
├── scripts/
│   ├── download_model.py                        # 模型下载与镜像SHA256核验
│   ├── serve_model.py                           # 使用已有vLLM环境启动服务
│   ├── bootstrap_model.sh                       # 下载完成后启动服务
│   ├── probe_model.py                           # 文本/单图/多图服务验收
│   ├── check_habitat_task.py                    # 真实场景/RGB-D/动作验收
│   └── run_vln_episode.py                       # 单条VLM导航与RSSI闭环入口
├── src/connectivity_vln/
│   ├── navigation/                              # R2R任务、模型工具决策与局部规划
│   ├── signal_simulation/                       # 路线A确定性RSSI查询
│   └── evaluation/                              # 运行后导航指标
├── docs/
│   ├── PROJECT_STRUCTURE.md                     # 本文件：目录地图和资料索引
│   ├── DATASETS.md                              # 服务器实际数据副本、规模与来源
│   ├── LOCAL_ENVIRONMENT.md                     # 本机环境和服务器接入登记
│   ├── experiments/
│   │   ├── b1_first_episode_2026-11-05.md          # 首条导航+RSSI闭环证据与边界
│   │   ├── project_storage_2026-11-04.md           # 资产归项目目录及迁移验收
│   │   └── server_bootstrap_2026-11-04.md          # 服务器部署与验收记录
│   ├── references/
│   │   ├── connectivity_aware_vln_project_proposal_2026-10-15.pdf
│   │   ├── wifi_aware_vln_literature_review_2026-10-15.pdf
│   │   ├── social_navigation_backbone_review_2026-11-02.md
│   │   ├── api_cost_review_2026-11-03.md
│   │   ├── local_zero_shot_feasibility_2026-11-03.md
│   │   └── backbone_selection_report_2026-11-03.md
│   ├── archive/
│   │   ├── radionav/                             # 先前 X-NavDP/RadioNav 方案
│   │   │   ├── RadioNav-v4.md
│   │   │   └── RadioNavDP-v3.md
│   │   └── radiofrontier/                        # 更早的 ObjectNav/CSI/AP belief 方案
│   │       ├── RadioFrontier-v2.1.md
│   │       ├── RadioFrontier-v2.md
│   │       ├── project_plan.md
│   │       └── action_plan.md
│   └── design/
│       ├── r2r_conn_benchmark_plan_v0.md          # 当前任务与benchmark分阶段制作计划
│       ├── task_benchmark_research_plan.md         # 任务选择与benchmark修改的调研任务单
│       └── radiofrontier/                        # RadioFrontier 现实/半现实演示设计
│           ├── demo_scenario.md
│           └── real_world_setup.md
├── data/                                        # 仅服务器：任务/场景实际副本，Git忽略
├── models/                                      # 仅服务器：实际模型权重，Git忽略
├── runtime/                                     # 仅服务器：日志/缓存/清单/PID，Git忽略
└── .obsidian/                                    # Obsidian 本地工作区设置
```

根目录还可能有 `.DS_Store`，这是 macOS 自动生成文件，不属于项目资料。

## 文档索引

| 类型 | 文件 | 用途 |
|---|---|---|
| 当前交接与进度 | [plan.md](../plan.md) | 已确定Qwen3.5-35B-A3B；当前状态、M0–M7里程碑、E0–E8执行任务与变更记录 |
| 当前任务与benchmark制作 | [R2R-Conn制作计划v0](design/r2r_conn_benchmark_plan_v0.md) | 用户已确认；B0核实资产/版本/协议，再单条闭环、10×3开发pilot、Oracle与后续扩展 |
| 阶段任务调研范围 | [任务调研任务单](design/task_benchmark_research_plan.md) | 保留历史讨论；不作为从零重选任务方向的要求 |
| 阶段选型记录 | [基座选型简报](references/backbone_selection_report_2026-11-03.md) | 旧首选已撤销；保留候选取舍与源码审计，当前选择见 plan.md |
| 当前具体方案 | [连通性感知 VLN 项目小样](references/connectivity_aware_vln_project_proposal_2026-10-15.pdf) | 在线贝叶斯信号场、连通代价注入 VLN、实验路线 |
| 文献参考 | [WiFi 信号感知 VLN 调研](references/wifi_aware_vln_literature_review_2026-10-15.pdf) | 文献版图、gap 论证、仿真和数据资源调研 |
| 新增基座调研 | [Social Navigation 基座与规划接口](references/social_navigation_backbone_review_2026-11-02.md) | 模型配置、训练路线、作者代码及对当前项目的选型建议 |
| API费用调研 | [API费用与预算测算](references/api_cost_review_2026-11-03.md) | 官方价格、地域/上下文档位与导航运行预算 |
| 本地部署调研 | [本地zero-shot可行性](references/local_zero_shot_feasibility_2026-11-03.md) | 用户报告4×4090条件下的模型容量与导航代码可用性 |
| 部署记录 | [服务器部署现场记录](experiments/server_bootstrap_2026-11-04.md) | 四步基础设施执行、资源、复用环境及服务验收 |
| B1首条闭环 | [首条导航与RSSI记录](experiments/b1_first_episode_2026-11-05.md) | 固定episode、信息隔离、失败修复、导航/RSSI指标及产物路径 |
| 服务器任务与场景 | [DATASETS.md](DATASETS.md) | 实际文件副本，无软链接；任务规模、场景覆盖、复制校验和来源 |
| 本机/服务器 | [LOCAL_ENVIRONMENT.md](LOCAL_ENVIRONMENT.md) | 本机软件信息、服务器参数登记表和接入核对项 |
| 历史 RadioNav | [RadioNav v4](archive/radionav/RadioNav-v4.md)、[RadioNavDP v3](archive/radionav/RadioNavDP-v3.md) | X-NavDP 轨迹级未来无线预测方向；不作为现主线 |
| 历史 RadioFrontier | `archive/radiofrontier/` 下的 4 份文档 | ObjectNav、frontier、CSI/AP belief 方向的历史方案 |
| 历史 demo 设计 | `design/radiofrontier/` 下的 2 份文档 | RadioFrontier 的真实与半真实场景草案，不能视为当前 VLN 实验已完成 |

## 当前源码与后续结构

当前已有模型服务、真实场景验收、单条VLM导航、局部navmesh控制、RSSI查询和离线评测代码。服务器模型在 `~/WiFiNav/models/`，日志/缓存/完整运行在 `~/WiFiNav/runtime/`，旧目录保存在 `~/WiFiNav_backups`。下述结构中的belief、批量评测和可视化仍待后续实现。

```text
WIFI+Nav/
├── README.md
├── plan.md
├── pyproject.toml / environment.yml
├── configs/{model,navigation,wireless,experiments}/
├── docs/{references,archive,design,experiments,decisions}/
├── src/connectivity_vln/
│   ├── signal_simulation/       # RSSI/覆盖场仿真接口
│   ├── belief/                  # 时间滤波、空间外推、不确定性
│   ├── navigation/              # VLN 适配、costmap、重规划触发
│   ├── evaluation/              # VLN、通信、开销与联合指标
│   └── visualization/
├── scripts/                     # 数据生成、服务/运行、评估
├── tests/
├── data/                        # 仅服务器：任务与场景实际文件，Git忽略
└── outputs/                     # 小型结果；模型和批量日志存服务器
```

源码、配置、数据和实验产物分开管理。大文件、密码、私钥和访问令牌不提交 Git；服务器数据路径和实验版本在环境说明及实验记录中追溯。
