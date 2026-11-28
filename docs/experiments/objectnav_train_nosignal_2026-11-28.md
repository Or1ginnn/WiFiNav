# HM3D ObjectNav NoSignal 开发首轮

在冻结的官方 `train` 20 条任务（5 个场景、7 个楼层）上接通 NoSignal 闭环，区分搜索、接近和停车失败。以场景和源文件记录序号核对四组任务，清单完全一致。正式 `val` 清单和评分协议保持原版，本轮闭环使用 `train`。这批任务同时用于诊断和试改，结论限于该开发样本。

## 执行口径

- 使用 Habitat-Sim 0.3.0，复用 v1.1 的相机和动作协议。每条最多 200 个动作，前进 0.25 m，转向 30°。执行 STOP 时，到同层任一官方合法视点的可通行距离须小于 0.10 m 才计成功。离开起始楼层高度带时立即记失败。保留完整动作及其合法前缀。
- 策略用第一视角深度、当前画面内目标类别的模拟器语义和相对位姿。无 RSSI、模型请求或训练。语义来自模拟器标注，因此这是一条工程基线，目标识别效果仍需用公开可复现的视觉系统单独衡量。
- 「看到」指任一帧中至少有 10 个目标类别像素具备有效正深度，与策略的目标像素数量门槛一致。p25 表示这些像素深度的第 25 百分位，可用于分析目标靠近过程。执行前进但水平位移不足 0.025 m 计一次无有效前进。
- `g7hUFVNac26` 源记录 552 的旧几何最短线未满足严格同层检查。复核时保持官方起点、朝向与类别，从旧归档取独立几何参考并验收其同层通行和合法终点，为该条 SPL 参考给出 3.72473–5.22514 m 的上下界。旧归档文件名含 RSSI，读取的 `baseline_route_xyz` 是几何路线，仅供评分。该条四次均失败，汇总 SPL 两界相同。

## 实际结果

| 20 条任务 | 原规则 | 加卡住恢复 | 再提前尝试 STOP |
| --- | ---: | ---: | ---: |
| 成功 | 1 | 3 | 5 |
| SR | 5% | 15% | 25% |
| SPL | 0.02984 | 0.05837 | 0.14151 |
| 至少有一条成功的场景 | 1 | 2 | 3 |
| 看到目标 | 7 | 13 | 13 |
| 看到但未成功 | 6 | 10 | 8 |
| 从未看到目标 | 13 | 7 | 7 |
| 动作用尽 | 17 | 10 | 5 |
| 无效 STOP | 1 | 3 | 6 |
| 越层终止 | 1 | 4 | 4 |
| 无有效前进次数 | 394 | 29 | 16 |
| 总前进动作 | 1,073 | 1,685 | 1,024 |
| 总动作 | 3,451 | 2,819 | 1,939 |
| 碰撞标记数 | 870 | 850 | 245 |
| 平均合法轨迹长度（m） | 4.12 | 14.64 | 11.87 |

动作、碰撞和路长均含失败轨迹。越层和无效 STOP 会提前结束任务，同时查看这些开销与终止原因。

1. 原规则在 `g7hUFVNac26:34162` 与 `hWDDQnSDMXb:46717` 上耗尽预算且未发出前进动作。`vDfkYo5VqEQ:9582`、`vDfkYo5VqEQ:975` 分别发出 195、185 次无有效前进动作。
2. 加入卡住恢复后，连续 8 次无位移或一次前进失败会切换策略，换到由当前深度图判为可前进的方向，恢复最多连续 4 次成功前进后回到原规则。原成功保留，新增 `hWDDQnSDMXb:46717` 和 `vDfkYo5VqEQ:9582` 两条成功。越层由 1 条增加到 4 条。
3. 卡住恢复版中，`DBBESbk4Y3k:20747`、`vDfkYo5VqEQ:17770` 和 `vDfkYo5VqEQ:975` 分别曾有 6、5、6 帧同时达到合法停车范围并看到目标，最终均失败。合法范围是离线评分器核验结果，闭环策略只使用当前观测。
4. 将策略的 p25 STOP 触发设为 0.75 m，较原 0.50 m 提前一小步，沿用同一成功判定。保留前两版成功，新增 `DBBESbk4Y3k:20747` 和 `vDfkYo5VqEQ:17770` 两条。无效 STOP 同时由 3 条增至 6 条。

正式基线暂未冻结。下一步逐帧核对这 4 条越层和 6 条无效停车，单独验证有明确观测依据的改动，并在独立 `train` 场景复测。正式 RSSI 配对需要等待基线冻结。

## 版本与复跑

| 运行 | 执行提交 | 服务器 `runtime/diagnostics/` 下的目录 |
| --- | --- | --- |
| 原规则 | `6a2f17a` | `objectnav_train_dev_20261128_initial` |
| 卡住恢复 | `6c514f1` | `objectnav_train_dev_20261128_progress` |
| 提前 STOP | `86149ad` | `objectnav_train_dev_20261128_earlier_stop` |
| 提前 STOP 独立复跑 | `86149ad` | `objectnav_train_dev_20261128_earlier_replay` |

各目录有 `metadata.json`、`results.json`、`summary.json` 及五个场景逐条完整轨迹。两个提前 STOP 批次的 `results.json` 和 `summary.json` 均逐字节一致。共 80 次真实闭环。最新代码 78 项本机测试通过。正式同层成功、提前 STOP、越层拒绝的三个 CPU 回归产物与原 v1.1 逐字节一致，正式 961 条清单 SHA-256 仍为 `96a7946a41d5183873125d9defc13a2b7124355827ab59fb2f52e2b6f69c5383`。

| 输入或结果 | SHA-256 |
| --- | --- |
| `runtime/diagnostics/objectnav_train_ap_review_20261124/manifest.json` | `3f3034ece428556e27134aa16363b39da052e724a03b88d5757dae2219a3c7f0` |
| 冻结清单内记录的构建配置 | `41412445378b2d80f271fcd0f62d98eec8b8ecf51c907a9dcde2e33e9b2936c8` |
| `runtime/diagnostics/objectnav_rssi_graph_20261125_v7/g7hUFVNac26.rssi_reference.json` | `7f25f2331e46d00338e857b14150fba8b0c791b4ea6120238e94abdbe8b462ef` |
| 提前 STOP 两批 `results.json` | `d82a295f33f93fcf4d119755089e24b29b7a3f48d722333aaa1315e849790d85` |
| 提前 STOP 两批 `summary.json` | `50bef12bd8fc07163f06a8e603a6793101e0f971ab1ce4627480dd6084f07a79` |

在服务器项目根目录以独立输出目录复跑。第一条命令用默认策略。两条命令使用的动作限制、清单和 v1.1 成功判定相同。

```sh
habitat_python=/opt/anaconda3/envs/habitat0.3.0/bin/python
train_manifest=runtime/diagnostics/objectnav_train_ap_review_20261124/manifest.json
export MAGNUM_LOG=quiet HABITAT_SIM_LOG=quiet OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
"$habitat_python" scripts/run_objectnav_dev.py --manifest "$train_manifest" \
  --output runtime/diagnostics/objectnav_train_repro_initial
"$habitat_python" scripts/run_objectnav_dev.py --manifest "$train_manifest" \
  --agent objectnav_progress_baseline:EarlierStopBaseline \
  --output runtime/diagnostics/objectnav_train_repro_earlier_stop
```
