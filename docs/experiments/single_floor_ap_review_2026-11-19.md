# 单层20任务 AP 布局审阅批次

日期：2026-11-19。用途：首个单层开发审阅样本的策略无关筛选、路线附近 AP 初始选点与本机交互校正。**不是正式发布集、导航实验结果或泛化评估。**原始train任务、旧B3/BM4和原10任务开发数据均未改动。

## 执行与来源

- 源：服务器 `~/WiFiNav/data/datasets/R2R_VLNCE_v1-3_preprocessed/train`；任务SHA256 `340a80133b2157520354ab055a91d98feb2f42e4bbda17b200c911f8788492ea`，dense GT SHA256 `b63fa10e5c57d1b80b241c49bdeddc3d481bbe54b41ca0d59f9584c10da7bd5d`。
- v1源数据构建commit：`07037c2a5c10ce26d81ae857ba0ce03ce7a1f94b`；v2（加入route_a确定性噪声观测样例）commit：`bcb215948bef155d126a1818388b73d1078d75c9`。服务器复用Habitat 0.3.0 CPU端PathFinder/navmesh，没有调用Qwen或GPU渲染。
- 构建器 `scripts/build_single_floor_ap_review.py`；配置 `configs/benchmark/single_floor_ap_review_v1.json`；筛选/AP规则见[设计记录](../design/single_floor_ap_review_v1.md)。
- 历史 v2 服务器产物：`~/WiFiNav/runtime/diagnostics/single_floor_ap_review_20261119_retry02/`；过程日志 `~/WiFiNav/runtime/logs/single_floor_ap_review_20261119_retry02.log`。`retry01`为只含truth的较早成功产物，继续保留；第一次尝试因粗网格`try_step`重复拒绝已验证的原生路线采样连接而停止，日志保留于`runtime/logs/single_floor_ap_review_20261119.log`。
- 历史 v2 本机交互 HTML 及本地数据副本：`runtime/reports/single_floor_ap_review_20261119_v2/index.html`；v1报告和文件留在相邻无`_v2`目录。报告未提交Git，也未上传服务器；没有CDN或外部请求。

## 筛选结果

| 统计 | 数量 |
|---|---:|
| train源任务 | 10,819 |
| 规则初筛candidate | 6,687 |
| 明确垂直移动词规则标记excluded | 1,971 |
| 高度起伏/楼梯语义歧义待review | 2,161 |
| 最终选中 | 20条、20个不同source path、5个场景 |
| 场景内布局 | 每场景4个任务，每个任务独立一个AP布局实例 |

`excluded`是基于指令词规则的范围标记，不等于人工语义真值；`review`不自动判为上楼或合格。只有选中的20条执行了native navmesh参考路径检查，未选的其他candidate并没有通过几何资格检查。任务按预先固定的scene/episode顺序和不同source path选择，不使用策略成功、模型输出或RSSI效果。

选中场景和episode：

| Scene | Episode IDs |
|---|---|
| `mp3d/17DRP5sb8fy/17DRP5sb8fy.glb` | 515, 575, 1074, 1116 |
| `mp3d/1LXtFkjw3qL/1LXtFkjw3qL.glb` | 85, 127, 743, 818 |
| `mp3d/1pXnuDYAj8r/1pXnuDYAj8r.glb` | 214, 268, 493, 825 |
| `mp3d/29hnd4uzFmX/29hnd4uzFmX.glb` | 160, 208, 287, 290 |
| `mp3d/2n8kARJN3HM/2n8kARJN3HM.glb` | 121, 134, 235, 512 |

## AP 与RSSI

每个episode独立生成一个AP floor-proxy初始位置：参考路线约35%进度、侧向偏移目标1.5m，再吸附到同层、可达、距路线2m内的navmesh网格候选。界面显示每任务合法候选点；当前初始AP坐标逐条列在本机HTML和`ap_review_data.json`中。20/20坐标都匹配合法候选点，且距原路线不超过2m。每任务有70–293个候选，均值162.8。

当前信号设置为同一个固定代理：1m参考RSSI -48dBm、路径损耗指数2.8、seed 20261119；叠加现有navmesh测地绕行遮挡代理和确定性空间阴影。按原生`SignalField`对参考路线各采样点查询latent truth与对应sample_index的带噪RSSI，共807个示例观测值。噪声曲线是静态参考路线剖面，不是模型执行轨迹。初始路线长度均值9.10m（范围6.13–14.81m）；20/20存在弱信号路径段，3/20存在低于断连阈值的路径段，平均断连路径长度比例1.8%。这些是固定代理下的描述性结果，不是AP选点目标、真实无线验证或导航结果。

报告中点击绿色合法候选即可修改当前episode AP；可恢复初值、浏览器本地暂存、导入/导出JSON。初始路线曲线是原生`SignalField`代理latent truth；空间热图和点击后的即时变化按同一RSSI公式、空间阴影与0.4m图距离估算，不是原生逐点查询。改点后仍要服务器原生信号场重新计算并复核；界面明确区分粗估与原生曲线。地图是可走网格点，不是建筑平面图；AP高度是仿真floor proxy，不代表墙面/顶棚安装。

