# RadioNavDP Project Plan v3

> Version: v3  
> Status: Idea freeze candidate  
> Backbone: X-NavDP  
> Primary task: Communication-Aware PointGoal Navigation  
> Core update: replace frontier-level wireless reranking with diffusion-trajectory-level future channel forecasting and optional RL post-training.

---

## 1. 项目名称

**RadioNavDP: Communication-Aware Navigation Diffusion Policy via Future Channel Forecasting**

中文暂定题目：

**基于未来信道预测的通信感知导航扩散策略**

---

## 2. 一句话 Idea

我们研究一个 **communication-aware visual navigation** 问题：

> 给定预训练 X-NavDP 生成的多条未来候选轨迹，机器人仅利用已经观测到的无线信号、历史运动状态、AP 信息和局部场景几何，预测每条尚未执行轨迹未来的无线通信质量，并利用该预测重新选择轨迹；进一步，可将通信质量作为强化学习奖励，对 X-NavDP 进行轻量 post-training，使导航策略主动生成 connectivity-preserving trajectories。

核心从原来的：

**Frontier → Channel Prediction → Frontier Reranking**

更新为：

**Diffusion Trajectory → Future Channel Prediction → Trajectory Selection / RL**

---

## 3. 核心研究问题

传统视觉导航主要考虑：

- 能否到达目标；
- 路径是否短；
- 是否碰撞；
- 轨迹是否可执行。

但对于远程控制、云端推理、视频回传、机器人协作等任务，机器人还必须维持无线连接。

因此我们的核心问题是：

> 当机器人不知道尚未经过区域真实无线信号时，能否根据历史无线观测和场景几何，预测不同未来候选轨迹上的通信质量，并利用预测结果避免通信中断，同时尽可能保持导航效率？

本项目优化的不是“信号最大化”，而是：

$$
\text{navigation utility}
\quad\leftrightarrow\quad
\text{communication utility}
$$

之间的 Pareto trade-off。

---

## 4. 为什么使用 X-NavDP

X-NavDP 对当前状态：

$$
s_t
$$

生成多条候选未来轨迹：

$$
\mathcal T_t = \{\tau_1,\tau_2,\ldots,\tau_N\}
$$

其中：

$$
\tau_i = \{p_{i,1},p_{i,2},\ldots,p_{i,H}\}.
$$

X-NavDP 原始 critic 为每条轨迹提供导航价值：

$$
Q_{\mathrm{nav}}(s_t,\tau_i).
$$

因此 X-NavDP 天然提供：

**候选未来轨迹 + navigation score**。

我们的贡献补充：

**future communication score**。

这使得通信预测模块可以直接作用在 trajectory level，而不需要 frontier extraction 或额外 A* candidate path generation。

---

## 5. 系统总览

```text
                 RGB-D + PointGoal
                        ↓
                   X-NavDP Actor
                        ↓
             Diffusion trajectory sampling
                        ↓
          τ1, τ2, τ3, ... , τN
            │                   │
            │                   │
            ↓                   ↓
      X-NavDP Critic      Channel Forecaster
            ↓                   ↓
      Q_nav(s, τi)       RSSI_{i,1:H}
                              ↓
                        Outage / Min RSSI
                        / Uncertainty
            │                   │
            └─────────┬─────────┘
                      ↓
          Communication-Aware Score
                      ↓
                 select τ*
                      ↓
                    MPC
                      ↓
              Execute trajectory
                      ↓
                Actual RSSI
                      ↓
             Optional RL reward
```

---

## 6. 系统输入与输出

### 6.1 X-NavDP 输入

保持官方 backbone 不变：

$$
o_t = [RGB_t, Depth_t, Goal_t]
$$

其中 PointGoal 表示为机器人局部坐标下：

$$
Goal_t = (\Delta x,\Delta y).
$$

第一阶段不把 RSSI 直接加入 X-NavDP actor 输入。

X-NavDP 输出：

$$
\mathcal T_t = \{\tau_1,\ldots,\tau_N\}
$$

以及每条轨迹的导航价值：

$$
Q_{\mathrm{nav}}(s_t,\tau_i).
$$

---

### 6.2 我们的 Future Channel Forecaster 输入

对每一条候选轨迹：

$$
X_i = [\mathcal H_t^{radio}, p_{AP}, \tau_i, G_t(\tau_i)].
$$

#### A. 历史无线观测

第一版使用最近 $K$ 个时刻：

