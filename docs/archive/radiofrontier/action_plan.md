# RadioFrontier Action Plan

## 1. 当前总目标

先完成一个能够回答以下问题的最小闭环系统：

> 当 OpenFrontier 给出多个语义合理的 visual frontier 时，候选路径的通信中断风险是否具有决策价值；若有，仅使用历史 CSI、AP belief 和路径几何能否在固定额外路径预算下逼近 Oracle 收益？

执行顺序必须遵循：

```text
冻结协议与评测
→ Oracle 生死实验
→ CSI/Bearing/AP belief
→ 强基线与路径风险预测
→ 外部域和端到端验证
```

不要一开始同时实现所有模块。

### 1.1 冻结的系统假设

- 单个静态、协作式 AP/无线锚点；
- 机器人与锚点可获取双向 CSI；
- 机器人位姿、RGB-D 和局部占据几何可用；
- 未来路径 CSI 只能用于标签或 Oracle，不能进入预测输入；
- 第一篇论文只做高层 frontier 重排序；
- 所有比较共享相同 Top-K 语义候选和额外路径预算；
- 主实验不依赖实时云端 API，网络失败采用可重复回放。

### 1.2 强制执行门

本文后续章节保留模块化编号，实际开发必须按以下 Gate 顺序推进：

| Gate | 问题 | 通过后才能做 |
|---|---|---|
| G0 | OpenFrontier、候选路径和网络失败闭环是否可复现？ | Oracle 实验 |
| G1 | Oracle 路径风险能否改善 SPL--Outage Pareto？ | CSI 复现与 AP belief |
| G2 | AP belief 是否改善未走路径的 outage prediction？ | 神经预测器 |
| G3 | 学习方法能否保留 Oracle 的端到端收益？ | 视频/实机 Demo 与投稿扩展 |

任何 Gate 未通过，优先修改任务定义或分析失败原因，不通过增加模型规模掩盖问题。

> 数学公式采用 GitHub/Typora 兼容的 `$$ ... $$` 块级格式。使用 VS Code 时需启用支持 LaTeX 数学渲染的 Markdown 预览插件。

---

## 2. 代码仓库建议

```text
RadioFrontier/
├── README.md
├── plan.md
├── action.md
├── configs/
│   ├── csi_paper.yaml
│   ├── csi_indoor.yaml
│   ├── openfrontier.yaml
│   └── experiment.yaml
├── third_party/
│   └── OpenFrontier/
├── radiofrontier/
│   ├── csi/
│   │   ├── simulator.py
│   │   ├── channel.py
│   │   ├── cfo.py
│   │   ├── noise.py
│   │   ├── trajectory.py
│   │   ├── virtual_array.py
│   │   └── bartlett.py
│   ├── localization/
│   │   ├── bearing_observation.py
│   │   ├── ap_belief.py
│   │   └── triangulation.py
│   ├── channel_prediction/
│   │   ├── dataset.py
│   │   ├── physics_model.py
│   │   ├── csi_encoder.py
│   │   ├── geometry_encoder.py
│   │   ├── path_predictor.py
│   │   └── losses.py
│   ├── navigation/
│   │   ├── frontier_adapter.py
│   │   ├── path_generator.py
│   │   ├── comm_ranker.py
│   │   └── risk_astar.py
│   ├── network/
│   │   ├── qos_model.py
│   │   ├── video_stream.py
│   │   └── query_model.py
│   ├── metrics/
│   │   ├── localization.py
│   │   ├── channel.py
│   │   ├── navigation.py
│   │   ├── communication.py
│   │   └── video.py
│   └── visualization/
│       ├── aoa_plot.py
│       ├── belief_plot.py
│       ├── path_risk_plot.py
│       └── demo_overlay.py
├── scripts/
│   ├── reproduce_paper_circular.py
│   ├── reproduce_paper_linear.py
│   ├── evaluate_bearing.py
│   ├── evaluate_ap_belief.py
│   ├── run_oracle_navigation.py
│   ├── generate_channel_dataset.py
│   ├── train_path_predictor.py
│   ├── evaluate_path_predictor.py
│   ├── run_radiofrontier.py
│   └── run_video_demo.py
├── tests/
│   ├── test_cfo_cancellation.py
│   ├── test_bartlett.py
│   ├── test_ap_belief.py
│   └── test_frontier_ranking.py
└── outputs/
    ├── figures/
    ├── checkpoints/
    ├── logs/
    └── videos/
```

