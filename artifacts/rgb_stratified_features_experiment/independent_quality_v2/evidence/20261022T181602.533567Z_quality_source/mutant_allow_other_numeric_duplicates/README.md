# Independent V31 quality replay successor V2

See [SUCCESSOR_V2.md](SUCCESSOR_V2.md) for the narrow shared-closure fix, unchanged numeric scope, retained failure and fresh V2 registry.

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
The combined report's exact schema is
`independent_stratified_training_geometry_audit_v1`, its scope is
`training_and_exact_geometry`, and `passed` is true. The single quality input
version is `rgb_stratified_quality_inputs_v1`.

The source-only wrapper is prepared for the root's later exclusive CPU grant:

```text
python -B run_audit.py --reserve-only --stage-freeze ABSOLUTE_STAGE_JSON --stage-bytes N --stage-sha256 SHA256 --evidence FRESH_EVIDENCE --reservation FRESH_RESERVATION_JSON
python -B run_audit.py --execute --reservation FRESH_RESERVATION_JSON --cpu-slot-granted
```

Reserve reads the pinned stage declaration and source/interpreter files only;
it opens no stage member, raw archive or bank. A stage-hash lock prevents a
second reservation with another filename. Execution consumes its attempt before
checking data or invoking the child, creates receipt parents before the guard,
pins sources before/after, and preserves `RUNNER_RECEIPT.json` and partial
outputs on failure. A consumed attempt is never retried automatically. The
guard watches wall time, RSS, audit bytes and log bytes; this is an observed
process bound, not an OS allocation sandbox. Full transitive Python runtime
acceptance remains separate root evidence. The wrapper does not create a native
timing acceptance automatically.

The original-padding C0 gate, common-padding C0 reference and pilot overlap are
compared independently from full raw archives. The B primary hypothesis remains
TP >= 215 and FP < 42112 after exact C0 reproduction; P remains diagnostic.
Numeric consistency, the primary hypothesis and production promotion are
separate fields. This code always records `production_promotion: false`.

The audit does not regenerate RGB gradients, template NMS or unrecorded native
candidate acquisition. Its zero matcher/image-read counters describe this
auditor only. Source/runtime/resource acceptance, heldout confirmation and
industrial generalization need separate evidence.
