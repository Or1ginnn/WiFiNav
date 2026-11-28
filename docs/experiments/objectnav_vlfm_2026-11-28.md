# VLFM 接入 WiFiNav 开发评测

按用户确定的顺序，先用 Habitat-Sim 0.2.4 执行原版 VLFM 策略，再把仿真执行换为 0.3.0。两组都由 WiFiNav 的 v1.1 代码核对同层、STOP 和 SPL。开发输入使用已冻结的 HM3D ObjectNav v2 `train` 清单。上游论文在其自己的 HM3D 设定下报告结果，因此 WiFiNav 的方法对照以同一份 WiFiNav 清单和评分规则重跑为准。

## 版本和接口

- VLFM 官方策略固定在 `584ed56008754fde7997d904983607def8328322`，使用 `HabitatITMPolicyV2`、原有目标地图、视觉打分及预训练 PointNav。进程间只传目标类别、640 × 480 RGB-D 和相对起点的平面位姿。评测器保留官方视点、单层高度约束及地图，开发跑法关闭 RSSI。
- 0.2.4 与 0.3.0 分别用已有 Habitat-Sim 环境控制同一动作。VLFM 的 Python 策略使用独立的 0.2.4 进程，沿用服务器现有 Torch 2.6.0+cu124。感知服务只监听本机，使用原版 YOLOv7、BLIP2-ITM 和 MobileSAM。六个目标类别均在原版 YOLO 分支的 COCO 类别内。模型请求通过本机服务完成。
- 开发实验不修改已有 Conda 环境。额外 Python 包位于 `runtime/envs/vlfm_py39_compat` 和 `runtime/envs/vlfm_py39_pins`。模型在 `models/vlfm`，源码快照在 `runtime/vendor`。设置、权重 SHA-256 和各源码版本分别记录在 `runtime/diagnostics/vlfm_setup_20261128/environment.sh`、`weights.sha256` 和 `revisions.txt`。
- 测试包含真实 RGB-D 渲染、视觉模型请求、PointNav、轨迹与评分。首轮 0.2.4 在扫描后第一次调用 PointNav 遇到输入张量在 CPU、网络在 GPU 的错误，保留日志 `runtime/diagnostics/objectnav_vlfm_20261128_hab024_smoke.log`。在 `2ca8931` 修复深度和递归控制输入的设备摆放。

## 0.2.4 首场景结果

执行 `2ca8931`，只跑冻结输入清单首个场景 `g7hUFVNac26` 的四条任务。共 140 个真实动作、3 个碰撞标记。三条检测到了目标，但 STOP 未进入评分半径。一条在探索中越层。成功 0/4，SPL 为 0。四条都完成闭环和评分；结果说明代码与仿真已接通。

| 任务 | 源序号 | 终止 | 动作数 | 最后合法位姿到最近同层视点的测地距离 |
| --- | ---: | --- | ---: | ---: |
| 找床 | 34162 | 无效 STOP | 32 | 0.150 m |
| 找椅子 | 24971 | 无效 STOP | 31 | 2.140 m |
| 找沙发 | 552 | 越层 | 18 | 3.004 m |
| 找马桶 | 41773 | 无效 STOP | 59 | 0.153 m |

完整数据在服务器 `runtime/diagnostics/objectnav_vlfm_20261128_hab024_smoke_r2/`。配置计算出参考合法 STOP 半径为 0.10 m。上述末端测地距离是离线诊断，策略输入仅含 RGB-D、任务类别及相对位姿。

## 0.3.0 迁移回归

0.3.0 在完全相同的四条测试中给出相同的终止原因和成功判定。找椅子、找沙发、找马桶三条的动作和位姿序列相同。找床从 32 个动作变为 31 个动作，停车点相差约 0.744 m，两次均未达到合法视点半径。迁移结论是两套版本都能完成闭环和判分，实际路线以 0.3.0 的产物为准。

原正式 961 条任务清单 SHA-256 仍为 `96a7946a41d5183873125d9defc13a2b7124355827ab59fb2f52e2b6f69c5383`。0.3.0 的三项 CPU 判分探针与原 v1.1 的结果、摘要逐字节一致，复验文件位于服务器 `runtime/diagnostics/objectnav_vlfm_20261128_val_cpu_regression/`。

