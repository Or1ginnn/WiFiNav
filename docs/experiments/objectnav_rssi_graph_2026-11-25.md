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

## 取消长度上限

用户确认取消早期为控制绕行而设的 120% 路长预算。主路线使用整层可通行图，去掉旧预算对应的椭圆裁剪。固定同一起点、停止视点和 AP，在全部可行路径上按字典序最小化 $(W_{-67},W_{-75},L)$。每个节点只需保留当前字典序最小代价，使用 Dijkstra 精确求解。详细公式见 [计划](../../plan.md#当前路径计算公式)。

320 个任务/AP 组合均有解，全部字典序代价优于或等于带预算版。147 个组合相较几何参考减少至少 0.05 m 弱信号距离，其中 31 个组合相较带预算版也减少至少 0.05 m。42 个组合超过几何参考长度的 120%，最大 4.10 倍。例 `vDfkYo5VqEQ` 源行 `9582`、`AP-01`，长度从 2.21 m 变为 9.07 m，低于 −67 dBm 的距离从约 0.37 m 降为 0 m。弱信号目标优先级高于总路长，小幅改善也可能产生长绕行，报告明确显示长度和倍率。

第一条「找一张床」切换 `AP-01` 到 `AP-09` 后，主路线从 1.91 m 变为 2.04 m，弱信号距离从 1.91 m 变为 0 m。在相同的 `AP-09` 下，和几何路线的对照仍是 0.57 m 至 0 m。Chrome 分别验收地图点选和下拉选择，线路、RSSI 曲线和弱信号距离使用同一 AP 的结果。报告离线切换每层 16 个已计算的位置。

执行提交 `ba67d26`，使用同一几何 manifest，服务器新目录为 `runtime/diagnostics/objectnav_rssi_graph_20261125_v3/`。该批次 `subsegment_audit.json` 核验 9,521 个不同子段全可达。65 项仓库测试通过，其中穷举覆盖无上限求解，并检查了旧上限外的绕行能被选中。本机 HTML 仍使用 `index-reviewed.html`，带上限版保存在 `index-before-unlimited.html`。

## 阈值依据与固定路线复算

- Cisco 的 WLAN 勘测指南以 −67 dBm 和至少 25 dB SNR 作为语音覆盖推荐。MiR 的 WLAN 指南 v2.2 给最强和次强 AP 分别设 −67、−75 dBm 的部署参考，同时列出丢包和时延要求。欧姆龙 MD 系列手册给出 −60 dBm 的推荐下限。不同业务和设备对应不同覆盖目标。[Cisco 勘测指南](https://www.cisco.com/c/en/us/support/docs/wireless/5500-series-wireless-controllers/116057-site-survey-guidelines-wlan-00.pdf) · [MiR WLAN 指南 v2.2，第 2.1 节](https://noll-sondermaschinenbau.de/downloads/downloads_fts/mir_main_network_and_wifi_guide_22.pdf#page=6) · [欧姆龙 MD 系列手册，第 4-26 节](https://assets.omron.eu/downloads/latest/manual/en/md-series_platform_users_manual_en.pdf?v=2)
- WiFiNav 单 AP 仿真中，−67 dBm 用作覆盖目标，−75 dBm 统计严重弱信号暴露。链路质量能否满足任务要求，需要结合目标设备、SNR、丢包、时延和实际业务流量。当前配置按这两档统计模拟 RSSI，现场链路阈值待实测校准。
- 只改变统计阈值，在 `DBBESbk4Y3k/L2` 源行 `20747`、`AP-10` 的两条固定路线及已有采样上重算。−67 dBm 下几何路线与蓝线分别有 1.34 m 和 0.96 m 低于阈值，−70 dBm 下分别为 0.75 m 和 0.88 m，−75 dBm 下两条均为 0 m。固定路径的相对表现会随阈值改变，完整敏感性验证还需要在各阈值下重新求解。主配置继续使用 −67 和 −75 dBm。

## 首版复核

- 校验本机 HTML 的内嵌报告 SHA256、选样 manifest SHA256、20 个唯一任务键、320 个配对结果的端点和 Oracle 目标值。服务器批次 `checksums.sha256` 的 10 个产物全部通过，65 项仓库测试通过。5 个开发场景的物理场景 ID 与官方 `val` 的交集为 0。
- 320 个组合中有 63 个能到达当前固定停止视点且全程达标。184 个组合的固定停止点低于 −67 dBm，其中 89 个的同一任务存在达标的其他同层合法停止视点。后一项用每个任务/AP 的 `stop_viewpoints_max_dbm` 判定，只说明终点局部覆盖。全程可行性需要对其他停止视点另行规划。固定终点的路线对照仍可用；正式成功和 SPL 用原 ObjectNav 的目标口径。[Habitat Challenge 评分](https://github.com/facebookresearch/habitat-challenge#evaluation) · [Habitat-Lab v0.3.0 配置](https://github.com/facebookresearch/habitat-lab/blob/v0.3.0/habitat-lab/habitat/config/habitat/task/objectnav.yaml)
- 与几何参考相比，19 个组合的蓝线增加至少 0.05 m 的低于 −75 dBm 距离。最长绕行是几何参考的 4.10 倍。现行代价适用于观察覆盖充分时的路径差异，通信可靠性结论需并报两档暴露和长度，并保留阈值敏感性对照。
- 已有 `runtime/diagnostics/objectnav_scoring_smoke_20261122/score.json` 仅覆盖一条公开场景任务的三种评分探针。20 条开发任务的联合轨迹评分待接通。服务器正式 `val` 的 36 处场景仅就绪 1 处，该处已作工程检查。正式比较前按物理场景固定保留集，锁定 AP 选择和评分配置。统计以任务或场景分组，16 个 AP 是同一任务的配对条件。

## 严重弱信号优先

根据用户确认，正式的离线参考依次最小化低于 −75 dBm 的距离、低于 −67 dBm 的距离和总路长。阈值、物理场、图、任务与 AP 清单固定。路线可经过一般弱信号区以避免严重弱信号，公式见 [计划](../../plan.md#当前路径计算公式)。

- CPU 执行提交 `f606461`，新结果为 `runtime/diagnostics/objectnav_rssi_graph_20261125_v4/`。沿用 v3 的全部导航图和冻结 manifest，各场景结果的 `graph_sha256` 与 v3 一致。选路结果哈希可在新批次 `checksums.sha256` 查验；独立 Habitat 复查 12,758 个去重路径短段全部可达，见 `subsegment_audit.json`。
- 320 个组合中有 126 个换路，106 个的严重弱信号距离相较 v3 减少至少 0.05 m。无严重弱信号的组合从 115 增至 122，全程达到 −67 dBm 的组合仍为 63。所有新版路线的严重弱信号距离均不超过几何参考。71 个组合的总路径长度超过几何参考的 120%，最大 4.42 倍。
- 例 `16 · 找电视`（`vDfkYo5VqEQ` 源行 `975`，`AP-05`）。v3 用 6.17 m 的路线，其中约 0.60 m 低于 −75 dBm。新版花 7.27 m 绕过该段，低于 −75 dBm 的距离降为 0；低于 −67 dBm 的总距离由 1.93 m 增至 3.03 m。HTML 分别显示两档距离和路长，图上最优的范围仍是固定起终点和模拟 RSSI。
- 例 `01 · 找床` 在默认 `AP-01` 下仍需穿过严重弱区。新版用 8.46 m 路线换取严重弱信号距离从 1.49 m 降至 1.33 m，几何参考为 1.91 m。这是无长度上限和严重弱信号优先共同导致的长绕行。
- 66 项仓库测试通过，包含两米一般弱区优先于一米严重弱区的回归。Chrome 验证原本机 HTML 入口已使用新版策略，包括任务 16 选路、地图与下拉菜单切换 AP、指标联动与报告导出。旧页面保留为 `index-before-severe-first.html`。
