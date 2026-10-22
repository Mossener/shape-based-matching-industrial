# Independent training checks

`training_audit.py` reads numeric evidence only. It imports only the independent
numeric oracle, strict pack reader and a byte-identical copy of the previously
independently tested bank reader. Its copied reader and source SHA are recorded
in `BANK_READER_ORIGIN.json`. No new native trainer, collector or sampler source
is read or imported.

The module implements the complete numeric stream, bank, summary/config and
run-directory boundary. The contract is pinned from `NATIVE_OUTPUT_SCHEMA_V1.md`
and the original frozen V11 helper. Full CLI acceptance has passed on the
actual native synthetic literal, while real training remains unexecuted by this
auditor. Source/runtime/reservation acceptance stays separate.

The complete API is `audit_native_directory(directory, expected_output_pins,
literal_only=False, freeze_path=None, freeze_sha256=None)`. Pins are a separately
trusted complete relative-path map of `{bytes,sha256}`. Production requires the
full pinned input freeze; literal mode uses only the documented one-pose fixture
and never opens the dataset freeze/CSVs. Every input/output hash is checked
before and after. Failure evidence or unexpected files prevent acceptance.

The CLI requires `--run`, `--output-pins`, `--output-pins-sha256`, `--receipt`
and either `--literal-only` or `--freeze` plus `--freeze-sha256`. The receipt
must be fresh and outside the audited directory. No CLI mode starts native code.
`expected_training_configs(report)` independently constructs the full original
writeConfig and four declared additions; `verify_training_summary` checks all
documented fields, counters, bounds and complete physical/logical byte totals.
All gzip payloads count uncompressed; other files count their exact size.
Summary's own bytes are added to its before-summary reported totals. Complete
literal receipts always set `real_training_accepted:false` and `accuracy_tested:false`.

```python
schedule, input_pins = training_audit.load_frozen_schedule(
    freeze_path, separately_frozen_input_sha256)
manifest = pool_stream.manifest_from_jsonl(pack_directory, pools_sha, shards_sha)
report = training_audit.audit_training_stream(
    schedule,
    pool_stream.iter_verified_pools(pack_directory, manifest,
        [pool_id for pose in schedule for pool_id in pose["pool_ids"]]),
    training_audit.iter_jsonl_pinned(selection_path, selection_pin),
    training_audit.iter_jsonl_pinned(attempt_path, attempt_pin),
    observations=training_audit.iter_jsonl_pinned(observation_path, observation_pin))
bank_report = training_audit.verify_bank_artifacts(
    bank_directory, report, independently_constructed_complete_configs)
```

The public schedule is generated independently from fixed objects
`[1,2,5,8,12,17]`, exactly 72 declared views/object, scales `.75,1,1.5,2` outside
angles `0..330` in steps of 30, preserving declared view order. The frozen six
original attempt CSVs must match that exact schedule and SHA/size. Their source
ROI, canvas and official warped-mask box are retained as the official geometry
reference. No images are opened to reconstruct those observations. The
20,736 poses have dense pose IDs, and pose p owns pool IDs `2*p,2*p+1`.

Smaller schedules require an explicit `literal_only:true` policy. Such a policy
cannot silently replace the public schedule or establish complete public-run
acceptance. The generic streaming core expects an independently created
schedule; calling it with arbitrary observed rows alone does not prove schedule
coverage.

For each scheduled pose, both pools are mandatory, including L1 after L0
failure. Every pool header must match pose/object/image/angle/scale bits,
level/canvas/K. The numeric oracle independently checks pool candidate fields,
dense row-major ordinals, nonzero mask domain, signed distances/strata, every
P/B selection step, quotas/borrowing, preserved bits and full trace. Native
statuses and strata must already use the agreed string boundary (`ok`,
`insufficient_features`, `S`, `I`). Every row/field of the P-then-B layer claims
is compared exactly; changed, extra and missing fields are rejected.

L1's complete actual uint8 mask must equal the exact floor-half nearest resize
of L0, including raw byte values. L0's nonzero box is independently calculated
and compared to the pinned original geometry.

`pool_observations.jsonl` has one row per pool:

```json
{
  "pool_id": 0,
  "target": 5,
  "dilated_mask_sha256": "sha256 of full raw 9x9 dilation",
  "nms_maxima": 99,
  "validation": {
    "dense_ordinals": true,
    "unique_rowmajor_coords": true,
    "finite_magnitudes": true,
    "labels_0_to_7": true,
    "inside_scan_domain": true,
    "source_order_preserved": true
  }
}
```

The raw dilation map is reconstructed independently using nonzero folding,
zero exterior and separable sliding counts; bytes are 255/0. It does **not**
clear the two-pixel NMS margin. Each candidate's scan-domain membership is
checked against that map plus the margin, separately. Target and all saved-data
validation facts are independently checked. Source order can be verified only
as canonical row-major accepted order within the saved pool. Candidate
omissions before acquisition and actual RGB gradient/NMS acceptance cannot be
proven from that pool. `nms_maxima` remains a checked uint64 native observation;
its total is explicitly named `native_nms_maxima_observed_sum`.

Each pose has exact P-then-B attempt rows with pose identity, original geometry,
pool IDs, success and contiguous per-object template ID. Failure occurs if
either layer has N<=4; failed ID is -1 and crop is `[0,0,0,0]`. P/B success must
agree. A failure never suppresses a later layer or arm row.

Successful cropping follows the unchanged V11 arithmetic: scale each selected
coordinate by `<< level`, calculate cross-layer global extrema, move odd minima
down to even, then use `(max-min)>>level` for width/height and `min>>level` for
origin. No +1 is added. Zero extent is preserved and checked; it is not silently
corrected. Feature order and labels are preserved after subtracting each
layer's own origin. A semantic digest of all layer fields and every ordered
integer feature permits subsequent bank comparison without retaining all
templates' large feature objects in memory.

Banks are strict original V11 class-bank YAML in gzip, under
`rgb_pooled_features/objN` and `rgb_stratified_features/objN`. Every serialized
template/layer/feature is compared with its independently cropped semantic
digest and actual canvas. Complete metadata uses original V11 fields:
`class_id,template_id,training_image_id,angle,scale,tl_x,tl_y,warped_mask_bbox`.
Numeric float representations of angle/scale/box are validated without accepting
booleans or nonfinite values. Metadata's box remains the official mask box,
not feature extrema. Template counts and exact directory file inventory are
checked. Zero-success objects must have metadata/config but no serialized bank;
they prevent comparison even when the numeric failure evidence is complete.

Attempts permit numeric token `1` for declared float scale `1.0`, while preserving
strict ID/counter/bool comparisons. This exact native serialization difference
was observed in `run_literal_v1`, retained as actual RED, covered by an explicit
regression RED, then corrected and accepted in actual GREEN. No score/magnitude/
theta bits or other identity fields were relaxed.

Training source/input closures, actual compiler/runtime modules, native
generator/decode counters, wall time/RSS/disk resources and any external bank
freeze remain the runner's separate evidence. This auditor does not establish
those facts or perform quality/timing evaluation. No successful synthetic test
authorizes a real heavy audit or changes the frozen algorithm.
