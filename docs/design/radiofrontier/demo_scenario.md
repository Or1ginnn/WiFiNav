# RadioFrontier 真实与半真实 Demo 环境协议

## 一、Demo 总体目标与证据定位

本项目最终需要在真实办公室或实验室环境中完成一个通信感知 Object Navigation Demo。

机器人接收任务：

> 在当前室内环境中寻找一个蓝色杯子。

机器人从固定起点出发，初始时不知道：

- 蓝色杯子的具体位置；
- 协作式无线锚点的真实位置；
- 在线构建的局部占据地图；
- 尚未经过区域的无线通信质量。

机器人通过 RGB-D 相机构建局部地图，使用 OpenFrontier 识别 visual frontier，并根据目标语义、探索价值和路径距离生成候选导航方向。

现实场景中设置两条都可能通往蓝色杯子的路线：

- **路线 A：路径较短，但经过 WiFi 弱信号区域；**
- **路线 B：路径略长，但整体 WiFi 连接更加稳定。**

Original OpenFrontier 主要考虑语义和路径距离，因此可能优先选择路线 A。

在 OpenFrontier 基础上，利用机器人沿途采集的真实 WiFi CSI：

1. 估计无线锚点相对方向；
2. 融合多个位置的 Bearing，建立 AP 位置后验；
3. 预测不同候选路径上的未来通信质量；
4. 在语义合理的 frontier 之间进行通信风险感知重排序；
5. 选择一条略长但通信更加稳定的路线；
6. 减少视频卡顿、云端 VLM 请求超时和过期决策；
7. 最终找到蓝色杯子。

Demo 需要展示的核心结论是：

> 不是让机器人追着 WiFi 信号走，而是在仍然优先完成蓝色杯子搜索任务的前提下，以有限的额外路径代价降低长时间通信中断。

本 Demo 的证据定位必须明确：

- Demo 用于验证系统可运行性、真实 CSI 接口和代表性闭环案例；
- Demo 不能替代大规模仿真、Oracle 生死实验和配对统计实验；
- 现场展示允许使用预先验收过的场地，但论文必须同时报告所有重复运行和失败案例；
- 视频、真实云端 API 和界面效果属于应用展示，不承担论文主证明链。

---

## 二、现实 Demo 的冻结边界

现实 Demo 不再使用仿真 CSI 作为机器人在线输入，而是使用：

- 真实移动机器人；
- 真实 RGB-D 图像；
- 真实机器人 Pose；
- 在线构建的局部占据地图；
- 协作式 WiFi 锚点；
- 真实 WiFi CSI；
- 真实 RSSI；
- 真实 SNR；
- 真实丢包、时延和带宽表现。

仿真阶段训练得到的模型部署在现实机器人系统中，对真实候选路径上的通信风险进行预测。

现实 Demo 冻结为：

- 单个静态、协作式无线锚点；
- 机器人端和锚点端均可采集并配对正向/反向 CSI；
- 机器人位姿、RGB-D 和局部占据几何可用；
- 仅使用历史 CSI，候选路径未来信号不能作为在线输入；
- 只做高层 visual frontier 重排序，不做低层 risk-aware A*；
- 所有方法共享相同 Top-K 语义候选、候选路径和额外路径预算；
- 网络失败采用预先冻结的确定性映射或 trace 回放，真实云端 API 仅用于展示。

整体路线为：

```text
有墙体的室内 CSI 仿真
        ↓
Oracle 价值验证（G1）
        ↓
生成训练数据并训练预测模型
        ↓
独立真实 CSI 校准与测试
        ↓
完成通信感知 Object Navigation
```

---

## 三、仿真模块的输入、处理与输出

### 3.1 仿真场景与基本假设

仿真直接面向带墙体的室内 ObjectNav 场景。它沿用 Dijkstra 等（2024）的双向 CSI、CFO/STO/WGN、虚拟天线阵列和 Bartlett Bearing 数据流，同时直接加入场景几何、墙体材料、穿透衰减、LOS/NLOS、空间相关阴影和位姿误差。

仿真器拥有完整场景和锚点真值，用于生成 CSI 与监督标签；在线算法只能获得历史 CSI、机器人里程计、已观测局部地图和候选路径。尚未经过区域的真实信号、锚点真实坐标及信道隐藏参数不能作为模型输入。

下面直接定义最终仿真的输入、处理和输出。

### 3.2 轨迹、无线与采样输入

#### 3.2.1 无线节点和机器人位置

可以调整：

- 锚点的二维或三维位置；
- 机器人初始位置；
- 锚点与机器人之间的距离；
- 锚点相对于机器人的方向；
- 不同 episode 中的锚点部署。

