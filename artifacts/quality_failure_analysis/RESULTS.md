# Six-object numeric failure decomposition

The fixed V11 development baseline's 185 false negatives decompose into
162 missing raw-box coverage opportunities and 23 candidate-pool capacity
losses between raw and selected outputs. The final frozen greedy GT assignment
adds no capacity loss. These are diagnostics of existing boxes, not new TPs or
an improved detector. No matcher was called and no image was opened.

| Object | GT | Raw maximum capacity | Selected maximum capacity | Actual TP | Raw deficit | Raw-to-selected loss | Assignment loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 50 | 42 | 37 | 37 | 8 | 5 | 0 |
| 2 | 150 | 87 | 69 | 69 | 63 | 18 | 0 |
| 5 | 50 | 22 | 22 | 22 | 28 | 0 | 0 |
| 8 | 50 | 1 | 1 | 1 | 49 | 0 | 0 |
| 12 | 50 | 36 | 36 | 36 | 14 | 0 | 0 |
| 17 | 50 | 50 | 50 | 50 | 0 | 0 | 0 |
| Total | 400 | 238 | 215 | 215 | 162 | 23 | 0 |

The maximum capacity uses one-to-one box assignment at IoU >= 0.5. It ignores
whether all chosen raw boxes could survive NMS together. The 23 lost capacity
opportunities cannot be attributed solely to NMS or treated as 23 recoverable
TPs. In general the raw deficit may include Hall competition; in this run it
equals the independently counted 162 individual GT boxes without any raw
candidate at IoU >= 0.5. Counts are over 2400 object/frame pairs on the same
400 development images, using 457376 preserved raw candidates per path.

The 42098 selected FPs have the following exclusive, ordered associations:

| Association, checked in this priority order | FP count |
| --- | ---: |
| Target-object GT IoU >= 0.5 | 0 |
| Other-object GT IoU >= 0.5 | 1225 |
| Target-object GT IoU >= 0.1 | 257 |
| Other-object GT IoU >= 0.1 | 6353 |
| No annotated GT box with IoU >= 0.1 | 34263 |

These are overlap associations only. The last category is not proof of pure
background, and an association with another GT is not proof of visual identity.

## Template box-size check

A separate diagnostic checks every current serialized template silhouette box
against each target GT box, allowing its mathematically best continuous
translation. The maximal intersection is min(widths) * min(heights), giving
an upper bound on possible bounding-box IoU before grid, edge or pose errors.
All 400 GT boxes have at least one existing template with this upper bound
>= 0.5. The smallest per-GT best upper bound for objects 1/2/5/8/12/17 is
respectively 0.72740/0.84485/0.89430/0.87715/0.86742/0.88730.

This rules out complete box-size incompatibility for those GTs. It does not
establish a correct silhouette, rotation, feature pattern or actual placement.
In particular, object8's 49 missed GTs cannot be explained simply by saying
that every template box is too large or too small. Enlarging padding also
produced exactly the same raw candidates in the separately controlled padding
experiment. The next accuracy experiment should examine the descriptor and
training evidence before changing scale ranges or NMS thresholds.

## Verification and replay

Eleven synthetic tests pass, including all 512 three-by-three adjacency graphs
against independent exhaustive partial injections and all 81 pairs of small
rectangle sizes against translated pixel-set enumeration. Hand fixtures check
IoU boundaries, FP category priority, sealed/training frame exclusion, malformed
raw rows, and invalid TP labels borrowing capacity from FP rows. No-op stubs
and the TP-integrity bug each failed before implementation, with logs retained.

The full diagnostic first reran the frozen preservation auditor for all six
numeric packages, then checked the exact 400-frame scope, raw ranks/counts,
selected class/template/box membership and each TP's unique, valid GT ID.
Every per-frame and per-object count agrees with the preserved baseline.
Source and input bytes are hashed before/after; run snapshots and per-frame
outputs are retained in `run_six_objects_v1/` and `run_size_coverage_v1/`.
An independent GT-subset bitmask dynamic program has now recomputed all 2400
object/frame pairs without importing this analysis or the evaluator. Every
per-frame, per-object, per-scene and global result agrees; its per-frame CSV
is byte-identical. The separate audit also restores full score bits from the
metrics JSON, verifies their six-digit selected-CSV projection, checks complete
raw identities and independently reassigns selected detections to GT. The first
failed CSV-precision assumption and its correction remain archived. See the
[independent report](../independent_reviews/capacity_dp/README.md).

The root review freshly checked 56 recorded source/input files, both per-frame
CSVs, source snapshots and all numeric closures, then reran the eleven original
synthetic tests, independent DP literals and selected-score collision fixtures.
All three commands passed. This lightweight review did not repeat the full DP
run or invoke a matcher; evidence is in `root_review_20261021_v1/results.json`
and [ROOT_REVIEW.md](ROOT_REVIEW.md).

```powershell
py -3.10 -m unittest discover -s artifacts/quality_failure_analysis -p 'test_*.py'
py -3.10 artifacts/quality_failure_analysis/verify_independent_review.py --output artifacts/quality_failure_analysis/my_new_review
py -3.10 artifacts/quality_failure_analysis/run_diagnosis.py --output artifacts/quality_failure_analysis/my_new_numeric_run --cpu-slot-granted
py -3.10 artifacts/quality_failure_analysis/size_coverage.py --output artifacts/quality_failure_analysis/my_new_size_run --cpu-slot-granted
```

Run the two numeric commands sequentially in the exclusive audit CPU slot.
The source dataset contributes index metadata only. No heldout frame is
processed, no object25/29 is trained or matched, and production code, templates,
thresholds and NMS remain unchanged.