---

# 3. Phase 0：环境与复现准备

## 3.1 OpenFrontier 环境

- [ ] Fork 或下载 OpenFrontier；
- [ ] 记录 commit hash；
- [ ] 创建独立 Conda 环境；
- [ ] 跑通一个官方 HM3D/MP3D episode；
- [ ] 保存原始 SR、SPL 和轨迹；
- [ ] 找到 frontier 数据结构；
- [ ] 找到 frontier utility 计算位置；
- [ ] 找到 frontier 到 PointGoal 的接口；
- [ ] 找到高层决策调用周期；
- [ ] 确认是否能读取候选路径点。

### 验收标准

- 可以运行至少 10 个 episode；
- 可以输出每一步候选 frontier；
- 可以输出每个 frontier 的原始语义分数和距离；
- 可以可视化选择的 frontier。

---

## 3.2 论文代码和参数核对

- [ ] 下载原论文官方仓库；
- [ ] 整理 MATLAB 文件与功能对应关系；
- [ ] 记录所有固定参数；
- [ ] 确认 CFO、STO、WGN 的实现；
- [ ] 确认圆形和线形轨迹坐标；
- [ ] 确认 Bartlett steering vector；
- [ ] 保存 MATLAB 原始输出作为 Python 对照。

### 需要记录的主要参数

```yaml
carrier_frequency_hz: 5.54e9
bandwidth_hz: 20e6
num_subcarriers: 30
sample_rate_hz: 100
snr_db: 3
delta_f: 10.0
c1: 10000
c2: 200
rx_tx_time_error_s: 1e-7
circle_radius_m: 0.30
linear_length_m: 1.884955592
trajectory_duration_s: 10
bearing_resolution_deg: 1
```

### 验收标准

- 有一份 `csi_paper.yaml`；
- 所有论文参数都有来源说明；
- Python 复现不依赖手动写死参数。

---

## 3.3 协议和失败机制冻结

- [ ] 画出机器人与协作式 AP 的 CSI 数据流；
- [ ] 明确双向 CSI 的采样、时间戳和 reciprocal cancellation 假设；
- [ ] 区分仿真可观测量、训练标签和部署可观测量；
- [ ] 定义 outage threshold 和最短持续时间；
- [ ] 定义中断如何造成请求超时、决策陈旧或帧丢失；
- [ ] 固定 Top-K 语义候选、决策周期和额外路径预算；
- [ ] 将所有设定写入版本化配置，禁止按测试结果临时修改。

### G0 验收标准

- OpenFrontier 能稳定导出候选 frontier、效用和路径；
- 同一 episode 和 seed 可复现完全相同的失败回放；
- Original、Current CSI 和 Oracle 使用完全相同的候选集；
- 日志能区分当前观测、预测值和 Oracle 真值；
- 形成一页系统假设与不支持范围说明。

---

# 4. Phase 1：Python 复现 CSI 与 Bearing

## 4.1 实现 CSI 基础模型

- [ ] 实现波长计算；
- [ ] 实现距离计算；
- [ ] 实现单径复数 CSI；
- [ ] 实现正向 CSI；
- [ ] 实现反向 CSI；
- [ ] 实现 CFO 模型；
- [ ] 实现 STO；
- [ ] 实现 WGN；
- [ ] 实现相位 unwrap；
- [ ] 实现双向 CSI 相乘消除 CFO。

### 单元测试

- [ ] 无 CFO 时相位符合理论值；
- [ ] 正反 CFO 符号相反；
- [ ] 相乘后 CFO 明显降低；
- [ ] 固定位置下消除后相位近似稳定；
- [ ] 不同随机种子可复现。

---

## 4.2 实现轨迹生成

- [ ] 圆形轨迹；
- [ ] 线形轨迹；
- [ ] 任意二维轨迹；
- [ ] Habitat 离散动作插值轨迹；
- [ ] 累计虚拟孔径长度计算。

### 验收标准

- 圆形轨迹半径和时长与论文一致；
- 线形轨迹长度和速度与论文一致；
- 100 Hz 下采样点数量正确。

