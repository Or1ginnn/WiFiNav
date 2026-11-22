# WiFiNav

连通性感知室内物体搜索研究，使用模拟 RSSI 和通信风险评估。

## 当前状态

主线采用 **Habitat HM3D ObjectNav v2**。服务器已安装官方任务包并通过一个匹配场景的 CPU 加载验收，完整场景待补齐。模型基座为冻结的 **Qwen3.5-35B-A3B**。原 R2R-Conn 的完整 B3 结论为 **No-Go**，其数据和结果供复现。见 [数据安装记录](docs/DATASETS.md)。

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
- [四卡资源等待](docs/experiments/gpu_queue_2026-11-16.md)：已部署后台等待器，四卡连续空闲后自动恢复模型并验收；状态/日志/取消入口。
- [四卡资源等待器](docs/experiments/gpu_queue_2026-11-16.md)：后台检测四卡空闲后恢复模型并图文验收，状态查询与取消方法。
- [协作规则](AGENTS.md)：新聊天接手与文件维护要求。

## 下一步

1. 从有访问许可的来源导入其余 HM3D v0.2 场景与语义资产，核对任务引用。
2. 验收 ObjectNav 任务与单层开发候选，冻结开发和保留评估划分。
3. 在新场景上构造 AP 与 RSSI 实例，检查通信条件能否改变机器人可选的搜索路线。

模型部署细节、实际请求结果和服务器资源见 [部署现场记录](docs/experiments/server_bootstrap_2026-11-04.md)。

## 同步与数据管理

本机开发并提交，经本仓库同步至服务器。服务器首次同步前盘点已有目录，保留未提交修改。模型、数据集、大日志和运行结果统一存服务器项目内models/、data/、runtime/（Git忽略）；仓库只保存代码、配置、文档和产物清单。认证信息不入库。