## 0.3.0 固定 20 条结果

五个场景全部完成，共 1,630 个动作。执行提交 `2ca8931`。在相同的 200 步、单层 STOP 协议下成功 6/20，SR 30%，SPL 0.16116。视觉模型在 15 条中报告至少一帧检测到目标类别。检测来自策略自己的掩膜，可能含误检。

| 场景 | 任务 | 成功 |
| --- | ---: | ---: |
| `g7hUFVNac26` | 4 | 0 |
| `j2EJhFEQGCL` | 4 | 0 |
| `DBBESbk4Y3k` | 4 | 3 |
| `vDfkYo5VqEQ` | 4 | 1 |
| `hWDDQnSDMXb` | 4 | 2 |

9 条无效 STOP，2 条越层，3 条动作预算耗尽。CPU 逐条重放了前两类共 11 条，实际位置和评分均与原闭环一致。5 条无效 STOP 距最近合法视点约 0.110–0.165 m，3 条仍有约 2.140–6.570 m。剩下的 `vDfkYo5VqEQ:975` 曾在第 161 步后到达合法位置，4 步后以 0.313 m 的偏差停车。九条沿最后方向额外执行一步的离线探针均未进入合法停车范围。

这是正式环境下可复跑的 VLFM NoSignal 开发结果，后续再验收独立场景。可以先用逐步观测诊断近距离停车和较远处提前停止，统一正式配对的传感器、动作和停车规则后再接入 RSSI。先用同一导航器建立有无 RSSI 的配对，论文公开 HM3D 分数用于上游背景参考。

## 产物与复跑

| 证据 | 服务器 `runtime/diagnostics/` 下的路径 |
| --- | --- |
| 0.2.4 首场景真实闭环 | `objectnav_vlfm_20261128_hab024_smoke_r2/` |
| 0.3.0 固定 20 条 NoSignal | `objectnav_vlfm_20261128_hab030_train20/` |
| 0.3.0 失败轨迹重放 | `objectnav_vlfm_20261128_hab030_failure_audit.json` |
| 环境、源码和模型清单、服务日志 | `vlfm_setup_20261128/` |

| 文件或内容 | SHA-256 |
| --- | --- |
| 冻结 `train` 清单 | `3f3034ece428556e27134aa16363b39da052e724a03b88d5757dae2219a3c7f0` |
| 清单中的构建配置 | `41412445378b2d80f271fcd0f62d98eec8b8ecf51c907a9dcde2e33e9b2936c8` |
| 实际使用的模型权重清单 | `a0a45fdb33b4ffbc982a8152934e97b47561c148e0fc2dbfa84b5e71dc8525a2` |
| 0.2.4 `results.json` | `cc2be1f9d0901f117c5e88a3e89cacca5fecdbaca914d6fd949fb26b481ce869` |
| 0.3.0 `results.json` | `b536964adefbf4dac249925f6b057d392204a9c1bd03b70b93f5c883dd5b072d` |
| 0.3.0 `summary.json` | `5ab30a8064742c072d23c407509cb6914f048d444efe0ce2a7d23a48c540d4c8` |
| 失败重放 | `f77c3fe77d91516c01872c20c45375dfcc150753e6d13096e4b587fe7bc52bb0` |

已有环境与资产就绪时，可用服务器上保留的启动脚本在新目录运行。它校验权重并启动这次使用的三个本地感知服务，退出时释放本次启动的进程。跑整批时省略 `--smoke`。启动脚本已通过 shell 语法检查，上述实际批次使用相同环境和服务命令。

```sh
bash runtime/diagnostics/vlfm_setup_20261128/replay.sh 0.2.4 \
  runtime/diagnostics/objectnav_vlfm_my_hab024 --smoke
bash runtime/diagnostics/vlfm_setup_20261128/replay.sh 0.3.0 \
  runtime/diagnostics/objectnav_vlfm_my_hab030
```

## 正式集 NoSignal 基线

