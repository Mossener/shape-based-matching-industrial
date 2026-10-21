# T-LESS exploratory detection adapter

`tless_eval.cpp` evaluates this project's detections on fixed real T-LESS RGB
slices. Dataset policy, NMS and metrics remain outside the matcher. This is a
2D detection diagnostic; it is not a T-LESS 6D pose benchmark.
Dataset sources, license and selection are recorded in
[the dataset survey](../../docs/datasets/public-dataset-survey.md).

## Fixed actual-85 development baseline through object 8

Objects **1, 2, 5 and 8** each completed one independent 400-frame development
run, including target-negative images. Both fallback and fused paths were called
on every frame: 3,200 matcher calls across 1,600 object/frame evaluations. All
1,600 strict raw candidate comparisons passed. These results establish a failing
quality baseline to improve; they do not show an accuracy improvement.

| Object | Templates / attempts | TP | FP | FN | GT | Precision | Recall | F1 | Mean TP IoU | Negative-image FP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2,153 / 3,456 | 37 | 7,842 | 13 | 50 | 0.004696 | 0.74 | 0.009333 | 0.708375 | 6,874 |
| 2 | 2,646 / 3,456 | 69 | 10,978 | 81 | 150 | 0.006246 | 0.46 | 0.012325 | 0.715454 | 7,511 |
| 5 | 3,416 / 3,456 | 22 | 2,196 | 28 | 50 | 0.009919 | 0.44 | 0.019400 | 0.698342 | 1,965 |
| 8 | 3,456 / 3,456 | 1 | 68 | 49 | 50 | 0.014493 | 0.02 | 0.016807 | 0.658537 | 63 |

All-GT micro totals are TP=129, FP=21,084, FN=171, GT=300, precision 0.006081,
recall 0.43 and F1 0.011993. These are independent per-object runs against the
same 400 images, not a joint multi-class scan. Visibility≥0.5 results, object
macro, per-object and per-scene metrics remain in the numeric reports.
Object 12 currently has a trained bank only; objects 12/17 have no quality results
in this version. New heldout scenes and objects 25/29 remain sealed for matching.

Object 8 has a material geometry limitation in this frozen recipe: **630 of 6,912
template levels** fail the declared coarse-size or refinement-center checks,
all at scale 2.0. Of these, 412 are level 0 and 218 are level 1; 402 levels also
have actual feature max+1 beyond a level dimension. The bank, padding and scales
were retained unchanged to expose the failed baseline. Many zero-candidate frames
and the 2% recall must be interpreted with this limitation. Equality between two
implementations is not an accuracy or memory-safety proof.

## Recipe and independence

The immutable predeclared recipe is
[`expanded_baseline_protocol.json`](expanded_baseline_protocol.json): 72 real
training views per object; 32 requested features; angles 0,30,...,330 degrees;
scales 0.75/1/1.5/2; T=[4,8]; gradients 20/40; **actual match(...,85)**; post85;
NMS IoU 0.3; match IoU 0.5. Insufficient-feature attempts are retained. Actual
feature counts can differ because the core's exhaustive fallback is recorded,
not silently discarded. No thresholds/scales/padding were tuned after results.

Each fixed pilot uses the minimum official image ID in each of the eight
development scenes. Pilot configs cannot authorize final evaluation. The full
baseline's original six-object budget is 4,800 matcher calls; the completed
subset above uses 3,200. The protocol file retains its original prepared status
and SHA; actual execution state is in run provenance and audit reports.

All recorded development PNG headers are 720×540. Fixed padding64 and alignment16
produce **848×672**, with level1 **424×336**. Geometry reports distinguish declared
template extents, actual feature extrema/max+1 and refinement center intervals.
Historical width==feature-max behavior is not treated as a format failure.
These diagnostics do not prove the full physical SIMD load boundary, especially
the fallback word path's wider physical reads. No templates are filtered by this
report. Early unpadded/wrong-raw-size geometry reports remain local and are named
`*_superseded_*`; their SHA and status are in `geometry_superseded_manifest.json`.

`metadata_guard_test.cpp` validates schema2 heldout→heldout_scene metadata alias
without RGB files. The integrity verifier does read original bytes/PNG headers,
including sealed members, for CRC/SHA/dimension validation. No heldout RGB was
decoded, viewed or matched. Objects25/29 were not trained or matched.

## Numeric evidence and source snapshots

The completed packages are `expanded_obj1_v11/`, `expanded_obj2_v11/`,
`expanded_obj5_v11/`, `expanded_obj8_v11/` and `tiny_v11_actual85/`. Each holds the
training config/bank/metadata/attempts, pilot or development metrics, selected
outputs, equality/config/provenance and one `raw_numeric.tar.gz` per run.
Full raw archives are about 3.24 MB, 3.28 MB, 0.50 MB and 0.05 MB respectively;
no original or derived RGB/failure PNGs are included. Each tar member has its own
SHA/length in the preservation manifest. All original raw/failed runs remain
untouched in ignored local dataset directories.

