# RadioFrontier Project Plan v2.1

> Version: v2.1  
> Status: Benchmark / AP protocol / method provenance partially frozen  
> Primary benchmark: OpenFrontier on HM3D ObjectNav V2  
> Core update: add method provenance, explicitly separate inherited components from RadioFrontier's novel components, and clarify the relationship to communication-aware radio-map planning.


## 1. 项目名称

**RadioFrontier: Outage-Aware Object Navigation via Path-Conditioned Channel Forecasting**

中文暂定题目：

**基于候选路径信道预测的中断感知目标导航方法**

> 数学公式采用 GitHub/Typora 兼容的 `$$ ... $$` 块级格式。使用 VS Code 时需启用支持 LaTeX 数学渲染的 Markdown 预览插件。

---

## 2. 一句话 Idea

我们研究一个受限但可验证的问题：在协作式 WiFi-CSI 基础设施下，机器人仅利用已访问位置的 CSI、AP 位置后验和候选路径几何，预测尚未经过路径的通信中断风险，并在 OpenFrontier 给出的语义合理候选中进行有额外路径预算约束的重排序，从而改善 ObjectNav 的 SPL--Outage Pareto。

---

## 3. 研究问题

现有 ObjectNav 方法主要根据视觉语义、探索收益和路径距离选择 frontier，但通常默认机器人在导航过程中始终拥有稳定网络连接。

在云端 VLM、远程视频监控或边缘推理场景中，这一假设并不成立。机器人进入房间、转角或墙后区域后，WiFi 信号可能迅速下降，导致：

- 视频帧丢失、卡顿或超时；
- 云端 VLM 请求失败；
- frontier 决策无法及时更新；
- 机器人继续使用过期决策；
- 最终降低 ObjectNav 成功率。

本项目研究以下问题：

> 在未知室内环境中，机器人能否利用稀疏历史 CSI、信号源位置后验和候选路径几何，预测尚未经过路径上的通信中断风险，并将预测结果用于受路径预算约束的 visual frontier 选择？

### 3.1 第一篇论文的任务边界

第一篇论文明确采用以下设定：

- 单个静态、协作式 AP 或无线锚点；
- 机器人与锚点能够按指定协议获得双向 CSI，用于 reciprocal cancellation；
- 机器人位姿来自导航系统，RGB-D 和占据几何可用；
- 仅允许使用已走过位置的 CSI，未来路径信号只能作为训练标签或 Oracle 上界；
- 主决策是高层 frontier 重排序，并受最大额外路径预算约束；
- 仿真用于大规模受控实验，但至少需要射线追踪、半真实回放或小规模真实 CSI 中的一种进行外部验证。

因此，第一篇论文不宣称支持任意商用 AP、无合作 CSI 定位、多 AP 切换或动态人群环境。

---

## 4. 核心假设

### H0：Oracle 通信信息对 ObjectNav 决策有价值

在固定语义候选集和额外路径预算下，若 Oracle 能提供候选路径的真实中断风险，则 frontier 重排序应当显著改善 SPL--Outage Pareto；在网络失败会造成请求超时或决策陈旧的闭环模型下，还应改善导航成功率。

H0 是项目的生死假设。若 H0 不成立，不继续训练复杂信道预测器，而是重新定义任务、候选集或网络失败机制。

### H1：CSI Bearing 可以为路径预测提供有用的 AP 后验

利用机器人运动构建虚拟天线阵列，通过 CSI 相位、CFO 消除和 Bartlett 波束形成，可以获得信号源相对方位。

融合多个位置的 Bearing 后，可以逐步缩小 AP 位置后验。该模块是否保留为论文核心，取决于它能否在自然导航轨迹和未见场景中显著改善路径中断预测，而不只取决于 AP 定位误差。

### H2：AP 后验和路径几何可以改善未来中断预测

相比仅使用当前位置 CSI、AP 距离或简单路径损耗模型，结合以下信息可以更准确地预测候选路径通信质量：

- 历史 CSI；
- AP belief；
- 路径坐标序列；
- 局部占据结构；
- LOS/NLOS；
- 墙体穿越情况；
- 距离最近观测点的距离。

### H3：受预算约束的通信预测可以改善 ObjectNav

在相同语义候选集和预先声明的额外路径预算下，通信感知 frontier 选择可以：

- 降低通信中断比例；
- 降低最长连续中断；
- 降低 VLM 请求超时和 stale decision；
- 在可重复的网络失败闭环下提高 ObjectNav SR 和 SPL。

视频有效 FPS 和真实云端请求成功率仅作为应用侧验证，不作为 H3 成立的必要条件。

---

## 5. 技术路线总览

```text
RGB-D + Pose + CSI
        ↓
OpenFrontier 检测 visual frontiers
        ↓
frontier 三维投影与候选路径生成
        ├──────── Oracle 路径风险 ────────┐
        │       （H0 生死实验）           │
        ↓                                 │
CSI 滑动窗口 + Bearing + AP Belief       │
        ↓                                 │
历史 CSI + AP Belief + 路径几何          │
        ↓                                 │
Path-Conditioned Outage Forecaster        │
        ↓                                 │
预测 Outage / P5 Goodput / Uncertainty ───┘
        ↓
固定 Top-K 语义候选 + 路径预算约束的通信风险重排序
        ↓
选择 frontier 并执行导航
        ↓
采集新的 RGB-D、Pose 和 CSI
        ↺
```

---

