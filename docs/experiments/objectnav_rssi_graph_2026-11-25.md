# 已知地图与 RSSI 的 ObjectNav 图上最优路线

2026-11-25 将 20 条任务的 HTML 主路线从一批预生成绕行中选取，改为在已知可通行图上按当前 AP 求解。起点、同层约束和合法停止视点沿用同一任务几何清单。几何最短参考由黄色虚线显示。官方 ObjectNav 的 STOP、SR、SPL 仍按原定义记分。供报告求解使用的完整 RSSI 场和目标停止视点留在离线评估端。

## 图、目标与最优范围

- 在单层 Habitat NavMesh 上用 0.15 m 网格连接八邻域，局部连线使用 Habitat 复核后返回的路径几何。加入原几何参考与早期 219 条通过复核的路线，使网格可表达本来存在的通行路线。每一个能满足长度预算的点必定位于起终点的欧氏距离和不超过预算的范围内，范围外的节点直接剔除。
- 允许运动距离最多为几何参考的 120%。沿图的边按不超过 0.075 m 采样，用相邻 RSSI 的均值为该短段分类。优化按字典序最小化低于 −67 dBm 的累计距离、低于 −75 dBm 的累计距离、总距离。短段长度换算成微米并向上取整，作为整数优化和保守的预算检查。报告显示未取整的距离。
- 采用带长度资源约束的多标签 Dijkstra。到同一节点时，代价更高的前缀如果更短且仍有机会满足预算，就继续保留。首次弹出的可行终点标签是固定图和代价下的最小值。对 50 个小图逐一和穷举对照，并单测较短但代价较高的前缀可以决定最终可行性。
- 最优性适用于冻结的图、已知 RSSI、固定起终点及预算。真实连续空间、未测遮挡和机器人实际动作序列的最优性仍需分别验证。换目标、停止视点、预算或阈值，可对应不同的最优路线。

## 验收结果

320 个任务/AP 组合都求到满足预算的路线，目标代价均不大于图中包含的原几何参考。164 个组合选择了不同的图路径，其中 141 个将低于 −67 dBm 的距离至少缩短 0.05 m。−67 dBm 优先于 −75 dBm，另有 15 个组合在低于 −75 dBm 的距离上增加至少 0.05 m。报告同时展示两档阈值，供 AP 审阅时识别这类取舍。

第一条「找一张床」`g7hUFVNac26/L1` 源行 `34162`。`AP-01` 下几何参考 1.91 m 也是图上最优，弱信号距离仍为 1.91 m。`AP-09` 下图上最优长 2.04 m，低于 −67 dBm 的距离从几何参考的 0.57 m 降至 0 m，按同一采样与阈值比较。

首轮构图 `81faca0` 的复查发现，少量网格直连用更短的子段重查时可能绕障，保留在 `runtime/diagnostics/objectnav_rssi_graph_20261125_v1/`。修订版 `289a915` 让边采用 Habitat 返回的实际路径。重新用 Habitat 对最终 320 条路径的 8,559 个不同短段查询，全部可达，子段测地距离与已绘几何距离的最大差小于 0.000001 m。明细见 `subsegment_audit.json`。

## 复现

- 数据、场景与 AP 来自原开发清单，SHA256 `3f3034ece428556e27134aa16363b39da052e724a03b88d5757dae2219a3c7f0`。使用现有 Habitat 0.3.0 与多墙射线 CPU 环境，模型调用为 0。
- 在 Habitat 环境运行 `scripts/solve_objectnav_rssi_graph.py --geometry <scene.geometry.json> --proposals <scene.refined_routes.json> --output <scene.navmesh_graph.json>`。在射线环境对同一 `--geometry` 传入 `--graph`，生成 `<scene.rssi_reference.json>`。服务器输出目录为 `runtime/diagnostics/objectnav_rssi_graph_20261125_v2/`，各场景哈希见 `checksums.sha256`。
- 本机渲染使用 `scripts/render_objectnav_ap_smoke.py --manifest <manifest.json> --with-rssi-graph --output <index-reviewed.html>`。本机 HTML 仍位于 `runtime/reports/objectnav_train_ap_review_20261124/index-reviewed.html`，上一版保存在 `index-before-graph.html`。64 项仓库测试通过，Chrome 验证首条任务随 AP 换路、图层对比、路线信号和导出联动。