## 可复现与文件完整性

- 单层配置SHA256：`f594165f5de7be8539512a9733a8c5164c168959c4598d8b2a8df78fd9720ce4`
- Builder SHA256：`9b2f4309758e3ecc3f300cf6dd6b8ed3ce4f901fc2021550425880974002bfd1`
- HTML renderer SHA256：`b4ba53d8ab8e585b97f447cb8e477d727cf5c62d82011f17ebdcb232dae93fac`
- 核心几何规划器SHA256：`18271f7be0fafb93bb04dd994c6b1e01b85f28fb9e3067f27110a06d52028f71`
- RSSI实现SHA256：`63aff5b45ba1ad27b1931a42fb2ee0578b60ba1824c1d8b4754c89f2ecc73046`
- v2批次`ap_review_data.json` SHA256：`e453813f02e382b8a29f1364c635727e7479aa29cf74791290db100761aaa4a0`
- v2批次`source_scope_audit.json` SHA256：`94dfa35ed7f4d96f8070c1f29cad4ebf21c9adc29d43562386522f7397458b4a`
- 本机 v2 在上一轮样式修改后，实际 HTML SHA256 为 `e50ed58f2d67bc1e124acc48341b721ba4020ecebe1ab563f78626f946656007`。v1 和 v2 都保留供追溯。
- 五个实际navmesh的SHA256、所有20条起终点/路线、AP候选索引及坐标、初始路线RSSI/弱区统计和运行时间保存在批次JSON与报告中。

实现测试：本机6项范围/辅助函数测试通过；Python编译检查、最小数据HTML渲染、内联JavaScript语法检查及实际任务替换合法AP节点后的动态网格RSSI smoke通过。自动化浏览器预览受本地`file:`URL策略阻止，因此报告本身已按文件/JS结构校验，但未做浏览器截图验收。

## 未闭合项

- 需要人工查看20条指令、参考地标与楼层范围；规则标签不是人类标注。
- AP人工修改后应导出布局修改JSON，并在服务器对每个新AP位置执行原生navmesh可达性与RSSI重算，形成独立冻结的layout版本。
- 路线兼容AP是受控开发布局，不代表自然AP部署分布；物理墙体传播、多AP/楼层传播与最终benchmark规模尚未验证。
- 原完整B3 No-Go不变；本批次未启动VLM导航或新收益对照。

## 复查与重做

旧排除正则允许 `up/down` 和楼梯词之间相隔多达 35 个字符，并把独立的 `upstairs/downstairs` 当作动作。例如，9 号原指令包含 “move down the hallway, past the stairs”，480 号包含 “walk around the upstairs hallway”，两条原被排除，现转待复核。现仅将直接的上下楼动作或乘梯指令按规则排除。97 号的 “up the stairs” 仍命中排除，源高度跨度约 0.60 m。原始任务和旧审计均保留。

| 状态 | 历史 v2 | 复查后 |
|---|---:|---:|
| 初筛候选 | 6,687 | 6,684 |
| 规则排除 | 1,971 | 1,326 |
| 待复核 | 2,161 | 2,809 |
| 已入选（候选子集） | 20 | 20 |

共 645 条从规则排除转待复核，3 条从初筛候选转待复核。筛选采用保守规则，待复核仍需人工解释。20 条任务记录逐项相等，包含 20 个初始 AP、全部候选、每条路线与合计 807 个原生和带噪配对采样点。候选最大水平距采样路线 2.00 m，均在楼层容差内。20 个默认 AP 到参考路线各采样点均获得有限的原生测地距离。

- CPU 执行提交 `666cc3eb31d1d15ae769d8e0e71e3b776d567e23`。数据 `runtime/diagnostics/single_floor_ap_review_20261119_reaudit/`，日志 `runtime/logs/single_floor_ap_review_20261119_reaudit.log`。复用 Habitat 0.3.0；模型调用数为 0。
- 新数据 SHA256 `436f47b920fc4466898ffd0843c6547385b887202eed1ab9114fc3efaf7984e3`，新范围审计 SHA256 `eaaa60b4f6c52c45ee889f203a6e4dbad263c98612ae6d73367b70bfb30dd147`。范围审计新增原指令和匹配短语供追溯。
- 本机 v3 报告 `runtime/reports/single_floor_ap_review_20261119_v3/index.html`，SHA256 `0c31cb69bad1ff77a2e4298995da4bcec54d62abdc313487878091c721350896`。入口为 `python3 scripts/render_ap_review_html.py --audit <范围审计JSON> --data <布局数据JSON> --output <HTML路径>`。
- 修复编辑后参考路线仍只显示旧 AP 导致的歧义。新版地图和草稿曲线都使用实际图边权重计算，曲线横轴使用累计米数，初始原生曲线单独标识。旧导入流程直接信任 JSON 中的坐标，失败时可能留下部分草稿；新版核对布局、候选、坐标和来源，整份通过才应用。
- 8 项单层规则和信号辅助测试通过。隔离的本机 Chrome 实际检查了桌面与 390 px 窄屏、按图点击 AP、路线预览更新、图层切换、撤销、草稿导出、合法及错误导入、搜索 97 号记录，并观察了截图；浏览器页面零外部 HTTP 请求。

