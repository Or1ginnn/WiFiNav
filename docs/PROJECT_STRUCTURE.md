# 项目目录结构与文档索引

> 最近整理：2026-11-19。单层20任务/5场景AP布局审阅数据已生成；可交互HTML只保存在本机`runtime/reports/`，待人工校正与语义复核。BM0视觉审计/源许可仍待闭合；原B3 No-Go不变。

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
├── configs/benchmark/pilot_v0.json               # B2固定任务选择/AP布局与运行预算
├── configs/benchmark/oracle_smoke_v0.json         # B3两场景/三布局/三权重接线协议
├── configs/benchmark/oracle_full_v1.json          # 完整10任务与预先固定的验收门
├── configs/ops/four_gpu_queue.json               # 四卡等待阈值与已冻结模型恢复负载
├── configs/ops/four_gpu_queue.json               # 四卡连续空闲条件与模型恢复负载
├── configs/ops/four_gpu_queue.json               # 四卡连续空闲条件与模型恢复负载
├── scripts/
│   ├── download_model.py                        # 模型下载与镜像SHA256核验
│   ├── serve_model.py                           # 使用已有vLLM环境启动服务
│   ├── wait_for_gpus.py                         # 等四卡空闲、互斥启动模型并图文验收
│   ├── bootstrap_model.sh                       # 下载完成后启动服务
│   ├── probe_model.py                           # 文本/单图/多图服务验收
│   ├── check_habitat_task.py                    # 真实场景/RGB-D/动作验收
│   ├── run_vln_episode.py                       # 单条VLM导航与RSSI闭环入口
│   ├── generate_pilot.py                        # 运行前固定10任务/30 case清单
│   ├── run_pilot.py                             # 串行NoSignal和明确错误/超时记录
│   ├── replay_pilot.py                          # 一轨迹三AP回放与任务级汇总
│   ├── audit_pilot_signals.py                   # 可导航探针位置的信号重复性审计
│   ├── diagnose_oracle.py                       # 固定局部目标的离线绕行诊断
│   ├── build_single_floor_ap_review.py          # 全train单层范围审计与20任务AP布局数据（服务器CPU）
│   ├── render_ap_review_html.py                 # 本机生成离线交互AP校正报告，不上传报告
│   ├── compare_pilot_interfaces.py              # 同清单接口消融的配对汇总
│   ├── run_oracle_pilot.py                      # 同规划器NoSignal/StaticMap闭环检查
│   ├── evaluate_oracle.py                       # 全case/固定基线子集验收与CSV
│   ├── plot_oracle.py                           # 验收JSON生成导航—通信取舍图
│   └── plot_pilot.py                            # 报告生成独立PNG/PDF诊断图
├── src/connectivity_vln/
│   ├── navigation/                              # R2R任务、模型工具决策与局部规划
│   ├── signal_simulation/                       # 路线A确定性RSSI查询
│   └── evaluation/                              # 运行后导航指标
├── docs/
│   ├── PROJECT_STRUCTURE.md                     # 本文件：目录地图和资料索引
│   ├── DATASETS.md                              # 服务器实际数据副本、规模与来源
│   ├── LOCAL_ENVIRONMENT.md                     # 本机环境和服务器接入登记
│   ├── experiments/
│   │   ├── b3_full_2026-11-12.md                 # 70执行/90case完整No-Go与错误分组
│   │   ├── b3_controller_repair_2026-11-12.md    # 离散动作与层高边界修复
│   │   ├── b3_oracle_2026-11-11.md               # B3诊断、18case与收益门判断
│   │   ├── b2_no_review_2026-11-11.md            # 关闭复核消融与接口冻结
│   │   ├── b2_interface_v1_pair_2026-11-10.md     # 接口配对结果、回退与开销
│   │   ├── navigation_interface_v1_2026-11-10.md  # 接口修复与针对性复核
│   │   ├── b2_pilot_2026-11-09.md                # 10任务/30回放与失败/覆盖诊断
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
│       ├── b2_pilot_protocol_v0.md               # B2执行前固定的样本/AP/信息/时间协议
│       ├── b3_oracle_protocol_v0.md              # 统一规划器及分阶段检查/扩展门槛
│       ├── b3_full_protocol_v1.md                # 完整开发集运行前冻结的收益规则
│       ├── task_benchmark_research_plan.md         # 任务选择与benchmark修改的调研任务单
│       └── radiofrontier/                        # RadioFrontier 现实/半现实演示设计
│           ├── demo_scenario.md
│           └── real_world_setup.md
├── data/                                        # 仅服务器：任务/场景实际副本，Git忽略
├── models/                                      # 仅服务器：实际模型权重，Git忽略
├── runtime/                                     # 仅服务器：日志/缓存/清单/PID，Git忽略
├── tests/test_weighted_planner.py                # 双路径、信息隔离、断图与缓存测试
├── tests/test_oracle_gate.py                     # 防止早停/错误前缀/分母变化误判收益
├── tests/test_gpu_queue.py                       # GPU条件、互斥、竞争、取消与图文验收模拟
├── tests/test_gpu_queue.py                       # 忙碌/稳定空闲/复查竞争/互斥/取消测试
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
| B2首轮pilot | [B2记录](experiments/b2_pilot_2026-11-09.md) | 固定10任务/30回放、失败分类、信号审计与当前限制 |
| 导航接口 v1 | [修复与复核](experiments/navigation_interface_v1_2026-11-10.md) | 工具校验、STOP复核、观察与无进展处理 |
| 接口配对结果 | [v0/v1固定清单复跑](experiments/b2_interface_v1_pair_2026-11-10.md) | 10任务/30回放、全部失败、SPL回退与复核开销 |
| 无复核消融 | [v1关闭STOP复核](experiments/b2_no_review_2026-11-11.md) | 独立开关、固定任务和基线冻结依据 |
| B3首轮协议 | [Oracle诊断与闭环检查](design/b3_oracle_protocol_v0.md) | 统一栅格规划器、双路径/局部目标诊断及两场景smoke；不是完整B3验收 |
| B3实际结果 | [首轮Oracle记录](experiments/b3_oracle_2026-11-11.md) | 局部目标诊断、已知限制和真实闭环状态 |
| B3共同执行器修复 | [离散动作与单层边界](experiments/b3_controller_repair_2026-11-12.md) | 六条历史轨迹证据、最小动作校验与新批次复跑 |
| B3完整开发集协议 | [固定10任务验收v1](design/b3_full_protocol_v1.md) | 70次执行/90case、几何入口门、固定配对子集与预先冻结的收益规则 |
| B3完整运行 | [固定开发集结果](experiments/b3_full_2026-11-12.md) | 实际执行状态、原始产物与正式开发门结论 |
| 四卡资源等待 | [排队与模型恢复](experiments/gpu_queue_2026-11-16.md) | 空闲条件、后台等待、状态查询与取消；新实验未排入 |
| 服务器任务与场景 | [DATASETS.md](DATASETS.md) | 实际文件副本，无软链接；任务规模、场景覆盖、复制校验和来源 |
| 本机/服务器 | [LOCAL_ENVIRONMENT.md](LOCAL_ENVIRONMENT.md) | 本机软件信息、服务器参数登记表和接入核对项 |
| 历史 RadioNav | [RadioNav v4](archive/radionav/RadioNav-v4.md)、[RadioNavDP v3](archive/radionav/RadioNavDP-v3.md) | X-NavDP 轨迹级未来无线预测方向；不作为现主线 |
| 历史 RadioFrontier | `archive/radiofrontier/` 下的 4 份文档 | ObjectNav、frontier、CSI/AP belief 方向的历史方案 |
| 历史 demo 设计 | `design/radiofrontier/` 下的 2 份文档 | RadioFrontier 的真实与半真实场景草案，不能视为当前 VLN 实验已完成 |

