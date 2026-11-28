# Social Navigation benchmark 对照与 WiFiNav v1 审查

2026-11-28。对照任务定义、场景设计、评分、基线和公开复现入口。优先读论文正式版本、作者的版本化预印本和评测仓库。本文的完成度判断属于项目审查。文献来源提供评测实践和作者建议，各会议没有统一的导航 benchmark 准入门槛。第 2 节记录修复前的 v1 状态，最新工程结果见第 4 节。

## 结论

WiFiNav 已完成一套可冻结的单层、模拟 RSSI ObjectNav **数据与离线参考 v1**。原始任务清点、AP、模拟信号、参考路线与内部复算都有证据。在此基础上，v1.1 补齐同层评分与闭环入口，通过 20 题的工程对照及独立复跑。论文主评测仍需具代表性的 ObjectNav 基线与更大规模的公平对照。[v1.1 验收报告](../experiments/objectnav_benchmark_v11_acceptance_2026-11-28.md)

本项目的问题是「机器人寻找目标物体时，能否少走弱信号区，同时保住找物体的表现」。应评测导航能力和通信覆盖两个维度。人群交互、社交行为、长文本路线指令和人类主观评分属于各文献具体任务的观测对象。模拟 RSSI 可用于覆盖诊断。关于丢包、时延、真正掉线或远端模型服务可用性的结论，需要链路模型或设备上的测量。

## 1. 代表工作具体怎样评测