锚点位置可以在 episode 间随机生成，但属于仿真隐藏状态。它只能用于生成 CSI、生成监督标签和误差评测，不能作为部署模型输入。

#### 3.2.2 机器人运动轨迹与里程计

可以调整：

- 直线轨迹；
- 圆形轨迹；
- 弧形轨迹；
- 任意 ROS 机器人轨迹；
- 机器人速度；
- 轨迹长度；
- 轨迹持续时间；
- CSI 采样密度。

论文使用圆形和直线轨迹验证了不同虚拟天线阵列几何产生的 Bearing 特征：圆形轨迹通常产生更明确的唯一峰，直线轨迹可能产生镜像方向。

#### 3.2.3 双向链路与帧配对

需要配置并生成：

- 节点 $i$ 到节点 $j$ 的 CSI；
- 节点 $j$ 到节点 $i$ 的 CSI。

除链路方向外，接口必须记录 frame number、采样时刻和 pair-valid mask。原 WSR 使用 round-robin 请求-应答和 frame number 配对近同时刻的正反向包，不能只依赖近似时间戳。通过有效的正反向 CSI 相乘，抵消符号相反的 CFO 相位偏移。

#### 3.2.4 Carrier Frequency Offset

可以模拟：

- 线性频率偏移；
- 随时间变化的 CFO；
- 周期性 CFO 分量；
- 两个无线节点之间的载波频率差异。

#### 3.2.5 Sampling Time Offset

可以模拟：

- CSI 采样时刻不完全均匀；
- 正向和反向数据包之间的时间偏差；
- 采样周期抖动。

#### 3.2.6 白高斯噪声与 SNR

可以调整噪声强度，从而改变：

- CSI 相位稳定性；
- Bartlett AoA profile 的清晰程度；
- Bearing 估计误差；
- Bearing 置信度。

#### 3.2.7 WiFi、采样和角度扫描参数

可以设置：

- 中心频率；
- 波长；
- CSI 采样率；
- 里程计采样率；
- AoA 搜索角度范围；
- AoA 搜索角度分辨率。

论文实验中使用 5.54 GHz 中心频率、20 MHz 带宽和 100 Hz 的 CSI/里程计采样率。真实 WSR 驱动导出 48 个子载波中的 30 个，并用子载波 12--19 插值得到中心子载波 15.5；论文理论模型本质上仍是围绕中心载波的单色复数模型，不能将其描述成完整的频率选择性多径 OFDM 仿真器。

### 3.3 CSI 与 Bearing 处理过程

每个采样时刻执行：

1. 从节点位姿计算 $d_{ij}(t)$；
2. 查询锚点到机器人连线穿过的墙体材料、次数和长度；
3. 根据 LOS/NLOS 路径损耗、墙体衰减和空间相关阴影生成接收功率；
4. 将接收功率与传播相位组合为室内复数 CSI；
5. 对正向/反向链路施加符号相反的 CFO，并分别加入 STO 和 WGN；
6. 按 frame number 配对并计算 $h^2_{ij}(t)=\hat h_{ij}(t)\hat h_{ji}(t)$；
7. 从里程计计算虚拟阵列相对位移和 steering vector；
8. 计算 Bartlett AoA profile、峰值方向与置信信息；
9. 将候选路径逐点聚合为 SNR、outage、P5 和最长连续中断标签。

### 3.4 CSI、里程计与 Bearing 输出

建议统一输出：

```text
timestamp
frame_number
tx_node_id / rx_node_id
robot_pose_ground_truth              # 仅仿真与评测
robot_odometry                       # 算法可见
anchor_pose_ground_truth             # 仅仿真与评测
ideal_complex_csi                    # 调试用
forward_complex_csi_hat
backward_complex_csi_hat
pair_valid_mask
raw_amplitude / raw_phase
cfo_cancelled_complex_csi
cfo_cancelled_phase
sto_sample
noise_sample / configured_snr
relative_displacement
aoa_profile
aoa_max_bearing                     # 论文原生最终 Bearing
aoa_max_likelihood                  # 论文原生峰值置信信息
top_k_bearing_peaks                 # 本项目派生输出
aoa_profile_entropy                 # 本项目派生输出
mirror_ambiguity_flag               # 本项目派生输出
```

其中真实锚点位置和理想无噪 CSI 只能由仿真器用于：

- 生成 CSI；
- 生成监督标签；
- 计算 Bearing 和 AP 定位误差。

不能直接作为模型输入。模型输入、监督标签和调试字段必须在数据 manifest 中分开列出。

### 3.5 室内几何、衰减与路径标签

