# 单层开发集的局部绕行机会审计

2026-11-20。与 20 个 AP 的人工审阅并行，在原 v12 绑定的 20 条 train 路线、5 场景、原布点和四组多墙参数上做 BM1 字段核对与 BM2 离线路线筛查。全部 80 个参数病例均保留。原指令和 AP 保持固定，真人复核、正式清单资格与在线可观测性待验收。

## 运行前写定的检查

- 固定布局数据、全量筛选审计、RSSI 剖面及网格四份 SHA256。复验任务、原指令、场景/源路径组、原生几何记录、AP 坐标与信号数组的对应性。四组参数是同一条语言任务的仿真假设。
- 用 −75 dBm 与已用的相邻点均值口径找参考路线的连续断连段。以先后至少 0.80 m 的原路线采样点作为相同替换端点，临近起终点时将窗口限制在路线内。两端外的参考路线保持固定。
- 在原 0.40 m 图中用同一个加权 Dijkstra 搜索，用原几何边及两端接入边，固定 λ 为 0、0.25、0.5、1、2、4、8。搜索代价用低于阈值的端点比例，候选验收计算的是沿路段平均 RSSI。相同顶点序列合并并保留对应权重。替换段长度至多为参考段的 120%，断连段总长至少降低 0.10 m 才记为有待语义复核的几何候选；预算外路径仍留在审计输出里。
- 保留无参考断连、无几何见证、连接失败等结果。有限扫描无见证只说明本配置未找到；同端点和图可走也不保证符合原指令、保留门与地标顺序、或者在线可发现。候选还要逐条复核语义并用独立传播查询确认其沿线 RSSI。报告仅供离线 QA，坐标和参考路线不进入 actor，不运行模型，不用于选 20 个任务或改 AP。

## 服务器命令

```bash
source=runtime/diagnostics/single_floor_ap_review_20261119_reaudit
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/audit_single_floor_route_opportunities.py \
  --data "$source/ap_review_data.json" --audit "$source/source_scope_audit.json" \
  --profiles runtime/diagnostics/single_floor_multiwall_dev_20261119/report.json \
  --grids runtime/diagnostics/multiwall_ap_preview_20261119/grids.json \
  --output runtime/diagnostics/single_floor_route_opportunity_20261120/report.json
```

## 独立验证结果

- 本机和服务器在执行提交 `2f337e7358f8144be13c8c3a87ecaea80322259c` 都通过 56 项测试，并生成逐字节一致的 `runtime/diagnostics/single_floor_route_opportunity_20261120/report.json`。配置 SHA256 `76ed5b586d2fbefb83ec3d713af5b9c6eca9b6210f115646bdb65d2f3e7c86d4`，报告 SHA256 `787e2edaffb00bc7e8aaf913d8850be0ef2d1f4c934a71c24063371a7d082ea6`。四份源哈希与配置相同，服务器日志 `runtime/logs/single_floor_route_opportunity_20261120.log`。
- 复验全部 20 条原指令、20 个源路径组、5 个场景和 80 个参数病例。61 个病例的参考路线按段均值没有断连段。其余 19 个病例构成 29 个局部窗口，15 个病例至少找到一个预算内几何候选，4 个未找到。几何候选涉及 575、743、818、214、493、825、208、235；512 的两档高损耗均未找到。相邻替换窗口可能重叠，收益不相加。
- 任务 493 在四组假设中各有几何候选。高损耗／0.20 m 的 [46, 57] 参考样本窗口，局部候选长度 2.45 m，参考 2.58 m，按既有网格估算断连段长度 1.15 → 0 m。该候选需要检查经过的门、最终地标与原指令，随后在双方一致的采样步长上重新查询传播，确认差值不会随采样改变。512 的两档高损耗作未找到见证的对照。
- 后续按固定任务对照做语义及传播复核，人工 AP 草稿到达后另建派生版本。仅在几何、传播与语义上都成立后，才讨论接入在线对照；保留原 B3 No-Go 和目前所有负例。

## 候选传播再采样协议

从既有报告读取任务 493 高损耗／0.20 m 的 [46, 57] 替换窗口和已选见证，要求两端坐标逐项一致。对原段、候选段分别用最大步长 0.10 m 和 0.05 m 均匀细分每条几何边，固定同一 AP、收发高度、语义墙门窗和四种配置，用现有多墙引擎直接重查每个点。查验原报告、数据及场景资产 SHA256。报告保留两条路径的空间断连统计及全部假设，语义审核仍标为待复核。

2026-11-20 补验结果。重核原批次报告 SHA256 一致；512 两档高损耗仍属于原扫描无见证病例。对 493 的同端点候选，0.10 m、0.05 m 步长下的高损耗／0.20 m 参考断连段长度分别为 1.234 m、1.159 m，候选均为 0 m。复核仅说明这对几何路线在同一多墙代理下的差异对这两种采样步长稳定。保留替换窗口之外的前后段，窗口内经过的门、最后转向与厨房地标仍需视觉核对。

- 执行提交 `18265739494cafe2cecb896dd4be3e3a9a9c87e2`。结果 `runtime/diagnostics/single_floor_route_recheck_20261120/report_493.json`，SHA256 `c5df513daf29a85773113a1aee40e8572943c320498ea474f187fce3c0bb745f`，日志 `runtime/logs/single_floor_route_recheck_20261120_493.log`。使用 CPU LLVM 环境并设置空 `CUDA_VISIBLE_DEVICES`，模型调用 0。
- 复现入口为 `scripts/recheck_single_floor_route_opportunity.py`，参数 `--episode 493 --assumption high_0.20 --interval 46 57 --spacing 0.10 0.05`，其余输入为固定的 `--data`、`--profiles`、`--opportunities` 和新的 `--output` 路径。