| 工作 | 评测单位与设计 | 指标、对照与可迁移点 |
|---|---|---|
| **Habitat Challenge 2023 ObjectNav** | HM3D-Semantics v0.2，145/36/35 个 train/val/test 场景，6 类目标。给目标类别和传感器，固定机器人、动作及控制配置。官方说明任务可在同层完成。 | 同层可解是任务性质。WiFiNav 若要求实际轨迹全程单层，执行边界和最短路分母必须显式规定。赛题用 Stretch 连续控制，直接比较绝对 SR/SPL 时还要对齐机器人、观测和预算。[官方挑战赛](https://github.com/facebookresearch/habitat-challenge#task-objectnav) · [配置](https://github.com/facebookresearch/habitat-challenge/blob/main/configs/benchmark/nav/objectnav/objectnav_v2_hm3d_stretch_challenge.yaml) · [ObjectNav 评测定义](https://arxiv.org/abs/2006.13171) |
| **HA-VLN 2.0** | 把动态行人、社会距离和相关语言加入 R2R-CE。90 个建筑扫描、16,844 条指令，公开划分，test 为 18 个保留建筑上的 3,408 条指令。提供离散和连续协议。 | 同时看到达准确度和人际碰撞。官方榜单的 SR 包含无碰撞条件，另报 NE、CR、TCR，区分 zero-shot 和 retrained。作者统计 35.5% 的路径与行人运动相交，说明新增变量确实有机会影响路线。沿用「先量化有机会改变行为的样本」的做法，比例由各自任务定义决定。[论文 §3、§5、§7](https://arxiv.org/html/2503.14229v5) · [官方榜单与定义](https://uwmilab.github.io/HA-VLN-webpage/) |
| **LISN-Bench**（ICRA 2026） | Arena 3.0 内定义 5 类具体任务，覆盖跟随行人、避让行人、到某区域、避开某区域。每任务至少 3 种场景变体，各随机初始化重复 5–9 次。 | 成功包含任务规定的行为，另看碰撞、平滑性、人群与区域合规指标。两种对照与作者方法使用相同 GPT-4o。可借鉴的是固定其余条件、对比是否接入新增信息，以及在同一设计下检验不同难度。[正式会议议程](https://ras.papercept.net/conferences/conferences/ICRA26/program/ICRA26_ContentListWeb_3.html) · [论文 §III、§V](https://arxiv.org/html/2512.09920v1) · [作者实现](https://github.com/Social-Nav/tvss_nav) |
| **SocialNav 的 SocNav Benchmark**（CVPR 2026） | PointGoal 闭环评测，用 Isaac Sim 与 3DGS，在训练未见的 9 个新场景中各取 20 个 start–goal case，合计 180 个。近距离和远距离分别采样。论文中的约 700 万样本属于训练数据。 | SR、路线完成度、SPL 与社会合规的距离比例和时间比例并列。作者的合规率将失败赋 0，且在共同起终点的实机试验中比较方法。WiFiNav 可以独立报告覆盖和任务完成，也应防止提前停下造成人为低暴露。升级公开版 ABot-Navigation 提供固定阈值、统一 agent 接口及单一评测命令，采用自己的指标口径。[论文 §3、§5](https://openaccess.thecvf.com/content/CVPR2026/papers/Chen_SocialNav_Training_Human-Inspired_Foundation_Model_for_Socially-Aware_Embodied_Navigation_CVPR_2026_paper.pdf) · [升级版仓库](https://github.com/amap-cvlab/ABot-Navigation#metrics) |
| **HabiCrowd**（IROS 2024）与 **SocNavBench** | HabiCrowd 在 HM3D 加模拟动态行人，480 个场景，400/40/40 划分，按行人密度覆盖难度。SocNavBench 用真实行人轨迹构造可复现的情境。 | HabiCrowd 验证行人动力学，并在 PointGoal 和 ObjectNav 上比较五种基线的 SR、SPL、到目标距离和单位距离人机碰撞。SocNavBench 统一比较多种方法，分别量化效率、避碰、社会遵从。对 WiFiNav，密度对应的是覆盖条件的多样性，行人模型验证对应的是对 RSSI 模型及阈值的验证。[HabiCrowd 原论文 §IV](https://www.csc.liv.ac.uk/~anguyen/assets/pdfs/2024_IROS_Habicrowd.pdf) · [SocNavBench 原论文](https://arxiv.org/abs/2103.00047) |
| **CapNav**（CVPR 2026） | 45 个真实室内场景、473 个起终点任务，按 5 种身体与行动能力构造 2,365 个问答。用场景图标注门、楼梯、尺寸等限制。 | 分别评可达判断、路径有效性、是否符合移动能力及推理。测试 13 个 VLM，并分析不同能力的失败。它采用离线输出评估，适合借鉴明确边界、逐条件给结果的方法。[CVPR 原论文](https://openaccess.thecvf.com/content/CVPR2026/html/Su_CapNav_Benchmarking_Vision_Language_Models_on_Capability-conditioned_Indoor_Navigation_CVPR_2026_paper.html) |

之前调研过的方法论文也有对照实验。VLM-Social-Nav 在 4 类真实人机相遇情境中比较 DWA 和行为克隆，并做用户研究。CoNVOI 比较室内走廊、室内行人、多种室外地面和人行横道四类情境。BehAV 在 5 类真实室外情境中各做至少 10 次，分别报告成功、行为规则遵从和与人遥操作路径的差距。G2-Nav 区分 SCAND 记录的轨迹预测和真实交互，前者比较位置与角度误差。Social-LLaVA 的 SNEI 和 CoRL 2025 的 SocialNav-SUB 评模型对社会情境的理解，后者以视频问答为主。横向比较时要明确各项实验是否实际执行，以及是否共享评测协议。[VLM-Social-Nav](https://arxiv.org/html/2404.00210v2) · [CoNVOI](https://arxiv.org/html/2403.15637v1) · [BehAV](https://arxiv.org/html/2409.16484v2) · [G2-Nav](https://arxiv.org/html/2607.16956v1) · [Social-LLaVA](https://ieeexplore.ieee.org/document/11247618/) · [SocialNav-SUB](https://proceedings.mlr.press/v305/munje25a.html)

通信领域更接近的是 Gordon 等的 INFOCOM 2026 工作。他们将传播图转为不同应用的端到端通信风险，将吞吐量、时延及误包率纳入定义，对比按通信风险规划与最短路径，并检查阈值变化。这是通信感知运动规划先例。WiFiNav 的研究区别需要在 ObjectNav 的目标搜索、冻结的共享评测任务，以及闭环方法比较中体现。[IEEE 正式论文](https://ieeexplore.ieee.org/abstract/document/11571354) · [作者全文 §IV–V](https://www.tkn.tu-berlin.de/bib/gordon2026communication-aware/gordon2026communication-aware.pdf)

## 2. 综合标准及本项目证据

Francis 等的 ACM THRI 指南把评价目标行为、定量指标、对照基线、可复现与可扩展、用人类数据支撑评价、验证评价工具列为六项建议。迁移到 WiFiNav，核心是指标要衡量预期属性，新增属性要能改变决策，且横向比较应共享评测条件。对人的评价证据只适用于人机交互主张。对模拟通信的外部验证应与论文的实际链路主张匹配。[Francis 等 §5](https://doi.org/10.1145/3700599)

| 审查维度 | WiFiNav v1 判断 | 证据与边界 |
|---|---|---|
| **任务定义和来源** | 数据层达到 | 从 HM3D ObjectNav v2 官方 `val` 的 1,000 条记录中逐条筛选。正式纳入 961 条、36 个场景、74 个场景楼层、6 类目标。保留 28 条无已验证的同层 STOP 和 11 条起点资格未过的记录。排除数按本项目更严格的几何见证规则统计。 |
| **覆盖面与通信挑战** | 达到首版静态仿真范围 | 256 条几何线全程达标，8 条换路全程达标，697 条仍有弱区。冻结的双采样 0.50 m 改善口径有 154 条（16.0%），分布在 29 个场景、38 个楼层。采用全部 961 条做主结果。比对共享 AP 的任务时，以场景为单位考虑相关性。每层一个固定 AP、单档位、静态传播的跨条件泛化需另验。 |
| **参考路线和制作复现** | 内部达到 | 独立审计核对输入文件、合法 AP、几何与 RSSI 路线及端点。以 1.875 cm 与 3.75 cm 复算。整批审计复跑逐字节一致。同一固定 STOP 的蓝线用于诊断已知地图上的可行取舍。当前离散图、顺序目标和固定停车点界定了 Oracle 的范围。 |
| **评分定义和实际约束** | 单层闭环未达到 | 既有轨迹评分按全场景官方成功视点查询，接收轨迹时未约束全程同层。`bCPU9suPUw9` 源行 0 的 Habitat 动作在离起始层高度 2.80 m 处 STOP，仍得到成功 1、SPL 0.271。现有评分的其他小批证据包含成功与提前 STOP。 |
| **公平的闭环对照** | 未达到 | 冻结几何线与 RSSI 线均为固定 STOP 的离线路线。仓库中的当前 ObjectNav 入口可以回放轨迹并评分。尚无使用正式清单、统一在线观测和动作预算的策略结果表。历史 R2R-Conn B3 涉及另一任务。 |
| **数据划分和信息隔离** | 原 split 清楚，协议待闭合 | `train` 用过开发，正式 `val` 曾用于构建复审与工程排错。采用冻结的公开 `val` 测可比结果。要求独立盲测时需冻结另外一批按物理场景隔离的评估任务。模型输入、完整地图、AP 坐标、未来 RSSI 和参考 STOP 的权限须在可执行接口中落实。 |
| **通信指标的有效性** | 模拟覆盖达到，服务指标待证 | 用 SR/SPL/路长和双阈值弱区累计距离、严重弱区最长连续距离、累计信号缺口并列报告。现在服务全程可用。阈值为模拟覆盖等级。12 条蓝线绕行达到两倍，最大约 4.81 倍，另有 55 条的弱区改善量在两个采样间距下变化至少 0.10 m。应披露取舍及模型敏感性。 |
| **第三方复现包** | 部分达到 | 仓库已有构建、审计入口和配置，部署、探针、哈希、报表均有记录。仍需固定 agent 接口、评分命令、测试样例和一条从合法取得资源到结果的流程。HTML 截图和纹理依现有约定留本机。HM3D 源数据按官方授权取得，发布前核查派生文件范围。 |

本轮重新读取正式清单和审计，核对了 SHA256 `96a7946a41d5183873125d9defc13a2b7124355827ab59fb2f52e2b6f69c5383`。154 条中的 148 条虽然明显改善但仍有弱区，另外 6 条换路后全程达标并达到明显改善门。100 条 HTML 有意多展示罕见例子，比例以正式 961 条为准。[全量验收与分层抽审](../experiments/objectnav_val_small_2026-11-26.md#2026-11-28-成品复审与分层抽审) · [评分实现](../../scripts/score_objectnav_trace.py) · [指标判据](../../scripts/build_objectnav_benchmark.py) · [官方 HM3D 获取与条款](https://github.com/matterport/habitat-matterport-3dresearch)

## 3. 成为可供论文使用的闭环 benchmark 的最小验收

1. **冻结单层任务协议，修复已复现的评分缺口。** 规定起始层约束、合格 STOP、跨层事件的终止与计分、超时和碰撞记录。若采用严格单层评分，SPL 的参考距离应与允许的同层空间、全部合格停止位姿一致。蓝线和单个参考 STOP 继续作为诊断。先用同层成功、提前 STOP、真实跨层轨迹和失败前缀做回归。锁定传感器、位姿、动作、预算和终止条件。
2. **提供可跑的策略基线和同样本对照。** 首表使用一个可复跑的 ObjectNav NoSignal 基线。保持导航器、动作和预算一致，做一组使用可用 RSSI 输入的闭环对照。全图 RSSI 条件明确标作特权诊断。同一任务的不同方法按键配对，报告失败、超时及缺测。全体与共同成功任务并列呈现，分别显示导航和覆盖。样本多的楼层仍共享信号图，统计区间建议按场景整组重采样。
3. **验证通信组的区分度与稳健性。** 在固定评测清单上分别报告覆盖良好、换路达标、可改善但有残余、未达改善标准的组。开发诊断可用同一试题的平坦信号场作负对照，采用冻结的轻量阈值扰动或少量替代 AP 作敏感性检查，分别存放。要宣称链路服务改善时，按具体服务补测端到端丢包、时延或请求恢复。
4. **打包可独立复跑的最小发行版。** 提供冻结清单版本、数据来源和许可要求、统一运行命令、闭环 agent 接口、评分脚本及小样例期望结果、基线汇总和已知局限。让另一环境按文档从用户自有的授权资产复跑小批。公开榜单可以在评测流程稳定后建设。

上述条目是依据文献与本项目证据提出的发布检查。本文完成了调研和清单复核。闭环回归、方法实验和链路实测以各自后续实际记录为准。

## 4. 10 月调研附件与 v1.1 复审

附件前两页的六篇方法论文均有正式发表记录。EnvGuard 为 RSS 2026。Social-LLaVA 为 IROS 2025，CoNVOI 为 IROS 2024，BehAV 和 OLiVia-Nav 为 ICRA 2025，VLM-Social-Nav 为 RA-L 2025 年 1 月刊。附件中其余 RF 研究的发表状态应逐条核对。[历史附件存档](wifi_aware_vln_literature_review_2026-10-15.pdf) · [EnvGuard](https://roboticsproceedings.org/rss22/p133.html) · [Social-LLaVA](https://ieeexplore.ieee.org/document/11247618/) · [CoNVOI](https://doi.org/10.1109/IROS58592.2024.10802716) · [BehAV](https://doi.org/10.1109/ICRA55743.2025.11127890) · [OLiVia-Nav 作者机构](https://asblab.mie.utoronto.ca/publications/2025.html) · [VLM-Social-Nav](https://ieeexplore.ieee.org/document/10777573/)

附件的核心可迁移点是直接量化新增约束。BehAV 在五种室外情境比较实际走法的规则遵从率。OLiVia-Nav 对同样的人机情境比较个人空间侵犯时间和路径误差。EnvGuard 在有烟、热、水等受控风险的实物环境比较导航暴露。Social-LLaVA 的四万余条是视觉问答数据量。按这些实验单位分别比较可以避免将问答、路线参考和闭环试验混计。[BehAV §V](https://arxiv.org/html/2409.16484v2#S5) · [OLiVia-Nav 论文](https://arxiv.org/pdf/2409.13675) · [EnvGuard](https://roboticsproceedings.org/rss22/p133.html) · [Social-LLaVA](https://ieeexplore.ieee.org/document/11247618/)

附件还列出了已经能在 Habitat 里提供视觉和 RF 观测的工作。WiFiSpaces / ViFiNav 与 Navigation with RF Cues 使用 RF 寻找发射设备。WiFiNav 以物体类别定义目标，用固定 AP 的覆盖作为路径代价与评测属性。附件提出过在线估计完整信号场、语言路线指令和云推理链路等问题。v1.1 的实证范围为单层 ObjectNav 与模拟 RSSI 覆盖，应以这个范围陈述贡献。[WiFiSpaces / ViFiNav](https://arxiv.org/abs/2610.12733) · [Navigation with RF Cues](https://arxiv.org/abs/2610.08105) · [云推理执行](https://arxiv.org/abs/2606.31497)

复核了 `dc882236` 的服务器结果。951 条参考距离精确，10 条保留区间。真实动作回归挡住了曾被判成功的跨层轨迹。固定 20 题配对与独立复跑的结果逐字节一致。两组仅 1 和 2 条成功，唯一共同成功的路线完全相同。ObservedRSSI 的全样本平均弱区距离为 5.72 m，NoSignal 为 2.69 m，其中包含失败前缀。数据集和工程协议已可验收，尚不能由此证明通信方法有效，也没有跨环境的独立复现实证。[验收、哈希与复跑命令](../experiments/objectnav_benchmark_v11_acceptance_2026-11-28.md)
