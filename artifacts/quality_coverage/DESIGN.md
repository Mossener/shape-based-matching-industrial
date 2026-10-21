# Isolated design: dense oriented edge coverage

Status: read-only design for a development experiment. No matcher, adapter,
training bank, source hash, V11 evidence, or heldout result is changed here.
No accuracy or speed improvement has been measured for this proposal.

## Problem established by existing evidence

The original tiny T-LESS development run has TP=5, FP=352, FN=3, GT=8 after
post-score >=85 and NMS IoU>0.3: precision 0.0140, recall 0.625. All eight
negative frames have false positives, totalling 185. At post-score 90 the
same cached coarse-50 candidates yield TP=1/FP=141; at 95, TP=0/FP=27.
Raising the existing score therefore does not separate this bank well.
These are development diagnostics from the preserved failed V10 equivalence
run, not a new V11 quality result or a heldout evaluation.

Sources:

- `artifacts/public_evaluation/v10_development_failed_strict_equivalence/development/development_thresholds.csv`
- `.../development/selected_detections.csv`
- `.../training/template_attempts.csv`
- `artifacts/public_evaluation/README.md`

Joining the saved selected detections to successful template attempts by
template ID gives this additional evidence; no images were matched to compute it:

| Selected label | Count | L0 feature min/median/max | L1 feature min/median/max | L1 below requested 16 |
| --- | ---: | --- | --- | ---: |
| TP | 5 | 25 / 35 / 36 | 5 / 7 / 9 | 5 |
| FP | 352 | 15 / 26 / 38 | 5 / 5 / 17 | 343 |

The five TP template IDs are 209, 424, 1376, 868, 1014; their L1 counts are
5, 7, 6, 9, 8 respectively. Requiring every level to reach its requested
feature count would remove every currently found TP from that saved list.
Filtering that list by L0>=32 would remove one TP and only 191/352 FPs;
this is not a reconstruction of filtering before NMS. Feature count is useful for reporting
failure strata, but is not a justified rejection rule here.

## Mechanism in the current source

1. `ColorGradientPyramid::extractTemplate` rejects insufficient candidates only
   when there are <=4. With >=5 it prints the exhaustive-mode warning and
   continues. `selectScatteredFeatures` relaxes separation and returns true;
   the requested count is neither a guaranteed exact count nor a minimum.
   `pyrDown` halves the requested count, not the observed count.
2. The mask is eroded and used as a filled inclusion region. The subtraction
   that would make a boundary-only ring is commented out. Selected features
   can describe interior gradients as well as the outer outline.
3. `hysteresisGradient` quantizes directions modulo 180 degrees into eight
   labels. Contrast polarity is deliberately discarded. `spread` ORs all
   observed labels in a T-by-T neighborhood. `computeResponseMaps` takes the
   best label response: exact direction contributes 4, adjacent direction 3,
   and unrelated direction 0. Independent feature queries need not refer to
   distinct observed edges. More clutter offers more opportunities for a good
   local response; unmatched scene edges incur no penalty.
4. Both coarse and refined scores divide the sum by `4 * actual_feature_count`.
   A very small common pattern can thus achieve a high score. Five coarse
   features at threshold 50 need raw sum >10; three perfect contributions
   already give 12/20=60. This is an explanation of vulnerability, not proof
   that each saved FP used that particular combination.
5. `collectCandidates` uses strict `score > threshold`; refined filtering
   removes only `score < threshold`, so equality survives refinement. For
   n=5, score steps include 5 points. At threshold 85, raw 17 (85) is excluded
   at the coarse stage while raw 18 (90) is admitted. A later verifier cannot
   recover a hypothesis already excluded here. This strictness can explain
   some misses, but cannot itself explain the thousands of admitted FPs.
6. Thousands of training views/angles/scales test many correlated hypotheses.
   NMS only removes overlapping boxes; it provides no independent shape
   evidence. Exact canonical consolidation corrects output identity and
   multiplicity, not detector specificity.

Relevant source functions: `extractTemplate`, `selectScatteredFeatures`,
`hysteresisGradient`, `spread`, `computeResponseMaps`, `collectCandidates`,
`matchClass` in `line2Dup.cpp`.

## Alternatives and recommendation

| Option | Added evidence | Cost / main failure |
| --- | --- | --- |
| Reject insufficient feature counts | No new scene evidence | Cheap, but the saved L1 rule removes all five TPs; reject this approach |
| Dense oriented forward coverage, balanced spatially | Unselected template edges must be supported throughout the shape | One image preprocessing pass plus O(samples) per checked candidate; vulnerable to occlusion/weak edges |
| Bidirectional contour / unexpected-edge penalty | Also penalizes extra observed edges | More template/ROI work; internal texture, occluders and reflections can penalize real objects |

Start with the second option as an external adapter check. Record reverse
coverage as a possible later diagnostic; do not introduce its penalty in this
first experiment. A broad reverse penalty over an entire rectangle would
incorrectly treat legitimate object texture, background outside a thin object,
or an occluder as evidence against the object.