---

## 4.3 实现 Bartlett Estimator

- [ ] 实现二维 steering vector；
- [ ] 实现 -180° 到 180° 扫描；
- [ ] 实现 AoA profile；
- [ ] 实现最大峰值；
- [ ] 实现 Top-K 峰值；
- [ ] 实现峰值置信度；
- [ ] 实现 profile entropy；
- [ ] 实现镜像峰检测。

### 验收标准

#### Circular Case

- 唯一主峰接近真实 Bearing；
- 平均 Bearing Error 达到预期；
- 多次噪声实验结果稳定。

#### Linear Case

- 出现两个镜像主峰；
- 两个峰值关于轨迹方向近似对称；
- 不强行错误消除镜像峰。

---

## 4.4 输出复现图

- [ ] CSI raw phase；
- [ ] CFO-cancelled phase；
- [ ] circular AoA profile；
- [ ] linear AoA profile；
- [ ] Bearing error distribution；
- [ ] 不同 SNR 下 Bearing 曲线；
- [ ] 不同 aperture length 下 Bearing 曲线。

### Phase 1 完成标准

```text
Python 能复现：
1. CFO 消除效果；
2. 圆形轨迹唯一 Bearing；
3. 线形轨迹镜像 Bearing；
4. 论文参数下的趋势。
```

---

# 5. Phase 2：AP Belief

## 5.1 实现二维 Belief Grid

- [ ] 定义地图边界；
- [ ] 初始化均匀先验；
- [ ] 排除障碍或墙体单元；
- [ ] 输入机器人位姿；
- [ ] 输入单峰 Bearing；
- [ ] 输入多峰 Bearing；
- [ ] 根据置信度设置角度方差；
- [ ] 归一化 belief；
- [ ] 输出 MAP 和期望位置；
- [ ] 输出 entropy。

---

## 5.2 实现 Bearing Update

单峰：

$$
p(\theta\mid s,p_t)
$$
双峰：

$$
p(\theta)=
w_1p(\theta_1)+w_2p(\theta_2)
$$
- [ ] 支持角度 wrap；
- [ ] 支持低置信度降权；
- [ ] 支持高熵观测跳过；
- [ ] 支持遗忘或时间衰减；
- [ ] 支持机器人位姿噪声。

---

## 5.3 仿真实验

测试轨迹：

- [ ] 圆形；
- [ ] 单直线；
- [ ] L 形；
- [ ] 多转角；
- [ ] 随机 ObjectNav 轨迹。

指标：

- [ ] AP Position Error；
- [ ] Coverage@1m；
- [ ] Coverage@2m；
- [ ] belief NLL；
- [ ] convergence steps；
- [ ] entropy over time。

### Phase 2 完成标准

- L 形或自然转弯轨迹可以消除线形镜像；
- belief 随观测增加逐渐收敛；
- 可生成 AP belief 动画；
- AP 定位模块可作为独立 Python 包调用。

---

# 6. Phase 3：最小价值验证

这一阶段暂时不训练路径预测网络。

目的：

> 先证明如果知道候选路径真实通信质量，通信感知 frontier 选择确实有价值。

---

## 6.1 构造 Indoor-Extended 无线真值

- [ ] 对数距离损耗；
- [ ] 墙体穿透损耗；
- [ ] LOS/NLOS；
- [ ] 空间相关阴影衰落；
- [ ] 可选简化多径；
- [ ] 从 SNR 映射到 Goodput；
- [ ] 从 Goodput 映射到视频 FPS；
- [ ] 定义 outage threshold；
- [ ] 准备至少两个参数不重叠的信道族；
- [ ] 预留射线追踪、真实回放或实采 CSI 的外部测试接口；

---

## 6.2 接入 OpenFrontier

- [ ] 获取候选 frontiers；
- [ ] 为每个 frontier 生成候选路径；
- [ ] Oracle 查询整条路径真实 SNR；
- [ ] 计算 path mean/min/P5/outage；
- [ ] 加入通信重排序；
- [ ] 保留原始 OpenFrontier 结果。

---

## 6.3 最小基线

- [ ] Original OpenFrontier；
- [ ] OpenFrontier + Current CSI；
- [ ] OpenFrontier + Distance-to-AP；
- [ ] OpenFrontier + Oracle Radio Path。

