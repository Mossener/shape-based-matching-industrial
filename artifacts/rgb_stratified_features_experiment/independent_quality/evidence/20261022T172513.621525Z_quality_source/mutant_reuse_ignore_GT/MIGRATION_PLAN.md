# V31 three-arm quality audit: minimal migration

Status: source-only plan.  No actual raw archive, template bank, metadata file,
dataset index or image has been opened for this preparation.  No matcher has
been run.  The full training v2 audit is a separate current stage.

## Preserve the established numeric core

Copy V30 `numeric.py` byte-identically into this directory.  Its float32
round-trip, canonical order, strict IoU NMS boundary, one-to-one GT matching,
eligible visibility and one-ignore-per-low-visibility-GT policy are unchanged.
Keep its SHA/origin explicit and retain literal/field mutation tests.

Do not import the native quality runner, native evaluator, OpenCV, NumPy or
the new feature sampler into the numeric audit.  Source contract checks and
numeric evidence replay remain separate.  Reader rejects image and SMD bytes;
only the separately pinned numeric dataset index is allowed under datasets.

## Quality audit changes

Use a locally frozen `contract.py` for V31 bindings instead of the
V30 erode-to-dilate seam.  Validate input version
`rgb_stratified_quality_inputs_v1`, arms C0/P/B in that order, accepted
training and 18-bank geometry pins, fixed protocol SHA, 400 development frames,
all six objects, 14,400 calls and complete native/execution file inventory.
Preserve zero-detection and negative frames as present evidence.

Read metadata through the accepted numeric allowlist, with three directories
and counts per object: control, pooled and stratified.  Raw coordinates are
mapped to the official mask box using that arm's own template origin.  No bank
feature payload is necessary for the quality replay; feature/geometry evidence
belongs to the accepted training/geometry stage.

For every object/frame/arm, replay both full raw paths, check rank/canonical
order and every score bit/identity/box field, compare fallback with fused,
recompute score filtering/NMS, allGT and eligible labels/GT IDs, per-frame
counts, negatives, object/scene/pooled/macro summaries, and serialized selected
rows.  Replace the V30 two-arm loop only after these literal tests remain GREEN.

Do not accept the native `reference_exact` flag alone.  Independently load the
separately frozen V30 common-padding C0 raw references for every development
frame and compare full ordered fields/score bits.  Independently compare every
pilot-overlap arm/path archive with its development archive.  A C0 difference
blocks the primary interpretation; no candidate filtering or pose renumbering
can make it pass.  old-gate/pilot counts remain independent stage evidence.

## Retention changes

The V31 CSV adds `comparison_arm`, `comparison_detected` and `identity_change`.
The identity key becomes `(object,scene,image,metric,gt_id,comparison_arm)`.
Expected comparison arms are P and B separately; an omitted or duplicated arm
must fail.  Recompute detected GT and pose tuple from the independently selected
TP records, not from CSV booleans.  Compare each P/C0 and B/C0 state and pose
identity, then report retained/lost/gained/neither per object, scene and pooled.
No P result can replace a failed B primary hypothesis.

Historical V22/V27/V30 strata may be emitted as additional reports by calling
the frozen identity summary once per comparison arm; their hardcoded two-arm
CSV reader must not parse the new three-arm CSV implicitly.

Primary gate remains B allGT TP >=215 and FP <42112 after exact C0 reproduction.
Keep `numeric_audit_passed`, `primary_accuracy_hypothesis_passed` and
`production_promotion:false` separate.  Output a timing acceptance only for the
complete three-arm development stage pin; accuracy failure still permits its
fixed cost measurement.

## Timing audit changes

Create independent `timing_audit.py` from the V30 numeric timing audit, without
reusing old four-variant constants.  Fix six arm/path variants, 64 timing frames
per object, rounds 0..12, warmup round 0, formal rounds 1..12, and route
`variant=(order+frame_ordinal+round)%6`.  Validate `frame_ordinal` itself from the
frozen input order.  Counts are 29,952 total samples, 27,648 formal rows, 4,608
formal samples per variant, and two occurrences at each order position for
each frame/variant across the 12 measured rounds.

Recompute nearest-rank median/p95 for matcher and external-call clocks.  Validate
the full `timing_pairs.csv` (new in V31) against same object/frame/round/path
source samples for P/C0, B/C0 and B/P: 27,648 paired rows total.  Preserve all
three comparison names in keys and report both pooled call quantiles and
equal-frame then equal-object summaries plus frame/tail regressions.

V31 native stage_summary has six variant summaries but no paired-summary array;
do not require V30 `paired_empty_mask_over_rgb`.  Pair statistics are independently
derived from the pair CSV.  Recheck the complete accepted development pin and
own-arm/path reference raw coverage.  Per-call `exact_own_reference` is a native
observation checked against the route/count contract; CSV cannot independently
reconstruct each timed call's full unretained output.

## Minimal test and runner scope

Tests must target three-arm omission/duplicate/mixed metadata; C0 raw changed by
one score bit or row order; pilot overlap mismatch; P/B retention swapped or
missing; same-pose mismatch; negative frames; warmup leakage; frame_ordinal
rotation; incomplete order balance; 13-to-8-round regression; wrong pair
direction and ratio-of-medians substitutions.  Tests use synthetic numeric
records only.

Provide fresh receipt parents before heavy children, explicit source/runtime
pin manifests and one reservation per quality/timing audit.  Stream one
object/frame pair at a time and bound the largest gzip/CSV payload; no actual
audit begins until root provides frozen evidence and an exclusive CPU grant.
Failures preserve partial evidence and never trigger a silent rerun.

