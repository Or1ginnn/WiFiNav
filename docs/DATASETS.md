# 服务器任务与场景数据

更新于 2026-11-28。任务集和场景以独立实际文件存放在服务器 `~/WiFiNav/data/`。Git 同步配置与记录。

## 当前主线：HM3D ObjectNav v2

官方 episode 包、ObjectNav v2 引用的 145 个 `train` 场景和 36 个 `val` 场景均已安装。独立的 `val_mini` 路径仍保留原状态。

| 内容 | 服务器项目内路径 |
|---|---|
| 官方 episode 包 | `data/datasets/objectnav/hm3d/v2/{split}/{split}.json.gz` 和各 split 下的 `content/` |
| 带语义的场景目录 | `data/scene_datasets/hm3d_v0.2/` |
| episode 包与逐文件 SHA256 清单 | `data/_manifests/hm3d_objectnav_v2_episodes.json` |
| 公开样例来源与逐文件 SHA256 清单 | `data/_manifests/hm3d_objectnav_v2_public_scene.json` |
| 下载归档与加载日志 | `runtime/data_imports/hm3d_objectnav_v2_20261122/` |
| 11 月 22 日初始场景覆盖 | `runtime/data_imports/hm3d_objectnav_v2_20261122/readiness.json` |
| 11 月 24 日 `train` 安装及逐文件校验 | `data/_manifests/hm3d_objectnav_v2_train_install.json` |
| `train` 原始 tar、清单与日志 | `runtime/data_imports/hm3d_train_v0.2/` |
| `val` 安装及逐文件校验 | `data/_manifests/hm3d_objectnav_v2_val_install.json` |
| `val` 原始 tar、上传校验、安装及全量预检 | `runtime/data_imports/hm3d_val_v0.2/` |

源 ZIP 大小为 260,304,032 字节，SHA256 为 `f551a0d8560804dc385c52f9aedb646c70917da36c1902d848b4fbc1615515d0`。CRC 校验通过，解出的 186 个 gzip 文件逐字节与包内一致，原始 JSON 和场景引用路径保留。官方 `train` 和 `val` 的 `episode_id` 在同场景的不同物体类别间会重复。后续派生清单使用源文件相对路径和文件内记录序号建立稳定标识，保留原 ID。

| 官方 split | Episode 记录 | 场景引用 | 场景已安装 |
|---|---:|---:|---:|
| `train` | 7,196,434 | 145 | 145 |
| `val` | 1,000 | 36 | 36 |
| `val_mini` | 30 | 2 | 0 |

六个目标类别为 `bed`、`chair`、`plant`、`sofa`、`toilet`、`tv_monitor`。表内是官方原始记录数。首批 `train` 开发审阅使用 5 个已安装场景中的 20 条单层任务和 7 套 AP 草稿。[首批开发审阅](experiments/objectnav_train_ap_review_2026-11-24.md)