当前热图是可走网格着色，房间语义与视觉地标待人工核对。正式使用草稿布点之前仍须用原生 navmesh 和信号代理重算。开发场景与布局之外的泛化和真实无线表现待独立评估。

## Habitat 原生俯视底图

本机 v4 报告默认显示 Habitat-Sim 0.3.0 的 `PathFinder.get_topdown_view` 输出。5 个场景中的 20 条任务共引用 9 个不同高度的切片，分辨率 0.05 m/像素，垂直容差 ±0.20 m。底图按 X/Z 米制坐标与路线、AP 和起终点对齐。叠加的 RSSI 继续用 0.40 m 粗网格估计，并裁切到俯视可通行区域。底图显示 navmesh 可走区域及边界，视觉材质和房间名称仍需独立查看场景。

- 导出脚本 `scripts/export_ap_review_topdown.py`，执行提交 `c3e10da101134ac0b03739b77c181da99fb42b66`。输入为复查批次 `ap_review_data.json`，按 navmesh SHA256 确认场景资源，逐任务核对起终点、初始 AP、全部候选和路线采样共 4,124 个位置。核对允许 ±2 像素边界余量。
- 服务器图层数据 `runtime/diagnostics/single_floor_ap_review_20261119_topdown/habitat_topdown.json`，SHA256 `fbff3375028edeadccaa24fb40d2ada92441b305a0cbabf47df06f6b5f33fa0b`。
- 本机生成报告时给渲染器增加 `--topdown <地图数据JSON>`，报告为 `runtime/reports/single_floor_ap_review_20261119_v4/index.html`，SHA256 `4a421096bbbfaf7d8e01226239a606e49cea671c0c002d6c8703c514b072d1b1`。Chrome 检查整层、回到路线、叠加 RSSI、点击 AP 及导入导出。

## AP 草稿验收与重算

在本机报告逐任务审阅，完成后点击「导出 AP 草稿」。服务器在独立目录确认草稿与原任务、坐标、navmesh 和参数指纹一致，对每个改动 AP 到参考路线的全部采样点做原生同层可达核验，然后生成新的布局、参数和验收记录。任何失败都需要保留该草稿供复核。所有成功的计算仍是单层开发审阅，手工校正集的用途和冻结条件另由 benchmark 协议决定。

服务器入口如下。`draft` 指向上传到项目 `runtime/` 的 JSON，`revision` 指向一个尚未创建的输出目录。

```bash
base=runtime/diagnostics/single_floor_ap_review_20261119_reaudit
draft=runtime/diagnostics/ap_review_drafts_20261120/wifinav-ap-review-edits.json
revision=runtime/diagnostics/single_floor_ap_revision_01
habitat=/opt/anaconda3/envs/habitat0.3.0/bin/python
radio=runtime/envs/sionna_rt_2_2_0_py311/bin/python

"$habitat" scripts/prepare_ap_review_revision.py --data "$base/ap_review_data.json" \
  --audit "$base/source_scope_audit.json" --draft "$draft" \
  --multiwall-config configs/benchmark/single_floor_multiwall_dev_v1.json --output-dir "$revision" &&
"$radio" scripts/run_single_floor_multiwall_dev.py --data "$revision/ap_review_data.json" \
  --config "$revision/multiwall_config.json" --output "$revision/report.json" &&
"$radio" scripts/export_multiwall_ap_preview.py --data "$revision/ap_review_data.json" \
  --multiwall-report "$revision/report.json" --output "$revision/grids.json" &&
"$habitat" scripts/export_ap_review_topdown.py --data "$revision/ap_review_data.json" \
  --output "$revision/habitat_topdown.json" &&
"$radio" scripts/export_ap_review_scene_views.py --data "$revision/ap_review_data.json" \
  --topdown "$revision/habitat_topdown.json" --multiwall-report "$revision/report.json" \
  --basis-decoder runtime/tools/basisu_v1_60/decode_basis_ppm --output "$revision/views.json"
```

`revision.json` 记录原始输入、草稿、派生输入的 SHA256，以及逐个改动的位置和原生核验。服务器的 `report.json` 与 `grids.json` 分别提供四组多墙曲线和楼层网格。将本批生成的布局、审计、底图、报告、网格、纹理 JSON 复制到本机，在本机运行 `render_ap_review_html.py` 生成新版。JSON 与 HTML 留在各项目 `runtime/`，源任务、全量筛选统计和已有布局报告保留。若基于已重算报告继续编辑，使用它对应的布局、审计和多墙配置作为下一批输入。
