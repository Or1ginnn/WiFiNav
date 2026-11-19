# 单层 RSSI 传播模型对照

2026-11-19。用户确认首版无线观测为 RSSI。用同批位置比较现有对数距离和 navmesh 绕行代理与 Sionna RT 生成的接收功率，检查这两种方法能否给出一致的 AP 选点和路线覆盖判断。这个批次评估参考路线，无导航策略运行。

## 固定输入与处理

- 一个开发场景 `2n8kARJN3HM`，同层 121、134、235、512 四条参考路线，共 170 个采样位置。布局 A 使用任务 235 的旧 AP 初值，布局 B 使用 512 的旧初值。两点由几何间距选出，两个布局分别对四条路线评估。
- 冻结配置 `configs/wireless/rss_pilot_v1.json`（SHA256 `c36ae92947fb4e42e3f34e543cac726d04e2c14210c2cc1a290bad6d9aaa5009`）。频率 2.437 GHz，发射 / 接收高度为 navmesh 楼层基准以上 1.6 / 0.6 m。Sionna 用各向同性发射和 1 m 自由空间 −48 dBm 的共同参考功率。这个归一化使两种传播模型可以用同一功率基准比较，仍需实地校准。
- 使用完整三维网格，以 Habitat `(X,Y,Z)` → MP3D GLB `(X,−Z,Y)` 送入射线追踪。GLB SHA256 `2edd5d22dbbf2c57cc0dd85b2f3eb7bc6594322f9f03009014d040abe7532fec`，navmesh SHA256 `89b16aa556cfbf32aef294163339cfb037b24ffb16951259a35c4e3927e9e237`。三维场景保留楼板和墙体用于传播，机器人和发射接收位置限定在同一层。
- 用两种均匀材质假设分别生成图，混凝土和石膏板都取 0.10 m 有效表面厚度。Sionna RT 计算直达、镜面反射和透射，最大深度 3，0.25 m 平面网格，每发射机 200 万射线，seed 42/43 独立重复，以瓦特平均后得到 dBm。参考路线查最近格。每对相邻路线点取端点均值判断该段是否低于 −67/−75 dBm。未取到有限功率的样本标记缺测。
- 对同一任务比较 AP 时，优先看小于 −75 dBm 的长度，差值至多 0.25 m 时比较 P10 RSS，差值至多 2 dB 记判平。自由空间验收要求最大功率误差不超过 1.5 dB，场景定位验收要求两个 AP 均对齐且至少 90% 采样点的地面偏差在 0.30 m 内，每材料、路线与布局的两次随机种子差异 P90 不超过 3 dB。

## 运行记录

- 脚本 `scripts/prepare_rss_pilot.py` 在 Habitat 0.3.0 下生成本项目服务器 `runtime/diagnostics/rss_pilot_20261119/paired_input.json`，执行提交 `1f85c82`，产物 SHA256 `3a197c03fbf6434da06a3366dbc767dc14648346a71a5e096ae3f575b649d87f`。
- 原 Python 3.10 导入 Sionna RT 2.2.0 时无法导入 `typing.Self`（日志 `runtime/logs/rss_pilot_20261119_rt.log`）。独立针对性复核中，系统 LLVM 15 的几何 JIT 探针出现 `Cannot select ... fminimum`，改用服务器已有 LLVM 19.1.2 后，同一探针 172/172 位置通过地面对齐。正式射线追踪改用项目 runtime 下独立的 Python 3.11 环境与 CPU LLVM 后端。
- v1 射线追踪执行提交 `d52d6f7`，结果 `runtime/diagnostics/rss_pilot_20261119/rt_py311/report.json`（SHA256 `6d19bce3db0b0866bafd19167eb857bbbc5e591fcccd7e2d57155c6542244efb`）。v2 只提高射线数到 800 万和深度到 8，由 `configs/wireless/rss_pilot_v2.json` 固定（SHA256 `26867491f53c0cde7e304df5351d9fb236388c7068cc151a817bab1a603d4fe7`）。v2 输入 `paired_input_v2.json`（SHA256 `d1508b387093000c0bd642c8f75e3100c68c29f44172baa80c03a71ba4f02a25`），结果 `rt_v2/report.json`（SHA256 `54a3ff30272395facee9a28e2ed9c75e6a039e1cb8b670095685f28e4c4f3c37`），执行提交 `a063714`。两版配对位置与轻量模型结果逐项一致。
- 两版使用 Sionna RT 2.2.0、Mitsuba 3.9.1、Dr.Jit 1.5.0、Trimesh 4.12.2 和 NumPy 2.4.6。依赖完整清单在 `runtime/diagnostics/rss_pilot_20261119/pip_freeze_py311.txt`（SHA256 `abd99bb60ad4ec2fc572abf3c084fca6c45158e0941012e7ecd1508ec45ac9bb`）。日志 `runtime/logs/rss_pilot_20261119_rt_py311.log` 与 `runtime/logs/rss_pilot_20261119_rt_v2.log`。全程 CPU，未调用 Qwen。

