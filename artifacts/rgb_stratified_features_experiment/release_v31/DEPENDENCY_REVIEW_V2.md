# V31 发布直接依赖复核 V2

2026-10-23。在已发布 `e3a226220a6631c9cdec9d239678473ffc2b0215` 的 V31 selection
（33,190 文件、443,319,869 selected bytes）上做有限直接依赖审查。
**确认一项必要小元数据遗漏：`quality/COMMON_PADDING_FREEZE.json`。** 未修改旧 selection、collector 或回执，未执行 Git 变更。

## 确认遗漏

| 项目 | 结果 |
| --- | --- |
| 文件 | `artifacts/rgb_stratified_features_experiment/quality/COMMON_PADDING_FREEZE.json` |
| 冻结引用 | `quality/QUALITY_INPUT_FREEZE.json` 的 `common_padding_json` 与 `frozen_numeric_files[22]` |
| 声明与实际字节 | 均为 **146** |
| 声明与实际 SHA-256 | 均为 `a70a32ee54b1b6ca576b869ae333f036e4b874aa89beac8d4f1198261d151aec` |
| 内容 | 848×848；padding `[64,64,64,244]`；18 banks；geometry_feasible=1，与内嵌 plan 相同 |
| 发布状态 | 不在 `PUBLISH_SELECTION_V31.json.files[]`；`git ls-files` 未列出 |
| 必要性 | input preparer 明确要求该路径存在、被 pin 且内容相同；native evaluator 从此独立 JSON 读取公共补边。只有内嵌 plan 不能满足原调用入口。 |

collector 的 `stage()` 选入 quality-input freeze 本身，却不展开其 `frozen_numeric_files`；
`collect_quality()` 与根文本白名单也没有显式加入此归一化 plan。
这解释了漏项：原 payload/index 验收只验证已选 inventory 的字节，不能从中推出全部输入依赖已发布。
前一份静态审查已明确未核全部传递闭包，本报告补充这项真实遗漏，不改写旧审查或冻结结果。

建议按 root 的新增补充方案，将该文件及本报告放入新的显式补充清单和小提交，保留旧清单原字节。
补充验收需分别确认声明 pin、实际文件及新增 Git blob 相同；后续 collector successor 可给该文件增加显式规则，
并用“根 freeze 引用的必要小 plan 未选入”作为回归案例。无需重跑训练、质量或计时。

## 已区分的非遗漏与可不重复发布项

- `datasets/tless_expanded/index.json`：直接 pin 为 3,616,125 bytes /
  `04d99feb07d0355a83f52ce8567c77e68dbc329f7393cc2ad694af69d4f82819`，当前未 selected、未 tracked。
  `INHERITED_PUBLIC_NUMERIC_AVAILABILITY.json.external_dataset_metadata_pins` 已将其列为精确外部例外，
  并明确 `all_declared_numeric_bundled=false`。本轮未读取其内容或计算 hash；不得因本次补依赖而发布可能命名封存成员的索引。
- P/B 的 12 份原 `run_training_v1/.../template_metadata.json` 均未直接 tracked，
  但逐一对照 46-member export 的 original 名称及 pin 均相同；对应 identity stored 成员已在 selection，stored pin 也相同。
  它们由既有无损运输和恢复流程提供，不需再发布原目录副本；本轮未读取这些 payload。
- 本范围内其他未在 V31 selection 的历史 JSON 直接引用，`git ls-files` 已确认存在于既有 Git inventory，
  包括 V30 input closure、quality freeze/stage 与继承的 C0 metadata/raw manifests；不能将“未重复列入 V31”当作“未公开”。
- 恢复副本、运行库二进制及操作用 pathspec 不应为本次补充而重复发布。新增审查报告的发布状态由 root 的补充清单决定。

## 范围与限制

显式读取九个根 metadata：`quality/QUALITY_INPUT_FREEZE.json`、`TRAINING_INPUT_FREEZE.json`、
`TRAINING_SOURCE_FREEZE.json`、`GEOMETRY_INPUT_FREEZE.json`、`quality/TRAINING_GEOMETRY_ACCEPTANCE.json`、
`ACCEPTED_TRAINING_GEOMETRY_REPORT.json`、`quality/QUALITY_AUDIT_ACCEPTANCE.json`、
`independent_timing/TIMING_INPUTS_V1.json` 和 `PUBLIC_EXPORT_ACCEPTANCE.json`。
只枚举这些已读 JSON 中的直接 full pin，与最终 selection 和只读 `git ls-files` 对照；已选同路径 pin 未发现冲突。
另读 export/继承可用性摘要、归一化 plan 和相关 preparer/collector 的静态片段解释上述结果。

没有递归扫描目录或打开引用 payload，没有重 hash 443 MB selection 成员、读取图片、外部数据索引或 bank/raw，
没有执行 tests、native、编译、训练、基准或 Git 修改。只对上述 146 字节 plan 实际计算 SHA。
本轮不声称完成所有 manifest、角色式 source pin、历史闭包或全仓直接/传递依赖审计；
也不重新核对历史 Git blob 的 hash。该限制不影响已确认 plan 遗漏及 12 个 export 映射的结论。
