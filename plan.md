# WiFiNav 项目计划与进度

> 更新于 2026-11-24。当前只做单层 HM3D ObjectNav benchmark。每次变更、验收或遇到阻塞时更新本文件，并链接可核验的证据。

## 0. 当前主线与交接

**首版目标。** 给一批官方 ObjectNav 任务配上可重算的室内 Wi‑Fi 覆盖，在同一份结果里看到机器人有没有找对目标、走了多远、经过弱信号区多久。用一个可复验的路线对照说明覆盖差异有可能影响选路。首版交付物是**任务清单、AP 与 RSSI 配置、评分入口和本机审阅报告**。

| 状态 | 已知情况 |
|---|---|
| 已确定 | HM3D ObjectNav v2，首版只做单层、每个布局一个 AP、模拟 RSSI。开发使用官方 `train`，保留评估候选使用 `val` |
| 已就绪 | 服务器已安装官方任务包 186 个文件及 ObjectNav v2 `train` 引用的 145 个 HM3D 场景。三个原始 tar 已上传并通过 SHA256 对比，145 个导航网格均由 Habitat 0.3.0 在 CPU 读入，另抽一处验收任务和语义 |
| 当前工作 | 已固定官方 `train` 20 条单层任务、5 个场景、7 套单层 AP 草稿。首轮 RSSI 与同起终点绕行对照已完成，等待本机 HTML 审阅。正式评估 `val` 场景待补。见 [首批 AP 审阅](docs/experiments/objectnav_train_ap_review_2026-11-24.md) |

