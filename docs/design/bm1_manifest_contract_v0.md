# BM1开发清单合约 v0

2026-11-19。状态：仅开发schema草案与程序化约束，固定复用原10条train任务/30AP，不筛样、不冻结正式单层资格或评估清单。BM0视觉语义与原资产官方逐字节/许可追溯尚未闭合；这些缺口不由字段校验自动解决。本轮推进的是独立可做的CPU字段审计，不把BM0/BM1整体标完成。

## 三份分离产物

| 文件 | 使用者/内容 | 约束 |
|---|---|---|
| `actor_inputs.json` | 运行适配器：case_id、instruction、scene_id、start_position、start_rotation | 严格字段白名单；不含goal/path/AP/无线图/评估指标。启动位姿用于环境初始化；Qwen不直接接收绝对位姿或scene标识 |
| `protected_manifest.json` | 构建/QA/评测：源hash、source split、group、布局/seed、受保护源任务/GT引用及无线实例 | 不传给actor；是项目runtime内部开发侧文件，不是可直接公开的数据集 |
| `checks.json` | 复现元数据、代码commit、schema/源文件hash、case/group/scene统计 | 不含原指令payload，不声称官方版本/发布资格已确认 |

根字段为schema_version=`bm1-dev-v1`、stage=`development_schema_audit`、official_release=false、source、cases。source记录task/GT/旧manifest三种SHA256及声明目录名、official_bytes_verified=false。

case字段：case_id、episode_id、scene_id、group_id、source_split、assigned_split、layout_id、channel_seed、instruction_sha256、qualification、protected_instance。group_id由scene_id与trajectory_id组合；同scene、源路径group及源episode不能跨development/held_out。该检查支持合成测试中的两类split，但实际builder硬限制train，只生成development，未读取保留集payload。

qualification固定unreviewed，不能用原模型成功/失败或本轮源层高诊断替代正式资格。case_id包含源split/scene/episode/layout/seed；同任务多个AP case不增加language_tasks计数。

## 已实现与边界

`src/connectivity_vln/evaluation/manifest.py`是针对上述草案的stdlib结构/语义校验器，**不是通用JSON Schema引擎或安全隔离沙箱**。检查唯一case、actor一对一、指令hash、起始位姿维度、split/group/scene一致性、缺失hash、非有限数值、开发/未审资格标记与actor字段白名单。

`scripts/build_bm1_development.py`仅从旧冻结清单读取原10任务，完整保留三个AP布局；读取源train与hash，不访问策略结果或val_unseen/test。它不运行Habitat/VLM、不写入原data，也不选择无线更优任务。派生测试包排他创建于runtime/diagnostics，正式data下的新benchmark尚未生成。

```bash
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/build_bm1_development.py \
  --output-dir runtime/diagnostics/bm1_schema_dev_20261119
```

新增6项有针对性的测试，本机和真实服务器Habitat环境累计35项均通过：正常分离、actor真值字段泄漏、重复case、group/scene跨split、指令变更/缺actor、伪装正式发布或资格通过。实际服务器审计已在6180a8d执行，10任务/30case全部保留、actor字段分离与group检查通过；commit/hash/产物见[实际验证记录](../experiments/bm1_schema_dev_2026-11-19.md)。

后续BM1：制定源版本固定方式与正式schema文件/迁移策略，冻结单层几何/语言歧义资格规则、人工复核流程、选中/排除原因编码，以及独立开发/保留评估清单。此开发schema不决定任何新评估样本或参数，不算发布质量门通过。

## 2026-11-19范围修正

按用户最新指示，正式任务不因包含楼梯而判无效。后续schema扩展将任务有效性、楼层属性、执行器supported/unsupported分开；当前开发字段qualification=unreviewed继续保持，不反向筛掉97或重写旧30case。此前“单层资格”表述只作为当时范围，后续按新任务卡/BM3规范落实能力分层。