$$
\mathcal H_t^{radio}
=
\{(p_k, yaw_k, RSSI_k, t_k)\}_{k=t-K+1}^{t}.
$$

后续可加入：

- CSI amplitude；
- CSI phase / phase difference；
- SNR；
- AoA embedding。

#### B. AP 信息

第一版假设 AP 位置已知：

$$
p_{AP}=(x_{AP},y_{AP}).
$$

输入使用相对坐标：

$$
\Delta p_{AP}=p_{AP}-p_{robot}.
$$

增强版再替换为 AP belief：

$$
B_t^{AP}.
$$

#### C. Candidate trajectory

每条 trajectory：

$$
\tau_i=\{p_{i,1},...,p_{i,H}\}
$$

使用机器人局部坐标表达，并可附加：

- relative $(x,y)$；
- cumulative distance；
- trajectory curvature；
- heading change；
- distance-to-AP。

#### D. 局部场景几何

$$
G_t
$$

第一版建议使用：

- local occupancy map；
- depth-derived BEV；
- wall intersection count；
- LOS/NLOS indicator；
- obstacle density。

---

### 6.3 Channel Forecaster 输出

模型不只预测 endpoint RSSI，而是预测整条 trajectory：

$$
f_\theta(X_i)
\rightarrow
[\hat R_{i,1},...,\hat R_{i,H}].
$$

增强版输出概率分布：

$$
[(\mu_{i,1},\sigma_{i,1}),..., (\mu_{i,H},\sigma_{i,H})].
$$

再聚合成 trajectory-level communication features：

$$
\hat C_i = [
\widehat{RSSI}^{mean},
\widehat{RSSI}^{min},
\hat P_{outage},
\widehat T_{outage},
\hat\sigma_i
].
$$

最终系统输出不是 RSSI，而是：

$$
\boxed{\text{selected trajectory } \tau^*}
$$

---

## 7. 无线仿真环境

每个 navigation episode 设置：

- 一个静态 AP；
- AP 在一个 episode 内固定；
- 同一个 scene 使用多个 AP placements；
- 不同方法共享相同的 scene、start/goal、AP placement、channel parameters 和 random seed。

无线真值表示为：

$$
R(x,y)=RSSI(x,y).
$$

第一阶段使用较便宜的模型：

- log-distance path loss；
- wall attenuation；
- LOS/NLOS；
- shadowing。

正式实验逐步升级为：

- Sionna RT radio map；
- 不同传播模型；
- 半真实 / 真实无线数据。

推荐对每个：

$$
(scene, AP\ placement)
$$

离线预计算 ground-truth radio map，RL rollout 时直接查询，避免在线 ray tracing 成为训练瓶颈。

---

## 8. 第一阶段：Oracle Communication 生死实验

第一阶段不训练任何通信模型。

对于每条候选 trajectory：

$$
\tau_i=\{p_{i,1},...,p_{i,H}\}
$$

直接从 ground-truth radio map 查询：

$$
R_{i,h}=R(p_{i,h}).
$$

### Mean RSSI

$$
C_{mean}(\tau_i)=\frac1H\sum_h R_{i,h}
$$

### Minimum RSSI

$$
C_{min}(\tau_i)=\min_h R_{i,h}
$$

### Outage Cost

给定 threshold：

$$
R_{th}
$$

定义：

$$
C_{outage}(\tau_i)
=
\frac1H\sum_h\max(0,R_{th}-R_{i,h}).
$$

最终选择：

$$
\tau^*
=
\arg\max_i
[
\widetilde Q_{nav}(s,\tau_i)
-
\lambda\widetilde C_{outage}(\tau_i)
].
$$

Oracle 实验只回答一个问题：

> X-NavDP 生成的候选 trajectories 中，是否存在 navigation quality 接近但 communication quality 明显更好的选择？

若 Oracle 在合理导航代价下仍无法改善 outage，则停止后续复杂 predictor / RL 开发。

---

## 9. Future Channel Forecaster

### 9.1 核心任务

训练：

$$
f_\theta(
\text{radio history},
\text{AP information},
\text{geometry},
\text{candidate trajectory}
)
$$

预测：

$$
\text{future RSSI / outage along unseen trajectory}.
$$

注意：训练输入只能使用当前时刻之前已经获得的信息；未来 RSSI 只能作为 label 或 Oracle。

---

### 9.2 Physics-Guided Prediction

先使用物理模型：

