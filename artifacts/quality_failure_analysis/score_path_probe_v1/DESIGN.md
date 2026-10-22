Status: **design phase only**; no native execution or production change has occurred.

# V22 score-path probe: two separately gated phases

This diagnostic keeps the production matcher and all V21/V22 frozen sources
unchanged. It must not be compiled or run while the V22 formal timing job owns
the CPU slot. The first delivery is a minimal, useful pipeline/consolidation
probe. Counterfactual scoring follows only after its exactness gate passes.

## Fixed evidence and scope

The completed independent V22 development audit has SHA256
`38f9025da7c7320f2e42eb632381f9995c6718d64eaa40d7378e205d73047e68`.
Select every all-GT RGB TP in its preserved native selected-detection CSV:
215 GT identities, comprising the 67 losses and 148 retained controls, for
objects `1,2,5,8,12,17`. There are 213 distinct object/frame keys, or 175 distinct
scene/image keys. Both arms therefore require exactly **426 full-class search
replays**, not 430. No held-out scene, reserved object 25/29, training image, or
additional development image is permitted.

The exact frame count per object is `37,67,22,1,36,50`, with RGB TP counts
`37,69,22,1,36,50`. The selected 213-frame raw reference closure contains
71,178 RGB and 156,638 binary candidates. These are scope checks, never tuning
criteria. Input preparation reads only preserved artifact numerics and pins
the permitted image paths/bytes without opening them. Native execution is the
only stage permitted to decode those pinned development images.

## Phase 1: exact replay, score oracle, consolidation provenance

A new standalone C++ translation unit includes the existing frozen
`artifacts/silhouette_empty_mask_experiment/private_v11/line2Dup.cpp` directly.
It is the only core definition in the executable; do not also link a core
object. A derived `Detector` exposes the protected memory-pyramid types and the
old `matchClass` overload, whose own workspace/default options are unchanged.
Original static quantization, spread, response-LUT/linearization, similarity,
and consolidation functions remain the actual executed implementations.

For each fixed object/frame/arm, build the same grayscale, common-padded image
pyramid and linear memories as V22 using the original functions and fixed
parameters. Run the original full-class `matchClass` once, obtaining the
pre-consolidation match vector. Preserve its multiset identity, then call the
original `consolidateMatches` on a copy. Convert the latter with the original
arm metadata and compare every ordered class/template/position/box/score bit
against that arm's preserved fallback raw CSV. V22 already established fallback
and fused equality, so replaying the default fused old overload is an explicit
cross-path equality gate, not a second reference call.

Before any cause classification, independently sum per-feature response values
for every emitted candidate and require exact binary32 score equality to the
unchanged native scoring path. Native-grid offsets, actual feature counts,
source bounds and linear-memory indexes must follow the real source. This is
the fine-score oracle gate. A failure retains its inputs and diagnostic report
and forbids Phase 2; it is not counted as a negative detection.

For every GT on the fixed RGB TP identity list, record pre/post-consolidation
candidate count and maximum IoU, and each discarded template whose representative
has a different official box. Consolidation uses class/x/y/score equality,
ignores template ID, and keeps the smallest template ID. Duplicate occurrences
of the same template/path must not be misreported as cross-template loss.
An identity is a consolidation candidate-support loss only if pre has a box
IoU>=0.5 and post has none; it is not automatically a recovered TP, since a
retained pre candidate could still lose NMS or compete for GT.

Phase 1 ends with its own exactness/completion freeze. It does not change a
single threshold, NMS decision, training feature or template, nor infer a new
precision/recall result. It produces numeric evidence and no image output.

## Phase 2: fixed same-pose placement and complete parent-window trace

Phase 2 is intentionally a separate future executable/mode and reservation. It
must require a passed Phase 1 receipt bound to the same build/input closure.
It must not be dispatched merely because Phase 1 completed. Its implementation
and call budget must be frozen before execution.

Probe all 215 RGB TP identities and both arms, mapping templates by training
image/angle/scale rather than arm-local template ID. Preserve the RGB official
box's physical placement using:

```
x_other = rgb_official_box_x + 64 - other.silhouette_x + other.tl_x
y_other = rgb_official_box_y + 64 - other.silhouette_y + other.tl_y
```

Record the oracle anchor and its predetermined native-grid floor/ceiling
neighbors. A fine output coordinate has `T=4, offset=1`; a coarse coordinate
has `T=8, offset=3`. Do not treat an off-grid oracle score as an emitted score.
Score with `(raw_sum*100.f)/(4*actual_serialized_feature_count)` and preserve
the strict coarse `>85` versus fine `>=85` distinction.

Enumerate every real coarse parent whose clamped 16x16 fine search window can
reach each legal fine point. Record coarse admission, exact fine-score vector,
first row-major local winner, pre-consolidation occurrence, representative
mapping, and NMS blocker. A single nearest parent is insufficient. The full
method requirements are retained in
`../v22_empty_mask_lost_gt/NEXT_SINGLE_POINT_DESIGN.md`.

## Safety, budgets, one-shot stages and verification

Phase 1 limits: 426 class searches, at most 175 distinct dataset image files
opened (213 decode operations if not caching across objects), 1.5 GiB peak RSS,
1 GiB numeric output, 60 minutes, and at most 1,000,000 pre-consolidation
matches per class replay. No CPU timing or throughput claim is made. Frame
scope and reference byte hashes are checked before/after; no private image is
copied into the publication selection.

Preparation and execution have distinct immutable manifests. Each native
stage requires a fresh output directory, a coordinated CPU-slot flag, a pinned
actual build/runtime/dependency closure, and an exclusive-create reservation.
A failed reservation is retained and cannot be silently rerun or overwritten.
The build is a separate single-TU target with recorded compiler `-M`/`-MD`
dependencies and tool/runtime/library pins. It must compile no production
working-tree source. A native numeric selftest must pass before dataset replay.

Verification proceeds in this order: small standard-library contract fixtures
(RED then GREEN), native synthetic geometry/consolidation/score fixtures (RED
then GREEN after timing releases the slot), exact pipeline/raw/score gate, then
fixed Phase 1 replay. A phase failure retains evidence and stops continuation.
All publication and Git mutations remain owned by the root task.