最终仿真场景直接使用以下室内传播输入和输出。该模型聚焦路径通信质量，不把简化墙体衰减误称为完整的真实 NLOS AoA。

#### 3.5.1 场景几何输入

```text
occupancy_map / floor_plan
wall_segments
wall_material_id
wall_thickness_m
door_state
robot_height_m
anchor_height_m
```

每种墙体材料对应独立的衰减参数，不能只使用一个无类型的全局 wall count。

#### 3.5.2 室内信道输入

```text
reference_distance_m: d0
reference_received_power_dbm: P0
path_loss_exponent_los: n_los
path_loss_exponent_nlos: n_nlos
material_entry_loss_db: {material_id: alpha_m}
material_attenuation_db_per_m: {material_id: beta_m}
tx_power_dbm
rx_noise_floor_dbm
shadowing_std_db
shadowing_correlation_length_m
```

同时随机化位姿噪声和发射功率漂移。显式多径不由这个简化模型直接生成，而通过射线追踪或真实 CSI 作为独立测试域验证。

#### 3.5.3 墙体衰减处理

对机器人位置 $x$ 和锚点位置 $s$，先计算直线路径穿过各类墙体的次数与内部长度：

$$
N_m(x,s)=\operatorname{CountIntersections}
(x,s,\operatorname{material}=m)
$$

$$
L_m(x,s)=\operatorname{PenetrationLength}
(x,s,\operatorname{material}=m)
$$

接收功率定义为：

$$
P_r(x)=P_0
-10n_{z(x)}\log_{10}\frac{d(x,s)}{d_0}
-\sum_m\left[\alpha_m N_m(x,s)+\beta_m L_m(x,s)\right]
+S(x)
$$

其中 $P_0$ 是参考距离 $d_0$ 处的接收功率，$z(x)\in\{LOS,NLOS\}$，$S(x)$ 是具有空间相关性的阴影衰落。为了保持复数 CSI，功率 dB 值相对归一化参考功率 $P_{ref}$ 转换为复振幅：

$$
h_{\mathrm{indoor}}(x)=
10^{\frac{P_r(x)-P_{ref}}{20}}
\exp\left(-j2\pi\frac{d(x,s)}{\lambda}\right)
$$

随后施加双向 CFO、STO 和 WGN，并进入 reciprocal cancellation 和 Bartlett Bearing 流程。

这里必须明确两个用途：

- 对数距离、墙体损耗和阴影衰落用于生成通信质量、SNR 和 outage 标签；
- 若没有显式反射/绕射模型，Bearing 仍基于直达单径近似，不能宣称已解决真实 NLOS AoA。

#### 3.5.4 通信质量与路径标签输出

除 CSI、里程计和 Bearing 外，输出以下点级字段：

```text
los_nlos_label                       # 监督/评测
distance_to_anchor_m
wall_intersections
wall_penetration_length_m
wall_material_sequence
total_wall_attenuation_db
path_loss_db
correlated_shadowing_db
received_power_dbm
snr_db
outage_label
goodput_label
channel_parameter_family
```

候选路径级标签输出：

```text
path_point_snr
path_point_outage
path_mean_snr
path_p5_snr
path_min_snr
path_outage_ratio
longest_outage_distance
longest_outage_duration
```

#### 3.5.5 最终仿真场景

每个 episode 从 Habitat 室内场景中随机采样一个场景、一个静态协作式锚点、一个 ObjectNav 起点与目标，以及一组信道参数。机器人沿 OpenFrontier 轨迹移动并持续采集双向 CSI；仿真器根据当前位置、锚点位置、墙体材质、穿透长度、LOS/NLOS 和相关阴影生成复数 CSI，同时产生候选路径逐点 SNR 与 outage 真值。

训练数据只保留具有至少两个有效语义 frontier 的决策时刻。用于 G1 和最终 Demo 的评测场景包含一个共同预热走廊和一个双 frontier 决策点：两个 frontier 都属于语义合理候选，但对应路径在长度、墙体穿越和通信中断风险上存在差异。Oracle 使用未来路径真值验证任务价值；学习方法只能使用历史 CSI、AP belief、候选路径和已观测几何预测风险。

最终仿真同时输出 Bearing/AP belief 评测数据、路径通信预测数据和端到端导航日志，直接服务 Oracle、训练、消融和端到端实验。

#### 3.5.6 防止仿真器自证

- 训练、验证和测试按场景、锚点部署和信道参数族划分；
- 同一 episode 的相邻决策点不能跨集合；
- 预测模型不能读取真实锚点坐标、LOS/NLOS 真值或生成器隐藏参数；
- 测试至少包含一个与训练生成器机制不同的外部域；
- 分别报告同域、跨参数、跨场景和外部域结果。

---

