# V23 fixed timing results

The fixed six-object timing stage completed with 12,288 matcher calls. The
independent numeric audit reproduced all native nearest-rank quantiles and
paired ratios and checked every route, round, order, clock, exact-reference
flag and raw/selected count against its own development arm/path.

The binary empty-mask training recipe was faster overall in this measured
development scope, but objects 1 and 8 were slower. The V22 recall loss and
remaining false positives also remain unchanged. This experiment does not
promote the recipe into the production default.

## Fixed scope

- Objects: 1, 2, 5, 8, 12 and 17.
- The same 64 timing-flagged frames from the frozen 400-frame development
  schedule are used for each object, in frozen order: 384 object/frame pairs.
- Every frame has one warmup and seven formal rounds. Four variants rotate by
  `(order + round) % 4`: RGB/fallback, RGB/fused, binary/fallback, binary/fused.
- The 1,536 warmup samples are excluded. Each formal variant and each paired
  path has 2,688 samples; 10,752 formal rows are retained.
- The build, input freeze, common 848×832 padding, threshold, NMS and matcher
  are the same as V22. Only the two already-frozen template recipes differ.

## Native pooled-call statistics

All values below are milliseconds. External call time includes padding,
matching, coordinate conversion and NMS. It excludes image decode, template
metadata/bank loading, reference archive reading, CSV output and exact-reference
comparison.

| Recipe | Path | Match median | Match p95 | External median | External p95 |
| --- | --- | ---: | ---: | ---: | ---: |
| RGB | fallback | 40.0172 | 172.4532 | 40.2722 | 172.5586 |
| RGB | fused | 36.8946 | 156.5525 | 37.0703 | 156.7036 |
| Binary empty mask | fallback | 31.7581 | 124.3541 | 31.8541 | 124.4754 |
| Binary empty mask | fused | 30.4177 | 117.1082 | 30.5125 | 118.1176 |

Ratios pair the same object, frame, round and path before taking quantiles.
They are binary/RGB; below 1 means binary is faster. These are medians of
per-call ratios, not ratios of the table medians.

| Path | Match ratio median | Match ratio p95 | External ratio median | External ratio p95 |
| --- | ---: | ---: | ---: | ---: |
| fallback | 0.802019 | 1.245623 | 0.802692 | 1.248856 |
| fused | 0.830457 | 1.286753 | 0.831494 | 1.287995 |

The external paired ratio medians correspond to 19.73% and 16.85% less time
for fallback and fused, respectively. The ratio p95 values exceed 1, so this
does not establish a per-frame latency improvement or a universal speedup.

## Additional equal-frame/object summary

The auditor first takes the median of the seven paired ratios within each
object/frame/path, averages those 64 frame medians per object, then averages
the six objects equally. This is a separate statistic from native pooled-call
quantiles. All 384 individual frame-median records are retained in the audit.

| Object | fallback external mean of frame-pair medians | fused external mean of frame-pair medians |
| --- | ---: | ---: |
| 1 | 1.087411 | 1.114933 |
| 2 | 0.851998 | 0.895026 |
| 5 | 0.741419 | 0.760192 |
| 8 | 1.023360 | 1.033249 |
| 12 | 0.698631 | 0.737445 |
| 17 | 0.531524 | 0.568770 |
| Equal-object overall | 0.822390 | 0.851603 |

The objects with regressions remain visible; no object or frame was removed
based on the measured result.

A second independent arithmetic review reproduced the same native statistics
and counted frame regressions: the fused external seven-round paired median
exceeded 1 on 103/384 frames, including 48/64 for object 1, 43/64 for object 8
and 12/64 for object 2. It exceeded 1 on none of the object 5, 12 or 17 frames.

## Evidence and limits

- [Completed native stage](run_quality_timing_v1/QUALITY_STAGE_FREEZE.json),
  SHA-256 `e7585e22bfe29d398cd344ab14c9c72923c27fbeb093b3a8df98f7062bc1dfa4`.
- [Independent numeric audit](../independent_reviews/empty_mask_timing_v1/run_20261022_timing_audit_v1/result.json),
  SHA-256 `0d6573de68574dd2a1364dc43805f3ff49b3c77cea4cd30fbbca80584d9810b2`.
- [25 passing synthetic mutation tests](../independent_reviews/empty_mask_timing_v1/run_synthetic_20261022_b/result.json),
  SHA-256 `0fba6f2a5968db146b87b9149ae5629614c96aefff72c76f01ea17558812fa18`.
- [Independent source review](../independent_reviews/empty_mask_timing_v1/source_review_20261022.json),
  SHA-256 `9c8275b49445cccbeaa4d6c1d867e41b160029b27da3a63ab1ba799953275a79`.
- [Second arithmetic review](../independent_reviews/empty_mask_timing_v1/root_arithmetic_review_20261022.json),
  SHA-256 `932a86fc33d482246dd60874ab936ea5384916a64b1f1b4332a852fb4a412e58`.

Native timing writes only `timing_samples.csv`, `bank_load_timings.csv` and
`stage_summary.json`, plus execution receipts outside its native directory.
Each timed call is compared by native code with its own development raw
reference, and every numeric exact flag and count passed. The timed full raw
and selected fields are not archived, so the independent timing auditor does
not claim to reconstruct timed full-field equality. Development raw/NMS/GT
correctness remains bound to the successful independent V22 quality audit.

The native median/p95 uses nearest-rank `sorted[ceil(q*n)-1]`; an even-size
median is the lower middle. Workspaces are reused across rounds and frames.
Eight rounds balance variant positions, but removing warmup leaves seven
formal rounds with unequal position counts: each variant appears 384 times
in its round-zero position and 768 times in each other position. The exact
position counts are retained in the audit result.

The native process recorded 4,378.8892 ms total image decode time and
170,176,512 bytes peak RSS. These are validated separately and are not included
in the external call quantiles. This is a fixed development benchmark on one
machine, not an industrial cycle-time, cold-start, end-to-end, held-out accuracy
or magnet acceptance claim. Held-out scenes and objects 25/29 remain sealed.
The production core remains V11.
