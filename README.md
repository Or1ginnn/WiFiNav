# WiFiNav

连通性感知视觉语言导航研究：在线 RSSI 信号场估计与通信风险规划。

## 当前状态

模型基座为冻结的 **Qwen3.5-35B-A3B**。服务器、模型和Habitat0.3.0真实MP3D任务已接通；B1固定episode的NoSignal导航与逐动作RSSI闭环通过。当前准备10个episode×3个AP布局的开发pilot和StaticMap/Oracle价值验证；首条结果仅作工程验收。

## 文档入口

- [计划与进度](plan.md)：当前选择、里程碑、E0–E8执行任务和交接记录。
- [目录索引](docs/PROJECT_STRUCTURE.md)：研究资料与历史方案分类。
- [环境与服务器记录](docs/LOCAL_ENVIRONMENT.md)：环境、连接、目录与同步约定。
- [服务器资产与日常操作](docs/experiments/project_storage_2026-11-04.md)：data/models/runtime与模型启动命令。
- [B1首条导航与RSSI闭环](docs/experiments/b1_first_episode_2026-11-05.md)：固定任务、信息隔离、运行指标和产物路径。
- [协作规则](AGENTS.md)：新聊天接手与文件维护要求。

## 下一步

1. 固定10个开发episode（至少2个scene）和每个episode 3个AP布局。
2. 回放NoSignal轨迹并运行StaticMap/Oracle，检查导航—通信权衡。
3. Oracle通过后加入Reactive与Online Belief，再扩大benchmark；并行补齐源资产版本和许可追溯。

模型部署细节、实际请求结果和服务器资源见 [部署现场记录](docs/experiments/server_bootstrap_2026-11-04.md)。

## 同步与数据管理

本机开发并提交，经本仓库同步至服务器。服务器首次同步前盘点已有目录，保留未提交修改。模型、数据集、大日志和运行结果统一存服务器项目内models/、data/、runtime/（Git忽略）；仓库只保存代码、配置、文档和产物清单。认证信息不入库。
