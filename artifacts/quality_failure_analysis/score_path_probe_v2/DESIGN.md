Status: **source preparation and pure-numeric verification only**. No Phase2 executable,
build, image access, matching call, or execution authorization exists.
All Phase1 sources, inputs, failures and results remain unchanged.

# Phase2: same-pose physical-placement admission trace

## Evidence and separate gates

Only accept Phase1 receipt ../score_path_probe_v1/probe_phase1_v2/PROBE_STAGE_FREEZE.json
with SHA256 f2be7500b13fbe1cad2bb9bc8d223b7bbf37af71919441f5b2bc2d1251e0d5ed.
Preparation verifies its complete 1,709 native-output members/bytes,
execution records, build manifest and project source pins. Input plan SHA:
353615a753a0be27a2665997488301259fe99989858068895870d16fe32de91c.
Image pins copied from that plan are never opened by preparation.

Phase1 observed exact independent scalar fine scores for 1,312,006 emitted
pre rows and exact V22 saved identity for all 227,816 post rows. There were
41,581 cross-template collision groups but zero complete GT candidate-support
losses at consolidation within the fixed 215 identities across both arms.
Those facts do not explain absences at another placement or template.

The completed independent Phase1 audit is also mandatory:
artifacts/independent_reviews/score_path_probe_v1/run_phase1_audit_20261022_v1/result.json,
SHA256 67ff1b3967e762984bf9a35e358fa2a1a9d039124de88b7fc53c98eb18eacc06.
It must pass and bind this exact Phase1 receipt/input plan. A passed V22 audit
is not a substitute. Root must still review the final Phase2 source, build,
runner, input closure and grant the specific CPU stage. Native RED/GREEN
fixtures precede a separately granted one-shot dataset stage. Failed stages
consume reservations and preserve partial evidence; no automatic continuation.

## Fixed scope and exact geometry budget

Probe all 215 RGB all-GT TP identities: 67 losses plus 148 retained controls,
both existing banks, objects 1,2,5,8,12,17, development scenes
1,4,6,7,8,10,12,13, 213 object/frame keys, 175 unique images.
Do not open training images, held-out scenes, objects 25/29 or private magnet
images. Thresholds, NMS, features, metadata and templates are unchanged.

Pure preparation uses the V22-audited loaded_layers.csv, 77,870 records,
SHA256 25f565342cd8959cb06176f6ab9a75a0cbc76803adf410be4da13e5d3a78cc66,
plus 12 pinned bank metadata files. Map each pose by object/training-image/
angle/scale; never equate numeric template IDs across arms. RGB physical
placement must reconstruct the actual original match coordinate.

Common fine size 848x832 halves to coarse size 424x416: 53x52 = 2,756 coarse
cells for each same-pose job. Fixed floor/ceiling neighbors and complete
geometric parent enumeration produce this data-score-independent budget:

| Work | Exact count / ceiling |
|---|---:|
| GT identities / arm identity jobs | 215 / 430 |
| Unique object/frame/arm/template jobs | 430 |
| Native fine-grid points, deduplicated per job | 751 |
| Point-parent links / distinct reachable parents | 12,016 / 7,185 |
| Distinct reachable 16x16 window bases | 7,185 |
| Original full coarse similarity kernel calls | 430 |
| Original local-map kernel calls | 7,185 |
| Original fused local-maximum kernel calls | 7,185 |
| Independently checked coarse / local cells | 1,185,080 / 1,839,360 |
| Coarse / local per-feature response digits | 15,295,800 / 58,042,112 |
| Standalone physical-point feature probes | 13,534 |
| Full-class search replays / public Detector::match | 0 / 0 |
| Maximum decode operations / distinct images | 213 / 175 |
| Before/after image hash operations | 350 |
| RSS / complete output / wall limits | 1.5 GiB / 1 GiB / 60 min |

Evaluate all 7,185 reachable windows, including coarse-rejected parents.
Rejected-parent local values are explicitly counterfactual and never an
actual emission. Numeric preparation stores every anchor, legal point, parent,
clamped center and window base in the fixed proposal plan.