## 结果与选型

两版的自由空间功率最大误差均低于 0.05 dB，172/172 个对齐位置通过几何检查。v1 的混凝土/石膏板分别只有 1/8 和 2/8 条完整路线剖面，共缺 311/680 个材质×路线点×AP 样本。v2 提高射线数和最大深度后，完整剖面提高到 6/8、5/8，共缺 19/680 个样本。两项参数一起改变，无法由此次试点识别各自贡献。v2 仅有 6/16 个剖面同时满足完整性与两随机种子差异 P90 ≤3 dB，整体未通过重复性门。

v2 完整剖面中低于 −75 dBm 的参考路线长度如下，单位为米。“缺测”表示该剖面有至少一个功率样本不可用。

| 任务 | AP | 现有距离与导航几何代理 | Sionna 混凝土 | Sionna 石膏板 |
|---|---|---:|---:|---:|
| 121 | A | 12.47 | 12.47 | 缺测 |
| 121 | B | 11.55 | 12.47 | 10.14 |
| 134 | A | 8.11 | 4.81 | 2.22 |
| 134 | B | 8.11 | 8.11 | 8.11 |
| 235 | A | 2.21 | 1.23 | 0.00 |
| 235 | B | 9.65 | 缺测 | 缺测 |
| 512 | A | 8.35 | 缺测 | 缺测 |
| 512 | B | 0.00 | 2.91 | 0.00 |

例如 512/B 的两种材料结果各自完整，随机种子差异 P90 仅 0.78 / 0.39 dB，但混凝土假设下有 2.91 m 估计断连，石膏板下为 0 m。235/A 也出现材料导致的覆盖分类变化（1.23 m / 0 m，种子差异 P90 为 0.77 / 0.28 dB）。因此提高射线预算本身无法解决射频材料未知导致的选点不确定性。该批次只计算固定参考路线，尚未验证符合语言指令的替代路线，也未验证真实 Wi‑Fi 掉线。

**选型决定。** 首版 benchmark 开发主线使用现有对数距离损耗、navmesh 遮挡代理、固定空间阴影及显式观测噪声，标记为可复现的合成 RSSI。Sionna RT 作独立覆盖审计，材料敏感或缺测的布局标为待复核。正式布局冻结前优先核查这种路线的墙体假设，或加入独立实测再定覆盖结论。保留既有 −75 dBm 仿真阈值，真实断链需有丢包或请求成功率证据。

## 复现入口

在服务器项目根目录运行，通过唯一的输出目录保留历史批次。CPU 射线追踪复用既有 LLVM 19.1.2，Python 依赖装在本项目 `runtime/envs/sionna_rt_2_2_0_py311`。

```sh
/opt/anaconda3/envs/habitat0.3.0/bin/python scripts/prepare_rss_pilot.py \
  --config configs/wireless/rss_pilot_v2.json \
  --ap-review-data runtime/diagnostics/single_floor_ap_review_20261119_reaudit/ap_review_data.json \
  --output runtime/diagnostics/rss_pilot_reproduce/paired_input.json

CUDA_VISIBLE_DEVICES="" \
DRJIT_LIBLLVM_PATH=/opt/anaconda3/pkgs/libllvm19-19.1.2-ha7bfdaf_0/lib/libLLVM-19.so \
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 \
taskset -c 0-3 runtime/envs/sionna_rt_2_2_0_py311/bin/python scripts/run_rss_raytrace_pilot.py \
  --input runtime/diagnostics/rss_pilot_reproduce/paired_input.json \
  --output-dir runtime/diagnostics/rss_pilot_reproduce/rt
```
