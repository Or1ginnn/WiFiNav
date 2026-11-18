# BM1开发schema：固定10任务/30布局CPU验证

2026-11-19北京时间04:35执行，代码`6180a8d8cb68a14cf16b93676951388441165b75`。规范见[开发清单合约](../design/bm1_manifest_contract_v0.md)，BM0任务卡见[首版规范](../design/r2r_conn_benchmark_v1.md)。本轮仅在BM0仍未闭合的人工作业/上游资产对应之外，推进可独立完成的字段与真值分离审计；不标记BM0或BM1整体通过。

## 实际完成

- 本机与服务器原Habitat环境均35测试通过（既有29+新增6），没有安装/升级共享依赖。
- 运行`scripts/build_bm1_development.py --output-dir runtime/diagnostics/bm1_schema_dev_20261119`，排他新目录，未写原data。
- 复用全部原10条train任务、10个源路径group、2个scene、30个AP case；assigned split仅development，qualification全部unreviewed。没有过滤、重选AP、读取模型结果或访问val_unseen/test payload。
- actor记录严格只有case_id/instruction/scene_id/start_position/start_rotation；source目标/GT引用和AP/无线实例留protected sidecar，不传给actor。instruction hash逐条与原源字段一致；scene/group跨split检查通过。该结构分离不宣称对恶意策略已实现系统隔离。
- 源train文件hash不变；与原manifest保持对应，原B3和全部旧批次不变。模型没有被此CPU构建调用。

## 产物与hash

服务器根`~/WiFiNav`，目录`runtime/diagnostics/bm1_schema_dev_20261119/`：

| 文件 | SHA256 |
|---|---|
| checks.json | e3c31aecbe8e06fa1cdbff35d5d212d8f734a3c2a0e4eb5e9c75ee106a110097 |
| protected_manifest.json | b41864a4abe1daca8dd42b5d13a2a9551bd25deeab1888d14a4d42bd033631d9 |
| actor_inputs.json | 24348a94ab00df15f4e392c26d616e43daa0407d6f74e8f551dee421fef731f8 |

checks保存执行commit、builder/validator/source train/GT/manifest的SHA256。原manifest SHA256 `8a0caf14400bd73939c97e976cdc5e97c34ce32eb2da35eee936c53a5dd1d326`。private与actor文件含原数据派生内容，只留服务器runtime，不提交公开仓库；Git提交仅自有代码、合约和汇总。

## 当前不能声称完成的事项

这不是正式benchmark数据发布、独立保留评估或单层资格冻结。BM0视觉/人工语义复核与官方资产逐字节对应/再分发许可仍未闭合；BM1尚需正式schema文件与迁移/资格/歧义/排除编码、最终清单及group划分。当前35测试与30case验证证明开发contract可运行，不证明无线物理保真、全路线语言合法性或任何策略收益。

下一项先补BM0的证据缺口，并制定BM1策略无关的几何/语言资格候选与人工复核流程；阈值先写定再形成新的资格统计，不反向修改旧开发集。同时进入BM3信号时间/缺测评测合约设计，不提前跑BM5或扩展Online Belief。04:30一次性唤醒的验收与下一项启动已执行，自动任务已删除，不新增周期任务。
