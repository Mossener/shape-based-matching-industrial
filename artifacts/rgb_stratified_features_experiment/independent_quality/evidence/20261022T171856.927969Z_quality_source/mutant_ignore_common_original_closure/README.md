# Independent V31 quality replay

This standard-library auditor compares C0, pooled P and stratified B using all
saved raw fields, float32 score bits, each bank's own origin, NMS, GT labels,
visibility ignores, negative frames and independent P/C0 and B/C0 retention.
The unchanged numeric core and reference sources are pinned in
`SOURCE_ORIGINS.json`.

`python -B run_selftest.py` snapshots only these source files and runs synthetic
GREEN tests plus deliberately weakened-source RED tests. It opens no real
data and grants no authority to run an actual audit.

After the root provides a complete, trusted development-stage pin, the numeric
CLI is:

```text
python -B quality_audit.py --stage-freeze ABSOLUTE_STAGE_JSON --stage-bytes N --stage-sha256 SHA256 --output FRESH_OUTPUT
```

The root must issue one exclusive execution reservation before the actual
audit. A failed audit retains `failure.json`; reuse of the output directory is
refused. Stage, native-member, execution-member, accepted training/geometry,
protocol, inherited C0 and raw-reference pins are all checked. The training and
exact-geometry acceptance must pin a passing combined independent report; that
report's `input_pins` dict/list must bind both the exact training input freeze
and the geometry freeze. A training-only numeric receipt cannot accept geometry.

The original-padding C0 gate, common-padding C0 reference and pilot overlap are
compared independently from full raw archives. The B primary hypothesis remains
TP >= 215 and FP < 42112 after exact C0 reproduction; P remains diagnostic.
Numeric consistency, the primary hypothesis and production promotion are
separate fields. This code always records `production_promotion: false`.

The audit does not regenerate RGB gradients, template NMS or unrecorded native
candidate acquisition. Its zero matcher/image-read counters describe this
auditor only. Source/runtime/resource acceptance, heldout confirmation and
industrial generalization need separate evidence.
