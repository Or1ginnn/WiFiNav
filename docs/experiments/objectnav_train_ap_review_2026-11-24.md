# HM3D ObjectNav 首批单层 AP 审阅

2026-11-24 完成 20 条官方 `train` 任务、5 个场景和 7 套单层 AP 布局的开发审阅。场景、任务及 16 个备选位置在计算 RSSI 前固定，每层启用一个 AP。保留原起点、朝向与目标类别，源任务分片不做删改。当前覆盖为 AP 草稿，供本机人工检查。

## 任务与场景核验

- 按冻结种子和场景引用的 SHA256 顺序遍历官方 `train`，每个场景每类最多抽 8 个官方源行，按楼层和类别轮换选 4 条。前五个场景均满足数量。抽审 232 条，选入 20 条，191 条合格但未选，17 条缺可核实的同层成功视点，4 条未满足起点规则。本轮只审计抽样范围；任务未入选也留在原数据。
- 楼层以起点高度聚类后取中位数，保守限定见证路径全程位于楼层高度 ±0.28 m。20 条均追溯到官方记录的 episode ID、物体类别、起点与朝向，且至少一个合法候选成功视点可同层抵达。两个场景横跨两套独立楼层布局，单条任务的见证路径全程在同一层。
- 轨迹和目标信息只用于构建、离线审阅及评分。全批次 CPU 执行，模型请求为 0；未运行闭环导航，未产生这 20 条任务的 SR/SPL。

## 覆盖与校正优先级

墙、门、窗使用已有多墙传播配置，`−67 dBm` 为弱信号阈值。覆盖比例是当前楼层可通行采样点中达到阈值的比例。16 个候选均已在三维结构网格中重新计算，页面切换位置时同步切换热力图、阈值边界及每条路径的采样。152 个 AP 底座、任务起点与参考 STOP 的物理网格对齐检查全部通过。

| 场景 / 楼层 | 任务数 | 默认 AP 覆盖 | 16 个候选覆盖范围 |
|---|---:|---:|---:|
| `g7hUFVNac26/L1` | 4 | 16.8% | 12.8%–72.8% |
| `j2EJhFEQGCL/L1` | 4 | 4.7% | 4.6%–37.6% |
| `DBBESbk4Y3k/L1` | 1 | 88.7% | 18.8%–88.7% |
| `DBBESbk4Y3k/L2` | 3 | 41.4% | 9.0%–48.7% |
| `vDfkYo5VqEQ/L1` | 4 | 77.8% | 25.4%–89.6% |
| `hWDDQnSDMXb/L1` | 2 | 39.5% | 17.1%–48.5% |
| `hWDDQnSDMXb/L2` | 2 | 87.3% | 14.8%–91.8% |

首次处理中 `j2EJhFEQGCL` 因已知标签不到 95% 停止。复核 43,805/441,787 个面包含语义表缺失的黑色顶点，未发现其他未知颜色。修订后分别计数，黑色未标注顶点不赋墙、门、窗标签。其余场景也有约 1.2%–3.6% 的面含未标注黑色顶点。RSSI 无实测校准，未标注区域的材质与遮挡影响尚未量化。保持冻结样本，在独立目录重算全部五处。另对 `j2EJhFEQGCL` 做一次冷启动复算，产物逐字节一致。

人工审阅先看 `j2EJhFEQGCL/L1` 和 `g7hUFVNac26/L1`。检查摆位可行性与起点、门口、房间、有效停止点的覆盖，再保存草稿。正式布局冻结前应区分自然弱区与需修正的摆位或源网格局限。草稿导出包含每层场景引用、候选 ID、坐标和原报告哈希。

### 第一条任务的指令和信号

`g7hUFVNac26/L1`，源 episode `830`、源行 `34162`。目标类别 `bed`，报告显示「找一张床」。中文指令由类别生成，参考路线和停止视点供离线评估。报告会随选中的任务显示指令，切换 AP 后同步更新起点、终点、最低 RSSI 及弱信号距离。