$$
R_{phy}(x)
=
P_0
-10n\log_{10}d(x,p_{AP})
-\sum_m\alpha_mN_m(x,p_{AP}).
$$

学习器只预测 residual：

$$
\hat R(x)
=
R_{phy}(x)
+
\Delta R_\theta(
\mathcal H_t^{radio},G_t,x
).
$$

这样可以降低数据需求，并为跨场景泛化提供更强 inductive bias。

---

## 10. Predictor 训练标签

训练数据完全自动生成，不需要人工 SFT 标注。

对 X-NavDP 的候选 trajectory：

$$
\tau_i=p_1,...,p_H
$$

查询 ground-truth radio map：

$$
Y_i=[R^{GT}(p_1),...,R^{GT}(p_H)].
$$

训练样本：

$$
(
\mathcal H_t^{radio},
p_{AP},
G_t,
\tau_i
)
\rightarrow
Y_i.
$$

每一个 navigation decision 可产生 $N$ 个 trajectory samples，因此数据可自动大规模积累。

---

## 11. Predictor 训练损失

### 11.1 RSSI Regression Loss

推荐 Huber loss：

$$
\mathcal L_{rssi}
=
\frac1H\sum_h
Huber(\hat R_h,R_h).
$$

### 11.2 Outage Classification Loss

定义：

$$
y_h^{out}=\mathbb 1[R_h<R_{th}].
$$

使用：

$$
\mathcal L_{out}=BCE(\hat p_h^{out},y_h^{out}).
$$

### 11.3 Trajectory Ranking Loss

若 ground-truth communication utility 满足：

$$
C_i^{GT}>C_j^{GT}
$$

则希望：

$$
\hat C_i>\hat C_j.
$$

可使用 margin ranking loss：

$$
\mathcal L_{rank}
=
\max(0,m-\hat C_i+\hat C_j).
$$

### 11.4 总损失

$$
\boxed{
\mathcal L
=
\lambda_1\mathcal L_{rssi}
+
\lambda_2\mathcal L_{out}
+
\lambda_3\mathcal L_{rank}
}
$$

若模型输出 uncertainty，再加入 NLL / calibration loss。

---

## 12. Communication-Aware Trajectory Selection

第一版完全冻结 X-NavDP。

原版：

$$
\tau^*=\arg\max_iQ_{nav}(s,\tau_i).
$$

我们定义：

$$
J_i
=
\widetilde Q_{nav}(s,\tau_i)
-
\lambda_o\hat P_{outage}(\tau_i)
-
\lambda_m\mathrm{ReLU}(R_{min}-\widehat R_{min}(\tau_i))
-
\lambda_u\hat\sigma_i.
$$

然后：

$$
\boxed{\tau^*=\arg\max_iJ_i}
$$

该阶段不需要重新训练 navigation backbone。

---

## 13. Communication-Aware Critic

如果简单 reranking 有效，进入第二级学习融合。

原 critic：

$$
Q_{nav}(s,\tau).
$$

改为：

$$
Q_{comm-nav}(s,\tau,z_{comm})
$$

其中：

$$
z_{comm}=[
\hat R_{mean},
\hat R_{min},
P_{outage},
\sigma
].
$$

这一阶段可以冻结 diffusion actor，只训练 critic。

目标：

> 学习一条 trajectory 在导航和通信上的联合长期价值，而不是固定手工权重融合。

---

## 14. Communication-Aware X-NavDP RL

这是增强项，不是项目成立的前提。

执行 trajectory 后，从 ground-truth radio map / simulator 得到实际 RSSI：

$$
R_{t:t+H}.
$$

定义通信奖励：

$$
r_{comm}
=
-\frac1H\sum_h\max(0,R_{th}-R_h).
$$

总奖励：

$$
\boxed{
r_{total}
=
r_{nav}
+
\lambda_{comm}r_{comm}
}
$$

X-NavDP critic 学习：

$$
Q_{total}(s,\tau)
$$

再通过 GQRM 对 actor 进行 post-training，使 diffusion policy 从“选择更好的通信轨迹”进一步升级为“主动生成通信更安全的轨迹”。

---

## 15. Benchmark

主 benchmark 更新为：

```text
X-NavDP
+
IsaacSim / IsaacLab
+
GRScenes
+
PointGoal Navigation
+
single-AP multi-placement radio protocol
```

第一阶段不再以 ObjectNav 为主 benchmark。

---

## 16. 评价指标

### 16.1 Channel Prediction Metrics