---

## 6.4 关键实验

- [ ] 调整通信权重；
- [ ] 绘制 SPL-Outage Pareto；
- [ ] 绘制 Path Length-Outage Pareto；
- [ ] 统计最长连续中断；
- [ ] 分析通信改变 frontier 的决策案例；
- [ ] 在固定额外路径预算下做配对 episode 比较；
- [ ] 加入网络失败导致决策陈旧的闭环实验；
- [ ] 报告收益、无变化和负收益三类案例。

正式样本量在 pilot 后依据 episode 方差或功效分析一次性冻结；不得看到显著性结果后反复增加 episode。主比较使用相同 scene、episode、AP deployment 和 seed 的配对评测，并报告 bootstrap 置信区间。

### Go / No-Go 标准

继续完整项目需要至少观察到：

- Oracle Radio Path 在预注册的路径预算下稳定改善 SPL--Outage Pareto；
- 配对 episode 结果的置信区间支持该改善，而不是少数 seed 驱动；
- 在确定性网络失败闭环中，通信改善能够减少 stale decision 或提升导航结果；
- frontier 改变后既有正收益案例，也完成负收益案例归因。

如果 Oracle 只改善平均 SNR、不能改善 outage/Pareto 或闭环导航，则 G1 不通过：停止 AP belief 和神经预测器开发，重新定义候选集、失败机制或论文问题。

---

# 7. Phase 4：路径信道预测数据集

## 7.1 样本生成

每个决策时刻：

1. 保存历史 CSI；
2. 保存 AP belief；
3. 保存候选 frontier；
4. 保存每个候选路径；
5. 保存路径局部几何；
6. Oracle 查询路径真值；
7. 写入数据集。

---

## 7.2 数据字段

```python
sample = {
    "scene_id": str,
    "episode_id": str,
    "step": int,
    "robot_pose": array,
    "csi_history": array,
    "csi_history_mask": array,
    "ap_belief": array,
    "ap_map_position": array,
    "ap_belief_entropy": float,
    "path_points": array,
    "path_mask": array,
    "geometry_features": array,
    "target_signal": array,
    "target_outage": array,
    "path_mean_signal": float,
    "path_min_signal": float,
    "path_p5_signal": float,
    "path_outage_ratio": float,
}
```

---

## 7.3 数据划分

- [ ] 按场景划分；
- [ ] 按 AP 部署划分；
- [ ] 未见场景测试；
- [ ] 未见 AP 测试；
- [ ] 不同信道参数测试；
- [ ] 不同噪声测试；
- [ ] 外部测试域：射线追踪、真实回放或实采 CSI 至少一种。

### 防泄漏检查

- [ ] 同一 scene 不跨 Train/Test；
- [ ] 同一 AP deployment 不跨 Train/Test；
- [ ] 同一 episode 的路径不跨集合；
- [ ] 同一 episode 的相邻决策点不跨集合；
- [ ] 归一化参数只由 Train 计算；
- [ ] 输入中不含未来 CSI、生成器隐藏参数或 Oracle AP 信息；
- [ ] 训练和测试的信道参数族明确分离。

---

# 8. Phase 5：Path Predictor

## 8.1 Baseline 先行

按顺序完成：

- [ ] Last CSI；
- [ ] Nearest Neighbor；
- [ ] AP Distance；
- [ ] Log-Distance；
- [ ] Wall Count；
- [ ] GP/Kriging；
- [ ] Physics-Only。

先获得稳定基线，再做神经网络。

---

## 8.2 神经预测器

建议第一版：

```text
CSI History Encoder: GRU / Transformer
AP Belief Encoder: Small CNN
Path Encoder: GRU / Transformer
Geometry Encoder: CNN / MLP
Fusion: MLP
Output: mean + log variance + outage probability
```

- [ ] 实现 CSI encoder；
- [ ] 实现 AP belief encoder；
- [ ] 实现 path encoder；
- [ ] 实现 geometry encoder；
- [ ] 实现 fusion；
- [ ] 实现 heteroscedastic regression；
- [ ] 实现 outage classification；
- [ ] 实现 physics residual。

---

## 8.3 损失函数