## Proposed signal and data contract

For every training template, cache an independent validation edge set in the
same L0 coordinate system as that template. For the T-LESS experiment, rebuild
the already frozen warp from the source training image and official training
mask. Use the existing 7x7 blur/Sobel/hysteresis gradient computation and the
existing strong threshold 40; select valid gradient pixels inside the official
mask. Select the strongest pixel in each fixed 2x2 canvas cell, with y/x
breaking ties. This samples many edges omitted by the sparse core template,
without weighting a thick edge by every pixel. It does not replace, cap, or
modify the core features. Preserve the sampled point and quantized orientation.

Store each point relative to `template.tl_x/tl_y`, not the silhouette bounding
box. Keep negative relative positions when a validation edge lies outside the
selected-feature bounding box. The existing bbox is not a proof that all
independent edges fit inside it. Cache the original canvas/mask coordinates,
source hash, warp, gradient settings, point count and occupied cells.

Build the scene L0 unspread one-label gradient field once per image with the
same existing weak threshold 20. For orientation k, a scene pixel supports k
when its label is k or an adjacent bin modulo eight. This keeps the core's
polarity-insensitive orientation tolerance. Build eight binary support maps
with a symmetric Chebyshev radius `r=ceil(T_at_level[0]/2)` dilation. For the
frozen TLESS T0=4 this means r=2. The radius follows the existing finest-grid
position uncertainty, not image size or a learned dataset value. No coarse
level dilation or coarse pixel units are used for this check.

For a core match m and validation point p, query at `m.x+p.x, m.y+p.y` in
the padded matching image. Equivalently subtract the input padding from both
coordinates when querying the original image. Do not apply `tl_x/tl_y` twice.
Integer training coordinates need no resampling; an SMD validation set with
subpixel coordinates must declare its deterministic rounding policy separately.

Let s(p) be 1 for orientation-compatible support within r and 0 otherwise.
Divide the validation set into a fixed 4x4 grid over its complete L0 extent.
For every occupied cell j compute `c_j = sum(s(p))/point_count_j`, then
`V = mean(c_j over occupied cells)`. Equal cell weighting prevents one long,
dense edge from hiding a missing part elsewhere. Also report the unweighted
point coverage, occupied-cell count, all cell values, and in-bounds fraction.
The score uses no requested feature count, absolute perimeter, maximum
feature count, or minimum/maximum template dimension.

The first experiment should compute diagnostic V values for all checked
candidates and evaluate three predeclared policies V>=0.50/0.65/0.80. Keep
the original matcher and post-score thresholds unchanged in this comparison.
Report every policy, including no-gain and recall-loss cases. Do not silently
select a new numerical threshold while looking at results. If a later
development-only choice is authorized, record it and freeze it before any
heldout run.

No validation points, unavailable trusted training source, or invalid metadata
means `unverified`, not a low quality score. The initial adapter must pass such
candidates through unchanged while reporting their count. A high unverified
fraction makes the experiment inconclusive. Out-of-bounds validation points
must be recorded and kept in the denominator as unsupported; do not inflate
coverage by dropping them. The first experiment excludes no template based on
validation point count.

## Large magnetic template guard

`artifacts/magnet_match/smd_manifest.json` records a 414x275 ROI with six explicit
SMD levels and point counts 1214/605/301/149/73/35. It also explicitly states
that the second embedded image's nonzero-mask semantics are unknown. Do not
use that image as an inclusion mask and do not infer contour geometry from it.
Do not regenerate this bank with the T-LESS 32-feature setting.

For a later magnet experiment, trusted supplied L0 contour points can be a
separate validation-set mode, retaining all 1214 points and preserving their
floats. Validate SMD orientation sign and image coordinates against the embedded
source before enabling any gate. Modulo-180 comparison is appropriate to the
current core; a signed-gradient gate is a separate behavior change. The six
stored dimensions are explicit (including odd sizes), not repeated integer
right shifts. A final L0 verifier neither changes nor substitutes those levels.

There must be no hard upper point count, no bbox-size rejection, no assumption
of two pyramid levels, and no buffer of 64/128/256 entries. Use dynamic
sample/cell storage and a wide count type. 1214 is within the core's existing
legal feature range (<8192); it is not an anomalous template to truncate.
The unverified/diagnostic mode remains the default until embedded-source
self-location and every supplied non-source positive preserve detections.
These guards prevent a size/count rule from rejecting the magnet template;
they do not mathematically guarantee that an untested edge-coverage policy has
zero false negatives.

## Placement and speed

Keep this check outside production and after the frozen core's canonical
output. Run it before adapter NMS so a rejected high-score FP cannot suppress
a lower-score valid detection. The retained core template ID defines the
validation set; canonical dedup has already removed alternative IDs for the
same class/x/y/score. This experiment cannot claim to test those discarded
template-specific validation sets.