## 6. 方法来源、继承关系与创新边界（v2.1 新增）

本项目不是从零构建完整导航与无线感知系统，而是明确继承三个已有研究方向中的成熟组件，并在其交叉位置提出新的问题设定与算法。为了避免将已有方法误表述为本文贡献，后续代码实现、实验记录与论文写作均应使用本节作为“方法血缘关系”依据。

### 7.1 OpenFrontier：ObjectNav / Frontier Backbone

主要来源：

**Esteban Padilla-Cerdio, Boyang Sun, Marc Pollefeys, Hermann Blum.  
“OpenFrontier: General Navigation with Visual-Language Grounded Frontiers.” 2026.**

本项目从 OpenFrontier 继承：

- visual frontier detection；
- 基于 VLM 的 frontier semantic relevance；
- visual frontier 的三维 grounding；
- global frontier maintenance；
- goal update / path finding / termination 的基础导航流程；
- HM3D ObjectNav V2 benchmark 接口与原始导航指标。

OpenFrontier 的核心思想是将 visual frontiers 作为可执行的语义锚点，并使用 VLM 对候选 frontier 进行目标相关性评估，再与 exploration information gain 结合形成高层导航优先级。

RadioFrontier **不把以下内容作为自己的贡献**：

- visual frontier detection；
- set-of-marks 式 frontier VLM reasoning；
- OpenFrontier 原始 semantic utility；
- OpenFrontier 的基础 ObjectNav navigation pipeline。

RadioFrontier 在 OpenFrontier 之后新增的接口是：

```text
OpenFrontier semantic candidates
        ↓
candidate path extraction
        ↓
communication-risk estimation
        ↓
budget-constrained reranking
        ↓
selected frontier
```

即：无线信息只在 OpenFrontier 已经认为语义合理的候选之间发挥作用，而不是取代 OpenFrontier 的视觉语义导航。

### 7.2 WiFi-CSI 仿真与 Bearing：Dijkstra et al. / WSR 路线

主要来源：

**Brendan Dijkstra, Ninad Jadhav, Alex Sloot, Matteo Marcantoni,  
Bayu Jayawardhana, Stephanie Gil, Bahar Haghighat.  
“WiFi-CSI Sensing and Bearing Estimation in Multi-Robot Systems:  
An Open-Source Simulation Framework.” 2024.**

该工作复现并扩展了 WiFi Sensor for Robotics (WSR) 的 CSI sensing / bearing pipeline。

本项目从该路线继承：

- WiFi CSI 的基础传播相位模型；
- forward / backward CSI；
- Carrier Frequency Offset (CFO) 建模；
- Sampling Time Offset (STO)；
- White Gaussian Noise (WGN)；
- 基于 channel reciprocity 的双向 CSI 乘积 CFO cancellation；
- 由机器人运动形成 virtual antenna array；
- Bartlett estimator；
- AoA / bearing profile；
- 圆形轨迹单峰与线形轨迹镜像峰等基本现象。

第一阶段 Python 实现中的 **Paper-Compatible Mode** 应优先忠实复现上述设定，而不是一开始加入复杂室内传播机制。

RadioFrontier **不把以下内容作为自己的贡献**：

- CFO cancellation 原理；
- synthetic / virtual antenna array；
- Bartlett beamforming / bearing estimation 本身；
- 基础 CSI simulator 的原始单径公式。

RadioFrontier 在此基础上新增：

1. 将自然 ObjectNav 轨迹上的连续 bearing evidence 融合为空间 **AP belief**；
2. 不强迫镜像歧义收敛成单点 AP estimate，而是允许多峰 posterior；
3. 将 AP belief 的价值最终定义为“是否改善未走 candidate path 的 outage prediction / ranking”，而不是仅看 AP localization error。

### 7.3 Communication-Aware Motion Planning：Gordon et al.

主要来源：

**Daniel Gordon, Mohammad Bariq Khan, Tommaso Zugno, Wu Yiqun,  
Mate Boban, Xueli An, Falko Dressler.  
“Communication-aware Robot Motion Planning via Online Estimation of Radio Maps.”**

该工作体现了本文第三条重要技术来源：机器人规划不应假设通信质量与运动决策无关，而应把无线网络状态转化为 trajectory-level planning risk。

本项目借鉴：

- radio quality / radio map → communication risk 的思想；
- 沿潜在轨迹评估通信性能，而不是只看当前位置；
- 将 throughput、delay、PER 等 QoS 属性转化为规划可用的风险；
- communication-aware planning 应显式处理“路径效率 vs 通信可靠性”的 trade-off；
- ray tracing / radio-map-based evaluation 可作为外部高保真验证方向。

但 RadioFrontier 与该类 radio-map-aware planner 存在关键区别。

Gordon et al. 的主要范式可概括为：

```text
known / online-estimated radio map
        ↓
QoS / service-specific risk map
        ↓
motion planner / costmap
        ↓
communication-aware trajectory
```

RadioFrontier 的主问题则是：

```text
unknown indoor scene
        ↓
only past / visited CSI observations
        ↓
AP belief + candidate path geometry
        ↓
predict communication risk on UNVISITED paths
        ↓
rerank OpenFrontier semantic candidates
```

因此第一篇论文不假设机器人已经拥有完整可信的 radio map；Oracle radio map 仅用于 V1 上界实验和监督标签，而不是最终可部署方法的输入。

### 7.4 方法继承关系总表

