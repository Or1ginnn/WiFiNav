# WiFiNav benchmark v1.1 单层闭环验收

2026-11-28。v1.1 是正式任务清单的执行和评分版本。正式数据仍来自已经独立验收的 HM3D ObjectNav v2 `val`，共 36 个场景、74 层、961 条任务。清单 SHA256 为 `96a7946a41d5183873125d9defc13a2b7124355827ab59fb2f52e2b6f69c5383`。验收入口按清单的哈希检验场景产物、原始分片与场景资源。原始数据的定位与规则见[全量制作验收](objectnav_val_small_2026-11-26.md#2026-11-28-全量验收)。

## 执行与评分协议

| 项目 | v1.1 |
|---|---|
| 初始条件 | 官方任务分片的起点、朝向及类别。用场景和源行号匹配官方记录 |
| 动作预算 | 最多 200 个动作。前进 0.25 m，左右转各 30°，STOP 结束 |
| 单层条件 | 检查 Habitat 实际解析出的每个动作后位姿及其导航表面，高度落在起始楼层冻结的 ±0.28 m 带内。离开时立即终止，记录实际越界动作。评分保留越界前的轨迹前缀 |
| 成功 | 同层导航后发出 STOP，距离同层任意官方合法视点的可通行距离小于 0.10 m。提前 STOP、越层、步数耗尽均计失败 |
| SPL | 优先用经过楼层验证的最短参考距离。无法证实精确值时使用可验证区间。失败的上下界均为 0，成功且区间影响 SPL 时报告上下界 |
| 无线 | 两组轨迹都使用原多墙 RSSI 模型、1.875 cm 采样及原阈值评估已执行前缀。报告弱区累计距离、最长严重弱区、累计信号缺口和缺测。路径变短或失败前缀的低暴露须结合导航结果解释 |

SPL 的参考针对当前目标类别的所有同层官方视点。若 Habitat 到其最近视点的原始最短路线通过同层表面检查，使用该距离。其他任务中，原始最短距离提供下界，v1 已验证的同层见证路线提供上界。在行进距离固定时，SPL 随参考距离单调增加，因此该范围可直接映射成 SPL 区间。界限未重合的任务保留在正式集。原报告中的蓝线用于同终点的离线选路对照。

执行检查以 Habitat 实际消解碰撞和滑动后的位姿为准。首轮曾把两帧位姿连成直线，再用离线规划的线段核验，误判了一次同层贴墙滑动。实际位姿高度偏差仅 0.003 m，线段穿过墙角，离可通行面约 0.070 m。规划参考仍使用原线段核验。

### 通信达标成功率

通信达标成功要求在合法位置 STOP，并且实际执行轨迹上低于 −75 dBm 的最长连续路段小于或等于配置上限。使用已计算的 `longest_outage_m`，与导航 SR、SPL 并列。任务失败时联合判定为失败。导航成功但信号缺测时联合判定为未知，汇总保留该任务和未知计数，达标率留空。信号齐全时，以全部任务数为分母。

在 `run_objectnav_eval.py` 的闭环评测或 `score_objectnav_trace.py --navigation` 的离线信号评分中，可传入 `--max-continuous-severe-m` 计算该指标。闭环评测把实际长度上限和信号阈值写入 `metadata.json`。省略此参数适用于复现既有批次。讨论中的 1 m 为演示值，正式上限在开发集核验后冻结。

## 基线与信息边界

工程基线使用第一人称深度、当前画面中目标类别的语义掩膜、相对起点的位置与朝向。语义来自仿真真值，能力边界要随结果披露。机器人依据画面找目标，自行探索和 STOP。完整对象位置、评估视点、地图和 AP 位置留在评测端。这个基线使用 96 × 128 传感器和离散动作，其分数对应本协议。

两组使用同一基线和动作预算。NoSignal 的在线 RSSI 字段为空，ObservedRSSI 每步最多收到当前位姿所在冻结网格的一个模拟 RSSI，缺测原样保留。策略只在探索时使用以前到过的格点的观测。两组的事后通信评分使用同一多墙射线模型。没有模型请求或训练。Habitat 的图像渲染使用一张 GPU，射线与参考距离验收使用 CPU。

首轮语义接入暴露了两项工程问题。HM3D 的任务类别和物体的原始语义类别名字存在映射，例如盆栽包含 `decorative plant`。基线采用固定的类别名映射，给策略的仍只是当前画面的像素掩膜。HM3D 的语义 GLB 使用顶点颜色，在当前 Habitat 0.3.0 中启用默认的语义纹理模式会产生全零画面。禁用该模式后在同一官方起点测得 45 个不同的像素 ID。评测现在会对全场景都无有效语义帧的情况报错。早期试跑保留供追溯。[Habitat-Sim 0.3.0 的 HM3D 接入说明](https://github.com/facebookresearch/habitat-sim/blob/v0.3.0/DATASETS.md#loading-semantics-for-hm3d)

## 验收结果

正式代码执行提交 `dc882236915fbc38a2ba405e9bed644d0e5f9b07`，使用 Habitat-Sim 0.3.0，未调用模型。参考审计覆盖 36 个场景的 961 条任务，951 条最短参考距离可以直接证实，10 条需要保留区间。

| 实际 Habitat 轨迹 | 成功 | SPL | 结果 |
|---|---:|---:|---|
| `GLAQ4DNUx5U` 源行 0，同层到目标 STOP | 1 | 0.97493 | 92 个动作后的合法停车，路长 14.786 m |
| 同一任务起点即 STOP | 0 | 0 | 正确识别提前停车，路长 0 m |
| `bCPU9suPUw9` 源行 0，原 33 动作跨层序列 | 0 | 0 | 第 5 个动作被判出层，保留前 4 个合法动作。原评分在跨层 STOP 时曾给成功 1 和 SPL 0.271 |

原清单的 20 条审阅任务全部按两组真实执行，40 条均有事后通信评分。15 个场景、18 个场景楼层均来自既有固定样本。

| 20 条配对结果 | NoSignal | ObservedRSSI |
|---|---:|---:|
| 成功 | 1/20 | 2/20 |
| SPL | 0.03938 | 0.05652 |
| 平均行进（m） | 4.53 | 8.33 |
| 平均弱区累计距离（m） | 2.69 | 5.72 |
| 平均严重弱区累计距离（m） | 0.66 | 2.34 |
| 平均最长连续严重弱区（m） | 0.57 | 2.02 |
| 平均信号缺口（dB·m） | 21.73 | 62.21 |
| 步数耗尽、提前 STOP、出层 | 16、2、1 | 12、4、2 |
| 总动作、碰撞 | 3,337、172 | 3,061、293 |

10 对的动作序列不同。ObservedRSSI 有 2,535 次有效在线观测、526 次缺测。在唯一共同成功的任务 `HY1NcmCgn3n` 源行 25 上，两组轨迹一致，均走 9.60 m、经历 0.71 m 弱区。**评分修复与闭环入口通过工程验收。此次基线成功率较低，ObservedRSSI 的平均弱区暴露上升，小批没有证实通信收益。** 合适的下一个研究步骤是在开发集验收更稳定的 ObjectNav 基线，然后在固定评测集跑正式对照。

| 服务器证据 | 路径 |
|---|---|
| 当前参考距离审计 | `runtime/diagnostics/objectnav_v11_20261128_references_r3/` |
| 真实动作回归 | `runtime/diagnostics/objectnav_v11_20261128_regression_r3/` |
| 小批配对与失败轨迹 | `runtime/diagnostics/objectnav_v11_20261128_paired20_r3/` |
| 小批独立复跑 | `runtime/diagnostics/objectnav_v11_20261128_paired20_replay/` |

同一执行提交独立复跑 40 次，两批 `results.json` 和 `summary.json` 逐字节一致。配对输出的 SHA256 为 `878484bf7ba03fbda070b2b6386e2ebfa3e419175f345bd0f91fa9b3fd738926`，汇总为 `040d41727477db65bd2c117044f3400eed516710468cd2d9276ba551d5293799`。本机 75 项仓库测试通过。

## 复跑入口

进入项目根目录，准备已有的授权 HM3D v0.2 场景及官方任务包，使用已经构建和独立验收的 v1 清单。其他环境可以按[数据安装说明](../DATASETS.md#当前主线hm3d-objectnav-v2)和[构建与审计入口](objectnav_val_small_2026-11-26.md#放量状态)重建输入。Habitat 和 CPU 射线 Python 使用现有版本。非项目环境可通过 `--radio-python` 指定射线解释器，按所用安装设置 `DRJIT_LIBLLVM_PATH`。

```sh
habitat_python=/opt/anaconda3/envs/habitat0.3.0/bin/python
manifest=runtime/diagnostics/objectnav_val_full_20261128_v3_checkpoint/manifest.json
"$habitat_python" scripts/run_objectnav_eval.py --manifest "$manifest" \
  --audit-references --output runtime/diagnostics/objectnav_v11_my_references
"$habitat_python" scripts/run_objectnav_eval.py --manifest "$manifest" \
  --cross-floor-probe configs/benchmark/objectnav_v11_cross_floor_probe.json \
  --output runtime/diagnostics/objectnav_v11_my_regression
"$habitat_python" scripts/run_objectnav_eval.py --manifest "$manifest" \
  --population review20 --egl-device 0 --output runtime/diagnostics/objectnav_v11_my_paired20
```

参考距离验收预期覆盖 961 条，951 条精确、10 条区间。动作回归预期同层成功、起点 STOP 失败、历史跨层序列在第 5 个动作被拒。配对评测在清单的固定 20 条样本各执行两次，写入 `metadata.json`、`results.json`、`summary.json` 和分场景轨迹。换成 `--population all` 可覆盖 961 条。第三方 Python 策略通过 `--agent module:factory` 接入，工厂对象实现 `reset()` 和 `act(observation)`，观察字段见[基线接口](../../scripts/objectnav_sensor_baseline.py)。每次使用新输出目录，已经生成的失败记录及多组轨迹便于追溯。
