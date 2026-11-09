# WiFiNav

连通性感知视觉语言导航研究：在线 RSSI 信号场估计与通信风险规划。

## 当前状态

模型基座为冻结的 **Qwen3.5-35B-A3B**。B1闭环和B2首轮开发pilot已执行：10条任务、2个场景、30个AP回放，SR=30%、平均SPL=0.2723；全部失败和3个错误前缀case保留。当前先处理解析/停止/无进展问题，再开展StaticMap/Oracle价值验证；尚无论文级方法收益结论。

## 文档入口

- [计划与进度](plan.md)：当前选择、里程碑、E0–E8执行任务和交接记录。
- [目录索引](docs/PROJECT_STRUCTURE.md)：研究资料与历史方案分类。
- [环境与服务器记录](docs/LOCAL_ENVIRONMENT.md)：环境、连接、目录与同步约定。
- [服务器资产与日常操作](docs/experiments/project_storage_2026-11-04.md)：data/models/runtime与模型启动命令。
- [B1首条导航与RSSI闭环](docs/experiments/b1_first_episode_2026-11-05.md)：固定任务、信息隔离、运行指标和产物路径。
- [B2首轮开发pilot](docs/experiments/b2_pilot_2026-11-09.md)：10任务/30回放、失败诊断、覆盖指标与复现路径。
- [协作规则](AGENTS.md)：新聊天接手与文件维护要求。

## 下一步

1. 用已冻结的10任务诊断工具说明字段长度、错误STOP和无位移保护，另存版本与新批次。
2. 实现同一加权规划器的λ=0/StaticMap对照，检查导航—通信权衡。
3. Oracle通过后加入Reactive与Online Belief，再扩大benchmark；并行补齐源资产版本和许可追溯。

模型部署细节、实际请求结果和服务器资源见 [部署现场记录](docs/experiments/server_bootstrap_2026-11-04.md)。

## 同步与数据管理

本机开发并提交，经本仓库同步至服务器。服务器首次同步前盘点已有目录，保留未提交修改。模型、数据集、大日志和运行结果统一存服务器项目内models/、data/、runtime/（Git忽略）；仓库只保存代码、配置、文档和产物清单。认证信息不入库。