| RadioFrontier 模块 | 主要来源 | 继承内容 | RadioFrontier 新增内容 |
|---|---|---|---|
| ObjectNav / frontier backbone | OpenFrontier | visual frontier、VLM relevance、3D grounding、global frontier、基础导航 | candidate-path communication risk layer |
| CSI simulation | Dijkstra et al. 2024 / WSR | CSI phase、CFO/STO/WGN、双向 CSI cancellation | HM3D indoor extension、与 ObjectNav episode 对齐 |
| Bearing estimation | Dijkstra et al. 2024 / WSR | virtual antenna array、Bartlett AoA | 多峰 bearing evidence 用于 AP belief |
| Communication-aware planning | Gordon et al. | radio/QoS → risk、trajectory-aware communication evaluation | OpenFrontier Top-K 上的 budget-constrained high-level reranking |
| AP belief fusion | 本项目 | — | 多时刻 bearing posterior → 2D AP belief |
| Path-conditioned outage forecaster | 本项目核心 | 借鉴 physics / radio-map 建模思想 | 历史 CSI + AP belief + path geometry → 未走路径 outage distribution |
| Budget-constrained frontier reranking | 本项目核心 | 借鉴 communication-aware planning 的 trade-off 思想 | 固定 semantic candidate set + path budget + outage / uncertainty penalties |

### 7.5 第一篇论文的主要 Novelty 声明

第一篇论文真正需要主张的创新应聚焦以下内容，而不是泛化为“首次把无线用于机器人导航”：

#### Novelty A：Outage-Aware ObjectNav Problem Formulation

在 OpenFrontier / HM3D ObjectNav 的高层 frontier decision 上，引入：

- 单 AP、协作式 CSI；
- 未走路径通信风险；
- 固定额外路径预算；
- SPL--Outage Pareto；
- 网络失败对远程 VLM / stale decision 的闭环影响。

#### Novelty B：Path-Conditioned Outage Forecasting

仅利用：

- 已访问位置历史 CSI；
- AP belief；
- 未走 candidate path geometry；
- 局部占据 / LOS / wall features；

预测 **尚未经过路径** 的 outage probability、low-tail communication quality 和 uncertainty。

这里的核心不是重建完整 radio map，而是直接预测“当前决策所需的候选路径风险”。

#### Novelty C：AP Belief as a Decision-Relevant Wireless Representation

将运动合成孔径 bearing 的多峰不确定性保留为空间 AP posterior，并验证：

> AP belief 是否对 candidate-path outage prediction / ranking 提供独立于当前 CSI、距离模型和单点 AP estimate 的增益。

如果消融不能证明这一点，则 AP belief 降级为辅助模块，而不强行作为主贡献。

#### Novelty D：Budget-Constrained Semantic Frontier Reranking

无线风险不能无限压过语义目标。

RadioFrontier 只在 OpenFrontier 的语义 Top-K 候选中进行通信优化，并通过最大额外路径预算显式限制绕路。

论文应以：

- 同一 semantic candidate set；
- 同一 ObjectNav episode；
- 同一 AP placement；
- 同一 path budget；

比较 Original OpenFrontier、简单无线基线、RadioFrontier 与 Oracle。

### 7.6 论文写作中的归属规则

后续论文和实验报告必须遵守：

1. 对直接复现的算法、公式和参数给出原始论文引用；
2. 对 OpenFrontier 的 frontier detection / semantic reasoning 不使用 “we propose”；
3. 对 Dijkstra / WSR 的 CFO cancellation、virtual antenna array、Bartlett bearing 不使用 “we propose”；
4. 对 communication-aware planning 的一般思想承认已有工作；
5. 将 “our method” 限定到：
   - AP belief fusion（若实验成立）；
   - path-conditioned outage forecasting；
   - budget-constrained frontier reranking；
   - 对应 benchmark protocol / Oracle-to-learned proof chain；
6. 若后续 literature review 找到更接近的 prior work，应及时更新本节和 novelty boundary，而不是保留过强的首创性表述。

---

## 7. 系统模块

### 7.1 ObjectNav Backbone

基座采用 **OpenFrontier**。

OpenFrontier 负责：

- 从当前 RGB/RGB-D 图像检测 visual frontiers；
- 使用 VLM 计算目标语义相关性；
- 将 frontier 投影到三维空间；
- 维护全局 frontier；
- 生成 PointGoal 或候选导航目标；
- 执行低层导航。

本项目不重新训练完整 ObjectNav 主干，主要修改 frontier 管理和路径评分部分。

---

### 7.2 CSI Simulation

根据论文：

**WiFi-CSI Sensing and Bearing Estimation in Multi-Robot Systems: An Open-Source Simulation Framework**

使用 Python 复现以下组件：

1. 单径 CSI 信道模型；
2. 正向和反向 CSI；
3. Carrier Frequency Offset；
4. Sampling Time Offset；
5. White Gaussian Noise；
6. 双向 CSI 相乘消除 CFO；
7. 机器人轨迹形成虚拟天线阵列；
8. Bartlett Bearing Estimation。

基础模型：

$$
h_{ij}(t)=\frac{1}{d_{ij}(t)}
\exp\left(-j2\pi\frac{d_{ij}(t)}{\lambda}\right)
$$
CFO 模型：

$$
CFO_{ij}(t)=\Delta f t+c_1\sin(c_2t)
$$
双向消除：

$$
h_{ij}^{2}(t)=\hat h_{ij}(t)\hat h_{ji}(t)
$$
Python 复现需要支持两种模式：