## 当前源码与后续结构

当前已有模型服务、真实场景验收、VLM导航、局部navmesh/共享风险栅格控制、RSSI查询、批量回放与诊断图代码。服务器模型在 `~/WiFiNav/models/`，日志/缓存/完整运行在 `~/WiFiNav/runtime/`，旧目录保存在 `~/WiFiNav_backups`。下述结构中的belief与正式规模评估仍待后续实现。

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

- `docs/experiments/empty_recovery_2026-11-17.md`：空候选修订、独立三次闭环协议及CPU候选路径诊断。
- `scripts/validate_empty_recovery.py`、`configs/benchmark/empty_recovery_validation_v1.json`：独立小验证入口；`configs/benchmark/candidate_routes_diagnostic_v1.json`：固定CPU诊断选择与扫描。

- `docs/experiments/benchmark_plan_review_2026-11-18.md`：模型恢复验收与benchmark优先方案的三Agent交叉审核、待冻结质量/评测合约和实施建议。

- `docs/design/r2r_conn_benchmark_v1.md`：BM0任务卡、信息权限与benchmark/参考基线边界；`docs/experiments/bm0_task_audit_2026-11-19.md`：原10任务文本/参考高度初审；`scripts/audit_bm0_tasks.py`：CPU源字段/GT层高与hash审计，非筛样。