$$
\mathcal L=
\lambda_{nll}\mathcal L_{NLL}
+\lambda_{out}\mathcal L_{BCE}
+\lambda_{rank}\mathcal L_{rank}
+\lambda_{path}\mathcal L_{path}
$$
建议包含：

- [ ] 点级高斯 NLL；
- [ ] outage BCE；
- [ ] 路径最差点误差；
- [ ] 候选路径排序损失；
- [ ] 可选 calibration loss。

---

## 8.4 预测评测

- [ ] 点级 MAE/RMSE；
- [ ] 路径 mean/min/P5 误差；
- [ ] Outage F1/AUROC；
- [ ] NLL；
- [ ] Coverage；
- [ ] Calibration；
- [ ] 未见场景；
- [ ] 未见 AP；
- [ ] 不同观测稀疏度；
- [ ] 不同 Bearing 误差。

### Phase 5 完成标准

G2 通过要求 Full predictor 在未见场景、未见 AP 和跨参数测试中稳定优于：

- AP Distance；
- Physics-Only；
- Source-Free；
- Point AP。

同时满足：

- AP belief 相比 No-AP 和 Point-AP 在 outage AUROC、校准或路径排序上有独立增益；
- 至少在一种外部测试域中不劣于最强简单基线；
- 端到端选路收益优于只看预测 RMSE 的替代方案；
- 结果包含多 seed 置信区间和失败案例。

若 AP belief 不能产生独立增益，则从论文标题和贡献中移除 AP 定位主张，保留更简单的 source-free forecaster。

---

# 9. Phase 6：完整 RadioFrontier

## 9.1 高层重排序

- [ ] 只在 Top-K 语义 frontier 中重排序；
- [ ] 加入 path outage；
- [ ] 加入 min/P5 signal；
- [ ] 加入 uncertainty；
- [ ] 加入最大绕路预算；
- [ ] 输出完整决策日志。

---

## 9.2 低层规划

第一版：

- [ ] 低层路径保持不变；
- [ ] 只研究高层 frontier 选择。

扩展版：

- [ ] Risk-aware A*；
- [ ] 对比普通 A*；
- [ ] 分离高层和低层贡献。

低层规划不属于第一篇论文的必做范围。只有 G3 已通过且不会影响主实验进度时才实现扩展版。

---

## 9.3 端到端方法

- [ ] Original OpenFrontier；
- [ ] Current CSI；
- [ ] Distance-to-Estimated-AP；
- [ ] Physics-Only；
- [ ] Ours w/o AP belief；
- [ ] Ours w/o uncertainty；
- [ ] Full RadioFrontier；
- [ ] Oracle AP；
- [ ] Oracle Radio Map。

### G3 验收标准

- Full RadioFrontier 在相同 Top-K 候选和路径预算下改善 SPL--Outage Pareto；
- Full 方法保留可观比例的 Oracle 收益，而不只是降低预测误差；
- 网络失败回放下 stale decision、SR 或 SPL 至少有一项得到稳定改善；
- 外部测试域结论与主仿真方向一致；
- 报告额外路径、推理时间、frontier 改变率和负收益 episode。

---

# 10. Phase 7：网络和视频 Demo

本阶段是应用验证，不承担论文主贡献。主实验使用固定 trace 或确定性 QoS 回放；真实云端 API 仅用于演示。

## 10.1 QoS 映射

建立：

$$
SNR
\rightarrow
Goodput
\rightarrow
Latency/Loss
\rightarrow
Video Quality
$$
- [ ] 固定码率模型；
- [ ] 自适应码率模型；
- [ ] Packet loss；
- [ ] RTT；
- [ ] Jitter；
- [ ] Frame deadline。

---

## 10.2 视频指标

- [ ] Effective FPS；
- [ ] Frame Drop；
- [ ] Freeze Ratio；
- [ ] Longest Freeze；
- [ ] P95 Latency；
- [ ] VMAF；
- [ ] SSIM。

---

## 10.3 云端 VLM 交互

每个高层决策步尝试请求：

- [ ] 根据 QoS 判断请求成功；
- [ ] 模拟上传时延；
- [ ] 模拟请求超时；
- [ ] 请求失败时继续旧目标；
- [ ] 统计 Stale Decision；
- [ ] 统计 Query Success。

---

