# B3完整固定开发集协议 v1

2026-11-12，完整批次运行前冻结。配置`configs/benchmark/oracle_full_v1.json`，实现`run_oracle_pilot.py`及`evaluate_oracle.py`。此为工程Go/No-Go规则，不是统计显著性检验或保留评估集结果。

## 清单与执行

保持B2 manifest字节不变，SHA256 `8a0caf14400bd73939c97e976cdc5e97c34ce32eb2da35eee936c53a5dd1d326`。两个scene、10条原始任务：515、575、1074、1116、1802、85、97、127、743、818；每条start/near/far三个原布局，不依据成败替换。

λ={0,1,4}，同一0.25米单层navmesh栅格Dijkstra、同一离散动作检查，固定Qwen revision、v1接口/STOP复核off、1.5米局部目标、500底层动作等原预算。先执行全部10条λ=0，再按固定顺序执行两个非零λ的全部30个布局case。NoSignal轨迹在3布局回放，StaticMap必须真实闭环：**70次实际执行，90个case行**。布局不是独立语言任务，结果按任务/场景分层，不以90行计算独立样本显著性。

新目录`runtime/batches/oracle_full_action_guard_v1`，原B2与两版smoke不覆盖。每批保存spec/hash、源worker/planner/policy/signal文件hash、代码commit、模型revision、manifest；每case保存无线实例、状态、请求/响应、RGB-D、轨迹、规划路径/代价/动作校验和通信回放。禁止混版本续跑或只重跑失败样本。

## 共同执行器入口门

修复smoke先确认515的基线成功保留且没有运行异常。完整批次先完成所有10条NoSignal，不因失败跳过样本；若运行异常/超时/缺summary，或丢失`pilot_v1_no_review`中的任一原成功任务，保存入口门失败并停止StaticMap扩展，先诊断共同执行器。

此外，完整NoSignal平均SPL不得低于无复核基线的90%（0.272316×0.9），平均nDTW不得下降超过0.05（基线0.439153）。这是控制几何换栈退化的开发门，不将原navmesh与新grid的差异归因为通信。

## 收益门与参数规则

在全部NoSignal结果产生后，由其成功case构成固定配对子集，**包含其中零断连case**。该子集在查看StaticMap结果前确定，不按某个λ的成功或通信改善筛选。所有任务（包括失败）也必须单独汇总SR/SPL/nDTW、长度/动作/碰撞、弱信号、断连总时长/比例/最长断连及模型请求/实际耗时。

每个非零λ须同时满足：

1. 完整覆盖原30个case，无运行异常、超时或缺失；所有原NoSignal成功case继续成功。
2. 固定配对子集的平均SPL下降≤0.02，平均nDTW下降≤0.03。
3. 固定配对子集总路径增长≤20%。这是**验收预算**，当前规划器没有据此提前终止轨迹，不能把它称作已实现的硬路径约束。
4. 固定配对子集的断连总时长合计至少下降10%，最长连续断连时长的合计不增加。NoSignal合计断连为0时改善未定义，不判为无限收益。

有通过者时，选择固定子集断连总时长最小的λ，相同时选较小λ；没有通过者则记录No-Go，不扩大Online Belief。不因失败调任务/AP、缩短轨迹、改变分母或在本批中修改阈值。新成功任务与原成功任务的通信暴露分别解释，不能把原失败短轨迹与新成功长轨迹的比例差直接作为通信收益。

任何错误前缀、无summary、正常无进展退出均保留并分别计数。错误前缀仍报告已发生暴露/路径，缺失导航指标在全样本汇总中填0并标明；这些不完整case会阻止相应λ通过收益门。正常无进展是完整终止轨迹，但导航成功为0。

## 信息与物理边界

保持已知几何/理想位姿和单层限制，不补造楼梯支持；97等任务失败继续保留。完整信号场仅供StaticMap低层与评估，模型不见GT目标/参考路径/评估指标/AP。无线仍为简化传播代理，规划用latent静态真值，评估用可复现噪声测量。暴露按运动仿真时间，含转向，不含等待模型的网络故障；实际耗时另报，不声称真实WiFi吞吐或云服务可靠性改善。

```bash
cd ~/WiFiNav
/opt/anaconda3/envs/habitat0.3.0/bin/python -u scripts/run_oracle_pilot.py \
  --spec configs/benchmark/oracle_full_v1.json \
  --batch-dir runtime/batches/oracle_full_action_guard_v1
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/evaluate_oracle.py \
  --batch-dir runtime/batches/oracle_full_action_guard_v1
```

脚本以排他方式创建批次和验收文件，已有产物不可覆盖。正式执行commit、起止时间、完整结果及结论运行后登记。