`expanded_v11_source_snapshot.tar.gz` stores all seven committed root core files,
all sixteen committed MIPP files and the exact adapter/build/run/protocol sources.
Its manifest records each member's SHA. Core revision is
`b25df46f6ddf9c24fb43f5836f1414dc38c8caed`. Original build manifests are preserved;
`dependency_integrity.json` supplements them with all nested MIPP inputs verified
against committed bytes. Before/after-run checks are in
`dependency_checks_through_obj8.json`.

The historically named `audit_expanded_pilot.py` supports both `--stage pilot` and
`--stage development_full`, schema1 tiny and schema2 single-object runs. It runs
nine hand-derived class/IoU/NMS/one-to-one/ignore/negative checks, then reconstructs
raw float32 bits, identity/coords/boxes, NMS outputs, GT labels and metric totals.
Every current audit embeds its own script SHA. `audit_versions.json` explains the
parameterization and preserves the earlier pilot report; raw execution evidence
and the frozen protocol were unchanged.

Example read-only re-audits (no matcher/image decoding):

```powershell
python artifacts/public_evaluation/audit_expanded_pilot.py --stage development_full `
  --training datasets/tless_expanded_obj2_f32_train `
  --pilot datasets/tless_expanded_obj2_f32_development `
  --output artifacts/public_evaluation/expanded_obj2_development_audit.json