#### Paper-Compatible Mode

严格复现论文设置，用于验证 Python 与原 MATLAB 结果的一致性：

- 5.54 GHz 中心频率；
- 20 MHz 带宽；
- 30 个子载波；
- 100 Hz CSI 采样；
- CFO、STO、WGN；
- 圆形和线形轨迹；
- Bartlett AoA profile。

#### Indoor-Extended Mode

用于受控 ObjectNav 实验，增加：

- 对数距离路径损耗；
- 墙体穿透损耗；
- LOS/NLOS；
- 空间相关阴影衰落；
- 简化多径；
- 位姿误差；
- 发射功率扰动。

Indoor-Extended 不能同时作为唯一数据生成器和唯一测试环境。正式实验必须满足：

- 按场景、AP 部署和信道参数族划分数据；
- 测试信道参数范围与训练配置错开；
- 学习器不能直接获得生成标签所用的隐藏参数；
- 至少加入一种不同建模机制的外部测试域，例如射线追踪、真实 CSI 回放或实机采集；
- 单独报告同域、跨参数、跨场景和外部域结果，避免“同一物理模型生成并拟合同一标签”的循环验证。

---

### 7.3 Bearing Estimation

机器人最近一段轨迹形成虚拟天线阵列：

$$
\mathcal W_t=\{p_{t-W+1},\ldots,p_t\}
$$
二维 steering vector：

$$
a(\theta,\tau)=
\exp\left(
-j\frac{2\pi}{\lambda}
\Delta p_\tau^\top
[\cos\theta,\sin\theta]^\top
\right)
$$
Bartlett profile：

$$
F_t(\theta)=
\left|
\sum_{\tau=t-W+1}^{t}
h^2(\tau)a^2(\theta,\tau)
\right|^2
$$
输出：

- 最大峰值方向；
- Top-K Bearing 峰值；
- 峰值置信度；
- AoA profile 熵；
- 是否存在镜像歧义。

线性轨迹可能产生镜像 Bearing，因此系统必须保留多峰分布，而不能强制选择一个方向。

---

### 7.4 AP Belief Fusion

将多个时刻的 Bearing 观测转化为 AP 二维位置后验：

$$
B_t(s)\propto B_{t-1}(s)
p(\hat\theta_t\mid s,p_t)
$$
角度似然：

$$
p(\hat\theta_t\mid s,p_t)=
\exp\left[
-\frac{
\operatorname{wrap}(
\theta(s,p_t)-\hat\theta_t
)^2
}{
2\sigma_{\theta,t}^2
}
\right]
$$
AP belief 输出：

- 二维概率栅格；
- AP MAP 位置；
- AP 期望位置；
- 置信椭圆；
- belief entropy；
- Bearing 观测历史。

若 Bartlett profile 为双峰，则使用混合角度似然更新。

---

### 7.5 Candidate Path Generation

对 OpenFrontier 产生的每个 frontier \(f_i\)，生成候选路径：

$$
\pi_i=\{x_{i,1},\ldots,x_{i,L_i}\}
$$
候选路径可以来自：

- OpenFrontier 原有 PointGoal；
- 轻量占据地图上的 A*；
- Habitat shortest-path follower；
- 后续风险感知 A*。

第一版优先使用统一 A*，便于提取路径点和进行通信评测。

---

### 7.6 Path-Conditioned Channel Forecaster

这是论文的主要算法模块。

输入：

$$
X_i=
[
\mathcal H_t^{CSI},
B_t^{AP},
\pi_i,
G(\pi_i)
]
$$
其中：

#### 历史 CSI

- 机器人位置；
- 朝向；
- CSI 幅度；
- CSI 相位或相位差；
- SNR；
- AoA embedding；
- 时间间隔。

#### AP Belief

- AP belief map；
- MAP AP 坐标；
- belief entropy；
- 各路径点到 AP 的距离分布。

#### 路径序列

- 相对坐标；
- 累计距离；
- 转角；
- 当前点至路径点距离。

#### 路径几何

- 局部占据 patch；
- 墙体穿越数量；
- LOS 概率；
- 障碍密度；
- 最近历史 CSI 观测距离。

输出每个路径点的通信分布：

$$
g_{i,j}\sim\mathcal N(\mu_{i,j},\sigma_{i,j}^{2})
$$
再聚合为路径级属性：

$$
Q_i=
[
\hat g_i^{avg},
\hat g_i^{min},
\hat p_i^{out},
\hat g_i^{p5},
\hat \sigma_i
]
$$
其中：

- 平均预测 SNR/Goodput；
- 最低预测通信质量；
- 中断概率；
- 5% 分位通信质量；
- 不确定性。

---

### 7.7 Physics-Guided Residual Prediction

先使用物理模型得到基础估计：

$$
g_{\mathrm{phy}}(x)=
P_0
-10n\log_{10}d(x,\hat s)
-\sum_m\alpha_mN_m(x,\hat s)
$$
神经网络学习残差：

$$
\hat g(x)=
g_{\mathrm{phy}}(x)
+\Delta g_\phi(
\mathcal H_t^{CSI},
B_t^{AP},
G(x)
)
$$
优点：

- 降低训练难度；
- 增强可解释性；
- 提高跨场景泛化；
- 便于进行 physics-only 消融；
- AP belief 能自然影响基础预测。

---

### 7.8 Communication-Aware Frontier Ranking

