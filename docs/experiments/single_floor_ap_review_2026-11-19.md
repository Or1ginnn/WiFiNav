# 单层20任务 AP 布局审阅批次

日期：2026-11-19。用途：首个单层开发审阅样本的策略无关筛选、路线附近 AP 初始选点与本机交互校正。**不是正式发布集、导航实验结果或泛化评估。**原始train任务、旧B3/BM4和原10任务开发数据均未改动。

## 执行与来源

- 源：服务器 `~/WiFiNav/data/datasets/R2R_VLNCE_v1-3_preprocessed/train`；任务SHA256 `340a80133b2157520354ab055a91d98feb2f42e4bbda17b200c911f8788492ea`，dense GT SHA256 `b63fa10e5c57d1b80b241c49bdeddc3d481bbe54b41ca0d59f9584c10da7bd5d`。
- 源码commit：`07037c2a5c10ce26d81ae857ba0ce03ce7a1f94b`；服务器复用Habitat 0.3.0 CPU端PathFinder/navmesh，没有调用Qwen或GPU渲染。
- 构建器 `scripts/build_single_floor_ap_review.py`；配置 `configs/benchmark/single_floor_ap_review_v1.json`；筛选/AP规则见[设计记录](../design/single_floor_ap_review_v1.md)。
- 最终服务器产物：`~/WiFiNav/runtime/diagnostics/single_floor_ap_review_20261119_retry01/`；过程日志 `~/WiFiNav/runtime/logs/single_floor_ap_review_20261119_retry01.log`。第一次尝试因粗网格`try_step`重复拒绝已验证的原生路线采样连接而停止，日志保留于 `runtime/logs/single_floor_ap_review_20261119.log`；修复后新目录成功生成，未覆盖旧尝试。
- 本机只存交互HTML及其本地数据副本：`runtime/reports/single_floor_ap_review_20261119/index.html`。它未提交Git，也未上传服务器；没有CDN或外部请求。

## 筛选结果

| 统计 | 数量 |
|---|---:|
| train源任务 | 10,819 |
| 规则初筛candidate | 6,687 |
| 明确垂直移动词规则标记excluded | 1,971 |
| 高度起伏/楼梯语义歧义待review | 2,161 |
| 最终选中 | 20条、20个不同source path、5个场景 |
| 场景内布局 | 每场景4个任务，每个任务独立一个AP布局实例 |

`excluded`是基于指令词规则的范围标记，不等于人工语义真值；`review`不自动判为上楼或合格。只有选中的20条执行了native navmesh参考路径检查，未选的其他candidate并没有通过几何资格检查。任务按预先固定的scene/episode顺序和不同source path选择，不使用策略成功、模型输出或RSSI效果。

选中场景和episode：

| Scene | Episode IDs |
|---|---|
| `mp3d/17DRP5sb8fy/17DRP5sb8fy.glb` | 515, 575, 1074, 1116 |
| `mp3d/1LXtFkjw3qL/1LXtFkjw3qL.glb` | 85, 127, 743, 818 |
| `mp3d/1pXnuDYAj8r/1pXnuDYAj8r.glb` | 214, 268, 493, 825 |
| `mp3d/29hnd4uzFmX/29hnd4uzFmX.glb` | 160, 208, 287, 290 |
| `mp3d/2n8kARJN3HM/2n8kARJN3HM.glb` | 121, 134, 235, 512 |

## AP 与RSSI

每个episode独立生成一个AP floor-proxy初始位置：参考路线约35%进度、侧向偏移目标1.5m，再吸附到同层、可达、距路线2m内的navmesh网格候选。界面显示每任务合法候选点；当前初始AP坐标逐条列在本机HTML和`ap_review_data.json`中。20/20坐标都匹配合法候选点，且距原路线不超过2m。每任务有70–293个候选，均值162.8。

当前信号设置为同一个固定代理：1m参考RSSI -48dBm、路径损耗指数2.8、seed 20261119；叠加现有navmesh测地绕行遮挡代理和确定性空间阴影。按原生`SignalField`仅对参考路线采样点查询latent RSSI。初始路线长度均值9.10m（范围6.13–14.81m）；20/20存在弱信号路径段，3/20存在低于断连阈值的路径段，平均断连路径长度比例1.8%。这些是固定代理下的描述性结果，不是AP选点目标、真实无线验证或导航结果。

报告中点击绿色合法候选即可修改当前episode AP；可恢复初值、浏览器本地暂存、导入/导出JSON。初始路线曲线是原生`SignalField`代理latent truth；空间热图和点击后的即时变化按同一RSSI公式、空间阴影与0.4m图距离估算，不是原生逐点查询。改点后仍要服务器原生信号场重新计算并复核；界面明确区分粗估与原生曲线。地图是可走网格点，不是建筑平面图；AP高度是仿真floor proxy，不代表墙面/顶棚安装。

## 可复现与文件完整性

- 单层配置SHA256：`f594165f5de7be8539512a9733a8c5164c168959c4598d8b2a8df78fd9720ce4`
- Builder SHA256：`64fdc878189bce91f1fa1b72c6133d32cab8588da773f52c6a2892a97b86ab6a`
- 核心几何规划器SHA256：`18271f7be0fafb93bb04dd994c6b1e01b85f28fb9e3067f27110a06d52028f71`
- RSSI实现SHA256：`63aff5b45ba1ad27b1931a42fb2ee0578b60ba1824c1d8b4754c89f2ecc73046`
- 新批次`ap_review_data.json` SHA256：`7fe0d048596cfd1b5b1a0d7475ec2b4ef63d10d58c2a4995e98d123f91284504`
- 新批次`source_scope_audit.json` SHA256：`4dcf4ef123dced4061d4e1f3e169451185d54736c74c8fd6b4cf4018e67b0c26`
- 本机单文件HTML SHA256：`af02f55daaa45af9b3ed8dff96e00ed4ce82124139ff3eb4c6903fd1cafae395`，大小6,081,907字节。
- 本机HTML生成器SHA256：`b12df6ce2f70447226c91549f58d9361b9ae15e147c6fb0d09f84258f0360320`。
- 五个实际navmesh的SHA256、所有20条起终点/路线、AP候选索引及坐标、初始路线RSSI/弱区统计和运行时间保存在批次JSON与报告中。

实现测试：本机6项范围/辅助函数测试通过；Python编译检查、最小数据HTML渲染、内联JavaScript语法检查通过。自动化浏览器预览受本地`file:`URL策略阻止，因此报告本身已按文件/JS结构校验，但未做浏览器截图验收。

## 未闭合项

- 需要人工查看20条指令、参考地标与楼层范围；规则标签不是人类标注。
- AP人工修改后应导出布局修改JSON，并在服务器对每个新AP位置执行原生navmesh可达性与RSSI重算，形成独立冻结的layout版本。
- 路线兼容AP是受控开发布局，不代表自然AP部署分布；物理墙体传播、多AP/楼层传播与最终benchmark规模尚未验证。
- 原完整B3 No-Go不变；本批次未启动VLM导航或新收益对照。