## Physical position and complete parent geometry

Preserve the RGB official-box left/top in either arm:

    x_arm = rgb_box_x + 64 - arm.silhouette_x + arm.tl_x
    y_arm = rgb_box_y + 64 - arm.silhouette_y + arm.tl_y

Record the resulting arm box size and GT IoU. Equal left/top need not imply
equal width/height. Enumerate predetermined Cartesian floor/ceiling neighbors
of (x-1)/4 and (y-1)/4, at most four legal encoded points 4*k+1. Preserve
off-grid anchors explicitly; never pick a best-scoring offset or label an
off-grid high physical score as a pruning failure.

Standalone physical scoring exists only for integer positions with every
feature lookup within its physical image domain. Otherwise record undefined/
out-of-domain, not zero or a negative detection. Keep this score separate
from every parent-conditioned window score.

For each legal point enumerate all coarse row/column cells, including zero
tail cells. Coarse encoded position is (8*c+3,8*r+3). Apply source clamp order:

    v = min(max(2*coarse+1,32),size-template-32)
    base = (v/4-8)*4

The division is exact C++ truncation toward zero. Do not interchange min/max
in undersized domains. Keep every parent identity even if parents share a
window base; only kernel execution/vector storage is deduplicated.

## Coarse scalar oracle: actual flattened native traversal

Call original similarity_64 or similarity according to actual serialized
coarse feature count. Independently model the true flat span:

    W=coarse_width/8; H=coarse_height/8
    wf=(template.width-1)/8+1; hf=(template.height-1)/8+1
    template_positions=(H-hf)*W+(W-wf)+1

Native code checks each original feature's bounds once. Included streams
start at the phase-specific LM row/base column and add flat j positions
0..template_positions-1. Preserve right-edge logical wrap. Remaining HxW
destination cells stay zero. Do not impose physical x+feature.x bounds per
cell or substitute an ideal rectangular template domain.

Read actual contiguous LM storage at native base+j offsets, including
phase-row traversal if native pointers do so. First prove actual reads stay
within allocated storage. An unsafe/unsupported domain aborts before the
kernel with retained evidence; it never becomes a skipped cell or no-match.

Every cell requires equality of native raw value and independently summed
per-feature responses, then exact binary32 normalization:
(raw_sum*100.f)/(4*actual_serialized_feature_count). Admission remains strict
coarse score>85, including the score-exactly-85 boundary.

## Local oracle: window-base skip, all 256 cells, first ties

For each distinct window call original similarityLocal_64/similarityLocal and
similarityLocalMaximum, the default unchanged V11 fused path. Adjust each
feature by the window base first. If adjusted coordinates are out of image
bounds, native skips that feature for the entire window, retaining it in the
denominator. Serialize 256 zero contributions and the skip reason. Never
reconsider a skipped feature at a later physically valid point.

For included features independently read native LM streams at
base_index+row*W+col with checked actual storage bounds. Compare all 256 raw
values and normalized score bits to native. The original fused maximum must
match the independent raw/row/col/score bits, with first strict row-major
improvement and complete tie mask/count. All-zero windows retain native
row/col=-1,-1; no invented (0,0) winner. Fine acceptance remains score>=85.

This independently validates arithmetic, native memory traversal, admission,
maximum and tie behavior given rebuilt native LM values. It does not
independently prove the image response, gradient, quantization, response-map
construction or generalization. Phase1's exact saved-raw gate and a pinned
unchanged preprocessing function bind that part of the pipeline.

## Occurrence, consolidation, full-class NMS and controls

Preserve each parent's coarse admission, fine-point raw/score bits, tied
maxima, actual winner, output coordinate and fine acceptance. Only admitted
parents with accepted winners predict actual pre occurrences.

