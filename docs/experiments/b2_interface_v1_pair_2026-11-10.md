# B2 v0/v1 导航接口配对复跑

2026-11-10 23:38（北京时间）开始。以[B2 v0](b2_pilot_2026-11-09.md)为原始对照，使用全部10条冻结任务。开发集结果用于判断接口改动与失败模式。

- 执行提交：`f6ff7b5`，接口实现：`947f786`。
- v0：`runtime/batches/pilot_20261109T154150Z`；v1：`runtime/batches/pilot_interface_v1`。
- 两份 manifest 字节一致，SHA256 为 `8a0caf14400bd73939c97e976cdc5e97c34ce32eb2da35eee936c53a5dd1d326`。
- 模型、两个场景、原始任务、导航预算和三种AP布局沿用原配置。v1仍为 NoSignal，AP回放不影响导航；该对照不检验通信选路收益。
- 所有冻结任务均保留；失败、解析异常和超时按原任务计入，不按结果补样。

```bash
cd ~/WiFiNav
/opt/anaconda3/envs/habitat0.3.0/bin/python -u scripts/run_pilot.py \
  --interface-version v1 --batch-dir runtime/batches/pilot_interface_v1
```

2026-11-11完成全部导航、30个AP回放和配对汇总。模型revision固定为 `59d61f3ce65a6d9863b86d2e96597125219dc754`。逐任务核对原任务hash、场景/轨迹标识、模型metadata与除interface_version外的settings一致；所有失败保留。接口改动包含解析、STOP和无进展三个方面，本次不能独立归因各组件，也不是多随机种子或保留集实验。

## 汇总

| 指标（全部10任务） | v0 | v1 |
|---|---:|---:|
| 成功任务 / SR | 3 / 30% | 3 / 30% |
| 平均SPL | 0.272316 | 0.221820 |
| 平均nDTW | 0.452765 | 0.406824 |
| 运行异常任务 | 1 | 0 |
| 平均路径长度（米） | 10.035 | 12.142 |
| 平均模型请求数（含重试/复核/恢复） | 9.1 | 14.8 |
| 平均任务实际耗时（秒，含启动） | 91.086 | 139.722 |
| 完整AP回放 / 错误前缀 | 27 / 3 | 30 / 0 |

v0的1074为解析失败前缀，nDTW和路径长度仍包含该前缀；因此跨版本均值不都是等长完整任务的比较。耗时是本次实测，不是固定吞吐保证。v1共15次STOP复核：confirm 2、reject 6、uncertain 7；不确定时仍允许原STOP。

## 逐任务

成功任务两版均为515、575、818。距离是仅供离线评估的目标测地距离，不输入模型或STOP复核。

| episode | v0→v1最终距离（米） | v0→v1 SPL | v1退出 | 观察 |
|---|---:|---:|---|---|
| 515 | 0.198→0.198 | 0.9193→0.9193 | model_stop | 路径不变，多一次uncertain复核 |
| 575 | 0.195→0.053 | 1.0000→0.4950 | model_stop | 两次reject后继续，路径7.245→14.724米；耗时71.7→193.1秒 |
| 1074 | 12.642→12.391 | 0→0 | model_stop | 解析中断消失；三次reject后最终uncertain，仍失败 |
| 1116 | 4.212→4.212 | 0→0 | model_stop | uncertain，错误停止仍在 |
| 1802 | 8.056→8.056 | 0→0 | model_stop | uncertain，错误停止仍在 |
| 85 | 8.972→8.972 | 0→0 | model_stop | uncertain，错误停止仍在 |
| 97 | 13.969→19.279 | 0→0 | model_stop | 一次reject后继续偏离，最终uncertain；楼梯支持仍不完整 |
| 127 | 3.477→3.477 | 0→0 | model_stop | uncertain，错误停止仍在 |
| 743 | 6.164→6.097 | 0→0 | consecutive_no_progress_limit | 新保护未使此任务成功 |
| 818 | 1.711→1.711 | 0.8039→0.8039 | model_stop | confirm，路径不变 |

575的两次拒停位置离线距离约2.942/2.977米，已满足3米成功半径，视觉复核却要求继续寻找房间/地毯。不能用最终更近来宣称整体改善：其SPL和nDTW明显下降。97同样说明“拒绝错误STOP”并不保证恢复路线正确。

## 通信回放与证据

v1全部30回放中25个出现断连、29个出现弱信号。v0完整27回放中22个断连/26个弱信号；若含错误前缀则为24/30与29/30。两版都不依据RSSI选路，轨迹和有效时长也有变化，不能由这些计数推断通信优化。AP回放不把10条导航样本扩成30条独立任务。

服务器项目根目录 `/mnt/data/suiqiuyi/WiFiNav` 下保存：

- `runtime/batches/pilot_interface_v1/{batch_metadata,progress,rollouts_complete}.json`：执行版本与完成状态。
- 同目录 `paired_comparison.json`：原始精度的逐任务/总体配对指标与一致性检查。
- 同目录 `pilot_report.json`、`pilot_overview.png`、`pilot_overview.pdf`：30回放及汇总图。
- 同目录 `episode_*/`：metadata、summary、decisions、完整请求/响应、trajectory及三个 `replay_*.jsonl`；每任务 `_status.json` 保留返回码和耗时。
- `runtime/logs/pilot_interface_v1.log`：批次运行日志。原v0目录保持不变。

```bash
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/replay_pilot.py \
  --batch-dir runtime/batches/pilot_interface_v1
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/plot_pilot.py \
  --batch-dir runtime/batches/pilot_interface_v1
```

回放脚本以排他方式新建文件；以上为本次已执行命令，已有回放目录不能直接重跑覆盖。本机忽略目录 `runtime/previews/b2_interface_v1_pair.json` 与 `b2_interface_v1_overview.png` 是核对副本。

## 判断与下一步

本轮完成工程配对验收，但未通过“导航质量提升”判断。解析修复有效；整套v1不能直接取代v0作为更优基线。下一次先将解析修复与STOP复核拆为独立开关，做不启用复核的固定清单消融，避免继续扩大复核成本。保存当前版本及批次，不在本批中调参或补样。随后冻结B3导航接口，接入同一规划器的λ=0与StaticMap对照；Oracle收益仍未验证，尚不进入Online Belief扩展。