原版 VLFM 单独运行全部 961 条 `val` 任务、36 个场景。固定原版检测、探索和 PointNav 权重、RGB-D 输入、200 个动作上限与同层 STOP 条件。结果报告导航 SR、SPL 区间、终止原因、路长和复算的弱信号暴露。通信达标长度上限另用开发集确定，正式基线保存逐轨迹 RSSI 分数供之后复算。

启动已核验的本地感知服务并设置兼容环境后，使用 Habitat 0.3.0 的共用评测入口执行。加 `--scene` 可以按正式清单中的一个完整场景独立落盘，并行批次最终按清单核验全部任务各执行一次。每次执行使用新目录，保存原始轨迹、合法前缀、RSSI 回放和配置。

```sh
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/run_objectnav_eval.py \
  --manifest runtime/diagnostics/objectnav_val_full_20261128_v3_checkpoint/manifest.json \
  --population all --track no_signal --agent objectnav_vlfm_baseline:VLFM \
  --egl-device 0 --output runtime/diagnostics/objectnav_vlfm_my_val961
```

2026-11-28 21:10（北京时间），冻结运行提交 `23b2c7bac2152f14fcc7d1c511d43ae2340d9dc2`，在 GPU 1、2、3 上各启动 12 个场景，分别为 321、320、320 条。RTX 4090 的 UUID 与各场景的分配保存在服务器 `runtime/diagnostics/objectnav_vlfm_20261128_val961/metadata.json`，SHA-256 为 `50e70a8b98daba7266f8e06e383c1d61bae8a16354cb49c2b807713530cb4270`。该文件同时记录冻结清单、配置、策略版本和权重收据。权重逐项校验通过。三组实际导航均收到本地 BLIP-2 与 YOLOv7 的 HTTP 200，MobileSAM 也收到真实分割请求。CPU 重放的三项原导航判分探针与 v1.1 结果逐字节一致，本机 84 项测试通过。

进度查 `gpu1.log` 至 `gpu3.log` 和各 `attempts/*.log`。完整场景进入 `scenes/`，失败尝试保存在 `attempts/`。批次保存启动脚本和汇总脚本。汇总逐场景核验执行提交、清单哈希、权重收据、任务唯一性及零在线 RSSI，再写 `results.json` 和 `summary.json`。`exit_code` 为 0 且场景结果齐全时确认完成。评测期间服务器工作区保持执行提交，文档提交在整批退出后同步到服务器。

### 论文结果与移植排查

22:18 已评分的 7 个场景共 196 条，其中 58 条成功，SR 29.6%，SPL 0.152。78 条停车未达标、43 条耗尽 200 步、17 条越层。78 条停车失败中，54 条距离最近同层官方视点为 0.10–0.25 m，3 条为 0.50–1.00 m，21 条在 1 m 或更远。距离为诊断用的 NavMesh 测地距离。

执行提交 `23b2c7b` 上，两个版本各在 CPU 重放相同的 196 条动作，196 条的实际位姿、终止原因、导航成功与各项得分都与原 0.3.0 结果一致，两份 JSON 逐字节相同。此结论覆盖固定动作的执行与评分。实时 RGB-D 进入模型后能否产生相同动作仍待更大样本验证。此前四条开发闭环中有一条的路线不同，两次都停车未达标。

| 设置 | 上游 VLFM 公开配置 | 当前 WiFiNav |
| --- | --- | --- |
| 任务 | HM3D ObjectNav `v1` 验证集，2,000 条 | HM3D ObjectNav `v2`，正式单层 961 条 |
| 动作预算 | 500 | 200 |
| 相机横向视野 | 79° | 90° |
| 深度归一化使用的米制区间 | 0.5–5 m | 0–10 m |
| 碰撞后允许贴墙滑动 | 关闭 | 两套当前接入均沿用 Habitat-Sim 默认开启 |
| STOP 评分 | 到官方有效视点测地距离小于 0.10 m | 同一 0.10 m 阈值，额外检查同层轨迹和视点 |

