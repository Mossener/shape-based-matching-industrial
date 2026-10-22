# V23 timing numeric audit

`timing_audit.py` independently checks the completed fixed timing stage using
only JSON, CSV and gzip-manifest numeric evidence. It does not import the
matcher, open images, invoke a native process or make Git changes.

The timing route is fixed to objects `[1, 2, 5, 8, 12, 17]`, the 64 frames
marked `timing=true` in the frozen 400-frame schedule, rounds `0..7`, and
orders `0..3`. The variant is `(order + round) % 4`, yielding RGB/fallback,
RGB/fused, binary/fallback and binary/fused. Round zero is warmup; the other
seven rounds provide 2,688 formal samples per variant and per paired path.

Native medians and p95 values use nearest-rank indexing
`sorted[ceil(q*n)-1]`. Paired ratios are formed from the same object/frame/
round/path before quantiles. The report also gives seven-round frame medians,
then equal-frame per-object means and equal-object overall means. Those values
are labelled separately from native pooled-call statistics.

Usage after the native timing stage completes:

```powershell
py -3.10 artifacts/independent_reviews/empty_mask_timing_v1/timing_audit.py `
  --stage-freeze artifacts/silhouette_empty_mask_experiment/run_quality_timing_v1/QUALITY_STAGE_FREEZE.json `
  --development-freeze artifacts/silhouette_empty_mask_experiment/run_quality_development_v1/QUALITY_STAGE_FREEZE.json `
  --output artifacts/independent_reviews/empty_mask_timing_v1/run_20261022_timing_audit `
  --cpu-slot-granted
```

The result records the fixed input and stage freeze pins. A timed call's full
raw/selected fields are not archived by the native timing stage; the audit
therefore validates its exact-own-reference flag and raw/selected counts
against development, without claiming to reconstruct timed full-field
equality.

The development counts and manifests are bound both to its completed stage
freeze and the hash-pinned successful independent V22 audit. This timing-only
audit does not repeat that audit's raw decoding and NMS arithmetic. It checks
the timing execution command, one-attempt reservation, build/input/selftest/
development bindings and matching before/after verification receipts, then
rehashes every accessed numeric/source byte before writing a passing result.

Run only tiny synthetic mutation tests while native timing uses the CPU:

```powershell
py -3.10 artifacts/independent_reviews/empty_mask_timing_v1/run_synthetic.py --output artifacts/independent_reviews/empty_mask_timing_v1/run_synthetic_unique_name
```
