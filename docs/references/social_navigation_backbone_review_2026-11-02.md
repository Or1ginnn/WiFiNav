# Social Navigation 基座与规划接口调研

检索日期：2026-11-02。范围：与本项目有关的 VLM/LLM 社会导航、行为约束导航及近期导航基础模型代表工作。依据原论文和作者仓库进行非穷尽比较；没有安装、运行或复现这些系统。论文中的模型名称是原实验配置，不表示当前服务接口已经验证可用。

## 主要发现

“基座”需要拆成视觉语言模型、导航系统、规划/控制器三个层次。给出一个通用 VLM 名称，并不能确定它如何读懂长程指令、定位子目标、维护任务进度或避障。

代表工作中存在多种路线：冻结通用 VLM 后输出行为偏好/参考路径/代价图；针对社会情境微调或蒸馏模型；训练 VLM 加动作专家直接生成轨迹。这些路线并存。本调研不能用于断言整个领域哪条路线占比最高。

## 代表方法比较

| 方法 | 原方法的模型/感知 | 模型输出与规划接口 | 训练情况 | 第一手来源 |
|---|---|---|---|---|
| VLM-Social-Nav（2024） | GPT-4V + YOLO；LiDAR 几何感知 | 推理方向/速度偏好，转换成候选动作的 social cost，与目标和障碍代价共同进入 DWA；社会线索触发查询 | 不为社会导航专门微调该 VLM | [论文方法与实现](https://arxiv.org/html/2404.00210v2) |
| CoNVOI（2024） | CLIP 做情境检测，GPT-4V / Gemini 生成参考路径 | 选择图像上的编号点，投影成参考路径，再由修改后的 DWA 跟随；情境未变化时外推路径，减少查询 | 无领域专用微调 | [论文](https://arxiv.org/html/2403.15637v1) |
| BehAV（ICRA 2025） | LLM 拆分指令、CLIPSeg 分割行为目标，GPT-4o 视觉定位地标 | 将行为规则转为 costmap，与 LiDAR 占据图结合，MPC 优化目标、避障和行为代价 | 使用预训练模型进行 zero-shot 场景理解，增加规则/代价和规划逻辑 | [论文](https://arxiv.org/html/2409.16484v2)、[作者代码](https://github.com/GAMMA-UMD-Outdoor-Navigation/BehAV) |
| LISN / Social-Nav-Modulator（2025 预印本） | GPT-4o；Grounded-SAM2、RoboPoint | 慢循环 VLM 调整动态社会 costmap 和控制器参数；快循环使用 Social Force Model 控制 | 复用模型，论文重点是工具调用和控制器调制 | [论文](https://arxiv.org/html/2512.09920v1)、[作者代码](https://github.com/Social-Nav/tvss_nav) |
| G2-Nav（2026） | 论文记录回放使用 Qwen3.5-2B，交互实物使用 GPT5.4-Nano；开放词汇感知 | VLM 给通行区域和社会实体打分，形成 BEV costmap；梯度下降生成轨迹，Pure Pursuit 跟踪，另有高频反射检查 | 使用预训练 VLM，另需标定代价权重 | [论文 §3–4](https://arxiv.org/html/2607.16956v1)、[作者代码](https://github.com/centiLinda/G2-Nav) |
| Social-LLaVA（2025） | LLaVA-v1.5-7B | 输出社会场景解释、推理及高层行动建议；重点包含社会理解数据和 VQA，不能等同于完整长程 VLN 系统 | 使用 SNEI 的约 40K VQA 进行 LoRA 微调 | [论文 §IV](https://arxiv.org/html/2501.09024v1) |
| OLiVia-Nav | 大 VLM 的语义能力蒸馏至 SC-CLIP；轨迹生成与选择网络 | 社会语境编码 → 多轨迹预测 → 轨迹选择 → 导航控制 | 包含蒸馏、轨迹模块训练及 lifelong 更新，不是整个系统免训练 | [作者论文](https://llhomerobots.github.io/docs/corl_llhomerobots_2024-cr_paper_14.pdf) |
| SocialNav（CVPR 2026） | 作者发布 Qwen2-VL / Qwen2.5-VL SAFE-GRPO checkpoints | VLM Brain + flow-based Action Expert，生成社会导航轨迹 | 有专门数据训练和后训练；直接使用现成 checkpoint 可省去本项目再训练，但原系统属于学习路线 | [作者仓库](https://github.com/AMAP-EAI/SocialNav) |

## 为什么会采用低频模型推理与高频规划

VLM-Social-Nav 把模型输出变成动作代价，并通过检测事件减少调用；CoNVOI 使用路径外推；LISN 明确区分慢速推理和快速控制。这些设计说明：语言/视觉推理的更新频率可以与运动控制分开设置。

不能把“不微调 VLM”理解为系统没有其他模型、标定、地图模块或计算负担。开放词汇分割、目标定位、仿真渲染、历史观测处理及本地模型推理仍需要资源。

## 作者代码的实际入口与限制

以下为网页和目录说明核查，尚未运行：

- **BehAV：** 作者仓库提供 instruction decomposition、landmark tracking、planning 目录，说明采用 ROS2 Galactic/PyTorch；适合阅读行为代价到 MPC 的连接方式，不是 Habitat R2R-CE 的现成评测系统。[仓库](https://github.com/GAMMA-UMD-Outdoor-Navigation/BehAV)
- **LISN：** 作者发布 `tvss_nav`，包含 costmap 插件、控制器和视觉语义管线；README 使用 ROS Noetic，并提供 Arena/Gazebo 环境相关 Docker 说明。它的 benchmark 和当前项目拟用的 Habitat/VLN-CE 不同。[仓库](https://github.com/Social-Nav/tvss_nav)
- **G2-Nav：** 作者仓库 README 给出 ROS1 Noetic、SCAND rosbag 回放入口 `run_scand.launch`、本地 vLLM 调用和 `/costmap_safe_viz`、`/plan_path` 输出。可作为 costmap 接口的具体参考，尚不能当成可直接运行的 VLN 基线。[仓库](https://github.com/centiLinda/G2-Nav)
- **SocialNav：** 官方发布模型实现和 checkpoint，列出训练与评估入口；训练集未计划公开。仓库声明 Qwen2-VL/Qwen2.5-VL 是复现已报结果的路径，Qwen3-VL 实现仅供参考，不能从“仓库有某模型代码”推断其结果已验证。[仓库](https://github.com/AMAP-EAI/SocialNav)

## 对本项目的推论与建议（尚未冻结选型）

1. 当前“RSSI belief → 连通代价 → 导航规划”与 BehAV/LISN/G2-Nav 的代价接口方向相容。这是方法接口的借鉴，不是证明这些系统已经满足 VLN 指令跟随要求。
2. 第一版优先采用冻结 VLM 加模块化规划的路线，符合用户确认的 zero-shot 约束。VLM 解释指令/给出导航子目标，RSSI 模块根据实际测量建立 belief，规划器组合几何、任务与连通代价。不要让 VLM 凭图像编造未观测的 RSSI。
3. 需要选择并验证支持目标 benchmark 的完整导航系统，检查其路径/子目标和规划接口，再决定模型服务后端。此前建议 Qwen3-VL-8B 只是模型候选，未构成经过验证的 VLN 方案。
4. 先以导航系统的原始模型配置跑通 NoSignal，再固定相同模型、提示和预算比较通信模块。更换较小开源模型应作为独立迁移/消融，不能同时替换模型和通信机制后归因效果。
5. “不做新增通信任务训练”和“原导航模型从未接受导航训练”是不同声明。若用经过社会导航训练的 checkpoint，必须披露其训练背景和评测划分。

## M0 选型必须交付的结果

| 选择项 | 最低证据 |
|---|---|
| VLN 任务与环境 | 确认 R2R-CE/RxR-CE 等目标任务和仿真版本；SocialNav 的 PointGoal/社会理解结果不能代替 VLN 结果 |
| 导航系统 | 指令、历史、子目标、终止判断及规划接口有代码可追踪 |
| 模型服务 | 固定模型 ID/版本、输入图像形式、结构化输出和超时处理；实测延迟与显存/API 开销 |
| 规划接入 | 一条可运行调用链表明连通代价能影响路径，同时保留避障和执行逻辑 |
| 冻结对照 | 同一 NoSignal 基线可复现，再接 Reactive/StaticMap/Online Belief |

本轮完成的是路线和公开实现调研，未完成最终选型或运行验证。