点级预测：

- RSSI MAE ↓；
- RSSI RMSE ↓。

Outage prediction：

- Precision ↑；
- Recall ↑；
- F1 ↑；
- AUROC ↑。

Trajectory ranking：

- Pairwise Ranking Accuracy ↑；
- Spearman Correlation ↑；
- Top-1 Trajectory Agreement ↑；
- Top-K Recall ↑。

Uncertainty / calibration：

- NLL ↓；
- ECE ↓；
- 95% Prediction Interval Coverage。

其中，Outage Recall 和 trajectory ranking accuracy 比纯 RSSI MAE 更接近最终导航目标。

---

### 16.2 Navigation Metrics

- Success Rate (SR) ↑；
- SPL ↑；
- Path Length ↓；
- Collision Rate ↓；
- Navigation Time ↓。

---

### 16.3 Communication Metrics

论文正文建议以以下指标为主：

- Outage Ratio ↓；
- Longest Outage ↓；
- Mean Outage Duration ↓；
- Minimum RSSI ↑；
- P5 RSSI ↑；
- Average RSSI ↑；
- Connectivity Rate ↑。

后续如果引入 network model，再加入：

- packet loss；
- goodput；
- latency；
- jitter。

---

### 16.4 Primary End-to-End Result

主结果不应只比较单一指标，而是报告：

$$
\boxed{\text{Navigation–Communication Pareto}}
$$

例如：

- SPL vs Outage Ratio；
- SR vs Longest Outage；
- Path Length vs P5 RSSI。

通过 sweep $\lambda_{comm}$ 得到 Pareto curve。

目标是证明 learned method 向 Oracle frontier 靠近，同时保持合理导航性能。

---

## 17. Baselines

核心方法至少比较：

1. Original X-NavDP；
2. X-NavDP + Current RSSI；
3. X-NavDP + Distance-to-AP；
4. X-NavDP + Physics-Only；
5. X-NavDP + Oracle Future RSSI；
6. X-NavDP + Learned Channel Predictor；
7. X-NavDP + Learned Predictor + Uncertainty；
8. X-NavDP + Communication-Aware Critic；
9. Communication-Aware RL X-NavDP（后期）。

主证明链：

```text
未来通信信息本身有没有价值？
        ↓
简单无线启发式够不够？
        ↓
learned predictor 是否接近 Oracle？
        ↓
prediction 是否改善真实 navigation–outage Pareto？
        ↓
learned critic 是否优于手工融合？
        ↓
RL 是否进一步改善 trajectory generation？
```

---

## 18. 数据集划分与防泄漏

不随机打散 trajectory points。

建议：

### Train

```text
training scenes
+
training AP placements
```

### Validation

```text
training scene family
+
unseen AP placements / unseen channel parameters
```

### Primary Test

```text
unseen scenes
+
unseen AP placements
```

### External Test

```text
Sionna RT / different propagation model / semi-real / real wireless data
```

严禁：

- 同一 episode 相邻 decision states 跨 train/test；
- 同一 AP placement 跨集合；
- 测试场景 radio statistics 参与归一化；
- 使用未来 trajectory RSSI 构造 predictor 输入。

---

## 19. 核心假设

### H0 — Oracle Utility

如果知道 candidate trajectories 的真实未来通信质量，则可以在较小 navigation performance 损失下显著减少 outage。

这是项目生死假设。

### H1 — Future Channel Predictability

基于 historical radio observations、robot motion、AP information、scene geometry 和 candidate trajectory，可以预测尚未执行 trajectory 的 future outage risk。

### H2 — Prediction-to-Decision

learned predictor 不仅降低预测误差，而且能够保留 Oracle trajectory ranking 和端到端收益中的可观比例。

### H3 — RL Adaptation

加入 communication reward 后，X-NavDP actor 可以主动生成 connectivity-preserving trajectories，而不仅依赖 reranking。

H3 是增强项，不是项目成立的必要条件。

---

## 20. 训练策略

整个项目不采用 joint training from scratch，而采用渐进式策略：

$$
\boxed{
\text{Oracle}
\rightarrow
\text{Supervised Channel Predictor}
\rightarrow
\text{Frozen X-NavDP Reranking}
\rightarrow
\text{Comm Critic}
\rightarrow
\text{Optional RL}
}
$$

### V0 — X-NavDP Reproduction

目标：

- 跑通官方 PointGoal benchmark；
- 导出 candidate trajectories；
- 导出 critic values；
- 确认 trajectory execution；
- 复现基本 SR / SPL。