OpenFrontier 原始语义效用记为：

$$
U_i^{OF}
$$
仅在语义排名靠前的 frontier 中进行无线重排序：

$$
\mathcal F_t^{top}=
\operatorname{TopK}(
\mathcal F_t,U_i^{OF}
)
$$
最终效用采用预算约束而不是无限增大无线权重。首先过滤不满足语义和路径预算的候选：

$$
\mathcal F_t^{feasible}=\left\{
f_i\in \mathcal F_t^{top}:D_i\le D_t^{base}+\Delta D_{max}
\right\}
$$

然后在可行集合中计算：

$$
J_i=
\widetilde U_i^{OF}
-\lambda_d\widetilde D_i
-\lambda_o\hat p_i^{out}
-\lambda_m
\operatorname{ReLU}(
g_{\min}-\hat g_i^{min}
)
-\lambda_u\hat\sigma_i
$$
选择：

$$
f_t^\ast=\arg\max_i J_i
$$
设计原则：

- 无线信号不能压过目标语义；
- 只在语义合理的候选之间进行通信优化；
- 避免机器人为了强信号走向与目标无关的区域；
- 使用不确定性惩罚过于乐观的预测。
- 使用不确定性惩罚过于乐观的预测；
- 主结果报告整条 SPL--Outage Pareto 曲线，并在相同路径预算下比较方法；
- 若无线重排序选择与原方法相同，不将其计作改进样本。

---

## 8. Benchmark 与无线环境协议（v2 新增）

### 7.1 主 Benchmark

第一篇论文的主导航 benchmark 固定为：

- **Backbone / baseline framework：OpenFrontier**
- **Dataset：HM3D ObjectNav V2**
- **Primary split：官方 validation split**
- **Scene 数：36 个 HM3D validation scenes**
- **导航任务、episode、起点、目标类别与 OpenFrontier 原 benchmark 保持一致**
- **RadioFrontier 不重新定义 ObjectNav 任务，只在 OpenFrontier 候选 frontier / candidate path 层加入通信风险建模与重排序**

第一篇论文暂不把 MP3D 或 OVON 作为主 benchmark。它们可作为后续 cross-dataset 或 open-vocabulary 扩展，但不承担第一篇论文的核心证明。

### 7.2 单 AP 协议

每个 ObjectNav episode 只包含 **1 个静态、协作式 AP / 无线锚点**。

需要区分：

- **单 episode 单 AP**：在一个 episode 内 AP 位置固定不变；
- **单 scene 多 AP placement**：同一个 HM3D scene 可以预先采样多个合法 AP placement；
- **不同方法共享完全相同的 scene / episode / AP placement / 信道参数**，用于 paired comparison。

不采用“每个 scene 永久固定一个 AP”的唯一部署方式，避免模型通过 scene identity 记忆 AP 位置，并允许显式测试对未见 AP placement 的泛化。

### 7.3 AP Placement 生成协议

AP placement 从场景的合法室内区域中采样，并满足：

- 不位于墙体、封闭障碍或不可达区域内部；
- 与机器人 episode 起点保持最小距离；
- 不与起点重合；
- 不全部集中在地图几何中心；
- 覆盖不同无线几何条件。

优先覆盖以下 placement 类型：

1. 中心 / 公共区域；
2. 房间内部；
3. 走廊附近；
4. 边缘 / 角落；
5. 与机器人路径存在明显隔墙、转角或 NLOS 的位置。

对每个 placement 记录：

- AP 三维位置；
- scene id；
- placement id；
- 与主要可通行区域的几何关系；
- LOS/NLOS 统计；
- 墙体穿越统计；
- 有效覆盖面积；
- outage 区域比例。

若某 placement 导致整张场景几乎全连通或几乎全 outage，应标记并决定是否纳入主分析，避免无线任务退化为 trivial case。

### 7.4 V1 Oracle Benchmark

V1 只回答一个问题：

> 在相同的 OpenFrontier 语义候选集与额外路径预算下，如果拥有候选路径真实通信风险，是否能够稳定改善导航--通信 Pareto？

V1 使用 ground-truth / Oracle radio information：

```text
HM3D scene
    ↓
固定一个真实 AP placement
    ↓
无线 simulator / 外部 radio truth
    ↓
得到 ground-truth radio field
    ↓
OpenFrontier 产生 Top-K semantic frontiers
    ↓
对每条 candidate path 计算真实 outage / P5 signal / longest outage
    ↓
在固定额外路径预算下 Oracle reranking
```

V1 阶段不需要：

- CSI Bearing；
- AP belief；
- 学习式 forecaster；
- 未来 CSI 预测。

如果 Oracle 在固定额外路径预算下仍不能改善 SPL--Outage Pareto，则停止 V2/V3 主线并重新检查：

- 候选 frontier 集是否存在足够决策自由度；
- 网络失败机制是否真正影响闭环导航；
- AP placement / outage threshold 是否合理；
- path budget 是否过紧或过松。

### 7.5 主对比方法

ObjectNav 主结果至少包含：

1. **Original OpenFrontier**
2. **OpenFrontier + Current CSI**
3. **OpenFrontier + Distance-to-AP**
4. **OpenFrontier + Physics-Only**
5. **OpenFrontier + Oracle AP**
6. **RadioFrontier (learned predictor)**
7. **OpenFrontier + Oracle Radio Map**

其中 Oracle Radio Map 是性能上界，不作为可部署方法。

主结论应回答：