## 四、从仿真迁移到现实

### 4.1 Domain Randomization

训练时随机化：

- CSI 整体幅度；
- 锚点发射功率；
- 路径损耗指数；
- 墙体衰减；
- CFO；
- STO；
- 相位偏置；
- 噪声；
- 阴影衰落；
- 位姿误差。

目的是防止模型过度依赖单一仿真参数。

显式多径不由当前简化仿真器生成；它通过射线追踪或真实 CSI 独立测试域评测。

### 4.2 CSI 特征归一化

现实设备中的 CSI 幅度会受到：

- AGC；
- 天线增益；
- 射频硬件；
- 网卡驱动；
- 接收功率标定；

等因素影响。

因此模型优先使用：

- 时间窗口内归一化 CSI 幅度；
- 相对幅度变化；
- 子载波间相对特征；
- 校准后的相位；
- 幅度变化趋势；
- RSSI 和 SNR 辅助特征。

### 4.3 少量真实数据校准

正式 Demo 前，在目标场地采集少量真实 WiFi 数据：

- 沿几条短轨迹采集 CSI；
- 记录真实机器人 Pose；
- 记录 RSSI 和 SNR；
- 记录 packet loss 和 RTT；
- 校准 CSI 整体幅度；
- 校准墙体损耗范围；
- 校准噪声、阴影和未建模残差的统计范围；
- 必要时进行少量微调。

校准数据与最终测试必须严格分离：

- 校准轨迹不得覆盖最终 A/B 决策后的完整测试路线；
- radio survey 只用于场地验收和参数冻结，不能作为在线未来路径输入；
- 校准完成后冻结模型、归一化参数、outage 阈值和网络映射；
- 最终测试使用不同运行时段，并保留全部成功与失败记录。

---

## 五、现实 Demo 场景布局

### 5.1 场地要求

选择具有“共同预热走廊 + 双 visual frontier”结构的办公室或实验室。A/B 必须对应两个不同的高层 frontier，而不是同一个 frontier 的两条低层规划路径。

推荐布局：

```text
                   ┌────────目标房间────────┐
                   │       蓝色杯子          │
                   └───────┬───────┬────────┘
                           │       │
                Frontier A │       │ Frontier B
                  较短/NLOS│       │略长/较稳定
                           │       │
                      ┌────┘       └────┐
                      │   决策路口       │
                      └────────┬────────┘
                               │
                         共同预热走廊
                      3--5 m，至少一次转弯
                               │
                            Robot

              协作式无线锚点位于 Frontier B 一侧
```

场地应满足：

- 蓝色杯子在起点不可见；
- 两条路线都能到达目标区域；
- 路线 B 比路线 A 长约 10%-25%；
- 路线 A 存在一段连续弱信号区域；
- 路线 B 的通信整体更加稳定；
- 两条路线都能安全导航；
- 决策点能够同时产生两个不同 visual frontier；
- 两个 frontier 的语义效用处于同一合理候选集；
- 所有方法在到达决策点前共享完全相同的预热轨迹；
- 预热轨迹提供足够 CSI 孔径，但不提前经过 A/B 测试路段；
- 路线 B 必须满足预先冻结的最大额外路径预算。

---

## 六、蓝色杯子布置

蓝色杯子可以放在：

- 办公桌；
- 会议桌；
- 茶水间台面；
- 房间内柜子。

杯子要求：

- 蓝色明显；
- 尺寸适中；
- 位于机器人相机可见高度；
- 起点不可直接看到；
- 不使用透明或强反光杯子。

场景中可以放置干扰物：

- 白色杯子；
- 红色杯子；
- 蓝色水瓶；
- 蓝色文件夹；
- 其他蓝色物品。

任务成功需要同时满足：

```text
目标类别为 cup
+
颜色属性为 blue
+
机器人到达目标成功距离
```

---

## 七、现实 WiFi 和 CSI 系统

### 7.1 协作式 WiFi 锚点

部署一个固定、协作式测试无线锚点，而不是假设任意商用 AP 都能提供双向 CSI。

固定：

- 锚点位置；
- 锚点高度；
- 锚点天线方向；
- WiFi 频段；
- WiFi 信道；
- 发射功率；
- 数据包发送频率。

算法不能直接读取锚点真实坐标。

真实坐标仅用于：

- AP belief 定位误差评测；
- Oracle baseline；
- 观众界面显示。

### 7.2 CSI 采集设备与配对协议

机器人需要配备能够导出真实复数 CSI 的无线设备。

采集内容至少包括：

```text
timestamp
frame_number
tx_node_id
rx_node_id
robot position
robot orientation
forward complex CSI
backward complex CSI
pair valid mask
CSI amplitude / phase
RSSI
noise
SNR
packet sequence
```