任务包来自 [Habitat-Lab 官方数据清单](https://github.com/facebookresearch/habitat-lab/blob/main/DATASETS.md)，场景配置、几何、navmesh 与语义样例来自 [Matterport 官方发布](https://github.com/matterport/habitat-matterport-3dresearch#-downloading-hm3d-v02)。公开样例 `00861-GLAQ4DNUx5U` 匹配 `val` 的 28 条记录，按原任务引用放在 `hm3d_v0.2/val/00861-GLAQ4DNUx5U/`。原 navmesh 判定 28 个起点可通行，无渲染模拟器成功加载场景与 908 个语义对象。Habitat 0.3.0 的任务加载器在 CPU 读入 `val` 的 1,000 条和 `val_mini` 的 30 条。样例用于资源验收，未进行导航评分或模型调用。

[新数据配置](../configs/data/objectnav_hm3d_v2.json) 单独登记路径。Habitat-Lab 0.3.0 中使用 `ObjectNav-v1` 加载器和显式的 v2 路径覆盖，加载器注册名与发布包版本各自固定。旧脚本继续用 [原 R2R 路径配置](../configs/data/server_paths.json) 的既有字段。开发候选取自 `train`，`val` 用于保留评估，`val_mini` 仅作加载检查。

**`train` 配置及导入记录。** 2026-11-24 从本机项目 `data/` 上传用户下载的三个正式 tar，共 37,860,229,120 字节。源几何文件名含浏览器追加的 ` (1)`，服务器归档使用官方原名。三个包的 SHA256 与本机一致。几何包包含 800 处场景，ObjectNav v2 的 `train` 引用 145 处，项目从完整归档中解出这 145 处的 580 个场景文件和一份训练场景配置。原全局配置与授权包逐字节相同。原始 tar 保留在服务器暂存目录，本机文件保留。

安装入口 `scripts/install_hm3d_train.py`，执行提交 `7d3f966`；日志 `runtime/data_imports/hm3d_train_v0.2/install_20261124.log`。Habitat-Sim 0.3.0 在 CPU 全量加载 145 个 navmesh。抽查 `00006-HkseAnWCgqk`，Habitat-Lab 0.3.0 读入该场景分片的 40,000 条任务，headless 模拟器读入 453 个语义对象并验证首个任务起点可通行。安装后复核了 581 个实际文件的完整目录、长度和独立 inode。安装清单 SHA256 为 `eea2abbf6cf5e5431a92107829aa2720a7b613f067dcde50de00b5ed3eb734ce`。

**`val` 配置及导入记录。** 2026-11-28 从本机项目 `data/` 上传三个官方 v0.2 tar，共 5,676,595,200 字节，逐包 SHA256 一致。由 `scripts/install_hm3d_val.py` 在提交 `49335ac` 导入。146 个清单文件均通过安装后长度、独立 inode 及 SHA256 校验，141 个新文件落盘，公开样例的四个场景文件和全局配置经匹配后保留。Habitat-Sim 0.3.0 成功加载 36 个导航网格。新场景 `TEEsavR23oF` 的无渲染抽查读入 661 个语义对象，28 条任务起点均可通行。安装清单 SHA256 为 `6c351787491fd67e9783ed8b75a0386e7e99305c2b868467b45abf1c5b8a3ad3`，独立 `val_mini` 资产与正式全量 `val` 范围分开。

2026-11-23 复核，服务器可解析并访问 Matterport，三个官方 `train` 下载 URL 的匿名响应均为登录 HTML。服务器直下入口为 `python3 scripts/download_hm3d_train.py`，从交互 SSH 终端运行。输入已获授权的 Token ID 和 Secret 后，先校验语义配置包，再后台下载两份大包到 `runtime/data_imports/hm3d_train_v0.2/`。凭据仅用于进程内认证。用同目录的 `download.log` 查看状态，全部校验后生成 `archives.json`，随后按项目要求验收并安装实际文件。

用户随后指定先下载到本机项目，再上传服务器。实际本机下载记录使用 `runtime/data_imports/hm3d_train_v0.2/local_archives.json` 保存包名、长度和 SHA256，服务器完整复核后导入。

## VLFM 上游对照：HM3D ObjectNav v1

从 VLFM 官方 README 指向的发布地址直下到服务器项目。ZIP 为 138,845,369 字节，SHA-256 为 `24d37da5a3919ca15c81251f9420eec5fef32a48ab26a6eeabda723e8387bee1`，CRC 校验通过。105 个原始 gzip 文件安装到 `data/datasets/objectnav/hm3d/v1/`，逐文件确认内容一致且为独立实际文件。原始 ZIP 保存在 `runtime/data_imports/hm3d_objectnav_v1_20261128/`，安装清单位于 `data/_manifests/hm3d_objectnav_v1_episodes.json`。

v1 正式 `val` 源文件共 2,000 条、20 个场景。全部场景在项目的 HM3D v0.2 资产中可定位。上游基线小批的派生清单只变更 `scene_id` 和 `scene_dataset_config` 的本地路径，保留 v1 原任务、起点、目标及视点。CPU 用 Habitat 0.2.4 原生任务加载器验收了所选 20 条的起点、navmesh 和场景注释对象索引。[上游数据说明](https://github.com/rai-opensource/vlfm/blob/584ed56008754fde7997d904983607def8328322/README.md#L66-L88) · [小批运行](experiments/objectnav_vlfm_2026-11-28.md#原入口-v1-小批)

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