不做无线训练。

### V1 — Oracle Radio Benchmark

加入：

- AP placement；
- radio map；
- Oracle trajectory-level RSSI query；
- communication-aware reranking。

输出 Navigation–Outage Pareto。

这是 Go / No-Go。

### V2 — Future Channel Forecaster

冻结 X-NavDP。

训练：

$$
\text{history + AP + geometry + trajectory}
\rightarrow
\text{future RSSI / outage}.
$$

使用 supervised regression + outage classification + ranking loss。

### V3 — Learned Communication-Aware Navigation

用 predictor 替代 Oracle：

$$
Q_{nav}+\lambda Q_{comm}
\rightarrow
\tau^*.
$$

X-NavDP actor/critic 全部冻结。

重点评价 learned method 保留多少 Oracle gain。

### V4 — Communication-Aware Critic

冻结 actor，只训练 critic：

$$
Q(s,\tau,z_{comm}).
$$

目标是让 critic 自动学习 navigation/communication trade-off。

### V5 — Communication-Aware RL

在前面全部成立后，再加入：

$$
r_{total}=r_{nav}+\lambda r_{comm}
$$

进行 X-NavDP GQRM post-training。

### V6 — CSI / AP Belief / Sim-to-Real

最后再加入：

- CSI；
- Bearing；
- AP belief；
- Sionna RT；
- semi-real / real wireless data。

这些不作为第一阶段成败的前置条件。

---

## 21. 第一版固定 Tensor Schema 建议

为了方便代码实现，第一版可先固定：

### Input

```text
K = 16 past states

radio_history:
[K, 4]
= [dx, dy, yaw, RSSI]

AP_relative_position:
[2]

local_occupancy:
[1, 128, 128]

candidate_trajectory:
[H, 2]

H = 24 future waypoints
```

### Output

```text
future_rssi:
[H]

future_outage_probability:
[H]

optional_uncertainty:
[H]
```

### Derived trajectory features

```text
mean_rssi
min_rssi
outage_ratio
predicted_outage_duration
uncertainty_score
```

这个 schema 后续可以扩展 CSI，但第一轮不建议增加模型复杂度。

---

## 22. 当前最小可行实验

第一轮只实现：

```text
X-NavDP pretrained checkpoint
        +
IsaacSim scene
        +
one AP
        +
precomputed radio map
        +
Oracle trajectory RSSI lookup
        +
trajectory reranking
```

不需要：

- 重新训练 X-NavDP；
- Channel Predictor；
- CSI；
- Bearing；
- AP localization；
- RL。

只有当 Oracle 实验证明 X-NavDP candidate trajectories 中存在有意义的 communication trade-off，才继续投入 predictor 和 RL。

---

## 23. 当前最核心的论文贡献候选

### Contribution 1

提出 **communication-aware navigation diffusion policy** 设定，在 PointGoal visual navigation 中联合评价 navigation efficiency 与 wireless outage。

### Contribution 2

提出 **trajectory-conditioned future channel forecaster**，根据历史无线观测、场景几何、AP 信息和尚未执行的 diffusion trajectory，预测 future RSSI / outage / uncertainty。

### Contribution 3

提出无需重新训练 navigation backbone 的 communication-aware trajectory selection，并进一步探索基于 communication reward 的 X-NavDP post-training，使 diffusion actor 学习 connectivity-preserving navigation behavior。

---

## 24. 最关键证明链

```text
Oracle future communication improves trajectory decisions
                     ↓
Future signal along unseen trajectories is predictable
                     ↓
Learned predictor approaches Oracle trajectory ranking
                     ↓
Predicted communication reduces actual outage
                     ↓
Navigation SR/SPL remains competitive
                     ↓
Optional:
Communication-aware critic / RL improves the Pareto frontier further
```

---

## 25. 当前项目最简洁定义

> **让机器人不仅预测“哪条路能到目标”，还预测“沿哪条路走不会失联”。**

数学上：

$$
\boxed{
\text{Visual Navigation}
+
\text{Future Wireless Forecasting}
\rightarrow
\text{Connectivity-Preserving Trajectory Planning}
}
$$

当前最重要的第一步不是训练大模型，而是：

$$
\boxed{
\text{X-NavDP + Oracle Future RSSI}
}
$$

若该实验成立，再训练 channel predictor，再考虑 communication-aware critic 和 RL。