## 10.4 Demo 画面

左侧：

- Original OpenFrontier 视频；
- 轨迹；
- 当前 SNR；
- FPS；
- 卡顿状态。

右侧：

- RadioFrontier 视频；
- AP belief；
- 候选路径风险；
- 当前 SNR；
- FPS；
- 选择原因。

底部：

- SPL；
- Outage；
- Longest Outage；
- Query Success；
- Effective FPS。

---

# 11. 论文实验表

## Table 1：Oracle 任务价值验证

| Method | SR ↑ | SPL ↑ | Extra Path ↓ | Outage ↓ | Longest Outage ↓ | Stale Decision ↓ |
|---|---:|---:|---:|---:|---:|---:|

## Table 2：路径通信预测

| Method | MAE ↓ | RMSE ↓ | Min Error ↓ | Outage F1 ↑ | NLL ↓ | Coverage |
|---|---:|---:|---:|---:|---:|---:|

## Table 3：端到端 ObjectNav

| Method | SR ↑ | SPL ↑ | Path ↓ | Outage ↓ | Longest Outage ↓ | QSR ↑ |
|---|---:|---:|---:|---:|---:|---:|

## Table S1：Bearing 和 AP 定位

| Method | Bearing Error ↓ | AP Error ↓ | Coverage@1m ↑ | NLL ↓ | Steps ↓ |
|---|---:|---:|---:|---:|---:|

## Table S2：视频传输

| Method | Effective FPS ↑ | Freeze ↓ | P95 Latency ↓ | Frame Drop ↓ | VMAF ↑ |
|---|---:|---:|---:|---:|---:|

---

# 12. 论文图

- [ ] System overview；
- [ ] Oracle SPL--Outage Pareto；
- [ ] Positive/negative frontier decision cases；
- [ ] CSI simulation pipeline；
- [ ] Circular vs linear AoA；
- [ ] AP belief convergence；
- [ ] Path-conditioned predictor；
- [ ] Frontier ranking example；
- [ ] Learned vs Oracle SPL--Outage Pareto；
- [ ] AP error over steps；
- [ ] Outage timeline；
- [ ] Video frame comparison；
- [ ] Real/demo system photograph。

---

# 13. 实验日志要求

每个 episode 保存：

```text
scene_id
episode_id
seed
target
start_pose
ap_pose
channel_params
candidate_frontiers
original_frontier_scores
candidate_paths
predicted_channel
oracle_channel
selected_frontier
executed_action
current_csi
bearing_profile
ap_belief
navigation_metrics
communication_metrics
video_metrics
```

所有实验必须支持：

- 固定随机种子；
- 断点续跑；
- 自动汇总；
- 配置文件保存；
- Git commit 记录；
- 输出 CSV 和 JSON。

---

# 14. 近期两周 Action

## Week 1：G0 与 Oracle 最小闭环

### Day 1：协议和指标冻结

- [ ] 建立仓库和版本化配置；
- [ ] 写出协作式 AP、双向 CSI 与部署可观测量；
- [ ] 定义 outage、网络失败闭环和额外路径预算；
- [ ] 固定 Top-K 语义候选与主指标。

### Day 2：OpenFrontier 复现

- [ ] 跑通官方 episode；
- [ ] 记录代码 commit、环境和基准配置；
- [ ] 输出候选 frontier、原始效用和最终选择；
- [ ] 验证 seed 可复现。

### Day 3：候选路径与日志

- [ ] 为每个 Top-K frontier 导出统一候选路径；
- [ ] 记录路径长度、局部几何和决策周期；
- [ ] 可视化候选路径及原始选择；
- [ ] 检查不同方法是否共享完全相同的候选集。

### Day 4：Oracle 重排序

- [ ] 实现最小无线真值和 Oracle 路径查询；
- [ ] 实现预算约束的 frontier 重排序；
- [ ] 跑 Original、Current CSI、Distance-to-AP 和 Oracle；
- [ ] 输出逐 episode 配对日志。

### Day 5：G1 初筛

- [ ] 扩展到足以观察趋势的 episode 集；
- [ ] 绘制 SPL--Outage 和 Path Length--Outage Pareto；
- [ ] 检查 frontier 改变率、正收益和负收益案例；
- [ ] 决定 G1 是继续、修订后复测还是停止。