论文表 I 的 52.5% 对应上游任务。当前首批 196 条的差距不能据此分摊给任何一项配置。上游配置差异需要在开发集按控制变量做闭环验证。该批正式轨迹继续保留供当前协议的基线。 [论文](https://arxiv.org/html/2312.03275v1) · [VLFM 实验配置](https://github.com/rai-opensource/vlfm/blob/584ed56008754fde7997d904983607def8328322/config/experiments/vlfm_objectnav_hm3d.yaml) · [相机和步数配置](https://github.com/facebookresearch/habitat-lab/blob/v0.2.4/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml) · [评测配置](https://github.com/facebookresearch/habitat-lab/blob/v0.2.4/habitat-lab/habitat/config/habitat/task/objectnav.yaml)

服务器证据位于 `runtime/diagnostics/objectnav_vlfm_20261128_port_audit/`，每版输出记录 7 个原始 `results.json` 的哈希。两份回放 JSON 的 SHA-256 均为 `d1fd90866f7e49c0ec9de3c862fd215f86efeb786ed7b160dc8d59b0d0641c96`。复用 `replay.py` 时复制到同级的新目录后，通过各 Habitat Python 解释器运行，导入路径指向项目 `scripts/`。

### 暂停正式评测与对齐配置

北京时间 22:53 按用户要求停止 961 条正式评测。保留已评分的 10 个场景、280 条任务和被中断场景的日志，批次的 `user_pause.json` 记录停机时间和评分数量。launcher 的非零退出码对应本次手动停止。原批次仍对应 200 步、90° 和 0–10 m 的参数。

新增 `--vlfm-official` 配置，涵盖 640 × 480 RGB-D、79° 横向视野、0.88 m 相机高度、0.5–5 m 深度裁剪并归一化、关闭贴墙滑动、0.88 m 机身高度、0.18 m 半径设置和 500 步限制。配置从评分进程传至策略进程，元数据保存配置和 SHA-256。复用 WiFiNav 冻结的 v2 场景导航网格、单层规则和到有效视点的 0.10 m STOP 阈值。[配置文件](../../configs/benchmark/objectnav_vlfm_habitat024.json) · [上游设置](https://github.com/facebookresearch/habitat-lab/blob/v0.2.4/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml)

只在固定 `train` 首场景做工程验收，复用原来的模型和开发清单。以下入口启动旧环境中的本地感知服务并在 Habitat 0.3.0 执行四条开发轨迹。

```sh
bash runtime/diagnostics/vlfm_setup_20261128/replay.sh 0.3.0 \
  runtime/diagnostics/objectnav_vlfm_my_official_dev --vlfm-official --smoke
```

实际执行提交 `a6d09d0d04d72fc09f7d79b62cb7c1711c282ef4`，服务器目录 `runtime/diagnostics/objectnav_vlfm_20261128_official_dev4/`。清单仍为 `3f3034ece428556e27134aa16363b39da052e724a03b88d5757dae2219a3c7f0`，执行配置 SHA-256 `9f3923a1aaa5c50f8c35c2dce43d4f4caf79fdab36630140b5f2440eb728e9a1`，沿用相同策略版本和权重。结果 `cb8b0875356e4348609b829c151ba0969a30edef786f21128a9a403c9587e8e9`。

四条均闭环落盘，402 个真实动作，成功 0/4，两条无效 STOP、两条越层。找马桶执行到第 318 步后越层，确认能越过旧预算继续执行。相同任务旧配置也为 0/4；新旧相机、深度、碰撞及步数同时改变，小样本只能验证对齐后的链路。四条失败均通过同配置 CPU 重放。官方 YAML 参数核对、200/500 步边界、原三条判分探针逐字节复验和 86 项本机测试均通过。正式评测保持暂停。

### 官方推理入口核对

上游 `584ed56` 的 README 先通过 `scripts/launch_vlm_servers.sh` 启动本机感知服务，再用 `python -m vlfm.run` 做 Habitat 评测。若缺少兼容 Habitat Baselines 的空权重文件，入口提示先用 `python -m vlfm.utils.generate_dummy_policy` 生成。`vlfm/run.py` 加载实验配置，移除语义传感器，交给 `VLFMTrainer` 驱动 `HabitatITMPolicyV2`。训练器传入每步原生观测和任务状态，执行动作后由 Habitat 生成成功和 SPL。实际 PointNav 使用仓库的预训练权重，按策略估计到目标点的距离在 0.9 m 内下发 STOP。评测要求停车时距离任务的合法视点小于 0.10 m，两项距离的参照点不同。[README](https://github.com/rai-opensource/vlfm/blob/584ed56008754fde7997d904983607def8328322/README.md#L98-L108) · [官方入口](https://github.com/rai-opensource/vlfm/blob/584ed56008754fde7997d904983607def8328322/vlfm/run.py#L33-L50) · [PointNav](https://github.com/rai-opensource/vlfm/blob/584ed56008754fde7997d904983607def8328322/vlfm/policy/base_objectnav_policy.py#L223-L256)

服务器运行官方 `python -m vlfm.run --cfg job --resolve`，退出码 0，合成配置确认官方 RGB-D、碰撞、500 步、STOP 判分参数和 ObjectNav v1 `val` 路径。WiFiNav 同参数探针通过。另对 1,225 个合成平面位姿，用 0.2.4 原生 `EpisodicGPSSensor`、`EpisodicCompassSensor` 与 WiFiNav 转换对照，误差小于 `1e-6` m 和 `1e-6` rad。证据在 `runtime/diagnostics/objectnav_vlfm_20261128_upstream_entry_audit/`，官方配置输出 SHA-256 `328585d9b5c88aadbe3614cf94f5b67c967726209ea0cef3844562dffbe55098`。

上游 README 为 HM3D 场景指定 v0.2 资产，为任务指定 ObjectNav v1 episode 包。首次入口核对时服务器只装了 v2 任务，四条对齐配置的开发验收由 WiFiNav 的 Habitat 0.3.0 单层评测器驱动。原入口随后完成下节的 v1 小批。[上游数据清单](https://github.com/rai-opensource/vlfm/blob/584ed56008754fde7997d904983607def8328322/README.md#L66-L88)

### 原入口 v1 小批

官方 ObjectNav v1 包已独立安装。[安装记录](../DATASETS.md#vlfm-上游对照hm3d-objectnav-v1) 从 v1 `val` 的 20 个场景各选 1 条，从排序后的场景开始轮换可用类别，并在目标类别内按固定种子生成的 SHA-256 排序选定源行。20 条覆盖 6 类，分成 7、7、6 条三组并行。选样发生在模型启动前，冻结样本 SHA-256 为 `fae20569e8391f7283523fb4ee9fb39ac5003fc6c45452135dce728a14ff9996`。

通过 GitHub 校验 `vlfm/run.py` 和 `vlfm/utils/vlfm_trainer.py` 与服务器源码逐字节一致，直接用 `python -m vlfm.run` 和原配置启动。只覆盖本机任务、场景、权重和日志路径。相机 79°、深度 0.5–5 m、500 步、贴墙滑动关闭和官方成功判定保持默认。使用原推理权重和 VLFM 策略 `584ed56008754fde7997d904983607def8328322`，运行环境为 Habitat-Sim 0.2.4、Habitat-Lab `0.2.420230405`、Habitat Baselines 0.2.4、LAVIS 1.0.2 与项目已有的 Torch 2.6.0+cu124 兼容环境。

第一轮原生评测在 `Env.reset()` 读取目标包围盒时因旧的场景注释配置路径找不到对象。重试保留相同 20 条源任务，只将副本中的 `scene_dataset_config` 和 `scene_id` 一并映射到项目现有的 HM3D v0.2 资产。20 条的起点、navmesh 和目标对象索引均通过 CPU 预检。首轮错误日志保留在批次目录后缀 `.path_preflight` 下。

服务器 `runtime/diagnostics/objectnav_vlfm_20261128_upstream_v1_small/` 保存 `sample_manifest.json`、`prepare_sample.py`、`launch.sh`、逐组原生 `eval.log`、官方逐任务 `stats/`、动作日志和实际配置。WiFiNav 的 961 条正式任务继续暂停。

北京时间 23:44 三组全部退出码 0。**20 条成功 12 条，SR 60%，SPL 0.34750**，共执行 2,911 个动作。三个分组分别成功 5/7、5/7、2/6。原生日志记录失败原因为 5 条误检和 3 条未见目标且未穿越楼梯，后者由上游诊断标记为可能不可行。汇总核对每组的原生输出、单条分数和 20 个场景键。`config_parity.log` 验证配置仅有任务路径、场景根目录、PointNav 路径、TensorBoard 目录及视频目录五个配置字段与上游不同。汇总 SHA-256 为 `a5d63fe215317b94a7c10dcb8a6924c7bc1c8fc1dad00333d38896b87f42e4d2`。该小批用于核对运行与量级，论文的 52.5% 对应原 2,000 条验证任务。 [原论文](https://arxiv.org/html/2312.03275v1)

### v2 开发任务配对

2026-11-29，配对使用已经冻结的 5 个 `train` 场景、20 条任务。两条执行链均复用同一策略及权重、官方相机与 500 步配置。官方入口由 Habitat 0.2.4 原生环境驱动，保留原始动作和原生评分。WiFiNav 接入由 Habitat 0.3.0 单层规则驱动。为了比对原本的导航与停法，离线使用 WiFiNav v2 的目标视点、同层限制和 SPL 参考重放原版动作，比较首次分歧之前的动作并核对终止。正式 `val` 暂停，未参与该对照。

| 结果 | 成功 | SR | SPL |
| --- | ---: | ---: | ---: |
| 官方入口，Habitat 0.2.4 原生 | 6/20 | 30% | 0.12213 |
| 官方动作，Habitat 0.3.0 按 WiFiNav 单层规则复算 | 4/20 | 20% | 0.09850 |
| WiFiNav 接入，Habitat 0.3.0 单层 | 6/20 | 30% | 0.13695 |

共用口径下，3 条都成功、13 条都失败、1 条仅官方动作重放成功、3 条仅 WiFiNav 接入成功。15 条终止原因相同，3 条共用规则下的动作序列完全一致。有动作分歧的任务，第一次分歧出现在第 16–50 步。给 0.3.0 相同的动作前缀，位姿逐帧相同。原生到共同评分有三条从成功变为无效 STOP，一条从失败变为成功。这四条在两版重放中均未出层，差异不能简单归到同层判定。20 条接入实跑动作在 0.3.0 CPU 上完整复验，位姿和分数与原批次相同。

单步离线重放同一串动作后，0.2.4 与 0.3.0 的位姿并非普遍一致。关闭贴墙滑动时，20 条官方动作中有 13 条、20 条接入动作中有 11 条的最大偏移超过 0.10 m。只在 CPU 诊断中开启滑动后，仍分别有 10 条和 6 条超过 0.10 m。移动差异可出现在同样的动作输入下，实时闭环的其余差异仍需逐步核对 RGB-D 和策略输入。旧版两条任务的 v2 单层参考路径也无法通过相同的表面核验，其中一条的起始位姿也无法通过同层判定，因此旧版 CPU 重放只作移动诊断，主表统一使用 0.3.0 的评分协议。

执行提交 `5fccd32`。服务器 `runtime/diagnostics/objectnav_vlfm_20261129_v2_paired20/` 保存两组原生 stdout、官方动作日志、两组接入实跑轨迹及所有诊断。原生 `vlfm.run` 的生效配置仅覆盖本地路径，20 条动作经官方动作文件逐条核对。冻结 v2 开发清单 SHA-256 为 `3f3034ece428556e27134aa16363b39da052e724a03b88d5757dae2219a3c7f0`，官方对齐配置 SHA-256 为 `9f3923a1aaa5c50f8c35c2dce43d4f4caf79fdab36630140b5f2440eb728e9a1`，原策略 `584ed56008754fde7997d904983607def8328322`。汇总 `paired_summary.json` 的 SHA-256 为 `d9b195f00123f5b8b5194ae45814b84b6c0171538a4f38421a8ed83af4144f9e`。86 项本机测试通过。