需要注意：

> 普通 WiFi 网卡通常可以读取 RSSI，但不一定能够导出完整复数 CSI。

现实协议采用 round-robin 请求-应答：机器人发包后，锚点返回带同一 frame number 的响应包。处理端按 frame number 配对正反向 CSI，并记录无法配对、丢包和超时。目标采样率可参考论文的 100 Hz，但必须以实测稳定吞吐为准，不能把 100 Hz 写成未经验证的硬保证。

CSI 采集链路可能影响普通网络传输。参考论文真实系统，应准备独立控制/管理链路，避免 CSI 驱动或实验性网卡导致机器人安全控制失联。

因此正式 Demo 的首要硬件验收条件是：

> 机器人静止和运动时，两端能够稳定输出可按 frame number 配对的双向复数 CSI，并与 Pose 对齐；配对率、实际采样率和丢包率均有日志。

---

## 八、现实环境中如何形成 WiFi 强弱变化

现实 Demo 使用真实 WiFi 信号，因此不能在软件中直接指定真实 CSI 强弱。

需要通过锚点布置和真实物理环境制造可控的无线传播差异。

### 8.1 锚点位置

将协作式锚点放置在路线 B 一侧。

这样可以使：

- 路线 B 整体更靠近锚点；
- 路线 A 更远离锚点；
- 路线 A 与锚点之间穿过更多墙体；
- 路线 B 具有更多 LOS 路段。

锚点位置是产生空间通信差异的主要方式。

### 8.2 墙体和转角

让路线 A 经过：

- 厚墙后方；
- 关闭的房门；
- 连续两个转角；
- 房间深处；
- 大型设备附近；
- 金属柜附近。

让路线 B 经过：

- 开放走廊；
- 墙体较少区域；
- AP 附近区域；
- 较长 LOS 路段。

这些物理结构会自然影响：

- CSI 幅度；
- CSI 相位；
- RSSI；
- SNR；
- 多径；
- Bearing profile；
- packet loss；
- goodput。

### 8.3 调整锚点发射功率

如果整个场地的 WiFi 都过强，可以逐步降低测试 AP 的发射功率。

调整目标为：

```text
路线 A：
出现一段可重复的连续弱信号区域

路线 B：
仍然保持可用且相对稳定的连接
```

不能把功率降得过低，导致两条路线都严重断网。

### 8.4 调整锚点天线和安装位置

可以调整：

- AP 安装高度；
- AP 天线方向；
- AP 是否靠近墙体；
- AP 是否放在房间内部；
- AP 是否被柜体部分遮挡。

这些设置可以改变真实覆盖形态。

### 8.5 固定物理遮挡

如果建筑结构不足以产生明显差异，可以增加固定遮挡：

- 金属柜；
- 设备机柜；
- 关闭的防火门；
- 大型固定设备；
- 射频吸收材料。

由于金属物体也可能产生反射和新的多径，因此必须提前实测。

### 8.6 射频衰减器

射频衰减器可以用于调整整个链路的信号动态范围。

它适合：

- 将整个场景由强信号调整到中等信号；
- 构建强、中、弱不同实验条件；
- 防止路线 A 和路线 B 都处于过强信号状态。

但衰减器通常不能单独产生空间路线差异。

推荐组合为：

```text
锚点位置 + 墙体和转角
→ 形成空间通信差异

锚点发射功率或射频衰减器
→ 调整整体信号范围
```

### 8.7 确定性网络失败映射

现实 CSI 和 SNR 可能已经存在差异，但视频卡顿或 VLM 超时不一定每次都足够明显。本模块应称为“真实 CSI 驱动的确定性半真实网络失败映射”，不能写成纯真实网络结果。

可以根据实时测得的真实 SNR，使用统一的网络层映射：

```text
SNR 高：
网络正常

SNR 中等：
增加少量延迟和丢包

SNR 低：
增加明显延迟、丢包和带宽限制
```

必须明确：

- 真实 WiFi 设备负责产生 CSI、RSSI 和 SNR；
- 网络模拟模块只负责产生可重复的应用层延迟和丢包；
- 网络模拟模块不能生成或修改 CSI；
- Original OpenFrontier 和 RadioFrontier 使用完全相同的映射规则。

映射函数、阈值和随机种子必须在对比实验前冻结。论文分别报告原始真实链路指标和映射后的应用指标，不能只展示被放大的卡顿效果。

---

## 九、正式 Demo 前的 Radio Survey

在正式演示前，需要对场地进行无线测量。

人工推动机器人分别沿路线 A 和路线 B 多次移动。

同时记录：

