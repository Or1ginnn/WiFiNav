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

本机29项测试通过；服务器完整导入测试、原始错误离线回放、CPU路径诊断及部署版本/产物将在实际执行后补记。四卡目前被其他任务占用，模型未就绪；尚未执行上述三次闭环验证。
