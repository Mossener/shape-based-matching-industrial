# V31 实际执行与发布结果

2026-10-23：V31 的训练、全模板几何、完整开发质量、配对计时及独立数值审计均已完成。
**主准确率假设失败，生产核心仍为 V11。** 本阶段公开可复算的实验结果和失败记录；
不会因数值审计通过而推广候选方案。

## 算法变化与结论

保留 RGB 梯度方向，在相同候选池上比较确定性的 pooled 采样 P 与固定轮廓/内部配额采样 B。
原 RGB bank 为 C0，B 为预指定主臂。六对象、400 张开发图的 allGT TP/FP/FN 分别为
C0 `215/42112/185`、P `178/10102/222`、B `187/11116/213`。
B 的召回率下降 7 个百分点；其减少的 30,996 FP 伴随 59 个原检出身份丢失和 31 个新增。
预定 `TP >= 215 && FP < 42112` 门槛失败，P 不替换主臂结论。

29,952 次固定计时调用及独立复算完成，B/C0 完整调用成对耗时比中位数为
0.809204 / 0.831725（fallback / fused）。对象 1 变慢，部分帧和尾部退化。
速度与召回损失必须一起解释，不能据此声称整体工业识别能力提升。
详见[质量报告](QUALITY_RESULTS_V31.md)和[计时报告](TIMING_RESULTS_V31.md)。

## 已完成的验收

| 阶段 | 实际范围 | 结果与入口 |
| --- | --- | --- |
| 原始训练 | 20,736 个姿态，P/B 共 41,472 次模板尝试，失败记录保留 | [训练验收](TRAINING_ACCEPTANCE.json) |
| 独立训练 | 完整候选池、采样、层、bank 和失败重算 | [v2 回执](independent/evidence/full_training_audit_v2/RUNNER_RECEIPT.json) |
| 共同几何 | 18 个 bank，59,623 个模板，119,246 层，2,823,355 个特征 | [训练/几何聚合](ACCEPTED_TRAINING_GEOMETRY_REPORT.json) |
| 完整开发质量 | 14,400 次调用，三臂 × 双路径 × 六对象 × 400 帧 | [development 冻结](quality/run_development_v1/QUALITY_STAGE_FREEZE.json) |
| 独立质量 | 全 raw、分数位、NMS、GT、身份与负组合 | [质量验收](quality/QUALITY_AUDIT_ACCEPTANCE.json)，numeric=true，primary=false |
| 配对计时 | 29,952 calls；27,648 formal 与 paired rows | [独立 timing 结果](independent_timing/real_timing_audit_v1/result.json) |
| 训练证据运输 | 46 个成员，235,876,886 stored bytes | [无损 export 清单](public_training_export_v1/EXPORT_MANIFEST.json) |
| 全新还原验收 | 独立遍历全部恢复文件，对原 provenance 逐一核字节/SHA，690,835,424 bytes | [还原验收](PUBLIC_EXPORT_ACCEPTANCE.json) |

还原复用了 exporter 的解码器，随后由另一段逻辑对原训练 provenance 独立核完整名字清单和全部
文件字节；这是运输可逆性验证，不是重新训练或新的数值算法审计。恢复副本只保留本地；
发布清单包含所有 46 个 stored 成员、完整映射及验收。71,295,252 字节的几何报告发布原文件。
编译器和运行库二进制仅以来源 pin 引用；公开数据图像仍通过原数据集说明获取。

[继承数值依赖检查](INHERITED_PUBLIC_NUMERIC_AVAILABILITY.json)逐字节核对了 9,813 个既有文件，
共 41,150,524 bytes，同时计算 Git blob ID 与已发布 HEAD 核对。C0 bank 和既有 raw 无需
重复打包。当地数据获取索引 `datasets/tless_expanded/index.json` 只保留外部 pin 声明，
本检查不读取或发布它；其他机器需按数据获取说明重建本地数据布局，不能声称所有依赖已内嵌。

## 保留的失败与能力边界

首次完整训练审计因入口输出目录问题失败；首次独立质量审计因共享历史 closure 的重复声明
被拒。原失败、consumed reservation 和日志均保留，后继修正独立编号；未重跑原训练或质量来
替换失败结果。[质量入口修正说明](QUALITY_AUDIT_ENTRYPOINT_FAILURES.md)区分合同缺陷与识别结论。
源码 RED/GREEN 与 mutation 的历史快照按各自回执保留，不将旧源码 pin 强加给当前文件。

已定位的历史源码按原 pin 保存；首次失败训练审计的旧 runner（12,482 bytes）、根工具中间
GREEN 的旧 helper（10,113 bytes）及一次早期审查文档（3,606 bytes）未定位到精确副本。
清单的 `unavailable_historical_sources` 明确保留这些引用，不宣称对应历史过程可完整重放。
最终成功审计和根工具验收使用各自最终源码与完整回执，不由缺失的中间版本替代。

公开源码检查点 `5acb270` 已先行保存，实际证据用新显式清单发布，旧检查点和冻结回执不重写。
发布校验须分别检查磁盘字节和 Git index 字节；校验结果不代替上表的算法数值验收。

新克隆可用 `preserve_training_evidence.py restore --export public_training_export_v1 --output run_training_v1`
还原原训练数值文件名；这些参数相对于本实验目录，输出必须不存在。原审计记录保留当时的
绝对路径和精确字节，当前验证器也检查 canonical 路径；尚未提供跨根目录的自动重映射入口，
因此运输完整性通过不等于任意路径/平台均能直接重跑整套历史审计。

本轮只用既有 development。留出 scenes `[11,14,15,16,17,18,19,20]` 及对象 25/29 继续封存。
私有磁片/SMD 图像与派生图不公开；已有磁片同组正图回归单列，不能外推通用准确率。
下一轮[有序轮廓对应提案](../../docs/superpowers/plans/2026-10-23-ordered-contour-verifier.md)
尚未产生真实质量结果；计划先保留完整 C0 提议，检验连接、顺序和链内唯一对应的判别力。
