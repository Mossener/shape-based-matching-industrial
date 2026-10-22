# 下一轮公开测试集候选：LM / LM-O 与 ITODD

核查日期：2026-10-23。本文是公开小文本与元数据调研，**未采集图像、未下载压缩包、未测量匹配速度或准确率**。没有读取当前真实模板库、原始检测结果或留出集，没有修改已冻结协议、算法默认值或质量/计时源码。下文的取样规则只是下一轮建议，尚未执行。

建议先将 **LM 与 LM-O 作为同一来源族**扩展视角与遮挡覆盖，再将 **MVTec ITODD 的公开 validation**作为不同来源的工业灰度零件候选。LM-O 不是独立于 LM 的第二份外部验证；ITODD 的非商业许可与私有测试真值也限制了它的用途。

## 官方来源与核实范围

| 候选 | 本次核实的数据量和图像 | 标注及可用边界 | 与当前 T-LESS 的关系 |
| --- | --- | --- | --- |
| [LM / LINEMOD](https://bop.felk.cvut.cz/datasets/#LM) | BOP 官方说明为 **15 个**有显著颜色、形状和尺寸差异的日常物体；toolkit 对象和 test 场景 ID 均为 1–15，图像 **640×480 RGB-D**。本次未读取档案目录，未核实每个序列的实际帧数。 | 官方说明每个对象对应的测试图组只标注一个对象实例，杂乱明显、遮挡较轻。可做已标注对象的定位/召回；不能把其他对象未出现在该组 GT 中直接当成负例。官方另列 PBR 训练图和孤立对象的合成训练图。 | 原始来源为 Hinterstoisser 等 ACCV 2012，T-LESS 为 Hodaň 等 WACV 2017；对象、采集和原始发布来源不同，适合扩展域。仅凭元数据不能证明图像级零重复，本次未做图像去重。 |
| [LM-O / Occlusion LINEMOD](https://bop.felk.cvut.cz/datasets/#LM-O) | toolkit 列 **8 个对象** `[1,5,6,8,9,10,11,12]`，test 只有 scene `2`，**640×480 RGB-D**。本次未核实档案中的实际帧数或逐帧目标缺失数。 | 在 LM 的一个测试图组上补充多对象 GT，重点是不同程度遮挡。与 LM 复用实拍图，PBR 训练图也相同。 | 与 T-LESS 是不同原始来源；与 LM 有明确复用，必须一起处理泄漏风险，不能分别算作两个独立来源。 |
| [MVTec ITODD](https://bop.felk.cvut.cz/datasets/#ITODD) | [MVTec 原站](https://www.mvtec.com/research-teaching/datasets/mvtec-itodd)写明 **28 个对象、3500 个带标签场景、5 个传感器（2 个 3D、3 个灰度相机）**。BOP Classic ITODD 使用 **1280×960 Gray-D**；toolkit 的 val/test 打包 scene ID 都是 `1`。原站 3500 场景不等于本地可公开评分的 BOP validation 帧数，后者本次未核实。 | BOP 官方明确训练和 validation 的 6D GT 公开，**test GT 不公开**。优先考虑公开 validation 做可审计的本地实验；不能在 test 上凭空计算召回、GT 框 IoU 或负帧误检。 | 原始来源为 MVTec / Drost 等 ICCVW 2017，工业零件、灰度传感器和采集来源均不同于 T-LESS。尚未做文件或视觉去重。 |

对象 ID、分辨率和 split 列表来自固定版本的官方
[dataset_params.py](https://github.com/thodan/bop_toolkit/blob/cea62d651c7e395b2e1962b9749e4e89693c6ac4/bop_toolkit_lib/dataset_params.py)。这是 toolkit 声明，不是本次对档案内容的清点。LM 的 15 对象也不能未经说明替换为某些论文常用的 13 对象协议。

ITODD 的灰度域可检验几何匹配是否泛化，但不能用它单独证明 RGB 颜色分层特征有效；应分别报告灰度与彩色域。本文指 BOP-Classic 的 **ITODD**，不将 **ITODD-MV**算作独立外部来源。BOP 明确 ITODD-MV 在 ITODD 相同场景上增加三个相机视角。

## 许可原文与未解决的差异

- **LM 的 BOP 发布**：[BOP 条目](https://bop.felk.cvut.cz/datasets/#LM)写明 `license: CC BY 4.0`；固定版本 [HF README](https://huggingface.co/datasets/bop-benchmark/lm/blob/750b2f78ed1093f789086b17ab43fe8517d51aed/README.md)仅含 `license: cc-by-4.0`。条款见 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。使用时保留原作者、来源、许可及变更说明。
- **LM-O 的 BOP 发布**：[BOP 条目](https://bop.felk.cvut.cz/datasets/#LM-O)写明 `license: CC BY-SA 4.0`；固定版本 [HF README](https://huggingface.co/datasets/bop-benchmark/lmo/blob/ecf444aa4ac48ce80a191c2266ad9deec8f5eb23/README.md)为 `license: cc-by-sa-4.0`。条款见 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)。不能把 LM 的 BY 许可直接套到 LM-O 的 BOP 包。
- **LM-O 存档元数据存在标示差异**：[作者项目页的 Occlusion Dataset](https://hci.iwr.uni-heidelberg.de/vislearn/research/scene-understanding/pose-estimation/#ECCV14)与 BOP 一致标示 `CC BY-SA 4.0`，作者还建议使用 BOP 的修订版本。另一方面，BOP 所链接的 [heiDATA 原始 DOI 页面](https://heidata.uni-heidelberg.de/dataset.xhtml?persistentId=doi:10.11588/data/V4MUMX)显示 `Licensed under a Creative Commons Attribution 4.0 International License.`，与作者页/BOP/HF 的 BY-SA 标示不同。本次只记录元数据不一致，未下载核对包内说明，也未获得发布方澄清；不能据此宣称原始 LM-O 统一适用 BY，或 BOP 的 LM-O 档案适用更宽松条款。后续若需要再发布原始数据或衍生数据，应先核清具体文件的适用许可。
- **ITODD**：[MVTec 原站](https://www.mvtec.com/research-teaching/datasets/mvtec-itodd)原文：`The data is released under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License (CC BY-NC-SA 4.0).` 并写明 `In particular, it is not allowed to use the dataset for commercial purposes.` [BOP 条目](https://bop.felk.cvut.cz/datasets/#ITODD)同样链接 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)，注明 `custom license available upon request`。本项目面向工业应用并不使这个数据集自动商业可用。HF 的 ITODD README 在本次固定提交下是空文件，不能以它缺少许可字段推断无许可限制。

LM-O 作者项目页的原文分别是 `We provide the dataset under the CC BY-SA 4.0 license.` 和 `The reworked version contains all data (images, poses, 3D models of objects) and some annotation errors have been corrected. We advise to use the reworked version of the dataset.` 这也说明原始版与 BOP 修订版不能未经核对就混用标注。heiDATA 的 [官方 metadata API](https://heidata.uni-heidelberg.de/api/datasets/:persistentId/?persistentId=doi:10.11588/data/V4MUMX)在 `termsOfUse` 中同样写 BY 4.0；差异尚未得到发布方解释。

数据许可与本仓库源代码许可分开处理。本文没有引入外部图像或将它们并入代码许可。

## 官方档案大小：只读元数据，未下载

下表是官方 HF Git/LFS tree API 声明的**压缩包精确字节数**，不是已采集量、解压占用或实际网络传输量。本次只读取小型 JSON、README、网页和源码，没有请求 ZIP、Range 或图像。档案哈希来自远端 LFS 声明，本次没有验证完整档案哈希。

| 仓库及固定提交 | 档案 | 字节数 |
| --- | --- | ---: |
| LM `750b2f78ed1093f789086b17ab43fe8517d51aed` | `lm_base.zip` | 10,988 |
| 同上 | `lm_models.zip` | 13,721,196 |
| 同上 | `lm_train.zip` | 854,182,242 |
| 同上 | `lm_train_pbr.zip` | 21,797,196,200 |
| 同上 | `lm_test_all.zip` | 10,307,252,420 |
| 同上 | `lm_test_bop19.zip` | 1,677,069,087 |
| LM-O `ecf444aa4ac48ce80a191c2266ad9deec8f5eb23` | `lmo_base.zip` | 5,684 |
| 同上 | `lmo_models.zip` | 5,367,178 |
| 同上 | `lmo_train.zip` | 355,285,200 |
| 同上 | `lmo_test_all.zip` | 720,158,597 |
| 同上 | `lmo_test_bop19.zip` | 117,550,985 |
| ITODD `55b4e3c777acfa7c0cf9091d0cfc226f06af8cd6` | `itodd_base.zip` | 4,042 |
| 同上 | `itodd_models.zip` | 5,504,325 |
| 同上 | `itodd_train_pbr.zip` | 36,509,921,761 |
| 同上 | `itodd_val.zip` | 195,550,980 |
| 同上 | `itodd_test_all.zip` | 2,542,223,067 |
| 同上 | `itodd_test_bop19.zip` | 2,542,223,067 |

固定版本的 API 证据：

- [LM tree JSON](https://huggingface.co/api/datasets/bop-benchmark/lm/tree/750b2f78ed1093f789086b17ab43fe8517d51aed?recursive=false&expand=false)
- [LM-O tree JSON](https://huggingface.co/api/datasets/bop-benchmark/lmo/tree/ecf444aa4ac48ce80a191c2266ad9deec8f5eb23?recursive=false&expand=false)
- [ITODD tree JSON](https://huggingface.co/api/datasets/bop-benchmark/itodd/tree/55b4e3c777acfa7c0cf9091d0cfc226f06af8cd6?recursive=false&expand=false)

LM-O 的官方 PBR 下载链接实际指向 **LM 的 `lm_train_pbr.zip`**，不能再算一份独立的训练图。`*_test_bop19.zip` 是挑战用测试子集，不能与 `*_test_all.zip` 相加当作独立样本。ITODD 两个 test ZIP 大小相同，但 LFS 哈希不同，不能从大小相同推断内容相同；二者 test GT 均不能假定公开。

## LM / LM-O 的重叠与泄漏控制

[BOP 官方原文](https://bop.felk.cvut.cz/datasets/#LM-O)：

> Provides additional ground-truth annotations for all modeled objects in one of the test sets from LM.
>
> Note the PBR-BlenderProc4BOP training images are the same as for LM.

固定版本 toolkit 又声明 LM-O test `scene_ids = [2]`。因此未来采集时至少要建立“原始数据源 + 原始序列/物理场景 + 原始图像 ID + 传感器”的来源键，不把文件夹名 `lm` 和 `lmo` 当成独立身份。未解析、核实原始映射前，将 **LM scene 2 与 LM-O 整个 test split 归入同一泄漏组**。本次未逐帧比对，也未取得 scene 2 与 benchvise 名称的官方明确映射，不声称已证明两个 ZIP 的像素字节一一相同。

推荐约束如下，均尚未执行：

1. 同一原始序列只进入一个 development / holdout 分组；相邻视频帧不能随机散到不同 split。
2. 如果用 LM scene 2 建模板、挖难例或选阈值，则其重标注版本 LM-O 不再作为独立留出；反向同理。可将 LM-O 整个序列预留为遮挡压力测试，但不能同时宣称 LM scene 2 提供独立调参样本。
3. 共享 PBR 图像、相同源图的裁剪、颜色变化、旋转/缩放衍生图沿用同一来源键，不跨 split。训练集允许共享时也必须披露，不能把相同训练证据当成两次独立验证。
4. 同时报告对象数、原始来源族数、独立场景/序列数、帧数与派生图数。多个物体或许多相邻帧能增加检查量，但不会自动增加独立来源数。

ITODD / ITODD-MV 也需要相同场景聚类。toolkit 的 ITODD val/test 都使用打包 scene `1`，这不足以证明所有帧属于一个物理场景，也不足以证明两 split 相互独立；需以后查官方原始场景/传感器映射。

## GT 框、负帧和旋转/尺度能验证什么

依据固定版本的 [BOP 格式文档](https://github.com/thodan/bop_toolkit/blob/cea62d651c7e395b2e1962b9749e4e89693c6ac4/docs/bop_datasets_format.md)：

- `scene_gt.json` 为逐图实例列表，含 `obj_id`、`cam_R_m2c`、`cam_t_m2c`。mask 文件名的 `GTID` 是该列表的实例索引，不是对象 ID。
- `scene_gt_info.json` 的 `bbox_obj` 是完整投影 silhouette 的 `[x,y,width,height]`，`bbox_visib` 是可见部分的框，原点为左上角；不能混成同一定位指标。`visib_fract = px_count_visib / px_count_all`。
- `mask` 与 `mask_visib` 分别表示完整 silhouette 和可见部分，但格式将它们列为 **optional**；正式采集仍需核实所选 split 中实际存在且索引一致，不能因符合 BOP 格式就假定每个包都有它们。
- `cam_K` 是相机内参；`depth_scale` 将深度图转为 mm。`cam_R_m2c` / `cam_t_m2c` 是模型到相机的 3D 变换，平移单位 mm。

**固定负帧可以设计，当前没有给出负帧 ID 或保证数量。** 未来必须先确认某个 split 对所测目标的标注覆盖完整，再从完整 `scene_gt.json` 确认目标不存在，并预先冻结来源键与 frame ID。LM 每图只标注一个实例，尤其不适合从其他序列中机械推断目标缺失。`test_targets_bop19.json` 是评测请求列表，缺少某个请求、GT 文件缺失或数组解析失败均不等于负帧；低可见度被 ignore 的实例也不能变成负例。LM-O 各目标是否有足够真负帧、ITODD validation 中的目标缺失数量，本次均未知。没有真负帧时只报告可验证的召回/定位，或另行收集已确认的负样本，不制造负例。

**可以用官方框测 2D 定位，不能直接把 6D 姿态当成 2D 旋转/尺度 GT。** 离面转动、透视、物体对称性和深度变化都会改变 2D 轮廓。后续若要测试匹配器的平面旋转与尺度鲁棒性，可在预先固定且与调参来源隔离的源帧上，施加已知 2D 仿射变换，并同步变换 mask/实例坐标，单独报告角度、尺度、位置误差和失败率。所有派生图随源帧分组；重算变换后的轴对齐框时以变换后的 mask/几何为准。这种测试是**受控变换测试**，不能替代真实跨视角或产线泛化。

## 下一轮采集前仍需解决

当前只完成来源筛选，下面事项尚未完成：

1. 核清 LM-O 原始发布与 BOP 发布的许可差异；固定要使用的具体分发版本。
2. 以后按受限下载方案获取官方小型目录/GT，核对实际帧数、完整标注覆盖、mask 可用性、LM/LM-O 原始序列映射与 ITODD 物理场景映射；不得将未公开的 test GT 当作已获得。
3. 在运行匹配器之前确定对象、来源分组、可见度 ignore 规则、正/负帧数量和样本预算，另立采集 manifest 与评测冻结记录。不能根据检测效果挑选样本，也不改动当前 T-LESS 留出。
4. 对每个新来源同时保存逐帧定位/召回/误检计数与计时；先证明标签和坐标适配正确，再讨论算法改进。本文没有任何新数据的结果、速度收益或工业准确率结论。