| 候选 | 起点 RSSI | 参考 STOP RSSI | 第一条路线低于 −67 dBm | 同层四条路线合计低于 −67 dBm |
|---|---:|---:|---:|---:|
| `AP-01` | −78.4 dBm | −85.1 dBm | 1.91 / 1.91 m | 10.47 m |
| `AP-06` | −49.5 dBm | −53.8 dBm | 0.00 / 1.91 m | 4.10 m |
| `AP-09` | −61.4 dBm | −65.8 dBm | 0.42 / 1.91 m | 3.43 m |

默认 `AP-01` 下，第一条路线约 1.35 m 低于 −75 dBm。用同一网格和合并规则复核，两端射线分别穿过 2 和 3 处标注为墙的结构，对应模拟墙损 16 和 24 dB。`AP-09` 在该层 16 个候选中使四条参考路线合计弱信号距离最短，四条参考 STOP 的 RSSI 均达到 −67 dBm；找沙发的路线仍有 3.01 m 低于阈值。候选保留给人工审阅。

## 同起终点的绕行对照

对 20 条任务按几何生成候选。固定同一初始 AP、起终点和同层条件，最多增加 20% 路长，剔除回头与重复段。用 0.15 m 和 0.075 m 两种步长分别采样，只有两次都减少至少 0.50 m 弱信号距离才计为通过。84 个合格对照中有 17 个通过，来自同一场景的 2 条任务。

示例 `DBBESbk4Y3k/L1` 源行 4341、`AP-01`。最短路 9.68 m，绕行 11.52 m，长 19.1%。0.15 m 采样下弱信号距离从 4.26 m 降至 2.17 m；按匀速 0.25 m/s 对应 17.0 s 和 8.7 s，细采样为 16.6 s 和 8.3 s。运动换算只计沿轨迹移动。这说明该离线例子存在选路权衡；方法收益和真实无线效果待独立验证。

## 复现与交付

- 配置 `configs/benchmark/objectnav_train_ap_review_v1.json`。SHA256 `41412445378b2d80f271fcd0f62d98eec8b8ecf51c907a9dcde2e33e9b2936c8`。
- 几何选样执行提交 `c0cfc03`，服务器产物 `runtime/diagnostics/objectnav_train_ap_review_20261124/`，含 `manifest.json`、源文件哈希、逐任务几何审计及第一次 RF 日志。manifest SHA256 `3f3034ece428556e27134aa16363b39da052e724a03b88d5757dae2219a3c7f0`。
- RF 与路线核验执行提交 `472a9b0`，服务器 `runtime/diagnostics/objectnav_train_ap_review_20261124_radio_v2/`，含各场景 `*.radio.json`、`*.routes.json`、`*.route_scores.json`。独立复算 `runtime/diagnostics/objectnav_train_ap_review_20261124_repro/j2EJhFEQGCL.radio.json`，SHA256 `5a09f74f1f68ad2549d1a6fdc7ced8be5242bdd795d5a877262a112733570712`。模型版本不适用，模型调用为 0。
- 几何环境运行 `scripts/build_objectnav_train_ap_review.py --config configs/benchmark/objectnav_train_ap_review_v1.json --output <新运行目录>`。CPU 射线环境对冻结清单逐场景运行 `scripts/run_objectnav_ap_radio.py --geometry <geometry> --basis-decoder runtime/tools/basisu_v1_60/decode_basis_ppm --output <scene.radio.json>`；路线脚本先在 Habitat 环境传 `--geometry` 生成 `*.routes.json`，再在射线环境另加 `--proposals` 生成 `*.route_scores.json`。
- 本机用 `scripts/render_objectnav_ap_smoke.py --manifest <manifest.json> --with-routes --output <index-reviewed.html>` 生成 HTML。最终文件位于本机 `runtime/reports/objectnav_train_ap_review_20261124/index-reviewed.html`。报告和浏览器验收截图留在本机，数据及审阅产物均由 Git 忽略。
- 58 项仓库单元测试通过。Chrome 离线验收确认地图点选、RSSI 联动、阈值边界及其他图层开关、草稿下载、重置、楼层筛选、绕行示例跳转和移动端宽度。浏览器证据为报告旁的 `browser-check.json`。

下一步读取用户确认的 AP 草稿，重新计算并冻结布局。在固定任务上接通 RSSI 查询与官方 STOP/SR/SPL 的轨迹评分，分别验证到达且 STOP、到达未 STOP、远处 STOP。正式保留评估所需 `val` 资产仍待接入。
