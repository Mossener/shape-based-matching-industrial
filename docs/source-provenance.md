# 来源与维护边界

本项目由 [Mossener](https://github.com/Mossener) 独立维护，目标是把已有的梯度方向模板匹配代码逐步完善为可验证、可维护的工业视觉轮廓定位组件。

## 上游来源

- 原项目：[meiqua/shape_based_matching](https://github.com/meiqua/shape_based_matching)。
- 算法路线：原 README 将其描述为沿用 LINEMOD 思路的 shape-based matching 实现，并讨论相对于 OpenCV LINEMOD 的修改。
- SIMD 依赖：[MIPP](https://github.com/aff3ct/MIPP)，当前仓库保留上游继承的本地头文件快照；其精确版本未核实。
- 根源码许可：BSD-2-Clause，原文见 [LICENSE](../LICENSE)。版权行保留导入时的内容，不凭推断补写原版权人。

本项目与原作者、OpenCV、MVTec/HALCON 或其他商业视觉软件没有隶属关系，不表示相关项目的背书，也不声称复现任何商业产品的全部功能。

## 当前历史能证明什么

当前仓库从本地源码快照初始化，根提交为：

```text
2a914712a0bea312f2af2e94d56ea69e7609a990
2026-10-21 — baseline: preserve original matcher and LED pyramid experiments
```

该提交包含继承的项目文件和当时已有的本地 LED 实验，不能把整个提交当作纯上游版本。它不包含更早的上游 Git 提交历史；导入快照对应的上游 commit、下载时间和 MIPP 版本尚未核实。

[README.upstream.md](../README.upstream.md) 保存根提交中的 README 字节，表示导入时保留的说明，不声称它与当前上游 README 相同。里面的 ICP/subpixel/sim3 等链接指向上游其他分支，不证明这些功能存在于当前主线。

两份用于验证的匹配器基线分别为：

- [响应优化 baseline](../artifacts/response_optimization/baseline/manifest.json)：本地优化前的匹配器源文件和字节哈希。
- [搜索优化 baseline](../artifacts/search_optimization/baseline/manifest.json)：响应优化 V4 的匹配器源文件和字节哈希。

这些基线用于本仓库内部的结果和性能对照，不充当上游 commit 身份证明。

## 本仓库的新增工作

- 针对给定 `LED/ku.smd` 的特征适配和 LED 金字塔实验。
- 可分离方向扩散、响应查表与内存重排融合、预处理缓冲区复用。
- 整数局部最大值、直接 8U 搜索、每 OpenMP worker 搜索缓冲区。
- `MatchWorkspace`、独立开关、分阶段计时及旧接口保留。
- 独立内核测试、不可变基线对照、搜索消融、运行环境/输入哈希和审计文档。
- 工业化路线、维护规范、来源声明及公开仓库整理。

各项修改和实测效果见 [optimization_versions.md](optimization_versions.md)，可通过 Git 提交与 `optimization-v*` 标签回溯。现有实验范围和不足在报告中保留，后续不得将“结果一致”解释为“工业识别准确率达标”。

## 外部代码、文献与数据

第三方通知及资产来源另见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。根许可证不用于重新授予第三方作品、论文或外部数据的权利。维护者应在引入新代码、样本或模型时记录来源和适用许可；尚未核实的信息保持明确标注，不能以项目名义补造授权。
