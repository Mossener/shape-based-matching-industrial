# V31 root quality join：只读源码与 tiny fixture 审查

日期：2026-10-23。未执行 `quality_acceptance`、`timing_inputs`、真实独立审计、native 或完整 input 验证；未读取真实 raw、bank、image 或 heldout。测试只调用 `validate_result`，输入为临时目录内独立编写的微型 JSON。

## RED → GREEN

- RED：本目录 `receipt.json`、`cases.json`；28 项中 26 通过。唯一失败是 `quality_gate.passed=0/1` 被 `==False/True` 接受。目标源码未由审查者修改。root 保存的 `complete_quality_evidence_before.py` 与 RED receipt 的 SHA/字节数完全一致。
- root 修正后：兄弟目录 `quality_join_review_green_v1/receipt.json` 为 **28/28 通过**，约 0.047 秒；`ENTRY_RECEIPT.json` 绑定保留的 fixture driver 与 fresh 入口。
- 覆盖：真假 B 门槛、TP=215 与 FP<42112 的边界、4 项错 C0、错 stage mode/pin、缺 stage input pin、4 项 raw exact 标志错误、primary 与 quality gate 的非 bool。失败 B 是有效的审计结果，不能被误判为数值审计失败或 production promotion。

复验必须使用新目录，保留旧证据：

```powershell
python -B artifacts/rgb_stratified_features_experiment/root_source_tests/quality_join_review_v1/run_fresh.py --output artifacts/rgb_stratified_features_experiment/root_source_tests/quality_join_review_green_v2
```

## 实际 schema / CLI 静态核对

已核对 `complete_quality_evidence.py`、原 v1 与实际 v2 `independent_quality/run_audit.py`、质量 worker/contract、`quality/run_quality.py`/contract、`independent_timing/evidence.py`/audit、`execution_guard.py`。

- 实际 runner v2 schema 为 `independent_three_arm_quality_runner_v2`；其 worker 的数值结果仍为 `independent_three_arm_quality_audit_v1`，scope 为 `quality_all_three_arms`。root join 对两者的区分一致。
- v2 source pin 最后一项为 Python executable；唯一 `quality_audit.py` 位于 `independent_quality_v2`。worker CLI 的 `-B`、`--stage-freeze/sha256/bytes`、`--output <evidence>/audit_output`，guard 的 `working_directory` 和 `<evidence>/execution/guard_receipt.json` 均与新增绑定相符。
- `quality/run_quality.py._modules()` 的五项返回、`quality_builder._source_manifest()`、`build_gate()`、`stage_gate()` 的实参顺序吻合。实际 acceptance 的字段满足 `quality_contract.validate_quality_acceptance()`；accuracy hypothesis 为 False 仍允许为失败候选记录计时，不表示通过质量门槛。
- timing-inputs 的 schema 与七项 pin 名称吻合 `independent_timing/audit.py.REFS`；后者还会校验完整 timing 输出、native CLI、guard、previous stage、selftest 与 accepted audit。root helper 生成输入文件本身不是独立计时审计。
- `quality/run_quality.py` 默认 acceptance 路径在 `quality/QUALITY_AUDIT_ACCEPTANCE.json`。若 root 写到其他目录，启动计时须显式传 `--quality-audit`。这不是 schema 冲突。

当前改动没有发现必然导致合法 v2 runner 失败的源码/CLI 冲突。源码静态审查及 tiny gate 测试不能证明真实 evidence 闭包通过。

## Marker 直接绑定与最终复验

初审时尚未直接检查 `consumed.development_stage == stage_pin` 及 reservation/consumed 的 v2 schema。root 随后补入 reservation v2 schema/runner_schema/reserved 与 consumed schema/development_stage 的明确核对；审查者未修改目标源码。最终 fresh `quality_join_review_green_v2/receipt.json` **28/28 通过**，约 0.047 秒，并记录目标源码的前后相同 pins；这些仍只是原28项 `validate_result` fixture，不将 marker 新绑定描述为动态覆盖。未以真实输入验证。此后停止本次审查编辑。