```text
Original OpenFrontier
        ↓
简单无线启发式是否有用？
        ↓
learned RadioFrontier 是否显著优于简单无线方法？
        ↓
RadioFrontier 能保留多少 Oracle 的端到端收益？
```

### 7.6 主结果展示

第一篇论文至少需要两类核心图表。

#### A. SPL--Outage Pareto

横轴：

- SPL，或
- 额外路径长度 / 额外路径预算。

纵轴：

- Outage Ratio；
- Longest Outage；
- P5 Goodput。

比较：

- Original OpenFrontier；
- Current CSI；
- Physics-Only；
- RadioFrontier；
- Oracle Radio Map。

目标不是单点“最好”，而是证明 RadioFrontier 的 Pareto 曲线系统性向 Oracle 靠近。

#### B. 端到端结果表

建议格式：

| Method | SR ↑ | SPL ↑ | Outage Ratio ↓ | Longest Outage ↓ | Path Length ↓ | Timeout ↓ |
|---|---:|---:|---:|---:|---:|---:|
| OpenFrontier |  |  |  |  |  |  |
| + Current CSI |  |  |  |  |  |  |
| + Physics |  |  |  |  |  |  |
| RadioFrontier |  |  |  |  |  |  |
| Oracle Radio |  |  |  |  |  |  |

所有方法必须共享完全相同的：

- HM3D scene；
- ObjectNav episode；
- AP placement；
- 信道参数；
- 随机种子。

### 7.7 Pilot 与正式评测规模

V1 先进行 pilot，不直接跑满全部组合。

建议起始规模：

```text
36 scenes
× 3 AP placements / scene
× 3--5 ObjectNav episodes / placement
≈ 324--540 paired episodes
```

若 H0 有稳定收益，再扩展到：

```text
36 scenes
× 5--10 AP placements / scene
× 更多 episodes
```

正式论文结果使用多随机种子、paired episodes、置信区间与显著性检验。

---

## 9. 训练数据生成

每个 episode 随机采样：

- Habitat 场景；
- ObjectNav 目标；
- 起始位置；
- AP 位置；
- AP 发射功率；
- 信道参数；
- 墙体衰减；
- 噪声参数。

训练时导航器只能看到已走过位置的 CSI：

$$
\mathcal H_t^{CSI}
$$
仿真器可以查询候选路径上的真实信号，但只能作为监督标签：

$$
Y_i^\ast=
\{
g^\ast(x_{i,j})
\}_{j=1}^{L_i}
$$
训练样本：

$$
(
\mathcal H_t^{CSI},
B_t^{AP},
G(\pi_i),
\pi_i
)
\rightarrow
Y_i^\ast
$$
数据划分：

```text
Forecaster Train:
HM3D train scenes + 训练 AP 部署

Forecaster Validation:
HM3D train scenes + 未见 AP 部署

Primary ObjectNav Test:
OpenFrontier 官方 HM3D ObjectNav V2 validation split
36 个未见 scenes + 固定的 benchmark AP placements

External Test:
不同信道建模机制或真实/半真实 CSI
```

最终 ObjectNav 主结果不从 36 个官方 validation scenes 中再随机切 train/test；学习式 radio forecaster 的训练应尽量使用 HM3D train scenes 或其他不与最终 36 个 benchmark scenes 重叠的数据。

严禁随机划分同一场景中的路径点。

另外必须防止以下泄漏：同一 episode 的相邻决策点跨集合、同一 AP 部署跨集合、测试场景统计量参与归一化，以及使用未来路径 CSI 构造输入特征。

---

## 10. 评测指标

### 10.1 Bearing 和 AP 定位

- Bearing MAE；
- Bearing Median Error；
- Bearing Top-K Recall；
- AP Position Error；
- Coverage@1m；
- Coverage@2m；
- AP belief NLL；
- Localization Convergence Steps；
- belief entropy。

### 10.2 路径通信预测

只在尚未经过的候选路径上评测：

- MAE；
- RMSE；
- Outage Precision；
- Outage Recall；
- Outage F1；
- AUROC；
- NLL；
- 95% Prediction Interval Coverage；
- Expected Calibration Error。

### 10.3 ObjectNav

- Success Rate；
- SPL；
- SoftSPL；
- Distance to Goal；
- Path Length；
- Navigation Steps。

### 10.4 通信稳定性

- Outage Ratio；
- Longest Outage；
- Mean Outage Duration；
- Outage Event Count；
- Average SNR；
- P5 SNR；
- Average Goodput；
- P5 Goodput；
- P95 Latency；
- Packet Loss；
- Jitter。

### 10.5 视频和云端交互

- Effective FPS；
- Frame Drop Ratio；
- Deadline Miss Ratio；
- Freeze Ratio；
- Longest Freeze；
- VMAF；
- SSIM；
- Query Success Rate；
- Query Timeout Rate；
- Stale Decision Ratio。

---

## 11. 基线

### ObjectNav Baselines

1. Original OpenFrontier；
2. OpenFrontier + Current CSI；
3. OpenFrontier + Distance-to-AP；
4. OpenFrontier + Physics-Only；
5. OpenFrontier + Oracle AP；
6. RadioFrontier（历史 CSI + AP belief + path geometry）；
7. OpenFrontier + Oracle Radio Map。

所有 ObjectNav baseline 在完全相同的 HM3D episode、AP placement、信道参数和随机种子上进行 paired comparison。

### Channel Prediction Baselines