### Week 1 交付物

- 一页系统假设与不支持范围；
- OpenFrontier frontier/path 日志；
- Oracle ranker 与可复现配置；
- 两张 Pareto 图；
- G1 决策记录和代表性 episode 可视化。

---

## Week 2：仅在 G1 通过后复现 CSI Bearing

### Day 1

- [ ] 下载并运行论文 MATLAB/官方仿真；
- [ ] 整理参数来源和坐标约定；
- [ ] 实现轨迹与基础复数 CSI。

### Day 2

- [ ] 实现 CFO、STO、WGN；
- [ ] 实现 reciprocal cancellation；
- [ ] 编写相位和可复现性单元测试。

### Day 3

- [ ] 实现 Bartlett 与 Top-K 峰值；
- [ ] 复现 circular 唯一峰；
- [ ] 复现 linear 镜像峰。

### Day 4

- [ ] 与参考输出对齐；
- [ ] 做不同 SNR、孔径和位姿误差实验；
- [ ] 记录自然 ObjectNav 轨迹的可观测性问题。

### Day 5

- [ ] 实现最小 AP belief；
- [ ] 测试 L 形和自然转弯轨迹；
- [ ] 设计 No-AP、Point-AP、Belief-AP 三组预测消融；
- [ ] 明确 G2 数据需求。

### Week 2 交付物

- `csi_paper.yaml` 与参数来源；
- CSI/Bartlett 单元测试；
- circular/linear 复现图；
- 最小 AP belief 可视化；
- G2 消融协议。

若 G1 未通过，Week 2 不进入 CSI 开发，改为修正候选集、路径预算或网络失败模型，并重新运行 Oracle 实验。

---

# 15. 首个里程碑

第一个必须完成的里程碑不包含 CSI 复现或 AP belief，而是：

```text
M1:
OpenFrontier 能输出多个 frontier 和候选路径；
系统假设、网络失败机制和额外路径预算已经冻结；
Original 与 Oracle 使用相同语义候选和路径；
Oracle 在固定预算下改善 SPL--Outage Pareto；
配对 episode 结果和案例分析支持该结论。
```

完成 M1 后，项目才进入 CSI Bearing 与 AP belief；完成 G2 后才进入神经路径预测器。

---

# 16. 每周例会汇报模板

```text
本周完成：
1.
2.
3.

当前结果：
- Gate 状态（G0/G1/G2/G3）:
- Oracle Outage Reduction:
- Path Length Change:
- Frontier Change Rate:
- Predictor Outage AUROC / Calibration:
- End-to-End Oracle Gap:

当前问题：
1.
2.

下周计划：
1.
2.
3.

是否影响总路线：
Yes / No

需要做出的决策：
1.
```

---

# 17. 当前立即执行顺序

```text
1. 冻结协作式 CSI 假设、失败机制、Top-K 和路径预算
2. 跑通 OpenFrontier，输出候选 frontier 和统一候选路径
3. 实现 Oracle 路径风险和预算约束重排序
4. 运行 G1：验证 SPL--Outage Pareto 与网络失败闭环
5. G1 通过后，复现 CSI、Bartlett 和 reciprocal cancellation
6. 实现 AP belief，并在自然轨迹/多径/位姿误差下验证
7. 生成无泄漏的数据集和外部测试域
8. 先完成强基线，再检查 AP belief 的独立增益（G2）
9. 训练最小 path-conditioned outage predictor
10. 运行端到端 Oracle-gap 实验（G3）
11. 完成跨场景、跨信道和外部域验证
12. 最后制作视频或真实云端 Demo
```

---

# 18. 当前不要做的事项

在 G1 完成之前，不要：

- 大规模实现 CSI、AP belief 或路径预测网络；
- 直接训练大型 Transformer；
- 直接做端到端强化学习；
- 预测整张无线热力图；
- 同时支持多 AP；
- 同时支持动态人群；
- 同时实现 BEV 和无 BEV；
- 先做复杂真实硬件集成；
- 让 VLM 自己计算所有无线数值；
- 花大量时间优化视频编码。

在 G3 完成之前，也不要实现低层 risk-aware A*。优先保证 Oracle 价值、预测增益和端到端收益三层闭环成立。
