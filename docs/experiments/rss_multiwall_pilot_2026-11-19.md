# 单层多墙 RSSI 传播模型试点

2026-11-19。目标是在固定任务与 AP 条件下，评估基于实际墙门几何的多墙近似能否替代 navmesh 绕行量作为正式 benchmark 的 RSSI 生成候选。多墙方法有室内 WLAN 规划实例及已发表模型。试点实现使用单层直达路径和公开的模型结构，穿透损耗取预先设定的敏感性参数。[Altair WinProp 示例](https://help.altair.com/winprop/topics/winprop/example_guide/network_planning_projects/comm_80211_multiwall_cost_indoor_winprop_c.htm) · [Lott 与 Forkel，IEEE VTC](https://ieeexplore.ieee.org/abstract/document/944886)

## 实现与固定设置

- 使用上一批配对输入 `runtime/diagnostics/rss_pilot_20261119/paired_input_v2.json`，SHA256 `d1508b387093000c0bd642c8f75e3100c68c29f44172baa80c03a71ba4f02a25`。同层四条参考路线 121、134、235、512，每条使用同样的两个 AP 位置，共 340 条直连收发链路。收发高度、绝对坐标与 −48 dBm 的 1 m 参考功率沿用上一批。
- [Matterport3D 语义格式](https://github.com/niessner/Matterport/blob/master/data_organization.md) 的 `_semantic.ply` 给出三角面的对象 ID，`.house` 衔接到类别。计算每条 AP→机器人线段沿途与墙、门、窗的交点。合并近邻表面来近似识别同一堵墙的前后面，同组只扣一次最大损耗。合并距离取 0.20/0.35 m。门框保持与门扇分开。
- 接收功率按 1 m 参考功率减去自由空间距离损耗，再减去墙、门、窗穿透损耗。低损耗分别为 3/2/2 dB，高损耗为 8/5/4 dB。四组假设独立报告。数值是敏感性测试档位，需要真实测量校准。模型间距衰减和阴影设置也有差异，因此整个对照反映模型差异，无法单独归因于墙体项。
- AP 排序使用上一批同一规则。先比低于 −75 dBm 的参考路线长度，差在 0.25 m 内时用 P10 RSS 比较，P10 差在 2 dB 内时判平。输出保留逐点交点和各假设下的沿途信号。无射线追踪反射、衍射或真实链路流量。

## 实际结果

试点语义资产 4,627,359 个顶点、9,048,926 个三角面，所有面 ID 都能关联到 `.house` 对象。链路包围盒内含 325,801 个墙面、88,526 个门面及 31,849 个窗面三角形。340 条链路里，266 条命中至少一个选定语义表面，74 条未命中；本批未命中窗面。合成平面检查验证了多面交点、双表面合并和接收端截断。实际场景第二次计算的 340 条交点及全部功率曲线逐项一致。其余四个开发场景均有相同类型的场景资产，几何标签质量与传播行为待逐场景验收。

| 任务 | 现有 navmesh 代理 | 多墙四组假设的 AP 排序 | 多墙在优先 AP 下低于 −75 dBm 的路线长度 |
|---|---|---|---:|
| 121 | B | B | 3.45–9.17 m |
| 134 | A/B 判平 | A | 1.19–5.29 m |
| 235 | A | A | 0–0.25 m |
| 512 | B | B | 0–1.08 m |

多墙四组假设均输出 8/8 个完整路线剖面。AP 的相对排序在本轮设定下稳定；235/A 与 512/B 的全程覆盖分类随损耗档位改变。射线追踪的有效读数可作参考，上一轮整体仍有缺测和种子敏感，不能作为验证准确率的实测参照。

## 选型与后续验收

多墙模型作为正式版 RSSI 的首选候选。先在已有五个开发场景检查墙、门、窗标签和近邻面合并的可靠性，并在可获得实测的场景校准频率和设备相关的墙体损耗。评估以留出的路线及 AP 布局验证弱区位置和 AP 排序。材料敏感的布局保留待复核，等判断稳定后才冻结覆盖标签。现有 navmesh 代理继续作为合成比较基线，Sionna RT 用于复核转角和多径可能影响决策的少量布局。上述验证完成前，正式主场和物理保真度仍未冻结。

## 复现与产物

- 执行提交 `e9e40c435f9a868169d014e9b6c123b551165097`，配置 `configs/wireless/rss_multiwall_pilot_v1.json`，SHA256 `653d63ca0e13677024c96d873c11c58231ece76cab1bc0236001dc4ee979da49`。
- 语义 PLY SHA256 `224ec2eda057c15c7822c3de74852576f8d28ce4d78b1ac4ba60337857d5549a`，house SHA256 `a4a2003cf551c5427c9910330739af4016c61aefc78c6a2381c23ff3f69b3b54`。
- 入口 `scripts/run_rss_multiwall_pilot.py --input <配对输入> --config <多墙试点配置> --output <新目录>/report.json`。沿用项目内的 Python 3.11、Mitsuba/Dr.Jit CPU 环境和 LLVM 19，单批约 5.3 秒（脚本内部计时），模型调用数 0。
- 原始结果在服务器 `runtime/diagnostics/rss_multiwall_pilot_20261119/report.json`（SHA256 `69910e5fcb1ca41f618356aea21a214b6f97e508312e243639b913913097007b`），日志为 `runtime/logs/rss_multiwall_pilot_20261119.log`。

## 用户确认采用与五场景开发验收

用户确认首版 RSSI 传播模型采用语义多墙。实际构建配置为 `configs/benchmark/single_floor_multiwall_dev_v1.json`，`rss_backend=semantic_multiwall`。开发验收沿用原审阅的 20 条路线及其各自的 AP 初值，按同一组损耗与墙面合并条件重算参考路线，每条任务生成四条曲线。使用同一 −75 dBm 仿真阈值，保留敏感分类。这个批次用于验证场景覆盖和接口；正式布局生成规则、穿透损耗和评测标签仍待校准。

| 场景 | 地面位置对齐 | 四假设全程覆盖 | 假设敏感 | 四假设均含低于阈值的路段 |
|---|---:|---:|---:|---:|
| 17DRP5sb8fy | 149/149 | 3 | 1 | 0 |
| 1LXtFkjw3qL | 160/160 | 2 | 2 | 0 |
| 1pXnuDYAj8r | 213/213 | 1 | 2 | 1 |
| 29hnd4uzFmX | 131/131 | 3 | 1 | 0 |
| 2n8kARJN3HM | 174/174 | 2 | 2 | 0 |
| 合计 | 827/827 | 11 | 8 | 1 |

20/20 路线、80/80 剖面完整，全部语义网格可解析。807 个 AP→路线点链路中，242 个命中结构面。坐标核查独立使用 GLB 物理场景，包含 807 个参考采样位置和 20 个 AP 锚点。AP 坐标与原审阅批次逐条相等。旧两 AP 试点用新代码重算，340 个交点列表、全部曲线及 AP 排序逐项一致。

敏感布局为 575、743、818、214、825、208、235、512，应优先核查墙面分类及穿透参数。493 在四组假设下都有低于阈值的参考路线段，范围 0.21–1.58 m，是否存在仍符合原指令的可在线替代路线待独立核查。当前结果是沿参考路线的模拟覆盖，语义映射与地面对齐通过提供的是工程证据。实际 RSSI、墙体损耗及真实掉线待实测验证。

- 执行提交 `b986326352d65041a51aa2f0b3e0e5675d3f35a6`。配置 SHA256 `ff415158c21bc04a96122a22bed6178b199c8867c494db245cc3bd67e49c74fa`，固定原 AP 审计数据 SHA256 `436f47b920fc4466898ffd0843c6547385b887202eed1ab9114fc3efaf7984e3`。
- 入口 `scripts/run_single_floor_multiwall_dev.py --data <原AP审阅数据> --config configs/benchmark/single_floor_multiwall_dev_v1.json --output <独立目录>/report.json`。沿用原 Mitsuba/LLVM 19 CPU 环境，4 个 CPU 核，脚本内计时 16.9 秒。未调用模型。
- 报告 `runtime/diagnostics/single_floor_multiwall_dev_20261119/report.json`，SHA256 `14b0e78b3643365af2682ad4052360836e2d90d9da76529d297b951febbdd196`。逐场景语义资产、GLB、navmesh 哈希与逐点证据均在报告内。日志 `runtime/logs/single_floor_multiwall_dev_20261119.log`。