1. Last-value CSI；
2. Nearest-neighbor；
3. Log-distance path loss；
4. Wall-count model；
5. Gaussian Process / Kriging；
6. Source-free neural predictor；
7. Point-estimate AP predictor；
8. AP-belief predictor；
9. Full physics-guided predictor。

---

## 12. 消融实验

主论文消融：

1. 去掉 AP belief；
2. AP belief 改为单点 AP；
3. 使用 Oracle AP；
4. 去掉局部几何；
5. 去掉墙体信息；
6. 去掉历史 CSI；
7. 去掉不确定性；
8. 只预测 frontier 点；
9. 预测完整候选路径；
10. 去掉排序损失，仅优化点级回归；
11. 不同额外路径预算与 Top-K。

低层风险感知 A*、高低层联合和 VLM 直接处理无线数值不属于第一篇论文的必做消融。

---

## 13. 关键证明链

论文需要依次证明：

```text
Oracle 路径风险在固定预算下确实改善决策（H0）
→ 历史 CSI 能预测未走路径的中断风险
→ AP belief 对强基线具有额外贡献
→ 学习方法逼近 Oracle 的决策收益
→ 通信中断更少
→ 网络失败闭环下 ObjectNav 性能更好
```

视频和云端 VLM 结果作为应用验证，不承担主证明链。不能只证明预测 RMSE 更低，也不能只证明平均 RSSI 更高；核心预测指标应包括 outage recall、AUROC、NLL/校准度以及候选路径排序质量。

---

## 14. 论文贡献

### Contribution 1

提出 outage-aware ObjectNav 设定和可复现评测协议，在固定语义候选与额外路径预算下联合评价导航效率和通信中断，并显式建模中断对远程推理闭环的影响。

### Contribution 2

提出 path-conditioned outage forecaster，利用已访问位置的 CSI、候选路径几何以及由运动合成孔径 Bearing 得到的 AP belief，预测未走路径的中断风险与不确定性。

### Contribution 3

提出受额外路径预算约束的 frontier 重排序方法，并通过 Oracle 上界、强预测基线、跨场景/跨信道测试和外部域验证，证明方法改善 SPL--Outage Pareto，并在网络失败闭环下提升 ObjectNav。

---

## 15. 预期结果

一个有说服力的结果应满足：

- Oracle 在固定额外路径预算下显著优于 Original OpenFrontier；
- Full predictor 在未见场景、未见 AP 和外部测试域中优于 physics-only、wall-count、GP/Kriging 等强基线；
- AP belief 相比无 AP 和单点 AP 表示对 outage prediction 或路径排序有显著增益；
- 弱信号区域 Recall、AUROC 和校准度明显提高；
- Full 方法能够保留 Oracle 收益中的可观比例；
- Longest Outage 显著降低；
- 路径长度增加不超过预先声明的预算；
- 在相同预算或相近 SPL 下，中断更少；
- 在可重复的网络失败回放下，SR 和 SPL 得到提升；
- 至少有一个射线追踪、半真实或真实 CSI 结果支持外部有效性。

不预设“降低 20%”之类结果导向阈值。所有主结果使用多随机种子、配对 episode、置信区间和显著性检验，并同时报告失败案例。

---

## 16. 风险与备选方案

### 风险 1：OpenFrontier 环境难以复现

备选：

- 使用其 frontier 接口和思想；
- 迁移至 ApexNav；
- 使用 Habitat 自带 frontier baseline 搭建最小版本。

### 风险 2：自然 ObjectNav 轨迹不足以形成稳定虚拟阵列

备选：

- 使用滑动轨迹窗口；
- 合并多个转向片段；
- 保留多峰 Bearing；
- 在低置信度时加入极短主动 sensing 动作；
- 将 AP 定位降级为辅助模块。

### 风险 3：原文单径模型过于简单

备选：

- Paper-Compatible 模式仅用于复现；
- Indoor-Extended 模式用于训练；
- 加入墙体损耗、阴影衰落和简化多径；
- 后续使用少量真实 CSI 进行校准。

### 风险 4：通信优化导致明显绕路

备选：

- 只在 Top-K 语义 frontier 中重排序；
- 使用通信约束而非无限增大无线权重；
- 绘制 SPL-Outage Pareto 曲线；
- 设置最大额外路径预算。

### 风险 5：云端 LLM 接口难以重复实验

备选：

- 主实验使用固定 VLM 输出或缓存结果；
- 网络只影响请求成功与延迟；
- Demo 再接入真实云端模型；
- 使用确定性无线重排序作为主方法。

---

## 17. 阶段划分

### V0：协议冻结与 OpenFrontier 最小复现

目标：

- 明确协作式 AP、双向 CSI、时间同步和可观测量；
- 跑通 OpenFrontier HM3D ObjectNav V2 benchmark，并导出 Top-K frontier、原始效用和候选路径；
- 固定网络失败如何作用于 VLM 请求、决策更新和导航；
- 固定 36 个 HM3D validation scenes、AP placement 协议、额外路径预算和主评测协议。

### V1：Oracle 通信感知 OpenFrontier（生死实验）

目标：

- 在固定 HM3D episode + AP placement 上使用真实无线地图或外部无线真值重排 frontier；
- 绘制 SPL--Outage Pareto；
- 验证固定预算下通信信息是否改善决策；
- 若 H0 不成立，在此停止预测器开发并重新定义问题。

### V2：CSI Bearing 与 AP Belief

目标：

