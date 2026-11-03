# RadioFrontier Project Plan

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

## 6. 系统模块

### 6.1 ObjectNav Backbone

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

### 6.2 CSI Simulation

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

### 6.3 Bearing Estimation

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

### 6.4 AP Belief Fusion

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

### 6.5 Candidate Path Generation

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

### 6.6 Path-Conditioned Channel Forecaster

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

### 6.7 Physics-Guided Residual Prediction

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

### 6.8 Communication-Aware Frontier Ranking

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

## 7. 训练数据生成

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
Train:
训练场景 + 训练 AP 部署

Validation:
训练场景 + 未见 AP 部署

Test:
未见场景 + 未见 AP 部署

External Test:
不同信道建模机制或真实/半真实 CSI
```

严禁随机划分同一场景中的路径点。

另外必须防止以下泄漏：同一 episode 的相邻决策点跨集合、同一 AP 部署跨集合、测试场景统计量参与归一化，以及使用未来路径 CSI 构造输入特征。

---

## 8. 评测指标

### 8.1 Bearing 和 AP 定位

- Bearing MAE；
- Bearing Median Error；
- Bearing Top-K Recall；
- AP Position Error；
- Coverage@1m；
- Coverage@2m；
- AP belief NLL；
- Localization Convergence Steps；
- belief entropy。

### 8.2 路径通信预测

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

### 8.3 ObjectNav

- Success Rate；
- SPL；
- SoftSPL；
- Distance to Goal；
- Path Length；
- Navigation Steps。

### 8.4 通信稳定性

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

### 8.5 视频和云端交互

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

## 9. 基线

### ObjectNav Baselines

1. Original OpenFrontier；
2. OpenFrontier + Current CSI；
3. OpenFrontier + Distance-to-AP；
4. OpenFrontier + Physics-Only；
5. OpenFrontier + Oracle AP；
6. OpenFrontier + Oracle Radio Map。

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

## 10. 消融实验

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

## 11. 关键证明链

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

## 12. 论文贡献

### Contribution 1

提出 outage-aware ObjectNav 设定和可复现评测协议，在固定语义候选与额外路径预算下联合评价导航效率和通信中断，并显式建模中断对远程推理闭环的影响。

### Contribution 2

提出 path-conditioned outage forecaster，利用已访问位置的 CSI、候选路径几何以及由运动合成孔径 Bearing 得到的 AP belief，预测未走路径的中断风险与不确定性。

### Contribution 3

提出受额外路径预算约束的 frontier 重排序方法，并通过 Oracle 上界、强预测基线、跨场景/跨信道测试和外部域验证，证明方法改善 SPL--Outage Pareto，并在网络失败闭环下提升 ObjectNav。

---

## 13. 预期结果

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

## 14. 风险与备选方案

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

## 15. 阶段划分

### V0：协议冻结与 OpenFrontier 最小复现

目标：

- 明确协作式 AP、双向 CSI、时间同步和可观测量；
- 跑通 OpenFrontier 并导出 Top-K frontier、原始效用和候选路径；
- 固定网络失败如何作用于 VLM 请求、决策更新和导航；
- 固定额外路径预算和主评测协议。

### V1：Oracle 通信感知 OpenFrontier（生死实验）

目标：

- 使用真实无线地图或外部无线真值重排 frontier；
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

## 16. 最终冻结版本

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

### 16.1 投稿前硬门槛

只有同时满足以下条件，才进入完整 CCF C 投稿冲刺：

1. Oracle 在固定路径预算下稳定改善 SPL--Outage Pareto；
2. Full predictor 在未见场景和外部测试域优于强基线，并具有合理校准；
3. AP belief 或其他 CSI 表示能对最终路径排序产生独立增益；
4. 预测方法保留一部分 Oracle 端到端收益；
5. 至少有一种不同于训练仿真器的外部证据，且失败案例得到解释。
