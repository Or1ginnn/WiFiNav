# 导航接口 v1：B2 故障修复与复核

接口实现提交：`947f786`。使用原冻结模型、任务、动作预算与场景；不使用评测 goal、参考轨迹或 RSSI 做决策。B2 v0 数据与运行目录只读保留。

| 问题 | v1行为 | 已核验 |
|---|---|---|
| 说明文字超过600字符导致终止 | 动作字段仍严格校验；reason/memory限长，非字符串按空值处理；原响应照常保存 | 1074两次历史响应均恢复为可解析的STOP请求，仍须通过复核；布尔候选编号与非法转角仍被拒绝 |
| STOP直接结束任务 | 用同一冻结模型单独检查原始RGB和任务指令；明确反证触发非STOP重选，格式重试耗尽则转向45°。不确定时保留原STOP | 分支检查覆盖重选、有限回退和不确定；历史8帧中拦截1/5错误STOP，放行3/3原成功STOP |
| 观察转向被当作无进展 | 以最近发生至少0.25米净平移的位置为锚点；原地转向到新朝向不加停滞计数，重复朝向或无效运动继续计数，平移重置计数 | 四次新朝向不触发停滞；四次回看触发计数上限；平移后重置 |

STOP审计为开发集定点复核，不能推出新轨迹的任务成功率。严格要求每个终点都在当前帧可确认的版本，曾误拦515和575，因而改成三态。最终规则判定97的房间与健身房终点冲突，其余四个历史错误STOP仍不确定。当前复核无法从单张画面可靠消除这类误停。

服务器证据：

- 初始严格复核：`runtime/runs/interface_v1_audit_3ba2edb`。
- 三态复核及最终规则：`runtime/runs/interface_v1_audit_3df52d2`、`runtime/runs/interface_v1_audit_d0db6b5`。
- 中间版本完整运行：`runtime/runs/interface_v1_smoke_515_3df52d2`，无接口异常，但发生误停，最终距目标6.22米。该版本将诊断计数传给了VLM；最终版只保留日志，常规运动反馈恢复原字段。
- 最终版本完整运行：`runtime/runs/interface_v1_smoke_515_947f786`。六次常规决策请求与v0历史请求逐条相同，另有一次STOP复核判为不确定并放行。正常STOP，成功=1，终点距离0.198米，SPL=0.9193。
- 旧批次恢复检查：`runtime/logs/interface_v1_resume_check.log`；v1写入v0批次在创建任务前被拒绝。

完整冻结10条任务的v1配对评估尚未执行。使用独立批次显式启用：

```bash
cd ~/WiFiNav
/opt/anaconda3/envs/habitat0.3.0/bin/python -u scripts/run_pilot.py \
  --interface-version v1 --batch-dir runtime/batches/pilot_interface_v1
```
