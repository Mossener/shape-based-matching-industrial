# Pinned geometry stage

`run_geometry.py` is a numeric-only, one-shot scanner. The root must accept the
completed training and authorize the real scan before using it. Source tests
use synthetic payloads held in memory; they do not authorize or perform a real
bank scan.

The input freeze uses schema `rgb_stratified_geometry_inputs_v1` and contains:

```json
{
  "schema": "rgb_stratified_geometry_inputs_v1",
  "production_promotion": false,
  "training_run": "D:\\absolute\\completed_training",
  "source_numeric_audit": {"path": "D:\\absolute\\audit.json", "bytes": 123, "sha256": "64 lowercase hex digits"},
  "banks": [
    {"object_id": 1,
     "control_training": "D:\\absolute\\control_obj1", "control_template_count": 2153,
     "pooled_training": "D:\\absolute\\completed_training\\rgb_pooled_features\\obj1", "pooled_template_count": 123,
     "stratified_training": "D:\\absolute\\completed_training\\rgb_stratified_features\\obj1", "stratified_template_count": 123}
  ],
  "bank_files": [
    {"arm": "C0", "object_id": 1,
     "bank": {"path": "D:\\absolute\\control_obj1\\templates_tless_object_1.yml.gz", "bytes": 123, "sha256": "64 lowercase hex digits"},
     "metadata": {"path": "D:\\absolute\\control_obj1\\template_metadata.json", "bytes": 123, "sha256": "64 lowercase hex digits"}}
  ],
  "original_attempts": [
    {"object_id": 1, "file": {"path": "D:\\absolute\\original_obj1_attempts.csv", "bytes": 123, "sha256": "64 lowercase hex digits"}}
  ]
}
```

The abbreviated example shows one object and one bank. The actual declaration
must include all six `banks` and `original_attempts` rows in frozen object
order `[1,2,5,8,12,17]`, and all eighteen unique `bank_files` rows for
`C0/P/B × objects`. The six bank rows use the exact directory/count names
expected by `quality/ACCEPTANCE_SCHEMA.md`. Counts are observations supplied by
the accepted declaration and must equal the complete serialized bank and
metadata counts; they never limit how many templates are scanned. C0 success
IDs and poses must also equal the independently pinned original CSV.

`source_numeric_audit` must pin a complete public report with schema
`independent_stratified_training_audit_v1`, successful numeric audit, a feasible
comparison, unchanged before/after output pins, and all 20736 poses, 41472
pools, 41472 arm attempts and 82944 layer-status rows. Every P/B bank and
metadata pin must equal its path in that report's `output_pins_after` closure.
Every original CSV pin must be in its `input_pins`. C0 file pins are supplied
by the root's accepted input freeze; this runner does not reinterpret the
numeric P/B audit as independent acceptance of C0 provenance or native runtime.

The original attempt CSV supplies the square training canvas for each
`(training_image_id, angle, scale)` metadata identity. The scanner validates
every feature against that template's own layer origin and actual training
canvas, using the independent strict bank reader. This training canvas is
separate from the fixed 720×540 query frame used to calculate padding. The
planner expands only right/bottom from 848×832 with alignment16 and the frozen
axis/pixel/memory limits. Inputs cannot override those values. No image file
is opened, and no native code or matcher is called.

Reserve using an externally checked input pin:

```text
python -B geometry/run_geometry.py --reserve-only --inputs INPUT.json --inputs-bytes N --inputs-sha256 SHA --output FRESH_OUTPUT --reservation FRESH_RESERVATION.json
python -B geometry/run_geometry.py --execute --reservation FRESH_RESERVATION.json
```

Reservation reads only the input declaration and audit JSON, validates their
declarations, and pins the sources. Execution creates a persistent sibling
`FRESH_RESERVATION.json.consumed.json` before any bank read. A failure consumes
the reservation and retains `failure.json` and `receipt.json`; neither an old
reservation nor an old output directory can be reused. A successor attempt
must be explicitly authorized with a new reservation and fresh output.

Successful execution writes:

- `common_padding_plan.json`: the small FileStorage-compatible plan.
- `bank_geometry_report.json`: all per-layer extents, own origins/canvases,
  resource requirements, actual feature counts and source bank pins.
- `GEOMETRY_FREEZE.json`: schema `rgb_stratified_common_geometry_freeze_v1`,
  `plan`, `training_freeze` (the input pin), `source_numeric_audit`,
  `geometry_report`, `common_padding_plan`, `reservation`, and `source_pins`.
- `receipt.json`: success/failure, output pins, scan counts and consumed marker.

The freeze marks `numeric_audit_passed: false` and
`independent_geometry_audit_required: true`. It records computation by this
scanner without claiming that an independent geometry audit or quality test
has passed. The root must produce the independent training/geometry acceptance
envelope documented in `quality/ACCEPTANCE_SCHEMA.md` before quality preparation.
