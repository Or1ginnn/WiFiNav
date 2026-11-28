# WiFiNav

连通性感知室内物体搜索研究，使用模拟 RSSI 和通信风险评估。

## 当前状态

主线采用 **Habitat HM3D ObjectNav v2**。冻结的正式集包括 36 个场景、74 个楼层、961 条任务。v1.1 评测通过单层轨迹回归、全量参考审计及固定 20 条的闭环配对验收。[数据安装记录](docs/DATASETS.md) · [v1.1 评测与复跑](docs/experiments/objectnav_benchmark_v11_acceptance_2026-11-28.md)

## 文档入口

- [计划与进度](plan.md)：当前主线、里程碑和交接记录。
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

先在开发数据上验收更稳定的 ObjectNav 基线，再用冻结的正式清单做导航与模拟 RSSI 的闭环配对。原 R2R-Conn B3 的 No-Go 记录供复现。

模型部署细节、实际请求结果和服务器资源见 [部署现场记录](docs/experiments/server_bootstrap_2026-11-04.md)。

## 同步与数据管理

本机开发并提交，经本仓库同步至服务器。服务器首次同步前盘点已有目录，保留未提交修改。模型、数据集、大日志和运行结果统一存服务器项目内models/、data/、runtime/（Git忽略）；仓库只保存代码、配置、文档和产物清单。认证信息不入库。
