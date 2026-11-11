# WiFiNav

连通性感知视觉语言导航研究：在线 RSSI 信号场估计与通信风险规划。

## 当前状态

模型基座为冻结的 **Qwen3.5-35B-A3B**。B1与B2接口消融已完成；固定10任务/30AP回放中，关闭额外STOP复核后无运行异常、SR30%、SPL0.2723、nDTW0.4392。B3统一通信加权规划器与两场景smoke已接通（14执行/18case），但高权重出现绕行/停滞，尚未通过通信收益门；不扩大在线belief。

## 文档入口

- [计划与进度](plan.md)：当前选择、里程碑、E0–E8执行任务和交接记录。
- [目录索引](docs/PROJECT_STRUCTURE.md)：研究资料与历史方案分类。
- [环境与服务器记录](docs/LOCAL_ENVIRONMENT.md)：环境、连接、目录与同步约定。
- [服务器资产与日常操作](docs/experiments/project_storage_2026-11-04.md)：data/models/runtime与模型启动命令。
- [B1首条导航与RSSI闭环](docs/experiments/b1_first_episode_2026-11-05.md)：固定任务、信息隔离、运行指标和产物路径。
- [B2首轮开发pilot](docs/experiments/b2_pilot_2026-11-09.md)：10任务/30回放、失败诊断、覆盖指标与复现路径。
- [接口v1配对结果](docs/experiments/b2_interface_v1_pair_2026-11-10.md)：固定任务复跑、路径质量回退和复核开销。
- [无复核消融](docs/experiments/b2_no_review_2026-11-11.md)：基础接口冻结依据和指标限制。
- [B3首轮记录](docs/experiments/b3_oracle_2026-11-11.md)：统一规划器、局部目标诊断及闭环结果。
- [协作规则](AGENTS.md)：新聊天接手与文件维护要求。

## 下一步

1. 复核高权重下515/near与85/near的绕行/停滞，区分局部目标、离散执行、转向时间及视觉反馈的影响。
2. 明确绕行预算/规划范围和可接受导航损失，再开展完整10任务/30布局B3验收；不把两任务smoke当作总体方法收益。
3. Oracle通过后加入Reactive与Online Belief，再扩大benchmark；并行补齐源资产版本和许可追溯。

模型部署细节、实际请求结果和服务器资源见 [部署现场记录](docs/experiments/server_bootstrap_2026-11-04.md)。

## 同步与数据管理

本机开发并提交，经本仓库同步至服务器。服务器首次同步前盘点已有目录，保留未提交修改。模型、数据集、大日志和运行结果统一存服务器项目内models/、data/、runtime/（Git忽略）；仓库只保存代码、配置、文档和产物清单。认证信息不入库。
