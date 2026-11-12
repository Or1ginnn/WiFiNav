# WiFiNav

连通性感知视觉语言导航研究：在线 RSSI 信号场估计与通信风险规划。

## 当前状态

模型基座为冻结的 **Qwen3.5-35B-A3B**。共同执行器边界修复及完整B3开发验收已完成：固定10任务、3布局、λ=0/1/4，共70执行/90case。NoSignal SR50%、SPL0.3856；两个非零λ均SR40%、丢失基线成功case且SPL损失超门，结论**No-Go**。错误前缀全部保留，不扩大在线belief。

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
- [共同执行器修复](docs/experiments/b3_controller_repair_2026-11-12.md)：离散前进裁剪/越层证据与最小修复。
- [完整B3结果](docs/experiments/b3_full_2026-11-12.md)：70执行/90case、冻结验收门、错误分组与No-Go结论。
- [协作规则](AGENTS.md)：新聊天接手与文件维护要求。

## 下一步

1. 独立处理无候选时的合法观察退路；不替换已保留的两条错误前缀。
2. 另立协议诊断候选路径空间、规划范围与离散执行代价，不改写本次完整B3 No-Go，也不靠重选模型或训练制造收益。
3. 新方案通过Oracle门后才加入Reactive/Online Belief；并行补齐源资产版本和许可追溯。

模型部署细节、实际请求结果和服务器资源见 [部署现场记录](docs/experiments/server_bootstrap_2026-11-04.md)。

## 同步与数据管理

本机开发并提交，经本仓库同步至服务器。服务器首次同步前盘点已有目录，保留未提交修改。模型、数据集、大日志和运行结果统一存服务器项目内models/、data/、runtime/（Git忽略）；仓库只保存代码、配置、文档和产物清单。认证信息不入库。