首版以信号覆盖作为环境和评分变量，仿真中的模型服务全程可用。请求掉线、恢复、本地识别和通信感知导航器属于历史讨论，保存在 [范围收紧前的计划](https://github.com/Or1ginnn/WiFiNav/blob/e2615326f4f826d2826283542d5b799bfde0d029/plan.md)。

## 1. 选任务

- 首批约 **20 条官方任务、最多 5 个授权开发场景**。保留原起点、朝向和目标类别。验证至少一个合法成功视点可从起点同层到达。记录源 split、场景、原文件和记录序号，保留原 episode ID。源任务照原样存放。
- 任务保持「找椅子」这种目标类别输入。目标具体位置、评估视点和完整 RSSI 场留给构建与评测。机器人如何探索、何时停下由接受评测的导航策略决定。目标在房间深处、被遮挡或所在区域信号差时，照常保留并按原 ObjectNav 规则评分。
- 按预先固定的场景及类别规则选样。开发与保留集按物理场景隔离。官方 `val_mini` 和已安装的公开 `val` 样例用于工程加载与评分检查。正式任务与 AP 布局在评测之前固定。[官方任务说明](https://github.com/facebookresearch/habitat-challenge#task-objectnav)

## 2. 放 AP 与生成 RSSI

- 自然任务先用**每个场景楼层一套布局、每套一个 AP**。把 AP 放在有物理依据的位置，例如室内墙面或设备架附近，记录坐标、高度与发射参数。同层任务共用布局。首批人工审阅允许修改 AP，修改后保存新版本并重算覆盖。
- 复用现有多墙传播方案，先核验 HM3D 的墙体几何能正确输入模型。固定传播参数、采样规则、接收高度和弱信号阈值。查验起点、房间、走廊、门口和若干有效成功视点的 RSSI。弱覆盖目标只需记录覆盖证据，缺证据保留待核验状态。[原多墙试点](docs/experiments/rss_multiwall_pilot_2026-11-19.md)
- 本机 HTML 展示 Habitat 俯视图、AP、RSSI 热力图、按阈值生成的覆盖边界和参考路线。继续提供点选 AP 与导出草稿。草稿经校验后重算，审阅用 HTML 留在本机。

## 3. 评分和制作验收

**评分。** 同一份轨迹用 Habitat ObjectNav 口径算 SR/SPL，并报告路径长度、低于冻结 RSSI 阈值的累计运动时间和最长连续低信号时间。复用离线 RSSI 积分器，计量用统一模拟运动时间。缺测留空，失败和已记录的轨迹前缀保留。弱 RSSI 时间描述模拟覆盖暴露。[Habitat-Lab 0.3.0 任务配置](https://github.com/facebookresearch/habitat-lab/blob/v0.3.0/habitat-lab/habitat/config/habitat/task/objectnav.yaml)

| 制作验收 | 通过时能看到什么 |
|---|---|
| 任务合法 | 清单可追溯、同层可达、官方 STOP/SR/SPL 用例通过。评测策略输入保持目标类别与允许的观测 |
| RSSI 可复现 | 同一场景、AP 和配置能重算相同覆盖，抽查信号与场景遮挡是否对应 |
| 路线差异可验证 | 独立选一个同起终点的例子，用同一 AP 比较较短路线和预算内绕行的距离、累计低信号时间。自然任务允许只有一条路或绕行无收益。若受控例子也没有稳定差异，记录首批覆盖设计缺口 |
| 交付可用 | 清单、AP 配置、RSSI 查询、评分入口和本机地图报告齐全，记录数据与配置版本、排除原因及缺测 |

参考路线供离线验收。整条任务路线由后续接受评测的策略自行产生。首版按此次制作协议交付数据与工具，方法收益由后续实验验证。

## 4. 当前执行顺序

1. **已做工程检查。** 干净版本 `e261532` 上，用公开场景的原导航网格和 Habitat 0.3.0 的视点评分器离线验证。已到达且 STOP 的成功值为 1、SPL 约 1，已到达但未 STOP 和起点 STOP 的成功值均为 0。使用预先计算的探针轨迹，未进行机器人搜索。结果在服务器 `runtime/diagnostics/objectnav_scoring_smoke_20261122/score.json`。本机已有 RSSI 积分测试 9 项通过。
2. **开发场景已入库。** 本机三份原始 tar 已校验并上传到服务器 `runtime/data_imports/hm3d_train_v0.2/`，导入的 145 个场景在 `data/scene_datasets/hm3d_v0.2/train/`。验收记录为 `data/_manifests/hm3d_objectnav_v2_train_install.json`。
3. **首批 AP 可以审阅。** 固定 20 条任务后计算了 7 层 × 16 个候选位置。离线对照比较 84 条合格绕行，2 条任务的 17 条备选路线在两种采样步长下都减少了至少 0.50 米的弱信号路段。HTML 位于本机 `runtime/reports/objectnav_train_ap_review_20261124/index-reviewed.html`。
4. **下一步。** 审阅 AP，优先核对默认覆盖率 4.7% 的 `j2EJhFEQGCL/L1` 和 16.8% 的 `g7hUFVNac26/L1`。根据草稿校验坐标、重算并冻结布局；随后在固定任务上接通 RSSI 查询及官方 STOP/SR/SPL 的轨迹评分验收。保留集场景和导航方法实验留待后续。

## 5. 历史记录

- 原 R2R-Conn B3 保留。70 次实际执行、90 个 case，结论为 No-Go。[完整 B3 记录](docs/experiments/b3_full_2026-11-12.md)
- 原 R2R-CE/MP3D 数据和单层 AP 审阅供复现与工具参考。[旧 AP 审阅](docs/experiments/single_floor_ap_review_2026-11-19.md)
- 2026-11-22，转用 HM3D ObjectNav 官方任务并安装一个公开场景。[数据验收](docs/DATASETS.md)
- 2026-11-22，将首版收敛到制作任务清单、AP、RSSI 与评分。保留弱信号和遮挡任务，把部署与掉线行为移出首版。
- 2026-11-23，核实服务器能直连 Matterport。提供隐藏输入 Token 的服务器直下入口，尚无授权 `train` 下载产物。
- 2026-11-23，准备本机项目及服务器暂存目录，切换为本机通过官方 API 下载后校验上传。浏览器途径未落盘。
- 2026-11-24，确认用户下载的三个原始包完整，完成上传及 145 个 ObjectNav `train` 场景的导入和 CPU 资产验收。
- 2026-11-24，完成 ObjectNav `train` 首批几何抽审、AP 覆盖和绕行对照；记录语义缺标、低覆盖布局与独立复算证据。[首批 AP 审阅](docs/experiments/objectnav_train_ap_review_2026-11-24.md)

新聊天先读第 0 节和第 4 节。需要操作服务器时核对 [数据配置](configs/data/objectnav_hm3d_v2.json)、[环境记录](docs/LOCAL_ENVIRONMENT.md) 与实际状态。
