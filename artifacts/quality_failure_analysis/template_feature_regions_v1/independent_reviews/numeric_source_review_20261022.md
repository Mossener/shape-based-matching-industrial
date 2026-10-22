# Numeric audit source review — 2026-10-22

Reviewer: `/root/v27_review`. This is a limited, read-only source review of the three historical template families. It does not evaluate the new dilated-mask treatment.

## Conclusion

No blocking arithmetic or traversal-coverage error was identified in the reviewed source. In particular, the signed distances, restoration using each layer's own origin, r4/r5/r6 neighborhood inequalities, complete failed-attempt layer accounting, and selected-event descriptor joins are internally consistent with the stated protocol.

This is not a successful full-audit result or a proof that the full run fits resource limits. The complete numeric audit still needs its guarded execution. The proposed 30-minute, 1.5-GiB RSS and 2-GiB output limits are useful operational guards; this review does not establish that the run will finish below them.

## Sources and evidence

The principal reviewed sources are `independent_numeric.py` and `audit_numeric.py`, with the relevant `bank_reader.py`, `input_contract.py`, preparation, protocol, observer header and test sources inspected for context. Exact source and small-receipt hashes are recorded beside this report in `numeric_source_review_20261022_pins.json`.

The existing `green_source_20261022_c/stderr.txt` records **22 passing tests**, elapsed 0.012 seconds. Its receipt pins the currently reviewed principal source bytes. The existing `selftest_audit_root_v1.json` records seven toys and 35 full pixel maps passing. These are existing receipts, not tests rerun by this reviewer.

The existing `profiling_v1/run_v1/receipt.json` records loading all 18 banks (59,647 templates, 119,294 layers and 2,905,834 features), then processing only object 1 / training image 0: 48 poses, 240 maps, 5,389 features and **240 descriptor summaries**. It reports 15.187 seconds elapsed and 462,344,192 bytes peak RSS. Its own limitation explicitly leaves full usage replay and full descriptor-memory growth unmeasured. It cannot establish full-run time or peak memory.

No full audit, native program, new probe or test was run for this review. No image bytes, fixture pack or large map/feature/quality pack were opened. Frozen auditor and region-root source files were not edited.

## Expected complete scope

| Family | Successful templates | Failed attempts | Raw occurrences | Selected events | allGT TP | allGT FP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `rgb_official_mask` | 18,199 | 2,537 | 457,279 | 42,327 | 215 | 42,112 |
| `binary_empty_mask` | 20,736 | 0 | 497,740 | 12,089 | 207 | 11,882 |
| `rgb_empty_mask` | 20,712 | 24 | 150,247 | 10,202 | 183 | 10,019 |

The traversal contract is 432 shared training masks, 20,736 poses and **103,680 full maps** (five per pose). It contains 62,208 family/pose attempts, including 2,561 failed attempts, 59,647 successful templates, 119,294 serialized layers and **2,905,834 serialized features**. Attempt-layer accounting is **124,416 rows**, including **5,122 failed-layer rows**.

Usage covers three families × 2,400 object/frame combinations = **7,200 family/frame combinations**, **1,105,266 raw occurrences** and **64,618 selected events**. Fallback candidates are counted once and fused output is independently required to equal them. The duplicate historical RGB control is compared rather than treated as a fourth family. There are 400 allGT identities per family and two metric projections, yielding **2,400 GT-link rows** across the three families.

## Arithmetic and geometry checks

- `read_map` requires complete canonical RLE rows, exact dimensions, supported dtype, valid byte/float-bit ranges, finite alpha within [0,1], and the reconstructed full-pixel SHA. It retains intervals; it does not expand all 103,680 maps into pixel arrays at once.
- `signed_distance` queries the nearest opposite-valued region with Chebyshev distance. Inside points include the zero exterior through `min(x+1,y+1,width-x,height-y)`. For half-open intervals, right-side distance `x-end+1` and left-side distance `begin-x` are correct. Stopping when vertical displacement is at least the current best distance cannot miss a smaller distance.
- `feature_observation` restores local coordinates with the **actual current layer's** `tl_x` and `tl_y`; the caller chooses the corresponding fine or coarse maps. The 3×3 clamped minimum implements replicated-border erosion. Mask distance uses nonzero M; crop-support distance uses alpha greater than zero; exact alpha bits and B values remain observable.
- Mask/crop crossing uses `abs(distance) <= r`, correctly counting either side when a radius-r support can reach the opposite region. Canvas crossing uses `edge < r`: a point at edge distance exactly r still has its complete radius-r support inside the canvas. The r4/r5/r6 cases therefore have different but consistent inclusive inequalities.
- The coarse nearest-mask validator checks floor-half dimensions and even source coordinates through `(begin+1)//2` and `(end+1)//2`. This is nearest-neighbor mask resizing, separate from grayscale `pyrDown` behavior.
- Descriptor summaries use all actual features, including counts above the requested 32/16 targets. Eight orientation bins and 17 spatial bins preserve the outside-bbox bin, along with deficit/surplus and entropy observations.

## Coverage and joins

`verify_attempt_layers` rederives the shared pose product and requires every family/pose/level row. It checks geometry, actual counts against the independent banks, dense successful IDs, and explicit failure IDs/error fields. Failed attempts are not silently dropped because no descriptor was serialized.

The main map loop consumes one pose's five maps at a time in the expected `M0,M1,B1,A0,A1` order, checks dimensions and official bboxes, restores every feature ordinal, and compares full local/origin/absolute-coordinate/label/M/B/alpha-bit identity to native observations. It checks no feature row remains and requires complete pose, descriptor-key and feature totals. Added distance/erosion/neighborhood fields are computed independently; the native feature CSV header does not already contain them.

Usage replay compares ground truth across historical stages, validates complete raw records including float32 scores, pose and boxes, requires canonical order and fallback/fused equality with multiplicity, and independently replays NMS and GT assignment. Its boundaries are NMS IoU > 0.3 and GT IoU >= 0.5. Eligible GTs are assigned before one-to-one low-visibility ignores. Every selected event is joined to both serialized descriptor layers, while every unused successful template receives zero usage counts. GT links preserve unmatched identities and explicitly mark a same-pose descriptor unavailable when its training attempt failed.

## Resource risk and reporting limits

The material unmeasured resource risk is `usage_replay`'s `rgb_signatures`: it retains all **457,279 detailed RGB raw candidate dictionaries** until the historical replay comparison. All 18 banks, all 119,294 descriptor-summary dictionaries, selected-event dictionaries, and distinct raw/selected frame sets are also retained. The existing probe exercises the bank load but only 240 summaries and no full usage replay. This retention warrants a guarded full run; it does **not** prove inevitable OOM, nor support a precise unmeasured memory estimate.

r4/r5/r6 flags describe local neighborhoods. They are not bounds on the global influence of NMS traversal or feature scatter; the design explicitly leaves that influence unbounded. The numeric audit validates full map encodings and observations but does not independently reproduce every native affine or `pyrDown` pixel; the seven pixel toys provide limited supporting evidence.

Descriptor `region_counts` report two-sided crossing counts. Inner/outer/remote signed splits are derivable from the full per-feature signed-distance rows, but are not separate descriptor-summary keys. The eligible GT projection retains low-visibility identities with `in_metric_gt=0`; any eligible-denominator reporting must use that flag rather than count all projection rows as eligible positives.
