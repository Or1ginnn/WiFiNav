# HM3D ObjectNav 单层基准小批验收

2026-11-26 在既有 CPU Habitat 0.3.0 和多墙射线环境运行。工程小批使用官方 `val` 已安装公开样例 `00861-GLAQ4DNUx5U`。未调用导航模型。

## 实际结果

- 筛查官方分片的全部 28 条记录，28 条均有通过实际导航表面检查的同层合法参考停止点。两个楼层各固定一个 AP。AP、起点及参考停止点的 58 次场景坐标对齐检查全部通过。
- 28 个任务/AP 组合在 1.875 cm 与 3.75 cm 间距各自求解。两种求解器的全部 56 个代价一致。独立审计核对冻结文件的 SHA256、AP 可达性、黄线和蓝线的端点、原生子段与实际楼层。28 条中有 2 条的几何最短参考全程达标，26 条的固定停止点对照在换路后仍有弱区。其中共有 5 条达到两种采样间距下均改善至少 0.50 m 的选路差异口径。样本只覆盖一个场景，比例留作工程诊断。
- 统一评分以同一序列的实际位置为输入。成功探针由 Habitat 的贪婪跟随器在模拟器中执行，包含结尾 STOP，提前停止探针在起点发出 STOP。两者都复用 Habitat 0.3.0 的原生导航指标及同一 AP 的沿路 RSSI。

| 轨迹 | 成功 | SPL | 路长 m | 低于 −67 dBm m | 低于 −75 dBm m | 最长连续严重弱区 m | 缺口 dB·m |
|---|---:|---:|---:|---:|---:|---:|---:|
| Habitat 动作到达后 STOP | 1 | 0.6871 | 14.7856 | 9.3894 | 5.6644 | 5.6644 | 184.8319 |
| 起点 STOP | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

成功探针的导航与 RSSI 计算路长相差约 2 微米，弱区平均信号为 −86.69 dBm。起点 STOP 的零暴露来自零行进距离，退出原因保留。另验证全程达标与信号缺测的数据处理。RSSI 结果来自多墙仿真。

第一次构建 `objectnav_val_small_20261126_v1` 的联合评分触发身份校验失败，因为 Habitat 加载时会重新编号 episode ID。修正后以官方分片和文件内记录序号匹配，并核对原 ID、场景、类别和初始位姿，保留首轮日志。

## 可复现产物

- 执行提交 `40fd7307de397c8d378655679e2a8c4f7b737af9`。配置入口 `configs/benchmark/objectnav_val_v1.json`，合并配置 SHA256 `f2dbf1e19c67b9bb814bb324f1abcb3773de6b5ca6f473e5b9eb3082ce0482cd`。
- 服务器正式小批 `runtime/diagnostics/objectnav_val_small_20261126_v2/`，独立复跑 `runtime/diagnostics/objectnav_val_small_20261126_v2_replay/`。生成 JSON 逐字节一致。两次 `manifest.json` 的 SHA256 均为 `189651a0d9907b7edcdb5504255eb6feef25be1ac0ac26226f8cfedd13c22285`。同目录 `audit.json` 和 `probe_scores.json` 提供单层和统一评分证据。
- 使用配置固定的随机种子 `wifinav-objectnav-val-v1-review` 从合格任务中无放回抽 20 条。HTML 在本机 `runtime/reports/objectnav_val_review_20261126/index-small-review.html`。Chrome 验证抽样键准确、地图纹理、覆盖图层、黄线、弱信号指标、楼层筛选、标签页及手机视图。原 `train` 报告仍使用原地址。

核心执行入口如下。评分程序的 `--probe` 用于动作验收。常规轨迹评分先用 Habitat 环境传 `--traces`（每条包含源记录序号、动作和起点起的实际位置序列），再在现有射线环境传 `--navigation` 重放 RSSI。

```sh
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/build_objectnav_benchmark.py \
  --small --output runtime/diagnostics/<新小批目录>
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/audit_objectnav_benchmark.py \
  --manifest runtime/diagnostics/objectnav_val_small_20261126_v2/manifest.json \
  --output runtime/diagnostics/<新审计文件>.json
```

## 放量状态

调用 `--full-after` 已通过小批配置与源码校验，随后因缺失 35 个正式 `val` 场景返回状态 2。三个官方 v0.2 `val` 场景包的匿名请求均返回登录 HTML。需补齐 `hm3d-val-habitat-v0.2.tar`、`hm3d-val-semantic-annots-v0.2.tar` 和 `hm3d-val-semantic-configs-v0.2.tar`。下载先经 Matterport 已有授权，再暂存到项目 `runtime/data_imports/hm3d_val_v0.2/`。[Matterport 官方下载表](https://github.com/matterport/habitat-matterport-3dresearch#-downloading-hm3d-v02)

```sh
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/install_hm3d_val.py
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/build_objectnav_benchmark.py \
  --full-after runtime/diagnostics/objectnav_val_small_20261126_v2/manifest.json \
  --output runtime/diagnostics/<新的全量目录>
```

全量构建验证全部 1,000 条原始记录均被清点，保留排除原因，之后使用同一审核入口检查成品。正式 HTML 用 `scripts/render_objectnav_ap_smoke.py --benchmark-manifest <全量 manifest> --output <本机报告>` 渲染，读取清单中冻结的正式随机样本和选中场景的审阅产物。