Join predicted occurrences to Phase1 complete same-template pre records by
class/template/x/y/score bits. Require presence and traced-parent multiplicity
no greater than that complete-record multiplicity. This subset is never a
reconstruction of the entire template pre vector. If an observed probed point
contradicts complete reachable-parent coverage, stop as a trace-exactness
failure, not a detection category.

Mandatory positive controls: all 215 original RGB TP anchors must be on-grid,
match exact saved RGB score bits, and have at least one coarse-admitted parent
whose native winner reproduces that template/coordinate/score. No binary
absence is interpreted before all these controls pass.

Find each complete post representative by unchanged class/x/y/score key and
minimum template ID. Record both boxes/GT IoUs. Point-specific representative
loss is not an overall GT support loss; Phase1 already found zero overall
losses in this scope.

Recompute unchanged NMS/assignment from each arm/frame's complete saved
full-class post raw, never only probed templates or window winners. Compare
full selected identities/assignments to pinned V22 selected_detections.csv
before attaching rank, first blocker, IoU or assignment. Pin and reuse the
previously tested pure numeric IoU/NMS/all-GT greedy-assignment conventions.
This does not define new detector precision/recall.

## Numeric evidence, source layout and verification

Store gzip CSV feature vectors with one 0..4 character per feature
contribution, fixed serialized-feature/cell order, skip flags, dimensions and
source/window IDs. The 73,337,912 response digits let a separate auditor
recompute sums, score bits, maxima and ties without native or image access.
Store actual native raw cell/score bits separately. Shared windows do not
duplicate arrays, while all parent records remain.

Store jobs.csv.gz with explicit job ID, object/frame/arm/template identity,
training-image/angle/scale, both serialized feature counts, GT ID and physical
anchor. Job IDs follow native traversal and do not assume the sorted plan's
order. Require all 430 fixed unique job keys consumed exactly once and 430
job-target rows; this mapping joins every feature/cell owner to the fixed plan.
Store anchors, points, parent links, cells, maxima, pre/post joins and fullclass
NMS/assignment as numeric records. No RGB, mask, resized image, response-map
image or visualization is written. Bound all bytes, including open streams
and logs, and retain sampled process RSS/output/time watchdog records plus
native checks at every job/vector flush. Final freeze includes complete file
membership/hashes, actual kernel calls, source/runtime/input pins and hashes
of exactly the same permitted 175 images before and after.

Native source uses one new single TU including exactly one frozen V11 core
definition and pinned frozen evaluator/helpers. It never includes Phase1
probe.cpp: that file already renames and undefines main internally. The build
extracts the exact Memories alias, Maps declaration and preprocessing function
bytes from its pinned source using four unique ordered literal boundaries,
then writes generated_preprocess.hpp with only a namespace wrapper added.
PREPROCESS_EXTRACTION.json records original and generated pins and exact
component bytes/hashes; the runner independently repeats the transformation.
RED/GREEN source closures differ only in the fresh generated-header path,
which must have identical size/hash. Phase2 calls only original coarse/local
kernels; it never dispatches Phase1, matchClass or Detector::match. Do not link
a second core object or compile production working-tree sources. New build,
runner, reservations and freeze remain inside this sibling directory.

Pure fixture failures are preserved. Boundary fixtures caught and corrected
a prototype's use of fine image size for coarse-grid enumeration before the
budget was issued. Final tests cover placement, legal neighbors, complete
clamped-parent multiplicity, half-size coarse grid, flat-wrap/zero-tail,
window-base skips, undefined physical domain, unsafe storage, exact clamp
order/C++ negative division, ties and zero sentinel.

Later native fixtures require separately retained RED/GREEN faults for
coarse, local and winner oracles without dataset images. Only reviewed,
frozen implementation/budget and explicit root CPU grants may run. Final
categories concern these fixed same-pose anchors/neighbors only: off-grid/
domain status, coarse admission, native fine threshold, winner/tie
displacement, representative mapping, NMS or assignment. Do not infer all
templates/placements fail, change thresholds, tune features or start a
hybrid descriptor before measured conclusions.
