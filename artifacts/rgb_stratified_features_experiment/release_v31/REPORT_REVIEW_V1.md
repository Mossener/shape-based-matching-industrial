# V31 发布文档轻量审查

2026-10-23。结论：本次核对未发现 V31 计时表格、质量汇总、恢复量或不推广生产结论的实质性错误。
修正一处措辞：质量报告末句由“不宣称工业泛化或速度收益”收窄为“不宣称工业泛化或普遍加速”，
使其与已完成的固定开发帧计时结果一致。该修改不改变准确率失败或生产默认仍为 V11 的结论。

## 对照范围

- [计时报告](../TIMING_RESULTS_V31.md)、[质量报告](../QUALITY_RESULTS_V31.md)、
  [阶段结果](../ACTUAL_RESULTS_V31.md)，以及仓库 [README](../../../README.md) 和
  [版本记录](../../../docs/optimization_versions.md) 的 V31 段落。
- [独立计时结果](../independent_timing/real_timing_audit_v1/result.json)的变体、成对比值、
  每对象等权汇总、退化计数和限制；[计时回执](../independent_timing/real_timing_audit_v1_RUNNER.json)。
- 小体量的[质量验收](../quality/QUALITY_AUDIT_ACCEPTANCE.json)与
  [身份保留汇总](../independent_quality_v2/real_development_audit_v2/audit_output/retention.json)。
  本轮没有再次解析 12 MB 的质量 result，也没有重做完整 raw 数值审计。
- [训练验收](../TRAINING_ACCEPTANCE.json)、[几何聚合](../ACCEPTED_TRAINING_GEOMETRY_REPORT.json)、
  [独立几何摘要](../geometry/real_independent_20261023_v1/audit_output/INDEPENDENT_GEOMETRY_AUDIT.json)、
  [export 清单](../public_training_export_v1/EXPORT_MANIFEST.json)、
  [恢复验收](../PUBLIC_EXPORT_ACCEPTANCE.json)和[恢复结果](../PUBLIC_EXPORT_RESTORE_CHECK/result.json)。
- 静态阅读 `quality/quality_eval.cpp` 的固定计时循环及 `quality/quality_support.hpp` 的调用时钟边界；
  此项用于解释文档，不是重新核验运行源码闭包。

## 核对结果

| 项目 | 核对结论 |
| --- | --- |
| 调用与统计口径 | 64 帧 × 6 对象 × 6 变体 × 13 轮 = 29,952 调用；其中 12 正式轮 = 27,648 样本，每变体 4,608；正式成对记录 27,648。顺序平衡每正式位置两次。 |
| 计时表格 | 用独立结果生成对应 Markdown 行，23 项表格行或百分比对照均一致；涵盖六变体、六组同轮比较、六对象、对象等权汇总、两项退化计数及两项百分比。 |
| 速度百分比 | B/C0 完整调用成对中位比 0.809204 / 0.831725，对应耗时下降 19.08% / 16.83%；没有使用合并绝对中位数相除替代成对统计。 |
| 慢对象与尾部 | 对象 1 的 B/C0 帧内比值中位数等权平均为 1.064986 / 1.067021。帧内成对中位比 > 1 为 50/384、52/384，p95 比 > 1 为 139/384、158/384；合并成对 p95 为 1.153545 / 1.160168。均已披露。 |
| 计时排除项 | 解码、bank/metadata 加载、CSV 写出及 raw 对照在调用时钟外。完整调用包含补边、match、转换与后处理，不能解释为磁盘输入至产线返回的总延迟。 |
| 输出证据限制 | 每次调用只保存与本臂、本路径参考 raw 的比较结果及计数，没有保存每次计时 raw；文档没有将此描述为可独立重建全部调用输出。 |
| 准确率和身份 | 质量摘要 C0/P/B TP 为 215/178/187；B 净少 28 TP、召回少 7 个百分点。全局 allGT 身份汇总核对为 B 保留 156、丢失 59、新增 31，P 保留 152、丢失 63、新增 26；没有重复累加对象或场景行。 |
| 几何及运输 | 独立几何摘要为 18 bank、119,246 层、2,823,355 特征，固定画布 848×848。export 为 46 成员、235,876,886 stored bytes；恢复摘要为 46 文件、690,835,424 原始字节，恢复守护退出 0。 |
| 推广与边界 | 质量验收和计时结果均为 primary=false、production_promotion=false；README 和版本记录保持生产 V11，披露对象退化，未解封留出集，也未混入私有磁片/SMD。恢复验证不被写成新的训练/质量审计。 |
| 链接 | 对上述五份被审文档的 68 个本地 Markdown 链接逐一检查存在性，未发现缺失；阶段结果中的下一轮有序轮廓提案链接存在。此项不表示已核对发布后的 GitHub 链接或 index 内容。 |

本次只编辑质量报告上述一个句子，并新增本审查记录。没有修改冻结文件、源码 pin 或历史失败记录，
没有运行 Git、编译、native、matcher、基准或测试，也没有解码图像、重读大 bank/raw/候选池或计算大文件 hash。
独立审计的 PASS 是既有证据状态；本审查只确认公开文档与读取的摘要一致，不替代执行审计或发布清单校验。