- 真实 CSI；
- RSSI；
- SNR；
- packet loss；
- RTT；
- goodput；
- 机器人位置；
- 机器人朝向。

Radio Survey 的用途仅限于：

- 判断场地是否存在可重复的空间通信差异；
- 冻结锚点位置、发射功率、门状态和网络映射；
- 建立 Oracle/外部测试标签；
- 确认安全控制链路不会进入失联状态。

Survey 轨迹和未来路径真值不能作为在线预测输入。若使用真实数据微调，必须另设校准轨迹，并与最终测试轨迹、运行时段分离。

### 路线 A 验收条件

- 至少存在一段持续弱信号区域；
- 弱信号区域能够重复出现；
- 不从起点开始就完全断网；
- 机器人低层安全控制仍然正常。

### 路线 B 验收条件

- 整体通信比路线 A 稳定；
- 不出现与路线 A 同样长的 outage；
- 路径长度只比路线 A 稍长；
- 仍然能够到达蓝色杯子。

如果条件不满足，依次调整：

1. 锚点位置；
2. 锚点发射功率；
3. 路线 A 所经过的门和墙体；
4. 锚点天线方向；
5. 固定遮挡；
6. 整体射频衰减；
7. 应用层网络映射。

---

## 十、现实 Demo 在线运行流程

### 步骤 1：系统初始化

启动：

- RGB-D 相机；
- 机器人定位；
- OpenFrontier；
- CSI collector；
- Bearing estimator；
- AP belief；
- path channel forecaster；
- frontier reranker；
- 网络状态监测；
- 日志记录系统。

输入任务：

```text
“在办公室中找到蓝色杯子。”
```

### 步骤 2：共享预热轨迹与初始视觉探索

机器人获取 RGB-D 图像并构建局部地图。

如果当前画面中没有蓝色杯子，系统开始 frontier-based exploration。

在到达 A/B 决策路口前，Original 和 RadioFrontier 执行完全相同的共同预热轨迹。该轨迹长度约 3--5 m，并至少包含一次转弯，用于：

- 验证双向 CSI 配对和 Pose 同步；
- 形成非退化虚拟天线阵列；
- 初始化 Bearing 和 AP belief；
- 避免在第一次关键 frontier 决策时没有足够 CSI 历史。

若 Bearing 置信度仍低或有效配对样本不足，RadioFrontier 必须回退到 Original OpenFrontier，不允许为了 Demo 强制使用不可靠预测。

### 步骤 3：生成候选 frontier

OpenFrontier 根据：

- 当前 RGB-D；
- 已探索地图；
- 蓝色杯子目标；
- VLM 语义结果；

产生多个 visual frontier。

每个 frontier 包含：

- frontier 坐标；
- 语义得分；
- 探索价值；
- 路径距离；
- 候选路径。

系统首先保留语义 Top-K frontier，避免机器人为了信号强而进入明显与杯子无关的区域。

### 步骤 4：机器人移动并采集真实 CSI

机器人沿共享预热轨迹和后续滚动路径持续采集 CSI。

无线设备持续记录：

- 真实 CSI 幅度；
- 真实 CSI 相位；
- RSSI；
- SNR；
- packet timestamp；
- packet sequence。

同时记录对应的机器人 Pose。

每个窗口还必须记录 frame number、正反向配对率、实际采样率、Pose 插值误差和有效样本 mask。

### 步骤 5：估计 AP Bearing

机器人最近一段运动轨迹形成虚拟天线阵列。

系统利用：

```text
机器人位移
+
CSI 相位序列
+
CFO 补偿
```

计算 Bartlett AoA profile。

输出：

- 最大 Bearing peak；
- Top-K Bearing peaks；
- Bearing confidence；
- AoA profile entropy；
- 镜像歧义信息。

真实自然轨迹可能产生多个峰，因此系统不能只保留一个强制 Bearing。

### 步骤 6：更新 AP belief

系统融合多个位置的 Bearing，建立 AP 的二维位置后验。

输出：

- AP belief probability map；
- MAP AP 位置；
- AP 期望位置；
- 置信区域；
- belief entropy；
- 多峰 AP 假设。

AP 真实位置只能供评测和观众界面使用。

### 步骤 7：生成候选路径

为语义 Top-K frontier 生成候选路径。

每条路径按照固定距离采样，例如：

- 每 0.25 米一个点；
- 或每 0.5 米一个点。

示例：

```text
Path A：
路径较短
经过墙后区域和连续转角

Path B：
路径略长
更靠近 AP
开放区域更多
```

### 步骤 8：预测候选路径通信质量

模型输入：

