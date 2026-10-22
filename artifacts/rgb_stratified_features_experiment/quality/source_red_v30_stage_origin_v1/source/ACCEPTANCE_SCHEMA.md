# Acceptance files

The preparer expects an independent training and geometry acceptance JSON with
schema `rgb_stratified_training_geometry_acceptance_v1` (the explicit alias
`rgb_stratified_training_and_geometry_acceptance_v1` is also accepted).  It
must contain `accepted_independent_audit: true`,
`scope: "training_and_exact_geometry"`, `numeric_audit_passed: true`,
`production_promotion: false`, and pins named `training_freeze`,
`geometry_freeze`, and `independent_audit`.  Every pin is checked before any
bank or raw-reference file is opened.

The accepted training freeze supplies six ordered `banks` rows.  Each row has
the object id and the three concrete bank directories/counts:
`control_training`/`control_template_count`,
`pooled_training`/`pooled_template_count`, and
`stratified_training`/`stratified_template_count`.  The geometry freeze has a
`plan` or `geometry` object accepted by `quality_contract.validate_padding`.

Before timing, `run_quality.py` additionally validates a
`QUALITY_AUDIT_ACCEPTANCE.json` whose `scope` is
`quality_all_three_arms`, whose `development_stage` pin exactly matches the
completed development stage, whose `numeric_audit_passed` is true, and whose
`production_promotion` is false.  The primary B accuracy boolean is recorded
but does not turn a failed candidate into a promotion.
