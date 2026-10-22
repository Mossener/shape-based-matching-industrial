# Acceptance files

The preparer expects an independent training and geometry acceptance JSON with
schema `rgb_stratified_training_geometry_acceptance_v1` (the explicit alias
`rgb_stratified_training_and_geometry_acceptance_v1` is also accepted).  It
must contain `accepted_independent_audit: true`,
`scope: "training_and_exact_geometry"`, `numeric_audit_passed: true`,
`production_promotion: false`, and pins named `training_freeze`,
`geometry_freeze`, and `independent_audit`.  Every pin is checked before any
bank or raw-reference file is opened.
The independent report must use schema
`independent_stratified_training_geometry_audit_v1` and scope
`training_and_exact_geometry`, and contain `passed: true` and `input_pins` binding
the exact outer `training_freeze` and `geometry_freeze`. `input_pins` may be
a list of full pins or a dictionary keyed by canonical absolute path with
byte/SHA values (an identical embedded path is allowed). Duplicate or
malformed entries are rejected. A training-only receipt with schema
`independent_stratified_training_audit_v1` cannot replace the combined report.

The accepted training freeze supplies six ordered `banks` rows.  Each row has
the object id and the three concrete bank directories/counts:
`control_training`/`control_template_count`,
`pooled_training`/`pooled_template_count`, and
`stratified_training`/`stratified_template_count`.  The geometry freeze has a
`plan` or `geometry` object accepted by `quality_contract.validate_padding`.

The current root `GEOMETRY_INPUT_FREEZE.json` is a supported training freeze
with schema `rgb_stratified_geometry_inputs_v1`. Its `bank_files` contains
exactly 18 ordered groups, objects `[1,2,5,8,12,17]` with `C0/P/B` per object.
Each group has `arm`, `object_id`, `bank` and `metadata`, with full absolute
file pins bound to the corresponding bank directory. It is not assumed to
contain a flat `files` array. An older independently accepted layout may
instead supply an explicit flat `files` pin list. Bank bytes are always
matched to accepted pins; a modified file is never freshly re-frozen.

For the current geometry-input layout, the numeric closure includes
`source_numeric_audit`, `training_execution_acceptance`,
`inherited_control_closure`, `source`, and six ordered `original_attempts`
entries (`object_id`, `file`). The joined training acceptance must explicitly
accept real training, source/runtime and the numeric audit, and bind the
same independent report. Its independent runner, training provenance and
acceptance source pins are retained as well.

C0 bank and original-padding pilot raw pins come from the fixed V30 inherited
closure. All 400-frame C0 common-padding raw pins come from the originally
accepted V30 development stage: 5,825,410 bytes, SHA256
`c3073775ffea2c9f4a1d0058b2e1e884d7bcde9c97590a8cd6459063d03d0b88`.
That origin was recorded in `QUALITY_AUDIT_ACCEPTANCE_V30.json`, pinned by
the V30 completion record; it is checked before consuming the stage map.
The outer acceptance envelope itself is included in the numeric pin closure.

Before timing, `run_quality.py` additionally validates a
`QUALITY_AUDIT_ACCEPTANCE.json` whose `scope` is
`quality_all_three_arms`, whose `development_stage` pin exactly matches the
completed development stage, whose `numeric_audit_passed` is true, and whose
`production_promotion` is false.  The primary B accuracy boolean is recorded
but does not turn a failed candidate into a promotion.
The pinned independent report must additionally contain `passed: true`,
`numeric_audit_passed: true`, `scope: "quality_all_three_arms"` and the same
full `development_stage` pin. The report and acceptance envelope are checked
before and after timing; schema-only acceptance is insufficient.