- 真实历史 CSI；
- 真实历史 Pose；
- 当前 Bearing；
- 当前 AP belief；
- 候选路径坐标；
- 已观察地图；
- 可观测路径几何；
- 路径点距离历史 CSI 观测点的距离。

输出：

- 路径逐点预测 SNR；
- 预测方差；
- 平均 SNR；
- 最低 SNR；
- outage probability；
- 连续弱信号区长度；
- 预测不确定性。

### 步骤 9：Communication-Aware Frontier Ranking

系统综合：

- OpenFrontier 语义得分；
- 路径距离；
- 预测 outage probability；
- 最低预测 SNR；
- 预测不确定性；
- 最大额外绕路预算。

决策原则为：

```text
首先保证寻找蓝色杯子
        ↓
只在语义合理候选中比较
        ↓
通信收益明显且额外路径有限时
选择更稳定的 frontier
```

如果两条路径通信质量相似，则选择更短路径。

如果通信稳定路径明显过长，则不应无条件选择它。

### 步骤 10：滚动执行

机器人只执行当前路径的一小段，而不是一次执行完整路径。

随后重新：

- 获取 RGB-D；
- 更新地图；
- 更新 frontier；
- 采集 CSI；
- 更新 AP belief；
- 预测路径风险；
- 选择 frontier。

完整闭环为：

```text
观察
→ 生成 frontier
→ 生成候选路径
→ 预测通信风险
→ 选择 frontier
→ 执行一小段
→ 再次观察
```

### 步骤 11：发现蓝色杯子

机器人进入目标区域后：

1. 检测候选杯子；
2. 判断类别是否为 cup；
3. 判断颜色是否为 blue；
4. 排除蓝色瓶子、文件夹等干扰；
5. 移动到目标成功距离；
6. 停止导航。

---

## 十一、配对重复实验与现场展示

正式结果不能只比较两次运行。实验采用配对重复设计：

- 固定起点、杯子位置、锚点位置、门状态和低层导航器；
- Original 与 RadioFrontier 共享相同 Top-K frontiers 和候选路径；
- 方法运行顺序随机化或交叉，避免时间漂移偏向某一方法；
- 使用相同 scene、episode、seed 和预热轨迹进行配对；
- 每种方法重复多轮，保存所有成功、失败和回退运行；
- 主实验使用冻结的网络映射或相同 trace 回放；
- 报告均值、配对差值、置信区间以及正/负收益案例。

现场可播放一组代表性对比，但必须明确它只是完整重复实验中的一个 episode。

### 代表性运行 A：Original OpenFrontier

Original OpenFrontier 不使用 CSI 和路径通信预测。

预期过程：

1. 系统产生路线 A 和路线 B；
2. 路线 A 更短；
3. Original OpenFrontier 选择路线 A；
4. 机器人进入墙后或转角区域；
5. 真实 CSI、RSSI 和 SNR 下降；
6. 视频有效帧率降低；
7. VLM 请求延迟增加或超时；
8. frontier 决策更新滞后；
9. 机器人继续使用旧决策；
10. 最终找到杯子，或花费更多时间恢复。

### 代表性运行 B：RadioFrontier

恢复相同条件：

- 相同起点；
- 相同杯子位置；
- 相同锚点位置；
- 相同网络配置；
- 相同视觉模型；
- 相同低层导航器。

预期过程：

1. 机器人采集真实 CSI；
2. Bearing estimator 推断 AP 方向；
3. AP belief 随机器人运动逐步收敛；
4. forecaster 预测路线 A 存在连续弱信号区；
5. forecaster 预测路线 B 的通信更加稳定；
6. RadioFrontier 选择路线 B；
7. 路径长度略有增加；
8. 视频传输更加连续；
9. VLM 请求成功率提高；
10. 机器人及时更新 frontier；
11. 最终找到蓝色杯子。

---

## 十二、现场可视化界面

### 12.1 机器人第一视角

显示：

- 当前 RGB 图像；
- 当前目标：“蓝色杯子”；
- 当前杯子检测结果；
- 视频 Effective FPS；
- VLM 请求状态。

### 12.2 导航地图

显示：

- 已探索区域；
- 未探索区域；
- visual frontiers；
- 候选路径；
- 当前选中路径；
- 机器人历史轨迹。

### 12.3 WiFi 状态

显示：

- CSI 采样状态；
- 平均 CSI amplitude；
- RSSI；
- SNR；
- packet loss；
- RTT；
- goodput。

### 12.4 Bearing 和 AP belief

显示：

- Bartlett AoA profile；
- Top-K Bearing peaks；
- Bearing confidence；
- AP belief heatmap；
- MAP AP 位置；
- belief entropy；
- AP 真实位置，仅观众可见。

