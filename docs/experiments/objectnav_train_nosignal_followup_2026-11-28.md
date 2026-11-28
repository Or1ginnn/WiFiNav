# HM3D ObjectNav NoSignal 失败复核与独立场景验证

在 [NoSignal 首轮](objectnav_train_nosignal_2026-11-28.md) 的同一份 `train` 清单上，重放提前停车版的 4 条越层和 6 条无效 STOP。CPU Habitat 重放的动作位姿及 v1.1 评分逐条与原结果相同。以下合法视点、楼层锚点和 NavMesh 查询均用于离线核实。

## 判分与失败原因

| 场景和源序号 | 首次越层动作 | 起始、越界前、越界后高度（相对起始层锚点，m） | 具体证据 |
| --- | ---: | --- | --- |
| `g7hUFVNac26:552` | 186 | 0.000、0.267、0.328 | 三次前进连续升高约 0.056–0.061 m |
| `j2EJhFEQGCL:44665` | 96 | −0.003、0.254、0.282 | 四次前进连续升高约 0.028–0.036 m |
| `vDfkYo5VqEQ:25302` | 100 | 0.002、0.215、0.368 | 两次前进分别升高约 0.160、0.153 m。最后实际位姿比 NavMesh 最近投影高 0.193 m，说明需区分执行位姿与投影 |
| `hWDDQnSDMXb:44719` | 2 | 0.191、0.278、0.283 | 初始位姿已接近高度边界，首步升高 0.087 m，第二步只再升高约 0.005 m 就越界 |

四条在前进时实际越过冻结的 ±0.28 m 高度带，越界前未看到目标。三个场景的越界位姿与最近 NavMesh 投影等高，一条的实际位置与投影高度不同。记录检验的是评分协议中的实际位姿，场景的楼梯、坡道或局部高差仍须按实际几何区分。

| 场景和源序号 | 停车时画面目标深度 p25（m） | 到最近同层视点的可通行距离（m） | 多走一步后能否合法停车 |
| --- | ---: | ---: | --- |
| `g7hUFVNac26:34162` | 0.717 | 0.194 | 否 |
| `g7hUFVNac26:24971` | 0.692 | 0.177 | 否 |
| `g7hUFVNac26:41773` | 0.533 | 0.186 | 否 |
| `j2EJhFEQGCL:17524` | 0.687 | 0.142 | 否 |
| `j2EJhFEQGCL:25497` | 0.718 | 0.279 | 否 |
| `vDfkYo5VqEQ:975` | 0.729 | 0.267 | 是，距视点 0.097 m |

六条停车时都在同层高度带内，连到最近视点的直线距离也都超过 0.10 m。失败停车的目标深度范围与成功任务重叠。五条在各自已执行的轨迹上从未进入合法 STOP 范围，有五条与最近视点的高度差约为 0.10–0.17 m。`vDfkYo5VqEQ:975` 曾在第 79 步后到达合法停车位姿，实际在第 83 个动作发出 STOP。额外走一步是在原动作重放结尾的离线探针。这些证据支持单独改进目标附近的导航。实验沿用 0.75 m 停车触发。

## 换向候选与固定样本

候选策略用前后两帧的相对高度变化判断上升和下降，每次前进绝对高差达 0.025 m 就在当前位置记下该朝向，并沿用卡住恢复的换向决策。两组在开发入口都获得同一相对高度观测，只有候选使用。仿真提供精确的相对位姿，实际里程计噪声尚未验证。策略继续使用当前画面中的语义标签和深度。正式 v1.1 入口沿用原观测口径和评分器。

独立批按既有种子排序，排除原五个 `train` 场景，按同层几何资格纳入另外 5 场景、20 条官方任务。清单先于运行冻结。固定表面查验通过的参考线作为各任务评分证据。选入 `XiJhRLvpKpX`、`u5atqC7vRCY`、`5biL7VEkByM`、`NEVASPhcrxR`、`wPLokgvCnuk`，涉及 7 个楼层，与原开发集及正式 `val` 场景互斥。

独立批首跑加载 `XiJhRLvpKpX:40389` 时暴露工程映射缺口。官方 `bed` 包括该场景唯一的 `massage bed`。按同一份官方目标类别和 HM3D 场景标签对照，开发词表新增 `massage bed`、`beanbag`、`double armchair`、`spa armchair` 与 `grass`。统一词表用于两组。清单、任务与评分均沿用冻结版。首跑日志保留。

## 配对结果和结论

| 指标 | 原 20 条对照 | 原 20 条换向 | 独立 20 条对照 | 独立 20 条换向 |
| --- | ---: | ---: | ---: | ---: |
| 成功 | 5 | 6 | 3 | 1 |
| SPL | 0.14151 | 0.17602 | 0.06061 | 0.02232 |
| 看到目标 | 13 | 14 | 12 | 8 |
| 动作用尽 | 5 | 6 | 14 | 10 |
| 越层 | 4 | 2 | 2 | 6 |
| 无效 STOP | 6 | 6 | 1 | 3 |
| 动作 | 1,939 | 2,199 | 3,202 | 2,631 |
| 碰撞标记 | 245 | 323 | 633 | 400 |
| 平均合法轨迹长度（m） | 11.87 | 13.38 | 16.56 | 13.89 |

