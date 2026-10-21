# 来源与第三方声明

本文件记录本仓库中已知的代码、依赖、参考资料和验证素材来源，以及尚未核实的事项。它不替代各文件已有的版权与许可证通知，也不为未明确授权的素材新增再分发许可。

## 项目来源与本地维护历史

本项目基于 [`meiqua/shape_based_matching`](https://github.com/meiqua/shape_based_matching) 的本地源码快照继续开发。该来源由随快照保留的 README 中的项目、分支和 issue 链接识别。目前尚未核实该快照对应的上游提交，也未核实快照中的所有文件是否均由该上游项目原创。

当前 Git 历史从本地基线提交 `2a914712a0bea312f2af2e94d56ea69e7609a990` 开始，不包含此前的上游 Git 提交历史。该基线还包含此前开展的 LED/SMD 本地实验，不能等同于未经修改的上游版本。README 中的 `fc3560a1a3bc7c6371eacecdb6822244baac17ba` 是原文提供的旧版本参考链接，不是已核实的本地快照来源提交。本地修改和验证记录见 [版本说明](docs/optimization_versions.md)。

本仓库由当前维护者独立维护，与原项目作者、OpenCV、MVTec/HALCON 无隶属或背书关系。引用相关项目、论文、产品名称或文档，不表示获得其认证或提供其完整功能。

## 根许可证

随原始快照提供的 [LICENSE](LICENSE) 为 BSD 2-Clause License，其原始版权行是 `Copyright (c) 2018,`，未填写版权持有人姓名。本仓库保留该许可证原文，不推测或补造原始版权持有人，也不以当前维护者的身份替换原有通知。

源代码再分发须按该许可证保留版权通知、条件和免责声明；二进制再分发须在随附文档或其他材料中重现这些内容。第三方组件仍适用各自的许可证。根 LICENSE 不应被解读为将本文件列出的第三方代码、图片、模型数据、论文或其他资料统一重新许可为 BSD。

## MIPP 与 SIMD 数学代码

本仓库包含 [MIPP](https://github.com/aff3ct/MIPP) 的源码快照。继承的 README 说明该项目曾为部分 `uint8_t` 指令扩展 MIPP；此处的副本不能视为未经修改的上游发行版，准确的上游版本和提交尚未核实。

以下通知保留在对应源文件中，分发时应一并保留。表格是来源索引，不替代文件中的完整许可文本。

| 文件 | 文件中的声明 |
| --- | --- |
| [`MIPP/mipp.h`](MIPP/mipp.h) | 完整 MIT License；`Copyright (c) 2016 MIPP`；另有作者 Adrien Cassagne 的文件说明。 |
| [`MIPP/math/sse_mathfun.h`](MIPP/math/sse_mathfun.h)、[`.hxx`](MIPP/math/sse_mathfun.hxx) | `Copyright (C) 2007 Julien Pommier`；完整 zlib-style 许可。 |
| [`MIPP/math/neon_mathfun.h`](MIPP/math/neon_mathfun.h)、[`.hxx`](MIPP/math/neon_mathfun.hxx) | `Copyright (C) 2011 Julien Pommier`；完整 zlib-style 许可。 |
| [`MIPP/math/avx_mathfun.h`](MIPP/math/avx_mathfun.h)、[`.hxx`](MIPP/math/avx_mathfun.hxx) | `Copyright (C) 2012 Giovanni Garberoglio`；完整 zlib-style 许可及机构信息；注明基于 Julien Pommier 的 `sse_mathfun.h`。 |
| [`MIPP/math/avx512_mathfun.h`](MIPP/math/avx512_mathfun.h)、[`.hxx`](MIPP/math/avx512_mathfun.hxx) | `Copyright (C) 2017 Adrien Cassagne`；标明 MIT license；注明基于 Julien Pommier 的 `sse_mathfun.h`。 |

MIT 许可要求在软件的副本或实质部分中保留版权与许可通知。上述 zlib-style 许可还要求不得歪曲来源、修改后的源码须明确标记、不得从源码发行物中移除或更改原通知。不能仅以 MIPP 的 MIT 声明概括所有嵌套数学代码的许可。

## OpenCV 与 LINEMOD

继承的 README 将本实现与 OpenCV LINEMOD 源码进行比较，并说明了移除深度模态、特征数量、姿态模板、特征选择和 SIMD 等修改。这一说明记录了算法与实现来源关系，但目前尚未核实所参考或改编的 OpenCV 源码的准确版本、提交和对应通知。不能将当前版本 OpenCV 的许可证直接追溯套用于历史来源代码；该部分来源核实仍待补充。

构建脚本通过 `find_package(OpenCV 3 REQUIRED)` 查找外部 OpenCV。本地验证记录中使用过 OpenCV 4.12；这不表示每个构建都使用相同版本，也不改变历史代码的来源。使用或分发时，应以实际采用的 OpenCV 版本及其发行包中的 LICENSE、NOTICE 和所包含第三方组件通知为准。若分发链接 OpenCV 或其他运行库的二进制，还应随该发行物提供其适用通知；本文件不是完整的二进制依赖许可清单。

## 论文、文档与继承的示例素材

继承快照中的参考资料包括：

- [`Gradient Response Maps for Real-TimeDetection of Textureless Objects.pdf`](Gradient%20Response%20Maps%20for%20Real-TimeDetection%20of%20Textureless%20Objects.pdf)：README 中的 LINEMOD 论文参考。
- [`Transforms in shape-based matching.pdf`](Transforms%20in%20shape-based%20matching.pdf)：README 中的变换说明参考。
- README 对 *Machine Vision Algorithms and Applications* 第 3.11.5 节的引用，以及指向 [HALCON 文档](https://www.mvtec.com/products/halcon/documentation/#reference_manual) 的链接。
- [`match.png`](match.png) 和 `test/` 下的示例图片、结果图、模板及相关数据。

这些文件随本地快照继承。目前未逐项核实其作者、原始发布位置或独立的再分发授权；将其保留或引用不构成对其版权归属的声明。根 BSD 许可证不能作为第三方论文、教材内容、产品文档截图或示例图片已经取得再分发许可的证明。引用资料的版权和使用条件应以各自权利人的原始声明为准；确认到具体来源或许可后应补充本文件。

## 本地 LED/SMD 数据与派生结果

`LED/1.bmp` 至 `LED/8.bmp` 和 `LED/ku.smd` 是用户提供用于本地验证的数据。当前记录未明确其原始制作者、权利人或单独的数据再分发许可证；用户授权公开当前项目，不等同于本仓库能够为其中的第三方内容另行授予许可。

由这些数据生成的预览、模板图、轮廓图及匹配结果图位于 `artifacts/led_match/`、`artifacts/led_pyramid_compare/` 和 `artifacts/response_optimization/led_results/` 等目录。派生图的生成过程和算法修改可在实验记录中追溯，但生成结果不会消除输入素材已有的权利限制。涉及这些素材的再使用或再分发，应依据其实际权利和授权范围判断，不能仅依赖根 LICENSE。

本地 SMD 读取实验只针对所提供的 `ku.smd` 文件布局进行了验证。文件扩展名和实验结果不构成通用 HALCON、CKVision 或其他厂商 SMD 格式兼容性声明，也不代表获得相关厂商的授权或认可。

## 本地磁片样本与验证记录

`磁片/M01.bmp` 至 `M07.bmp` 和 `磁片/moban.smd` 同样由用户提供用于本地验证，尚无单独的数据再分发许可证。原始磁片文件及派生图片保留在本地，不包含在本次公开提交中。`artifacts/magnet_match/` 保存样本 SHA、结构与轮廓数值、人工粗框、匹配结果、复现程序及独立核验；这些数值记录不为原始素材或其派生数据新增许可。

`moban.smd` 中的内嵌来源图与 M01 像素完全相同，M01 因此只算来源自检。该文件的字段解释与兼容性结论仅针对已记录 SHA 的样本，不适用于任意 SMD 或第三方软件格式。六张其他图均为开发中已观察的同组正样本，不能作为独立留出准确率证明。

## 新增的 T-LESS 公开验证子集

数据来自 T-LESS / BOP 官方链接的固定版本，适用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。
署名：T. Hodaň, P. Haluza, Š. Obdržálek, J. Matas, M. Lourakis, X. Zabulis，
“T-LESS: An RGB-D Dataset for 6D Pose Estimation of Texture-less Objects”，IEEE WACV 2017。
本项目选择少量原始 RGB、mask 和标注并产生简化索引；原始成员未修改，外部图片保存在
忽略的本地缓存中。数据不适用本仓库的根 BSD 代码许可。

官方出处、固定提交、抽样规则、下载范围、逐文件 CRC/SHA 及适用边界见
[tiny 数据说明](docs/datasets/public-dataset-survey.md)、[扩展获取报告](docs/datasets/tless-expanded-acquisition.md)、
[来源 manifest](artifacts/public_datasets/tless_tiny_manifest.json)和
[扩展 manifest](artifacts/public_datasets/tless_expanded_manifest.json)。

## 后续补充原则

如取得准确的上游提交、历史代码来源、资料原始链接或素材授权，应在保留已有通知的基础上补充记录。新增贡献的版权声明仅覆盖相应新增贡献，不替代继承代码及第三方素材的声明。本文件中“尚未核实”的事项表示当前证据不足，不是对侵权或授权状态的确定判断。