### 12.5 路径通信预测

显示：

- 每条路径长度；
- 预测平均 SNR；
- 预测最低 SNR；
- outage probability；
- 预测连续弱信号区；
- 预测不确定性；
- 最终 frontier score。

### 12.6 应用状态

显示：

- Effective FPS；
- VLM query latency；
- Query Success；
- Query Timeout；
- Stale Decision Duration。

---

## 十三、Demo 评价指标

比较 Original OpenFrontier 和 RadioFrontier：

- 是否找到蓝色杯子；
- ObjectNav Success Rate；
- 总路径长度；
- 完成时间；
- SPL；
- Outage Ratio；
- Longest Outage；
- Mean Outage Duration；
- Average SNR；
- P5 SNR；
- Packet Loss；
- RTT；
- Effective FPS；
- VLM Query Success Rate；
- Query Timeout Rate；
- Stale Decision Ratio。

现场最需要突出三个指标：

```text
额外路径长度
最长连续中断
云端请求成功率
```

理想结果是：

> RadioFrontier 只增加有限路径长度，但显著缩短最长通信中断，提高视频连续性和云端视觉请求成功率。

---

## 十四、实施阶段

### G0：基础系统与硬件冒烟测试

```text
真实机器人
+ RGB-D
+ OpenFrontier
+ 蓝色杯子识别
+ 协作式无线锚点
+ 双向 CSI 配对
+ Pose/CSI 时间对齐
```

目标：

- 完成真实环境中的蓝色杯子搜索；
- 完成目标识别和停止逻辑；
- 稳定输出可配对的双向复数 CSI，并验证独立安全控制链路。

### G1：Oracle 双 frontier 生死实验

```text
共享预热轨迹
+ 两个不同 visual frontier
+ 室内仿真路径真值
+ Oracle 路径风险
+ 固定额外路径预算
```

目标：

- 验证 Oracle 是否改善 SPL--Outage Pareto；
- 验证网络失败回放下 stale decision 或导航指标是否改善；
- 若 G1 不通过，停止预测器与完整 Demo 开发。

### CSI/Bearing 正确性验证

```text
参数化锚点和机器人轨迹
+ 正向/反向 CSI 与 frame pairing
+ CFO/STO/WGN
+ Bartlett Bearing
+ AP belief
```

目标：

- 复现论文 CSI 相位和 CFO 消除；
- 复现圆形单峰和直线镜像峰；
- 在共享预热轨迹上测试 Bearing/AP belief 可用性。

### G2：室内路径预测器

```text
大量随机室内场景
+ 随机锚点部署
+ 随机无线参数
+ 墙体衰减、LOS/NLOS 和相关阴影
+ 路径通信标签
+ Path-Conditioned Channel Forecaster
```

目标：

- 训练路径逐点 SNR 和 outage 预测模型；
- 验证未见场景和未见锚点部署泛化；
- 证明 AP belief 对 No-AP 和 Point-AP 基线具有独立增益。

### 外部域、真实 CSI 校准与测试

```text
协作式无线锚点
+ CSI-capable hardware
+ Pose/CSI 时间同步
+ Radio Survey
+ 分离的校准/测试轨迹
```

目标：

- 稳定采集真实 CSI；
- 测量路线 A 和路线 B；
- 缩小仿真和现实差距；
- 在与训练生成器不同的真实或射线追踪域验证结论。

### G3：完整现实 RadioFrontier

```text
真实机器人寻找蓝色杯子
        ↓
真实 WiFi CSI
        ↓
CSI Bearing
        ↓
AP belief
        ↓
候选路径通信预测
        ↓
Communication-Aware Frontier Ranking
        ↓
稳定视频和云端 VLM 交互
        ↓
找到蓝色杯子
```

---

## 十五、最终场景定义

> RadioFrontier 的最终仿真直接生成带墙体的室内 ObjectNav 场景。每个 episode 随机设置协作式无线锚点、机器人起点、目标、墙体材质与厚度、LOS/NLOS、路径损耗、空间相关阴影、位姿误差、双向 CFO、STO 和 WGN。机器人沿导航轨迹采集双向复数 CSI，通过 frame pairing、reciprocal cancellation 和 Bartlett estimator 获得 Bearing，并融合为 AP belief。仿真器同时为尚未经过的候选路径生成逐点 SNR、outage 和最长连续中断标签。场景包含共同预热走廊与两个不同 visual frontier；所有方法共享相同语义候选和额外路径预算，RadioFrontier 只能利用历史 CSI、AP belief、候选路径和已观测几何预测未来风险。射线追踪或真实 CSI 作为独立测试域，用于检验简化墙体模型之外的泛化能力。
