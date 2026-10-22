# V27 results: RGB grayscale source with an empty feature-selection mask

V27 evaluates one isolated factorial cell: the existing grayscale RGB warp is
unchanged, while the third `Detector::addTemplate` argument is `cv::Mat()`.
The official warped mask still supplies the crop, affine geometry and reported
silhouette box. The production checkout is unchanged and remains pinned to
`b25df46f6ddf9c24fb43f5836f1414dc38c8caed`.

## Training and geometry

All six public T-LESS development objects used the fixed 72-view × 12-angle ×
4-scale recipe, for 20,736 attempts. There were no OpenCV exceptions and every
object had complete pose coverage. Successful treatment templates were:

| object | templates | control templates |
| ---: | ---: | ---: |
| 1 | 3432 | 2153 |
| 2 | 3456 | 2646 |
| 5 | 3456 | 3416 |
| 8 | 3456 | 3456 |
| 12 | 3456 | 3372 |
| 17 | 3456 | 3156 |

The treatment and RGB control share every frozen ROI, affine, canvas, official
mask box and pose key. The 12-bank union has 77,822 layers and fits the fixed
848×832 canvas with padding `[64,64,64,228]`; estimated dynamic memory is
361,234,432 bytes. Evidence: `run_training_v1/training_audit.json`,
`run_plan_v1/plan_audit.json` and `run_plan_v1/COMMON_PADDING_FREEZE.json`.

## Development quality

The fixed development run contains 2,400 object-frame pairs, both fallback and
fused paths, and 9,600 matcher calls. The independent audit agrees with the
native summaries and raw candidate identities.

| arm | TP | FP | FN | raw candidates |
| --- | ---: | ---: | ---: | ---: |
| RGB control | 215 | 42,112 | 185 | 457,279 |
| RGB empty mask | 183 | 10,019 | 217 | 150,247 |

The treatment reduces FP by 76.2% and raw candidates by 67.1%, with a net
decrease of 32 TP and increase of 32 FN. Identity replay finds 156 retained,
59 lost, 27 gained and 158 undetected GT identities. Precision changes from
0.5080% to 1.7938%, recall from 53.75% to 45.75%, F1 from 0.010064 to
0.034522, and mean matched IoU from 0.72058 to 0.74773. These aggregate
improvements do not remove the loss of recall. The pre-registered promotion rule was
`TP >= 215 AND FP < 42112`; it therefore fails. This experiment does not
support a production default or an overall accuracy-improvement claim.

| object | control TP / FP / FN | empty-mask TP / FP / FN |
| ---: | ---: | ---: |
| 1 | 37 / 7842 / 13 | 35 / 3786 / 15 |
| 2 | 69 / 10978 / 81 | 74 / 3752 / 76 |
| 5 | 22 / 2196 / 28 | 19 / 578 / 31 |
| 8 | 1 / 68 / 49 | 1 / 127 / 49 |
| 12 | 36 / 4665 / 14 | 24 / 193 / 26 |
| 17 | 50 / 16363 / 0 | 30 / 1583 / 20 |

The visibility-eligible subset changes from TP/FP/FN 209/42112/165 to
182/10019/192. Negative-frame FP changes from 35089 to 8170, and negative
frames with FP from 1706 to 1310. Object 8 has no recall gain and more FP.

The fixed V22 historical strata are all retained in the report. V27 detects
137/148 of the identities previously found by both arms, 19/67 previously
found by RGB only, 18/59 previously found by binary only, and 9/126 previously
found by neither. The V27 RGB control's detected GT identity set equals V22's
RGB set. Per-object/per-scene tables, including zero-count cells, are in
`../independent_reviews/rgb_empty_mask_quality_v1/run_identity_strata_20261022_b/`.

The old gate (96 calls), pilot (192 calls), and full development run completed;
the quality audit is in
`run_quality_development_v1/native/independent_audit.json`. The separate
standard-library review is in
`../independent_reviews/rgb_empty_mask_quality_v1/`.
Public release evidence contains no private magnet/SMD images and does not
read held-out T-LESS scenes or reserved objects 25/29.

## Timing

The separate timing stage completed all 12,288 scheduled calls. After excluding
warmups, each arm/path has 2,688 paired samples. Empty-mask/control paired
matcher-clock median ratios are 0.824297 for fallback and 0.836674 for fused, corresponding
to about 17.6% and 16.3% lower median time in this run. The p95 ratios are
1.257819 and 1.258701, so tail regressions remain and the result is not a
universal speed guarantee. External-call ratios are 0.823875 / 0.836770
(median) and 1.255158 / 1.257741 (p95). Each external call includes padding,
matching, box conversion and NMS, and excludes decode, bank load, reference
IO/comparison and output IO. Discarding the warmup also makes measured order
positions unbalanced: every variant occupies one position 384 times and each
other position 768 times. This single run provides no confidence interval or
cold-start guarantee. The original timing audit is
`run_quality_timing_v2/independent_timing_audit.json`; its reproducible,
standard-library successor and 15 synthetic/mutation checks are in
`../independent_reviews/rgb_empty_mask_timing_v1/`. Timing CSVs contain counts
and the producer's equality flag; they cannot independently reconstruct all
timed candidate vectors. Native code compares each call to its own complete
quality raw reference outside the clock.

## Reproduction, failures and provenance

The complete training/geometry audit sources and corruption fixtures are in
`../independent_reviews/rgb_empty_mask_training_v1/`. These new audits reparse
serialized banks and numeric artifacts; they do not regenerate descriptors
from pixels. Original ad-hoc audit receipts remain unchanged. Quality audit
sources, source snapshots, failures and mutation tests are under
`../independent_reviews/rgb_empty_mask_quality_v1/`.
The reproducible independent checks include 21 training/geometry, 9 quality
and 15 timing tests; root reran all 45 before publication. Fresh root training,
quality, identity and timing rechecks are retained beside the independent
receipts.

`build_source_test_v1/failure.json` records a rejected private include path
before any compiler command. Four later builds completed; their eight actual
compile commands, four links and eight dependency scans remain recorded.
`run_quality_timing_v1/failure.json` records a pre-run member-set rejection
after the quality audit was appended to the development directory. The
corrected development freeze was accepted before the separately reserved
`run_quality_timing_v2` ran; no timed native call was made in the failed v1.

Historical initial protocol/status counters remain frozen. Current derived
execution totals are in `EXECUTION_STATUS.json`: 22176 matcher calls and 3744
image-read operations (864 training RGB/mask, 48 old-gate, 48 pilot, 2400
development, 384 timing). The historical training freeze's `image_decodes=432`
counts RGB views and omits mask reads; it is not a complete decoder counter.
The derived total comes from completed loop coverage, rather than an
independently instrumented image-reader hook. External compiler/runtime
prerequisites and original absolute paths are pinned, not vendored. Frozen
manifests and numeric outputs are verified with `verify_release.py`.

## Decision

V27 is a completed, reproducible negative quality gate with a useful speed
signal. It remains an isolated experiment. The frozen production core, default
template recipe and default mask behavior are unchanged. Future work should
target recovery of the lost true positives before considering a combined
accuracy/speed promotion.