For a first correctness oracle, verify every candidate passing the same frozen
post-score filter, then run the existing NMS. For an equivalent faster path,
process candidates in the same canonical score order: if a candidate overlaps
an already accepted, verified candidate by IoU>0.3, suppress it immediately;
otherwise verify it and accept it only if it passes. A rejected candidate must
never suppress a later candidate. With candidate-independent verification,
this lazy order is exactly equivalent to full verification followed by NMS.
It is not top-K truncation. Mark skipped candidates as NMS-suppressed, not
verified. Worst case, when everything fails verification, every post-score
candidate still needs checking.

Support maps cost O(8*image_pixels) work and eight byte maps: 2.34 MiB for
640x480, excluding dilation scratch. These are shared by every template in
that image. Store each template's validation points once. Each checked
candidate then costs one map lookup per sample plus cell accumulation,
O(N_validation). A 1214-point magnet candidate requires 1214 queries, not a
new full-image search and not a 16x16 local score map per feature. Total
verification cost is O(sum of samples over attempted candidates), so the
hundreds of thousands of raw TLESS candidates can still be expensive. Count
raw/post-score/lazy-attempted/passed/suppressed candidates and actual point
queries. No latency estimate should be substituted for measurement.

Existing final gradient fields are private workspace data. A first isolated
adapter may create a public `ColorGradientPyramid` once per image to reproduce
the same unspread field, paying an additional gradient pass. Do not claim
production latency based on an experiment that reuses private fields without
accounting for that architectural change. Measure support preparation,
validation, NMS, and full external-call latency separately.

## Independent validation and promotion criteria

1. Literal scalar cases: exact edge, adjacent/wrapped orientation, unrelated
   orientation, blank/clutter field, two shapes with the same sparse features
   but different omitted edges, every one-pixel boundary around r, nonzero
   padding/tl offsets, negative relative validation points, odd dimensions,
   template/image boundaries, and unequal cell densities. Use a direct
   per-point neighborhood-loop oracle to check the dilated maps exactly.
2. Test full-verify-then-NMS against lazy verification field by field, including
   a failing high-score candidate overlapping a passing lower-score candidate.
   Preserve original float scores, boxes, IDs and ordering for retained matches.
3. Add size stress for 5, 32, 1214 and 8191 validation points, six-level metadata,
   and a 414x275 contour. This verifies storage and coordinate behavior, not
   real detection quality. Test unverified pass-through explicitly.
4. Use frozen V11 sources and the existing tiny development inputs only.
   Keep templates, coarse threshold, original post-score policy, NMS and bbox
   rules fixed. Existing coarse-50/post-85 diagnostics are a different protocol
   from a new coarse-85 run; do not compare them as the same experiment.
   Reuse raw candidate caches only when exact core/bank/policy provenance and
   complete candidate recovery are confirmed.
5. Save per-candidate V/cell coverage and reject reason, TP/FP/FN by frame,
   negative FP counts, per-object results and quality by L0/L1 count, size,
   view, visibility and validation-set mode. Report precision at the original
   TP count, along with the full tradeoff. A variant that reduces FP by
   discarding existing TPs is a tradeoff, not an unconditional improvement.
6. For the magnetic samples, preserve embedded-source localization and every
   supplied known-positive detection in diagnostic comparisons before any
   gate becomes a candidate default. Do not infer negatives or accuracy from
   an all-positive sample pack.
7. Run exclusive paired timings only after correctness and development quality
   results justify the added work. Keep preparation cost, no-gain cases,
   worst-case attempted-candidate counts and memory visible.
8. Expanded development can test generalization after this design and the
   candidate policies are frozen. Original tiny heldout, new heldout scenes,
   and reserved objects remain outside policy selection. Promotion requires
   independent review and a frozen final evaluation under the existing
   authorized workflow.

## Failure boundaries

- It cannot recover no-candidate failures caused by coarse threshold equality,
  missed viewpoints/scales, bad SMD conversion, pyramid geometry or input
  padding. Those need boundary diagnostics before adding a final gate.
- Occlusion, weak contrast, blur, specular edges and different 3D viewpoints
  can remove otherwise valid dense template edges. Equal spatial weighting
  can increase this penalty for an occluded region.
- Similar textureless parts can share an entire contour; edge coverage alone
  cannot establish identity in that case. Depth, richer training views or
  object-specific structure may be required.
- Clutter can still support many dense edges, especially at large r. The
  proposed radius is therefore derived from the finest search grid and is
  not enlarged to rescue failures.
- The gradient preprocessing and orientation tolerance are correlated with
  core scoring. Independent evidence comes from omitted edges and spatial
  balance, not an independent sensor. If that does not separate development
  TPs/FPs, retain diagnostics and reject this proposal rather than adding
  successive tuned thresholds.
- A trusted training mask/source is required to build the TLESS validation
  set. SMD mask semantics and subpixel angles need their own proven adapter.
- A warped image's black exterior can produce a strong training silhouette
  edge that is weak against the real scene background. The mask is not proof
  that this photometric edge will be visible at inference time.
- Runtime may regress badly when many high-score candidates fail, because
  lazy NMS cannot skip them. Do not promise a net speed gain from this design.
