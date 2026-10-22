# Numeric comparison with the retained V15 baseline

Status: planned after the fixed full-development quality stage. This adds zero
matcher calls and reads no dataset image. The already reviewed native quality
sources, stage budget and V20 selected files remain unchanged.

The report will keep three explicit comparisons on the same six objects and
400 development frames:

| Comparison | Before | After | Interpretation |
| --- | --- | --- | --- |
| Padding | V15 RGB, 848x672 | New RGB, 848x832 | Input padding effect with the same frozen RGB bank |
| Training policy | New RGB, 848x832 | Binary/empty-mask, 848x832 | Combined training-source and feature-selection-mask policy effect at shared input geometry |
| Overall change | V15 RGB, 848x672 | Binary/empty-mask, 848x832 | Overall development result; changes cannot be assigned to one factor |

Before comparison, bind the complete successful new development
`QUALITY_STAGE_FREEZE.json`, its exact build/input/previous/selftest chain and
the V15 `baseline_summary_all_six.json`. For every object, verify the retained
`expanded_obj{object}_v11/development/` numeric package, its preservation
manifest, raw tar, selected CSV, metrics and fixed config against its retained
source and audit pins. Match each RGB bank/config/metadata with the inherited
RGB input closure. The V15 report remains historical evidence and is not edited.

Use the fixed keys `(object_id, scene_id, image_id)` and exact same set of
2,400 object/frame combinations; compare fallback with fallback and fused with
fused. Each raw archive must retain every row and canonical order. Compare
class, template ID, match x/y, official bbox and float32 score bits. Compare
full selected rows as well. Report equal/changed frame counts and raw/selected
counts per object/scene and pooled; preserve the first differing canonical row
as a diagnostic. A difference is a measured padding effect, not an error to
repair by filtering, retuning or silently rerunning matching.

Independently recompute NMS and GT assignment from raw candidates and allowed
numeric GT metadata for each of the three arms. Use the existing fixed policy:
post score >=85, class-aware NMS suppressing IoU strictly >0.3, GT IoU >=0.5,
visibility eligibility >=0.5 with one-to-one ignores. Check recomputed selected
rows and every reported per-frame label/count/IoU sum before aggregating.

For each comparison, report allGT and eligible TP/FP/FN/GT/IGNORE, precision,
recall, F1, TP IoU sum/mean, negative-frame FP and negative frames with FP.
Retain per-object, per-scene, micro and object-macro summaries. Report retained,
new and lost GT identities, including gains and losses hidden by unchanged net
TP. Cross-arm pose comparisons use `(object, training_image, angle, scale)`;
numeric template IDs are comparable only between the two identical RGB banks.
For the padding pair, also report retained exact original TP detection rows.

Use only the preserved raw references, numeric index metadata and completed
quality outputs. No image decode/view/match, heldout frame, reserved object,
new parameter choice or new matcher invocation is permitted by this comparison.
The V15 single-pass timings and new quality diagnostic timings were collected
under different schedules and cannot establish a padding speed ratio. The
fixed new timing stage compares binary/RGB at common padding only; report its
paired measurements separately.

The numeric comparison should have independent mutation cases for changed
frame identity, float32 score bit, raw row order, bbox origin, selected row,
retention identity and aggregate count, then a complete successful audit. All
partial or rejected evidence remains in a fresh output directory.