原样本保留了五条对照成功，额外救回 `hWDDQnSDMXb:44719`。还有一条原来无效停车的任务换向后越层。独立样本丢掉 `NEVASPhcrxR:424`、`wPLokgvCnuk:42842` 两条原成功，没有新成功。独立批少走、少碰撞伴随更多任务提前因越层或无效 STOP 退出。

独立样本两组的 12 条越层和无效 STOP 用 CPU 逐条重放，位置、评分与原结果相同。候选中有两条从高度带内约 0.15 m 在一次前进后就越界，动作后的高差检测已来不及阻止。另有四条在越界前刚刚换向，沿新朝向前进一步仍超过了高度范围。动作后测高差再转向无法稳定守住单层范围。

**换向候选未通过独立复验。** 保留为诊断对照，并保留原提前停车版作为工程对照。导航基线尚未冻结。接下来优先研究能在前进前估计地面高差的局部观测，以及能在目标周围搜索可达位置的停靠策略，分别用开发数据验证。独立样本作为失败证据保留。下一版要验证泛化时，应冻结新的互斥场景。

## 复跑与产物

输出统一位于服务器 `runtime/diagnostics/`。目录前缀为 `objectnav_train_dev_followup_20261128`。

| 后缀 | 内容 | 执行提交 |
| --- | --- | --- |
| `_failures.json` | 十条失败的原位姿重放、高度和停车证据 | `b11660c` |
| `_disjoint/` | 另一批 20 条任务清单和同层几何 | `b11660c` |
| `_original_control/`、`_original_guard/` | 原样本第一组完整闭环结果 | `deaff85` |
| `_disjoint_control.log` | 独立批首跑类别映射加载错误 | `deaff85` |
| `_val_probe/` | 同层成功、提前停车、越层拒绝的 CPU 探针，结果与 v1.1 逐字节一致 | `deaff85` |
| `_original_{control,guard}_r2/`、`_disjoint_{control,guard}_r2/` | 统一语义词表后的开发对照，保留完整轨迹 | `860a163` |
| `_disjoint_{control,guard}_failures.json` | 独立批越层和无效 STOP 的原位姿重放 | `860a163` |
| `_val_probe_r2/` | 最新版本重新执行的三项 CPU 判分回归，结果和摘要与原 v1.1 逐字节一致 | `860a163` |

最终配对共 80 条真实闭环轨迹，模型请求为 0。修补词表前后原样本两组的结果分别逐字节一致。两个开发清单均有 20 条唯一任务键，配对两组各自一致。80 项本机测试通过。

| 证据 | SHA-256 |
| --- | --- |
| 原样本清单 | `3f3034ece428556e27134aa16363b39da052e724a03b88d5757dae2219a3c7f0` |
| 独立样本清单 | `f7852a2e67943896eef8ea1ec1b8984acd916fb205d1ddf191f15b6cbcea5a9b` |
| 构建配置 `configs/benchmark/objectnav_train_ap_review_v1.json` | `41412445378b2d80f271fcd0f62d98eec8b8ecf51c907a9dcde2e33e9b2936c8` |
| 十条失败复核 | `6e3cec58fca75d0d7146cb22985910102791750384b6a87b79962d99f1a62f35` |
| 独立批对照组 `results.json` | `ba4d15220b113ff2f1f196aba529df1ba0d5c41b2a27e977d247bda493887557` |
| 独立批换向组 `results.json` | `c5b96195de2667583e1e6e2bef0431b36d562269f5a951941290525bdfb8545c` |
| 正式 961 条 `val` 清单 | `96a7946a41d5183873125d9defc13a2b7124355827ab59fb2f52e2b6f69c5383` |

在服务器项目根目录复跑下列命令，输出使用新目录。将策略名换成 `LevelRecoveryBaseline` 即可复跑换向组。原样本可将 `--manifest` 改为 `$train` 并省略 `--manifest-sha256`。

```sh
habitat_python=/opt/anaconda3/envs/habitat0.3.0/bin/python
train=runtime/diagnostics/objectnav_train_ap_review_20261124/manifest.json
prefix=runtime/diagnostics/objectnav_train_dev_followup_20261128
manifest="${prefix}_disjoint/manifest.json"
export MAGNUM_LOG=quiet HABITAT_SIM_LOG=quiet OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
"$habitat_python" scripts/audit_objectnav_dev_failures.py --manifest "$train" \
  --run runtime/diagnostics/objectnav_train_dev_20261128_earlier_stop \
  --output "${prefix}_repro_failures.json"
"$habitat_python" scripts/run_objectnav_dev.py --manifest "$manifest" \
  --manifest-sha256 f7852a2e67943896eef8ea1ec1b8984acd916fb205d1ddf191f15b6cbcea5a9b \
  --agent objectnav_progress_baseline:EarlierStopBaseline \
  --output "${prefix}_repro_disjoint_control"
```