python artifacts/public_evaluation/check_dependency_integrity.py --stage review
```

Times in metrics are one matcher call per variant, fixed fallback-first order,
without repeated trials or order balancing. They are cost diagnostics, not a speed
benchmark. Mean fallback/fused ms were object1 41.148/38.549, object2 46.329/42.270,
object5 35.447/33.716 and object8 19.700/19.913. They exclude integrity auditing,
training, archive writing and report generation.

The tiny development set was separately rerun under current V11 actual85 with
its exact legacy 2,212-template bank: TP=5, FP=338, FN=3, GT=8; precision 0.014577,
recall 0.625, F1 0.028490 and mean TP IoU 0.708598. All sixteen raw comparisons
passed; eight negative images produced177 FP. This is separate from V10 coarse50.

## Historical tiny starting policy (V10)

- 72 real object-1 training views; angles `0,30,...,330`; scales `[0.75,1,1.5,2]`.
- 32 requested features by default; the core's exhaustive fallback can return
  a different count, which is recorded per level. 48 is an explicitly separate development experiment.
  Two pyramid levels use `T=[4,8]`, gradient thresholds 20/40.
- Crop to the official training silhouette, warp into a diagonal-sized canvas
  with 16 pixels of border, extract with the nearest-neighbor warped mask.
  Every attempted template, including insufficient-feature failures, is recorded.
- Fixed matcher coarse threshold 50. At the coarse stage the core uses `>50`;
  refined candidates are retained with `>=50`. The post-processing grid is
  `[50,55,60,65,70,75,80,85,90,95]` and uses `>=`.
  These are filters of **fixed-coarse** results. They are not asserted equivalent
  to calling `match(image, threshold)` again: intermediate pyramid filtering differs.
- Adapter NMS is fixed at IoU 0.3 and suppresses only `IoU > 0.3`. No raw candidates
  are truncated. All boxes remain in original-image coordinates without clipping.
- Development selects maximal all-GT micro F1; ties choose higher precision,
  then higher score threshold. No heldout observations enter this choice.
- Heldout reads saved templates and the frozen policy, refuses feature overrides,
  and creates a once-only marker in the training run before reading heldout images.
  It refuses another final run for the same training run, including after an
  interrupted final. Preserve the failed run and investigate before a new protocol.

Prediction bounding boxes use the official warped training silhouette, not the
feature bounding box:

```
pred.x = match.x - input_padding + warped_mask_bbox.x - template.tl_x
pred.y = match.y - input_padding + warped_mask_bbox.y - template.tl_y
pred.w = warped_mask_bbox.width
pred.h = warped_mask_bbox.height
```

`template_attempts.csv` records crop coordinates, canvas size, mask bbox,
`tl_x/tl_y`, both feature counts and failures. Returned `match.x/y` locate the
cropped feature template; failing to subtract `tl_x/tl_y` shifts localization.

## Metrics and equivalence

IoU uses continuous `[x,y,w,h]` rectangles, with no inclusive-pixel `+1`.
All-GT and visibility≥0.5 counts are independent greedy evaluations, both at
IoU≥0.5. Candidates are sorted by score descending, then template ID, match y/x,
and bbox y/x/w/h ascending. Each prediction selects the highest-IoU unmatched GT;
GT-ID ascending breaks an equal-IoU tie. A target can be consumed once.

For visibility≥0.5, match eligible GT first. Then each low-visibility target may
consume **one** remaining detection as IGNORE; further duplicates are FP.
Negative frames remain in both splits and count every post-NMS detection as FP.
Reports include TP/FP/FN/GT/ignored, precision/recall/F1, per-frame GT/detection
labels, and negative image/FP counts. An empty precision denominator is 0.

Each image is matched once with `fused_local_search=false` and once with it true;
all other options are identical. Both raw outputs are saved and compared as exact
multisets, including template identity, coordinates, score and bbox. Any inequality
returns exit code 2. Quality is reported from the fallback results; equality is
regression evidence, not an accuracy improvement. Current expanded runs record
single-call matcher times only as cost diagnostics.

Current runs stream every candidate directly to `*_raw.csv.gz` in 64 KiB batches,
using 17 significant score digits. A small per-image manifest records image/class,
counts, archive path, compressed/uncompressed sizes and zlib version; execution
provenance records each gzip SHA-256. This replaces the first run's redundant huge
JSON/CSV pair. All raw candidates remain recoverable; there is no top-K truncation.
The compiled selftest exactly recovered 2,048 candidate rows, including float32
scores, identity, coordinates and boxes, across multiple batches; Python gzip/CSV
verification also checks the empty archive. No dataset matching is needed for it.

## Historical tiny execution and preserved evidence

The current environment defaults match the existing local experiments. Adjust
compiler/OpenCV paths through script parameters when needed. Build requires C++17
for `std::filesystem`; the core's language contract is unchanged.
The original V10 run snapshotted committed core revision `c41f047`; its preserved
provenance is independent of the current V11 default.

Review the training/development dimensions and every template-attempt count before
matching. Coordinate CPU use with any performance experiment. Historical tiny
training artifacts remain compatible, but current develop/pilot calls use actual
threshold85. The original coarse50 run is preserved and must not be relabeled.

Every output must be fresh. The wrapper verifies all cached dataset SHA/CRC values,
checks compiled source/executable hashes, records input hashes and thread settings,
and verifies inputs did not change during execution. Keep numeric JSON/CSV,
configuration, provenance and image paths when publishing results. Failure PNGs
are derived external images; output folders are locally ignored and images should
not be committed.

`metrics_literal_test.cpp` contains hand-derived cases for bbox offsets, IoU, NMS,
one-to-one matching, eligible priority, bounded ignore, negative images and exact
candidate equality. RED/GREEN evidence is recorded in `validation.json`.

## Preserved V10 development failure

The first run used committed core `c41f04762fb62ca5598f60e5d66ea9cfa2fbc2a0`.
Of 3,456 extraction attempts, 2,212 succeeded; all 72 source views have a successful
template. At scales 0.75/1/1.5/2, successes were 12/472/864/864 out of 864 each.
Actual level-0 feature counts were 15–41 and level-1 counts 5–22.

The fixed tiny development policy selected post-threshold 85. Fallback results were
TP=5, FP=352, FN=3, GT=8; precision 0.0140 and recall 0.625. All 8 negative
development images had false positives (185 total). These are a failed starting
configuration's development diagnostics. The low precision is a baseline to
improve; it does not establish industrial capability or heldout accuracy.

Strict fallback/fused candidate multisets failed equality on all 16 frames, so the
runner returned 2 and heldout was never matched. The diagnostic breakdown matters:

| Comparison | Equal frames |
| --- | ---: |
| Semantic set: class, x/y, exact float32 score | 16/16 |
| Semantic multiset, including multiplicity | 0/16 |
| Strict set/multiset, also template ID | 0/16 |
| Bbox of every common strict key | All, zero differences |
| Complete post-85/NMS-0.3 detection list | 16/16 |

An independent repeated-call experiment subsequently reproduced differences with
the same variant at 4 OpenMP threads, while 1-thread results were stable. This
points to the existing global sort/adjacent-unique contract, which sorts equal
scores by template ID without a coordinate total order and deduplicates while
ignoring template ID. It is not evidence of a changed x/y/score semantic set.
See [repeat experiment](../local_center_optimization/public_repeat_v10.csv).

Different template IDs can still change the predicted silhouette box. For example,
the same score 55.7142868 and match (661,65) in scene 5/image 7 maps to
`[594,-2,89,157]` for one view and `[591,-1,108,145]` for another (IoU 0.77146).
At selected threshold 85 such examples did not change final NMS outputs; that
observation does not establish identity irrelevance at other thresholds or data.

Numeric failure evidence, annotations, metadata, frozen configuration and PNG paths
are preserved under `v10_development_failed_strict_equivalence/`. Additional exact
set/multiset evidence is in `v10_development_candidate_differences.json`, and cached
NMS reconstruction in `v10_cached_nms_identity_impact.json`. Original large raw
outputs remain local and ignored; no additional matching is justified until the
deterministic candidate contract is verified. The saved training YAML can be reused
after that fix, avoiding a new training experiment.