- 复现 CFO 消除、圆形唯一峰和线形镜像峰；
- 多位置 Bearing 融合并保留多峰后验；
- 在自然轨迹、位姿误差和多径条件下验证；
- 以“是否改善路径风险预测”为保留 AP belief 的最终标准。

### V3：Path-Conditioned Channel Forecaster

目标：

- 仅使用历史 CSI、AP belief 和路径几何；
- 替代 Oracle 无线地图；
- 完成预测基线、消融和泛化实验。

### V4：端到端评测与外部域验证

目标：

- 对比 Original OpenFrontier 与 RadioFrontier；
- 在统一路径预算下比较预测方法与 Oracle；
- 完成射线追踪、半真实回放或真实 CSI 验证；
- 使用确定性的网络失败回放测试网络受限 VLM 交互；
- 视频传输和实机画面仅作为应用 Demo。

---

## 17. v2/v2.1 已冻结的关键决策

截至 v2，以下内容视为第一阶段冻结项：

1. **主 benchmark 使用 OpenFrontier + HM3D ObjectNav V2。**
2. **最终导航主评测使用官方 36 个 HM3D validation scenes。**
3. **每个 episode 只有 1 个静态协作式 AP。**
4. **同一 scene 使用多个 AP placements，而不是一个 scene 永久固定一个 AP。**
5. **所有方法共享完全相同的 scene / episode / AP placement / channel parameters。**
6. **V1 先做 Oracle radio reranking，验证 H0 后再继续 V2/V3。**
7. **主结果以 SPL--Outage Pareto 为核心，而不是只比较平均 RSSI 或 predictor RMSE。**
8. **RadioFrontier 的目标是保留 Oracle 通信信息带来的可实现端到端收益。**
9. **学习式 forecaster 不使用最终 36 个 HM3D benchmark scenes 进行训练。**
10. **MP3D / OVON 暂不作为第一篇论文的主 benchmark。**

---

## 18. 最终冻结版本

本项目第一篇论文聚焦：

```text
OpenFrontier
+ 协作式单 AP CSI
+ Path-Conditioned Outage Forecasting
+ AP Belief（仅在消融证明有效时保留）
+ Budget-Constrained Frontier Ranking
+ Oracle 与外部域验证
```
第一篇论文暂不强求：

- 完整无线热力图重建；
- 完整原始 CSI 矩阵的未来预测；
- 端到端强化学习；
- 任意商用 AP 的无合作 CSI 定位；
- 同时实现 BEV 和无 BEV 两套系统；
- 复杂动态人群多径建模；
- 低层风险感知 A* 与高层策略联合优化；
- 将实时云端 API 或视频编码质量作为主实验；
- 把 Bearing/AP 定位单独包装成与主线平行的贡献。

### 18.1 投稿前硬门槛

只有同时满足以下条件，才进入完整 CCF C 投稿冲刺：

1. Oracle 在固定路径预算下稳定改善 SPL--Outage Pareto；
2. Full predictor 在未见场景和外部测试域优于强基线，并具有合理校准；
3. AP belief 或其他 CSI 表示能对最终路径排序产生独立增益；
4. 预测方法保留一部分 Oracle 端到端收益；
5. 至少有一种不同于训练仿真器的外部证据，且失败案例得到解释。


---

## 19. v2.1 版本变更记录

v2.1 在 v2 的 benchmark / AP protocol 冻结基础上，新增“方法来源与创新边界”层面的收敛。

### 相比 v2 新增

- 正式加入 **OpenFrontier** 作为 ObjectNav / visual frontier 方法来源；
- 正式加入 **Dijkstra et al. 2024 / WSR** 作为 CSI simulation、reciprocal cancellation、virtual antenna array 与 Bartlett bearing 的方法来源；
- 正式加入 **Gordon et al.** 作为 communication-aware radio-risk planning 的相关技术来源；
- 新增“方法继承关系总表”，区分：
  - inherited components；
  - adapted components；
  - RadioFrontier novel components；
- 明确 Gordon 类 radio-map-aware planning 与 RadioFrontier 的关键差异：
  - prior work：radio map → risk map → planner；
  - RadioFrontier：historical CSI → AP belief + path geometry → unseen-path outage prediction → semantic frontier reranking；
- 明确第一篇论文不主张：
  - 首次 communication-aware robot navigation；
  - 首次 CSI bearing；
  - 首次 virtual antenna array / Bartlett estimator；
  - OpenFrontier 的 visual frontier / VLM semantic reasoning；
- 将第一篇论文的 novelty 收敛为：
  1. outage-aware ObjectNav formulation；
  2. path-conditioned unseen-path outage forecasting；
  3. decision-relevant AP belief（仅在消融成立时）；
  4. budget-constrained semantic frontier reranking；
  5. Oracle-to-learned proof chain 与对应评测协议；
- 增加论文写作中的 attribution rules，防止后续 autoresearch / paper-writing agent 把已有模块误写成本文贡献。

### v2 已保留的关键更新

- 主 benchmark：OpenFrontier + HM3D ObjectNav V2；
- 最终主评测：36 个 HM3D validation scenes；
- 单 episode 单静态协作式 AP；
- 单 scene 多 AP placements；
- paired scene / episode / AP / channel comparison；
- V1 Oracle radio reranking 为 go/no-go 生死实验；
- SPL--Outage Pareto 为主结果形式；
- forecaster 不使用最终 36 个 benchmark scenes 训练。
