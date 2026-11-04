# 服务器任务与场景数据

更新：2026-11-04。用户要求：**任务集和场景直接存放在服务器项目的数据目录，使用独立实际文件，不使用软链接；来源保留不动。** 数据仅存服务器，本机和GitHub保存配置与记录。

## 当前目录与复制状态

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

## 已核实的任务内容

来源目录标记为 `R2R_VLNCE_v1-3_preprocessed`。以下来自实际gzip/JSON解析，非估算：

| split | episode数 | scene数 | GT参考记录 | 场景缺失 |
|---|---:|---:|---:|---:|
| train | 10,819 | 61 | 10,819，episode ID全部覆盖 | 0 |
| val_seen | 778 | 53 | 778，episode ID全部覆盖 | 0 |
| val_unseen | 1,839 | 11 | 1,839，episode ID全部覆盖 | 0 |
| test | 3,408 | 18 | 未提供；任务也未提供goals/reference_path | 0 |

train/val任务含指令、起始位置/旋转、goals、reference_path、scene_id及episode/trajectory ID。test有指令与起始信息，但不能把场景文件齐全等同于可在本地计算完整任务指标。

目录另含envdrop、joint_train_envdrop相关文件与embeddings；它们不自动成为本项目训练或评测输入，本项目不新增导航权重训练。首轮只采用明确划分的train/val任务，附加数据的完整性和使用范围另行登记。

## 已核实的场景

- 90个MP3D场景目录，90个`.glb`和90个`.navmesh`，来源目录约21GiB。
- 上述四个split引用的场景均找到对应`.glb`。
- 目前确认的是文件与任务引用关系；真实场景在所选Habitat版本中的加载、navmesh适配、位姿/动作及坐标验证仍属于B0后续，不写作导航已跑通。

## 来源与排除项

| 内容 | 实际来源（保持不动） |
|---|---|
| MP3D | `/mnt/data/suiqiuyi/internNav/InternNav/data/scene_data/mp3d_ce/mp3d` |
| R2R-CE | `/mnt/data/suiqiuyi/0511-Article/nav_ws/ActiveVLN/data/datasets/R2R_VLNCE_v1-3_preprocessed` |

CFRP/data中的入口是指向这些来源的符号链接；本项目只借此定位来源，复制后不依赖这些入口。JanusVLN/data中的另一份mp3d/r2r目录基本是占位，`val_seen.json.gz`为0字节，未采用。

目录名称提供版本线索；与官方发布包的逐字节一致性尚未核实。以本次复制manifest的来源、大小和hash固定当前资产，后续适配时记录必要差异，不能仅凭目录名断言完全未经修改。

## 复用规则与下一步

1. 原始任务与场景副本按只读原始资产使用；生成R2R-Conn时另建派生目录，不覆盖原指令/参考路径。
2. 开发样例优先从train中按预设规则选择，val_unseen作为保留评估候选，不用其结果调参或筛样本。
3. 本次实际复制不代表取得场景或原任务的公开再分发许可。Git已忽略data，公开仓库仅同步配置、清单摘要和自有生成/评测代码。
4. 复制核验已完成，B0继续确认导航实现、具体Habitat版本、真实场景加载、信息隔离与模型/仿真资源共存，再选首条开发episode进入B1。
