# 服务器任务与场景数据

更新于 2026-11-22。任务集和场景以独立实际文件存放在服务器 `~/WiFiNav/data/`。Git 同步配置与记录。

## 当前主线：HM3D ObjectNav v2

官方 episode 包已完整安装。场景仅安装一处官方公开样例。完整切换需要有访问许可的 HM3D v0.2 Habitat 场景包与 HM3D-Semantics v0.2 配套文件。

| 内容 | 服务器项目内路径 |
|---|---|
| 官方 episode 包 | `data/datasets/objectnav/hm3d/v2/{split}/{split}.json.gz` 和各 split 下的 `content/` |
| 带语义的场景目录 | `data/scene_datasets/hm3d_v0.2/` |
| episode 包与逐文件 SHA256 清单 | `data/_manifests/hm3d_objectnav_v2_episodes.json` |
| 公开样例来源与逐文件 SHA256 清单 | `data/_manifests/hm3d_objectnav_v2_public_scene.json` |
| 下载归档与加载日志 | `runtime/data_imports/hm3d_objectnav_v2_20261122/` |
| 当前场景覆盖与缺失清单 | `runtime/data_imports/hm3d_objectnav_v2_20261122/readiness.json` |

源 ZIP 大小为 260,304,032 字节，SHA256 为 `f551a0d8560804dc385c52f9aedb646c70917da36c1902d848b4fbc1615515d0`。CRC 校验通过，解出的 186 个 gzip 文件逐字节与包内一致，原始 JSON 和场景引用路径保留。官方 `train` 和 `val` 的 `episode_id` 在同场景的不同物体类别间会重复。后续派生清单使用源文件相对路径和文件内记录序号建立稳定标识，保留原 ID。

| 官方 split | Episode 记录 | 场景引用 | 场景已安装 |
|---|---:|---:|---:|
| `train` | 7,196,434 | 145 | 0 |
| `val` | 1,000 | 36 | 1 |
| `val_mini` | 30 | 2 | 0 |

六个目标类别为 `bed`、`chair`、`plant`、`sofa`、`toilet`、`tv_monitor`。表内是官方原始记录数。尚未生成单层派生集或筛选 AP。

