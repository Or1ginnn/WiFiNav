# WiFiNav

连通性感知视觉语言导航研究：在线 RSSI 信号场估计与通信风险规划。

## 当前状态

模型基座已选定为 **Qwen3.5-35B-A3B**，使用冻结权重进行多模态推理。服务器盘点、项目同步和模型部署已完成，文本/单图/双图服务验收通过；已有Habitat环境可复用。**用户已确认连通性感知VLN任务及MP3D/R2R-CE→R2R-Conn制作计划；B0已完成原始资产盘点及独立复制，继续协议/适配核对，具体版本与导航实现待闭合，无导航实验结果。**

## 文档入口

- [计划与进度](plan.md)：当前选择、里程碑、E0–E8执行任务和交接记录。
- [目录索引](docs/PROJECT_STRUCTURE.md)：研究资料与历史方案分类。
- [环境与服务器记录](docs/LOCAL_ENVIRONMENT.md)：环境、连接、目录与同步约定。
- [服务器资产与日常操作](docs/experiments/project_storage_2026-11-04.md)：data/models/runtime与模型启动命令。
- [协作规则](AGENTS.md)：新聊天接手与文件维护要求。

## 下一步

1. 按 [R2R-Conn制作计划v0](docs/design/r2r_conn_benchmark_plan_v0.md) 核对MP3D/R2R-CE资产、实现与协议。
2. 跑通单条导航+RSSI闭环，生成10个开发episode×3布局的pilot。
3. 先验证Oracle收益，再加入在线belief并扩大benchmark；保留原始指令和导航指标。

模型部署细节、实际请求结果和服务器资源见 [部署现场记录](docs/experiments/server_bootstrap_2026-11-04.md)。

## 同步与数据管理

本机开发并提交，经本仓库同步至服务器。服务器首次同步前盘点已有目录，保留未提交修改。模型、数据集、大日志和运行结果统一存服务器项目内models/、data/、runtime/（Git忽略）；仓库只保存代码、配置、文档和产物清单。认证信息不入库。
