# Fixed silhouette-source template experiment

Status: static design for root review. No training image/mask has been decoded,
no new bank has been trained, no development image has been matched and no core
implementation is changed by this design.

## Question and alternatives

Can replacing the training grayscale source with its existing binary official
warped mask improve detection of objects whose RGB templates contain few useful
external-shape features? The retained source code shows a one-pixel mask
erosion, 7x7 Gaussian smoothing, Sobel derivatives, orientation filtering, 5x5
gradient suppression and scattered selection. That mechanism motivates the
question but does not prove which extracted points cause the current failures.
The six-object size upper-bound diagnosis already shows a geometrically
compatible silhouette box for every GT; object 8's 49 FN cannot be attributed
to lack of a compatible box size alone.

The selected bounded experiment changes only the image passed as the training
source to `addTemplate`. Direct polyline feature injection would also change
the selector/gradient conventions, while a mixed RGB-plus-contour bank would
change bank size and scoring competition. Those are separate future questions.
The selected experiment keeps the V11 extractor and matching logic intact.

## Frozen source change

Use the same 72 official training views per object, mask-derived crop, affine
transform, canvas, scales [0.75, 1, 1.5, 2], angles 0..330 at 30-degree steps,
training border 16 and nearest-neighbor mask warp. The original mask must be
single-channel 8-bit binary 0/255; fail visibly on a different representation.
Do not add threshold tuning, morphology, contour simplification or resampling.

At each pose use `warped_mask.clone()` as the training source and retain the
unchanged `warped_mask` as the object mask. The clone separates source/mask
ownership. Keep the frozen extractor's erosion, blur, Sobel, weak/strong
thresholds 20/40, orientation bins and feature selection. Requested features
remain 32 at L0 and 16 at L1. Actual counts can be smaller under V11's existing
exhaustive behavior and must be recorded, never padded with fabricated points.
The fixed erosion/NMS combination might reject silhouette gradients entirely;
that is a possible result, not permission to change the selector.

The original RGB banks are reused byte-for-byte. New mask banks have separate
arm directories and their own dense successful IDs; IDs need not denote the
same pose across arms. Record all 3,456 attempted poses for each of all six
objects, including failure reason, source crop/canvas/warped box, actual layer
features, and successful-ID-to-(object, training view, angle, scale) mapping.
Compare every pose's crop/canvas/mask box with its original attempt record.
No pose is removed because of quality, feature count or template extent.

## Before any development-image decoding

Freeze implementation/build/source hashes and all training input hashes.
After the fixed six-object training completes, freeze every bank, metadata and
attempt file SHA in a separate immutable `BANK_FREEZE.json`. Record failed
poses as first-class results. A zero-success object is a training failure of
the experiment: preserve it and stop the full comparison as incomplete; do not
silently omit that object or count unexecuted frames as negatives.

Scan every loaded template layer from both arms across all six objects.
Compute one shared width/height for the complete union, keeping source size
720x540, left/top 64, minimum old total 848x672 and alignment 16. For refined
L0 require each dimension >= declared extent + 16*T0 (64). For coarse L1 use
max(declared extent, actual maximum feature coordinate + 1), multiplied by 2.
Choose the minimum aligned dimensions satisfying all constraints, then freeze
the shared dimensions, padding and complete layer CSV before the first
development decode. Do not shrink either bank to satisfy a resource limit.
Bank/core provenance binds the exported geometry; an independent CSV constraint
audit does not itself reparse native YAML maximum feature coordinates.

This shared dimension is used by both arms and all objects. The unchanged
left/top offset keeps the source origin and grid phase fixed. Historical RGB
cache candidates are reusable only for an exactly identical input size/padding;
fresh common-padding RGB outputs are the quality baseline for this experiment.

## Fixed correctness and quality stages

First verify the original RGB executable/banks on the old padding using the
same eight fixed pilot frames per object, fallback and fused, against their
preserved original raw cache (96 calls). Then run those eight frames for both
arms at shared padding, fallback and fused (192 calls). Every same-arm pair
must match complete fields, order and float32 score bits. Arms may differ.
Pilot quality changes do not select objects or tune parameters.

After correctness/resource gates pass, run every one of the 400 frozen
development frames for all six objects, both arms and both paths (9,600 calls).
Retain every raw candidate, exact path comparisons, selected detections and
one-to-one GT assignments. Keep actual matcher/post threshold 85, NMS IoU 0.3,
GT IoU 0.5, eligibility visibility 0.5 and original coordinate conversion.
No coverage gate, threshold sweep, per-object configuration or combined bank
is introduced. Reserved objects 25/29 and heldout images remain sealed.

Report pooled and per-object/per-scene allGT and eligible TP/FP/FN/GT,
precision/recall/F1/mean TP IoU, negative-frame errors, new/lost baseline GT
identities and feature/bank-success distributions. Cross-arm retention uses
GT identities and pose keys, not coincident numeric template IDs. Report all
six objects even if only one improves. Independent Python box/NMS/greedy and
GT-subset DP diagnostics must reconstruct numeric results without importing
the adapter implementation. Do not automatically promote a default from this
development-only experiment.

## Performance and resource limits

Performance is a separate fixed stage: 64 predetermined frames (8 per scene),
one warmup and seven measured rounds, both arms and paths, all six objects
(12,288 calls). Rotate four variants each round. Check every timed call against
its own arm/path full-quality raw reference. Publish every timing sample,
nearest-rank medians/p95 and paired mask/RGB ratios. Time the external call
including padding allocation/copy, matching, box conversion and NMS; report
decode and bank-load durations separately. If only counts are archived per
timed call, explicitly separate the native exact-content assertion from the
independent numeric counts/clock audit.

Maximum matching budget is 22,176 calls: 96 provenance-gate + 192 pilot +
9,600 full-quality + 12,288 timing. Training is exactly 20,736 attempts, not
matcher calls. Fixed resource ceilings are axis 2,048, padded pixels 2,097,152,
conservative 512 bytes/pixel and 1 GiB estimated dynamic memory, process peak
RSS 1.5 GiB, 1,000,000 raw candidates per frame/arm/path and 1 GiB new raw
output per quality stage. Soft wall-time checkpoints are 120 minutes total
training, 20 minutes pilot, 180 minutes full-quality and 60 minutes timing.
Single native calls are not interruptible by those checkpoint limits.

On source mismatch, geometry/resource overflow, native exception, disk failure
or incomplete stage, preserve failure reason, counts and partial outputs;
never silently truncate a candidate set into a valid result, switch budgets,
drop an object or treat missing frames as negative. If a raw set cannot be
fully materialized within output resources, mark that archive incomplete and
do not publish valid metrics from that stage.

## Implementation boundaries after root review

All future files stay in this experiment directory: a training adapter,
full-bank shared-padding planner, numeric provenance wrapper, quality/timing
adapter, independent auditors and run evidence. Include/reuse frozen public
helpers only where unchanged and source-pinned; do not edit production core,
public evaluator, feature selector or existing banks. Synthetic source/mask
ownership, boundary/overflow, raw serialization and numeric-audit tests precede
real image stages. Native builds and execution wait for the coordinated CPU
slot. Root owns integration, version notes and commits/pushes.
