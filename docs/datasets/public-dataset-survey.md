# 公开工业物体数据与可复现小子集

核查日期：2026-10-21。选用 **T-LESS 的真实 Primesense 图像**，从 BOP 官网直接链接的
`bop-benchmark/tless` Hugging Face 仓库按 HTTP Range 获取固定小子集。它有明确的
CC BY 4.0 许可、真实杂乱场景、逐实例 2D 框和可见区域 mask，可以建立比原有演示图更严格的
定位与误检检查。这个 tiny exploratory slice 不能代表完整 T-LESS 或工业产线的准确率。

## 官方来源与许可

| 数据 | 官方来源与许可证据 | 本次处理 |
| --- | --- | --- |
| T-LESS | [原项目](https://cmp.felk.cvut.cz/t-less/)、[原下载页](https://cmp.felk.cvut.cz/t-less/download.html)、[BOP 官方列表](https://bop.felk.cvut.cz/datasets/#T-LESS)。原项目明确写明 “This work is licensed under Creative Commons Attribution 4.0 International.”，BOP 同样链接 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。 | 选用。保留署名、许可链接及子集/索引变更说明。数据没有并入本仓库代码许可。 |
| MVTec AD metal_nut | [官方介绍及许可](https://www.mvtec.com/research-teaching/datasets/mvtec-ad)、[分类下载页](https://www.mvtec.com/research-teaching/datasets/mvtec-ad/downloads)。许可为 **CC BY-NC-SA 4.0**，官网明确禁止商业使用。metal_nut 页面标示 157 MB；transistor 为 384 MB。 | 未下载。metal_nut 官方 mydrive 链接在本次核查时 GET、HEAD 均返回 404；没有换用不明镜像。即使重新可用，AD 的异常 mask 也不是物体姿态或完整实例 mask。 |
| MVTec ITODD / BOP | [BOP 官方列表](https://bop.felk.cvut.cz/datasets/#ITODD)链接 **CC BY-NC-SA 4.0**，注明可另询定制许可。 | 备选。`itodd_val.zip` 为 195,550,980 bytes；完整测试包为 2,542,223,067 bytes。未下载，不将其非商业许可描述为商业可用。 |

T-LESS 应署名：T. Hodaň, P. Haluza, Š. Obdržálek, J. Matas, M. Lourakis, X. Zabulis,
“T-LESS: An RGB-D Dataset for 6D Pose Estimation of Texture-less Objects”, IEEE WACV 2017。
CC BY 4.0 要求署名、提供许可链接及说明修改；完整条款以许可正文为准。

BOP 官网直接列出的数据仓库提供 HTTPS 下载，使用固定提交
`5fd309a04476a842d93abfb584fba9ee7caecdf1`，而不是不明镜像。

| 官方 BOP 档案 | 完整压缩包精确字节数 | 本次用途 |
| --- | ---: | --- |
| [`tless_train_primesense.zip`](https://huggingface.co/datasets/bop-benchmark/tless/resolve/5fd309a04476a842d93abfb584fba9ee7caecdf1/tless_train_primesense.zip) | 2,486,152,818 | 只读 ZIP 目录及 object 1 的连续数据块，保留指定 72 个视角的 RGB/mask 和官方 JSON。 |
| [`tless_test_primesense_bop19.zip`](https://huggingface.co/datasets/bop-benchmark/tless/resolve/5fd309a04476a842d93abfb584fba9ee7caecdf1/tless_test_primesense_bop19.zip) | 825,276,992 | 只读 ZIP 目录、4 个场景的 JSON 和指定 32 个图像块。 |

完整档案均没有下载。脚本要求服务器返回精确的 HTTP 206 和 `Content-Range`，拒绝把忽略
Range 的全包响应保存到本地；默认数据响应体传输硬上限为 190,000,000 bytes。
精确的实际传输字节、每次范围、保留文件大小、CRC32、SHA-256 和 ZIP 内原路径见
[`tless_tiny_manifest.json`](../../artifacts/public_datasets/tless_tiny_manifest.json)。该计数包含 ZIP
目录及取图块中未保留的 depth 数据，排除 HTTP/TLS 头和之前只读调查请求。
完整包 SHA-256 来自官方仓库的 LFS 元数据；由于没有取完整包，**未声称验证了全包哈希**。
保留的每个原始文件都验证了 ZIP CRC32，并另算 SHA-256。
本次成功获取实际传输了 **87,594,592 bytes**，保留 663 个原始成员、共 **24,534,389 bytes**。
页面许可原文片段、请求时间、页面哈希和官方文件大小另见
[`source_evidence.json`](../../artifacts/public_datasets/source_evidence.json)。

## 冻结取样与本地路径

外部图像与原始标注保存在被局部 `.gitignore` 排除的 `datasets/tless_tiny/`；不提交外部图片。
脚本和来源 manifest 可进 Git。官方图片及 JSON 原样保存，`index.json` 是本项目产生的简化索引。

目标类别是 `obj_id = 1`。训练取 `train_primesense/000001` 的图像 ID
`range(0, 1296, 18)`，共 72 个真实视角，每个都有 RGB、完整 silhouette mask 和可见 mask。

测试对每个指定场景的 50 个官方 BOP19 目标帧按图像 ID 排序，固定取 rank
`[0, 7, 14, 21, 28, 35, 42, 49]`。取样在运行任何匹配器之前确定。

| Split | Scene | 对 object 1 的角色 | 精确图像 ID |
| --- | ---: | --- | --- |
| development | 5 | 正例，1 实例/图 | 7, 70, 127, 215, 293, 353, 436, 493 |
| development | 2 | 负例，GT 无 object 1 | 3, 92, 153, 214, 295, 374, 446, 494 |
| heldout | 9 | 正例，3 实例/图 | 0, 70, 147, 217, 278, 356, 431, 495 |
| heldout | 3 | 负例，GT 无 object 1 | 5, 55, 144, 225, 292, 354, 432, 493 |

共 32 张测试图，development / heldout 各 16 张；16 张正例、16 张负例。
两个 split 使用不同物理场景，帧跨视角分布，仍然只有两个正例场景和一个目标类别。
development 可选阈值、模板数、尺度范围和 NMS 参数；冻结这些参数后再报告 heldout。
不要依据 heldout 结果反复调参后继续称其为独立留出结果。

## 标注语义与适用边界

格式来源：[BOP dataset format](https://github.com/thodan/bop_toolkit/blob/master/docs/bop_datasets_format.md)。

- `scene_gt.json` 的列表位置是该图的 `gt_id`；它与 `scene_gt_info.json` 的同位置和
  `mask/<image_id>_<gt_id>.png` 对应，不能按类别 ID 当作实例下标。
- `bbox_obj` 和 `bbox_visib` 都是原始 RGB 像素坐标的 `[x, y, width, height]`，原点在左上角，
  没有做缩放。`bbox_obj` 围住完整投影轮廓，可能部分超出图像；`bbox_visib` 围住可见轮廓。
  二者语义不同，评估必须明确选哪一种。
- `mask` 是官方物体 silhouette mask，`mask_visib` 是其可见部分，非零表示前景。
  `visib_fract` 是官方可见比例。PNG 尺寸、实例数量、SHA 与 CRC 均由准备脚本检查。
- `cam_R_m2c` / `cam_t_m2c` 是模型到相机坐标的 3D 旋转/平移，平移单位为 mm。
  它们不是 2D 平面旋转或缩放真值；简化索引故意不输出这两个字段。
- 该子集可以测真实物体存在/缺失、全物体或可见物体的框定位、多实例召回、负例误检；
  如果匹配器输出变换后的 mask，还可另报 silhouette 或可见区域 IoU。
- 当前匹配器是离散 2D 模板方法。单个模板无法覆盖任意离面视角；多视角模板缺失带来的漏检
  是有意义的失败，不能以“只保留容易检测的视角”消除。
- 该子集不能给出真实 2D 角度/尺度误差、6D 姿态准确率、完整 T-LESS 排名、缺陷检测能力，
  或生产线的误检概率。它也没有覆盖目标工件、相机和产线条件的代表性抽样。

## 可运行的数据准备与读取

在仓库根目录运行，仅需 Python 3.9+ 标准库（本环境为 3.12.10）：

```powershell
python tools/datasets/fetch_tless_tiny.py
python tools/datasets/fetch_tless_tiny.py --verify-only
```

第一次联网取小子集并输出来源 manifest；已有完整 cache 时离线验证。第二条命令逐文件复验
CRC/SHA/大小、图片尺寸，并从官方 JSON 重建索引核对。它不会运行匹配或 CPU 性能测试。

`datasets/tless_tiny/index.json` 中的路径相对索引所在目录，`training` 和 `test` 分别是样本数组。
每个样本含 `rgb`、`width`、`height`、`scene_id`、`image_id`、`split`、`target_present` 和
`instances`；每实例含 `obj_id`、`gt_id`、`bbox_obj`、`bbox_visib`、`visib_fract`、
`mask` / `mask_visib` 路径，C++ 可以直接据此读取图像、训练 mask 与 GT 框。

```python
import json
from pathlib import Path

root = Path("datasets/tless_tiny")
index = json.loads((root / "index.json").read_text(encoding="utf-8"))
template = index["training"][0]
template_rgb = root / template["rgb"]
template_mask = root / template["instances"][0]["mask"]
heldout = [row for row in index["test"] if row["split"] == "heldout"]
for row in heldout:
    targets = [a for a in row["instances"] if a["obj_id"] == 1]
    print(root / row["rgb"], [a["bbox_obj"] for a in targets])
```

## 建议的首次真实定位评估

以 72 个训练视角的官方 mask 建模板，保留原图裁剪偏移，使用 development 选择尺度范围、
分数阈值与 NMS。固定后在 heldout 图上做一次评估，保存逐图候选、分数、模板来源 ID、
预测框及可视化，便于检查模板裁剪/坐标转换错误。

建议首先报告 `bbox_obj` IoU≥0.5 的一对一多实例 precision / recall，另列
`visib_fract>=0.5` 与更低可见比例的召回。低可见度目标应明确保留还是设为 ignore，
不能把忽略目标上的匹配算成负例。负例场景报告每图误检数和出现至少一个误检的图数。
如果另报 `bbox_visib`，在列名中标出其语义。每图、每场景的原始计数应与汇总一起保存。

数据准备脚本只验证来源、缓存与标注读取。随后使用独立适配器完成的首轮 development 检测
暴露了低特征模板的严重误检和原有全局去重的不确定性；heldout 尚未运行。
原始数值保存在 [失败开发记录](../../artifacts/public_evaluation/v10_development_failed_strict_equivalence/development/metrics.json)，
去重修复与回归见 [确定性验证](../../artifacts/match_consolidation/README.md)。扩展评测适配器正在独立整理；
不能把准备成功或 development 指标称为工业准确率。