任务包来自 [Habitat-Lab 官方数据清单](https://github.com/facebookresearch/habitat-lab/blob/main/DATASETS.md)，场景配置、几何、navmesh 与语义样例来自 [Matterport 官方发布](https://github.com/matterport/habitat-matterport-3dresearch#-downloading-hm3d-v02)。公开样例 `00861-GLAQ4DNUx5U` 匹配 `val` 的 28 条记录，按原任务引用放在 `hm3d_v0.2/val/00861-GLAQ4DNUx5U/`。原 navmesh 判定 28 个起点可通行，无渲染模拟器成功加载场景与 908 个语义对象。Habitat 0.3.0 的任务加载器在 CPU 读入 `val` 的 1,000 条和 `val_mini` 的 30 条。样例用于资源验收，未进行导航评分或模型调用。

[新数据配置](../configs/data/objectnav_hm3d_v2.json) 单独登记路径。Habitat-Lab 0.3.0 中使用 `ObjectNav-v1` 加载器和显式的 v2 路径覆盖，加载器注册名与发布包版本各自固定。旧脚本继续用 [原 R2R 路径配置](../configs/data/server_paths.json) 的既有字段。开发候选取自 `train`，`val` 用于保留评估，`val_mini` 仅作加载检查。

**继续切换所缺资产。** 当前服务器可用目录未找到其余场景，Matterport 官方下载在未登录状态下返回登录页。拿到有访问许可的场景目录或下载包后，按上述引用导入，核验每个场景的几何、navmesh、语义与必要配置，再接 Habitat 任务。访问入口见 [HM3D 官方获取说明](https://github.com/facebookresearch/habitat-sim/blob/main/DATASETS.md#habitat-matterport-3d-research-dataset-hm3d)。

2026-11-23 复核，服务器可解析并访问 Matterport，三个官方 `train` 下载 URL 的匿名响应均为登录 HTML。服务器直下入口为 `python3 scripts/download_hm3d_train.py`，从交互 SSH 终端运行。输入已获授权的 Token ID 和 Secret 后，先校验语义配置包，再后台下载两份大包到 `runtime/data_imports/hm3d_train_v0.2/`。凭据仅用于进程内认证。用同目录的 `download.log` 查看状态，全部校验后生成 `archives.json`，随后按项目要求验收并安装实际文件。

## 原 R2R-CE / MP3D 数据

以下是 2026-11-04 的复制与验收记录，供旧实验复现。

```text
~/WiFiNav/data/                              # Git忽略整个目录
├── datasets/
│   └── R2R_VLNCE_v1-3_preprocessed/           # 原始任务，不直接修改
├── scene_datasets/
│   └── mp3d/                                # 场景实际文件
└── _manifests/
    └── raw_assets_copy.json                  # 来源、文件大小与SHA256
```

复制已完成：任务12个文件、262,152,738字节；场景360个文件、22,341,948,844字节。共372个文件、22,604,101,582字节；逐文件SHA256及大小一致，inode独立，无软链接或硬链接。已核验后移入上述正式目录，源目录未改动。

数据路径配置：[server_paths.json](../configs/data/server_paths.json)。路径相对服务器checkout，不要求Mac具有同样目录，也不将场景/任务payload提交GitHub。

### 已核实的任务内容

来源目录标记为 `R2R_VLNCE_v1-3_preprocessed`。以下来自实际gzip/JSON解析，非估算：

| split | episode数 | scene数 | GT参考记录 | 场景缺失 |
|---|---:|---:|---:|---:|
| train | 10,819 | 61 | 10,819，episode ID全部覆盖 | 0 |
| val_seen | 778 | 53 | 778，episode ID全部覆盖 | 0 |
| val_unseen | 1,839 | 11 | 1,839，episode ID全部覆盖 | 0 |
| test | 3,408 | 18 | 未提供；任务也未提供goals/reference_path | 0 |

train/val任务含指令、起始位置/旋转、goals、reference_path、scene_id及episode/trajectory ID。test有指令与起始信息，但不能把场景文件齐全等同于可在本地计算完整任务指标。

目录另含envdrop、joint_train_envdrop相关文件与embeddings；它们不自动成为本项目训练或评测输入，本项目不新增导航权重训练。首轮只采用明确划分的train/val任务，附加数据的完整性和使用范围另行登记。

### 已核实的场景

- 90个MP3D场景目录，90个`.glb`和90个`.navmesh`，来源目录约21GiB。
- 上述四个split引用的场景均找到对应`.glb`。
- 目前确认的是文件与任务引用关系；真实场景在所选Habitat版本中的加载、navmesh适配、位姿/动作及坐标验证仍属于B0后续，不写作导航已跑通。

### 来源与排除项

| 内容 | 实际来源（保持不动） |
|---|---|
| MP3D | `/mnt/data/suiqiuyi/internNav/InternNav/data/scene_data/mp3d_ce/mp3d` |
| R2R-CE | `/mnt/data/suiqiuyi/0511-Article/nav_ws/ActiveVLN/data/datasets/R2R_VLNCE_v1-3_preprocessed` |

CFRP/data中的入口是指向这些来源的符号链接；本项目只借此定位来源，复制后不依赖这些入口。JanusVLN/data中的另一份mp3d/r2r目录基本是占位，`val_seen.json.gz`为0字节，未采用。

目录名称提供版本线索；与官方发布包的逐字节一致性尚未核实。以本次复制manifest的来源、大小和hash固定当前资产，后续适配时记录必要差异，不能仅凭目录名断言完全未经修改。

### 原路线的复用规则

1. 原始任务与场景副本按只读原始资产使用；生成R2R-Conn时另建派生目录，不覆盖原指令/参考路径。
2. 开发样例优先从train中按预设规则选择，val_unseen作为保留评估候选，不用其结果调参或筛样本。
3. 本次实际复制不代表取得场景或原任务的公开再分发许可。Git已忽略data，公开仓库仅同步配置、清单摘要和自有生成/评测代码。
4. 复制核验已完成，B0继续确认导航实现、具体Habitat版本、真实场景加载、信息隔离与模型/仿真资源共存，再选首条开发episode进入B1。
