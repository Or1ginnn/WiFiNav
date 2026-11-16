# 空候选退路与候选路径诊断（独立修订）

## 证据与边界

原完整B3代码976bd10，批次`runtime/batches/oracle_full_action_guard_v1`、manifest SHA256 `8a0caf14400bd73939c97e976cdc5e97c34ce32eb2da35eee936c53a5dd1d326`，保留70次执行/90case及全部失败。

743/near在λ=1/4的`decision_003/candidates.json`均为`[]`；两次输出仍选择candidate_id=4、3。严格验证两次均拒绝，原始request/response/parse_error在各决策目录。已证实是空候选下非法waypoint耗尽重试；不能据此推断整个No-Go根因，也不能说修复会恢复VLN成功。这两个错误均不属于基线成功配对子集。

## 唯一导航行为改动

新增默认关闭的`--empty-candidate-recovery`。开启后仍执行原两次严格解析；仅当候选为空且两次均非法时，由控制器产生LOOK +45°，保留先前有效memory。合法STOP/LOOK不变，有候选时非法输出仍失败。不更改prompt、1.5m子目标、风险代价、候选生成或栅格；λ=0/nonzero共享同一执行器。原动作/决策/无进展预算不变，原错误输出保留，fallback在决策record中标记。

测试覆盖两次重试、默认关闭、非空候选、合法STOP/LOOK、严格角度及有限观察循环。Mac用实际policy类AST隔离Habitat导入，服务器使用完整真实模块；均不调用模型。45°观察重复时原ProgressGuard在11次决策/33次转向后累计4次无进展，不能无限旋转。

## 冻结的小验证协议（GPU就绪后）

配置`configs/benchmark/empty_recovery_validation_v1.json`。固定三次真实闭环：515/start/λ0、743/near/λ1、743/near/λ4，均启用修复，interface v1、STOP复核off；沿用原任务、AP、模型revision和动作预算。新批次必须排他创建，不能混版本续跑：

```bash
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/validate_empty_recovery.py \
  --output-dir runtime/batches/empty_recovery_v1_20261117
```

验收：515原成功须保持且无新增执行错误；743必须保留全部失败和fallback记录，若到达空候选应不再产生非法waypoint或解析异常。若未重现空候选，只能记真实闭环未触发，不能称该路径已通过。同时检查模型请求/动作、碰撞、退出、完整/错误前缀、SR/SPL/nDTW/路径长度及通信总时长/比例/最长断连。工程三次验证不足以证明全10任务无退化，更不能替换原B3或证明通信收益；下一轮正式对照前另行冻结导航损失/绕行预算/λ扫描。

## CPU候选路径空间诊断（预先固定）

`configs/benchmark/candidate_routes_diagnostic_v1.json`：所有原10条λ0轨迹各前两个已记录模型局部目标，三个原AP布局，λ=0/.25/.5/1/2/4/8，路径长度预算0/10/20/50%。85仅有一个目标，保留不足，不替换任务或选成功轨迹。模型输入不变；CPU PathFinder与完整信号场仅用于离线诊断，使用已知单层几何、.25m栅格、±.20m高度容差和简化无线代理。

```bash
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/diagnose_oracle.py \
  --source-batch runtime/batches/oracle_full_action_guard_v1 \
  --spec configs/benchmark/candidate_routes_diagnostic_v1.json \
  --output-dir runtime/diagnostics/candidate_routes_20261117
```

统计不同路径数量、长度及空间断连暴露，收益至少超过.01m/.1m分别报告，保留所有错误。不将静态长度暴露当成实际断连时间，不将局部目标路径多样性当成VLN成功或干预因果证据。不据本轮扫描挑λ重报旧B3。

## 当前状态

代码执行提交`8047932afc6754553a98122ebcb61b459b8b0f05`，已push并以Git bundle快进服务器（服务器GitHub代理127.0.0.1:7894拒绝连接）；本机与服务器真实Habitat环境均29项测试通过。未升级Gym/其他共享依赖。

原两组原始response在CPU完整policy离线回放：共4个开关条件，off均重现ToolParseError，on均两次重试后合法LOOK；没有新模型请求或闭环成功宣称。可复现入口：`scripts/replay_empty_candidate_errors.py --output-dir runtime/diagnostics/NEW_UNIQUE_DIR`。实际产物`runtime/diagnostics/empty_candidate_replay_20261117/report.json`，SHA256 `e47f5a3642d7dc8768655a2e31fa79eda1e74cc5427216d1d4b97bef2e849aad`；报告含commit、模型固定revision、manifest及原错误文件hash。

CPU路径诊断实际得到19个局部目标×3布局×7权重=399条查询，57组目标/布局，无查询错误。46组仅1条不同路径、7组有2条、3组有3条、1组有4条。31/57组λ0空间断连暴露>.01m；全部57组分母固定，布局和相邻局部目标不视为独立语言样本。

| 允许长度增加 | 暴露减少>.01m的组 | 暴露减少>.1m的组 | 单组最大减少(m) |
|---|---:|---:|---:|
| 0% | 2/57 | 1/57 | .1036 |
| 10% | 3/57 | 2/57 | .2861 |
| 20% | 4/57 | 3/57 | .6744 |
| 50% | 4/57 | 3/57 | .6744 |

>.1m的三个目标/布局为1074/decision1/near、85/decision0/near、97/decision1/near。该结果提示本次短局部目标下路径选择空间有限；不是全部决策、未知地图、真实无线或真实闭环的根因证明。不依据这些数选择生产λ。实际产物`runtime/diagnostics/candidate_routes_20261117/diagnostic.json`，SHA256 `f38d092e540b3f51523048f6970691b8c7eb388ae9d75a47947af60e097c953f`；含源文件hash、完整路径、风险/暴露、配置及所有查询。

03:14仍四卡有其他计算PID，新等待器2773082状态waiting/0/3，源码pin均匹配；直连localhost:8010拒绝连接，文本/单图/双图均未验收。本轮三次GPU真实闭环尚未运行，不能写作修复已通过闭环或共同执行器无退化。完整B3继续No-Go。下一步先在资源恢复且probe通过后运行已冻结三次工程验证；若保持成功且确实触发合法退路，再单独设计候选路径空间干预协议，一次只变一个因素，预写导航损失/绕行预算后才运行新的完整对照。