- `docs/design/r2r_conn_benchmark_v1.md`：BM0任务卡，区分benchmark规则、真值权限与参考导航器限制；正式清单/评分参数仍待BM1–BM3。
- `docs/experiments/bm0_task_audit_2026-11-19.md`、`scripts/audit_bm0_tasks.py`：原10任务文本/源层高初审与CPU可复现来源诊断，不作正式语义或单层资格标注。

- `docs/design/bm1_manifest_contract_v0.md`、`src/connectivity_vln/evaluation/manifest.py`、`scripts/build_bm1_development.py`：BM1仅开发schema/actor输入分离及CPU试建，未冻结正式资格/清单。
- `docs/experiments/empty_recovery_validation_2026-11-19.md`：3次工程回归已结束，定点fallback验收通过但导航方法未通过收益门。

- `docs/experiments/bm1_schema_dev_2026-11-19.md`：6180a8d开发schema在固定10任务/30case的实际CPU验证与hash；非正式资格/发布验收。

- `docs/design/bm3_radio_and_refusal_v0.md`、`src/connectivity_vln/evaluation/radio_metrics_v1.py`、`tests/test_radio_metrics_v1.py`：路线兼容AP/拒绝/跨层规范与独立latent暴露参考计算器；不替换旧评分，在线机制待实现。
- `configs/benchmark/single_floor_ap_review_v1.json`、`src/connectivity_vln/benchmark/single_floor.py`、`scripts/build_single_floor_ap_review.py`、`scripts/render_ap_review_html.py` 、`scripts/ap_review_report/` 与 `scripts/export_ap_review_topdown.py`：训练split单层资格审计、20任务/5场景候选AP布局与带 Habitat 俯视底图的本机 AP 布局校正 HTML；真实产物在本机`runtime/reports/`，不是发布清单或导航结果。
- `docs/experiments/single_floor_ap_review_2026-11-19.md`：单层审阅批次真实统计、源/配置/产物hash、选中任务和待闭合项；20条AP实际坐标详见本机报告。
- `scripts/prepare_rss_pilot.py`、`scripts/run_rss_raytrace_pilot.py` 与 `configs/wireless/rss_pilot_v{1,2}.json`：单层 RSSI / Sionna RT 对照；版本与结果见[试点记录](experiments/rss_propagation_pilot_2026-11-19.md)。
- `scripts/run_rss_multiwall_pilot.py` 与 `configs/wireless/rss_multiwall_pilot_v1.json`：语义面直达路径与穿透损耗敏感性，见[多墙试点记录](experiments/rss_multiwall_pilot_2026-11-19.md)。
