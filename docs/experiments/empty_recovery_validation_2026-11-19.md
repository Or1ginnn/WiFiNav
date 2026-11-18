# BM4三次真实回归与凌晨验收

执行提交`9245a8b361d0f5ad0060ae68535aafb50f47943b`，spec `configs/benchmark/empty_recovery_validation_v1.json`；固定模型revision `59d61f3ce65a6d9863b86d2e96597125219dc754`，BF16/TP4/8K。原manifest SHA256 `8a0caf14400bd73939c97e976cdc5e97c34ce32eb2da35eee936c53a5dd1d326`，interface v1、STOP复核off、empty recovery on，原动作/决策预算不变。

批次`runtime/batches/empty_recovery_v1_20261119`，日志`runtime/logs/empty_recovery_v1_20261119.log`，启动flock进程2323871已结束。三个worker均同一9245a8b、源码hash匹配；运行期间未同步新HEAD。结束后才同步BM0代码64b3901，不混版本续跑，不覆盖原B3结果。

## 结果

| case | 退出 / SR | SPL | nDTW | 路径m | 动作 / 请求 | 断连秒 / 比例 / 最长秒 |
|---|---|---:|---:|---:|---|---|
| 515/start/λ0 | model_stop / 1 | 1.0000 | .754231 | 4.50 | 44 / 4 | 0 / 0 / 0 |
| 743/near/λ1 | model_stop / 1 | .194051 | .005041 | 30.75 | 286 / 30 | 65 / .318627 / 23 |
| 743/near/λ4 | consecutive_no_progress_limit / 0 | 0 | .00004746 | 44.50 | 460 / 44 | 92.5 / .289969 / 40 |

三次均无运行异常/timeout、碰撞动作0，完整终止轨迹均保留，没有错误前缀。模型决策数为4/29/43；运动时长30.5/204/319秒，wall time36.76/301.37/457.86秒；总请求78次（不含独立probe的3次），总动作790，总wall约796秒。成功与失败分开：515与λ1成功，λ4正常无进展失败；不对这三个异质诊断case作总体统计推断或AP独立性宣称。

## 工程验收与研究结论分开

**空候选退路的定点工程验收通过。** 743的λ1/λ4均在decision003实见候选[]、两次原解析失败后合法LOOK +45°，原错误响应/parse_error保留；没有把非法waypoint交给控制器。515成功保留。λ4最终无进展退出，说明退路不是无限旋转豁免，原进度/动作/决策预算仍生效；但本次只验证选定case，不能证明全部任务无退化。

**导航质量和通信收益没有因此通过验收。** λ1虽然SR=1，但30.75m路径与极低nDTW说明明显路线偏离，不能把“成功”解释为语言完全遵循；λ4失败且断连总时长更高，比例较低不能称收益。这是两条同源语言任务的工程诊断，不是新完整B3、随机评估或严格成对方法提升。原70次/90case B3 No-Go保持，不据此进入Online Belief或调AP/样本。

04:31复核模型health/models直连200、四卡仅本项目worker、没有导航重复进程。运行前服务器29测试和独立probe `runtime/manifests/service_probe_20261119_prevalidation.json`文本/单图/双图均真实通过；复用既有环境，未升级依赖或重启模型。

机器验收`engineering_acceptance.json`保存3份summary、worker commit、fallback及预算检查、源/产物hash；完整原始report/metadata/decisions/trajectory/request/response不变。BM0源字段CPU审计已在64b3901执行，见[BM0初审](bm0_task_audit_2026-11-19.md)。下一步按benchmark质量线推进任务资格/清单/评测合约，不把工程修复当G收益门通过。

机器验收JSON的SHA256为`18df5954c955bb2e3162daf342eff756b997ed578972c3e0c1da9bfcab90ea86`。检查所有worker同commit、源hash、两次fallback的原候选/parse_error、动作与决策上限均满足；不覆盖原report。
