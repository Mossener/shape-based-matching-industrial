# Independent review: coverage integration with the T-LESS adapter

Status: static integration review only. This review reads `DESIGN.md`,
`PADDING_POLICY.md`, the current helper headers, the core, and the public
evaluation adapter. It does not train, rematch, read heldout RGB, modify the
frozen baseline, or establish an accuracy/speed gain.

The proposal is suitable for an isolated diagnostic experiment. It should not
become a default rejection rule until the adapter contracts below are fixed
and their integration cases pass. The standalone scalar/helper tests do not
exercise OpenCV quantization, training reconstruction, metadata lookup, or
the padded-image coordinate transform.

## 1. Required interfaces

### Template identity and reconstruction

The validation cache key must include `(class_id, template_id)` and the exact
bank/source/recipe hashes. Template IDs are per class, not global. Build one
entry for each successful `addTemplate` ID; failed training attempts do not
consume IDs. Keep an explicit unavailable/untrusted entry instead of shifting
the subsequent cache entries or treating a missing entry as zero coverage.

The existing `TemplateMeta` stores training image ID, angle, scale, silhouette
box and `tl_x/tl_y` (`tless_eval.cpp:27,115-126`). That is enough only when
joined to the frozen training index/config/attempt CSV and the same recipe.
It does not, by itself, identify the RGB/mask SHA, crop rectangle, canvas,
full double-precision affine matrix, interpolation/border modes, gradient
recipe or dense sampling rule. A new validation-cache manifest should record
those inputs and assert consistency with the bank and metadata. Hash or
recipe mismatch is a run-integrity failure; lack of a trusted per-template
validation source is an explicitly reported `unverified` pass-through.

Rebuild the exact current training warp (`tless_eval.cpp:128-162`):

1. Decode the official training RGB as grayscale and the official mask as
   grayscale, find the nonzero mask bounding rectangle, and crop both using
   that rectangle.
2. Compute `side=align16(ceil(hypot(roi.width,roi.height)*scale)+2*border)`.
   Rotate/scale about `(roi.width/2.f,roi.height/2.f)` with
   `getRotationMatrix2D`, then apply the existing canvas-center translations.
3. Warp grayscale with `INTER_LINEAR` and mask with `INTER_NEAREST`; both use
   `BORDER_CONSTANT(0)` and the same square canvas.
4. Reuse the angle already present in the warped pixels. Do not rotate dense
   coordinates or labels by `TemplateMeta.angle` a second time.

The current crop contains the source pixels throughout the rectangular ROI;
it is not first multiplied by the object mask. Keep that behavior during
reconstruction. Applying a mask to image pixels before blur/Sobel changes the
photometric edges and creates a different experiment.

Prefer extracting the dense validation set while the exact training `warped`
and `warped_mask` are available, then associate it with the successful ID.
If reconstructed later, verify the warp/mask hash and `tl_x/tl_y` against the
saved bank rather than accepting visual similarity as equivalence.

### Dense samples and cropped template origin

The source for a validation point is an integer L0 warped-canvas pixel
`q=(qx,qy)`. Use the declared original warped official mask inclusion rule,
not a silhouette rectangle. The core erodes its extraction mask once and
applies 5x5 magnitude NMS (`line2Dup.cpp:451-507`); the proposal deliberately
uses denser omitted-edge evidence and must not accidentally reproduce those
selection steps.

For the declared recipe, use a valid core hysteresis orientation and strict
`magnitude > 40*40`, since `magnitude` stores squared Sobel magnitude. Comparing
it to 40 is incorrect. Choose the strongest eligible pixel in each fixed 2x2
canvas cell, breaking equal-magnitude ties by y then x. State that cells are
anchored at the warped canvas origin (`qx/2,qy/2`), not at a recomputed object
box. Preserve the quantized label chosen by the hysteresis histogram; simply
rounding `angle_ori` is not the same orientation rule.

`cropTemplates` takes feature extrema over *all* pyramid levels in L0 units,
makes the minimum even, and shifts each level's features
(`line2Dup.cpp:111-156`). Consequently, `pyramid[0].tl_x/tl_y` is not necessarily
the L0 selected-feature minimum or the warped-mask top-left.

Use exactly this transform:

```text
relative_validation_point = q - (template_L0.tl_x, template_L0.tl_y)
query_in_padded_scene     = (match.x, match.y) + relative_validation_point
query_in_original_frame   = query_in_padded_scene - (left_pad, top_pad)
```

`prepare_template(canvas_points,tl_x,tl_y)` performs the subtraction once;
`evaluate(maps,prepared,match_x,match_y)` adds only the core match coordinates.
Feed it `Detection.match_x/match_y`, not `Detection.box.x/y`. Do not subtract
`tl_x/tl_y` again or use `warped_mask_bbox.x/y` as the validation origin.
Negative relative validation coordinates are valid and must remain stored.

The adapter's output/NMS box stays the existing official-mask box:

```text
box.x = match.x - left_pad + silhouette.x - template_L0.tl_x
box.y = match.y - top_pad  + silhouette.y - template_L0.tl_y
```

That is `boxAtMatch` in `eval_metrics.hpp:17`. Do not replace it with dense
point extent, cropped core extent, or a box computed after clipping validation
points. Such a replacement changes the frozen IoU/NMS protocol.

### Core bit masks to helper labels: explicit conversion is mandatory

`ColorGradientPyramid::quantize` returns `CV_8UC1` with **0 for no edge and
one bit `1<<k` for orientation k** (`line2Dup.cpp:214-291,444-449`). The coverage
helper accepts **255 for no edge and integer labels 0..7**. Passing the
quantized matrix bytes directly is wrong: core zero would become a valid
horizontal label, bit value 4 would become helper label 4 instead of label 2,
and several higher bits would be rejected.

The adapter conversion must implement:

```text
q == 0                 -> helper.invalid_label (255)
q == 1<<k, 0 <= k < 8   -> k
any multibit value     -> invalid input / wrong pipeline stage
```

Read matrices row by row with their actual step. A multibit pixel indicates
that a spread field has probably been supplied; do not pick one bit and
silently use it as the proposed unspread one-label field.

For scene preparation, a public `ColorGradientPyramid` at L0 with the exact
grayscale matcher input, empty mask, weak threshold 20 and the existing
gradient implementation is sufficient. Calling `extractTemplate` or
`pyrDown` is unnecessary and would introduce feature selection or coarse
coordinates. Calling it separately incurs a second gradient pass; count it.

## 2. Scene borders and padding need one frozen evidence domain

Use the exact padded image supplied to `match` when reproducing its L0
gradient context. The adapter currently pads zero on every side, preserves
left/top 64, adds right/bottom alignment, and uses 16-pixel alignment for
T=[4,8] (`tless_eval.cpp:238-244`). The actual four pad sizes belong in the
coverage manifest.

The design's phrase that a padded query is equivalent to subtracting padding
and querying the original image needs a qualification: the **coordinate
transform** is equivalent, but independent gradient preprocessing is not.
The core uses 7x7 Gaussian blur and 3x3 Sobel with `BORDER_REPLICATE`, followed
by a 3x3 orientation histogram. Recomputing on unpadded original pixels sees
replicated border intensities where the padded pipeline sees zeros. This
can affect labels up to five pixels from the original border; radius-2 support
can expose those differences farther inside. A crop of a precomputed label
field can also lose dilation support coming from its discarded halo.

For the first diagnostic adapter, use padded-field maps and padded match
coordinates consistently. Record both padded-map in-bounds fraction and the
fraction of queried points inside the original frame. A point in padding can
be in map bounds without being observed source evidence. In particular, the
zero-padding transition can create an artificial edge. Do not interpret a
high padded coverage on a border candidate as proof of support from camera
pixels. If a later policy excludes the padded halo, define when masking is
applied (before or after dilation), preserve out-of-domain points in the
denominator, and declare that as a separate evidence-domain change.

Do not mix a padded-field baseline with an unpadded-field gate or silently
clip query coordinates to the nearest valid pixel. Queries outside the
chosen map/domain must remain unsupported, and their points remain in every
cell denominator. An image with no labels is a **verified blank scene**,
not unverified metadata that should pass through.

`PADDING_POLICY.md` correctly separates geometry preconditions from final
verification. Check the full bank before matching. For T-LESS's two levels,
the refined L0 requirement is `D0 >= template_width0+64` and the coarsest
level must contain a legal full-template placement with proper divisibility.
Do not assume the small ROI or current 64 padding proves that for every view
and scale. `cropTemplates` uses `max-min`, without `+1`; check actual feature
maxima too, since a feature can lie at the declared width/height. The generic
preflight must inspect coordinates as well as extents.

If the frozen bank fails preflight, preserve that baseline failure. A new
padding policy changes preprocessing size, coarse sampling/candidates and
runtime and therefore needs its own adapter/protocol revision; it cannot be
smuggled into a coverage-only comparison or used with old raw caches.

## 3. Coverage V is different from the core score

The core first histogram-filters directions modulo 180 degrees, then spreads
bit masks over a one-sided TxT window. A response is 4 for an exact label, 3
for an adjacent label, otherwise zero. It sums over sparse selected features
and divides by `4*actual_feature_count`. A single observed edge can support
multiple selected features, and extra scene edges have no penalty.

The proposed V instead uses a binary exact-or-adjacent support decision over
dense held-out-from-selection template edges, with equal weighting of
occupied 4x4 spatial cells. Adjacent support counts as 1 rather than 0.75.
It is not a recalibration of the old score, a probability, an independent
sensor, or a drop-in replacement for `match(...,85)`. A candidate can have
high core score/low V or low core score/high V without an implementation bug.

At frozen T0=4, the core reports match positions with offset 1 while its spread
queries cover offsets [-1,+2] around that reported position. Symmetric radius
2 covers [-2,+2], i.e. a 5x5 region rather than the core's 4x4 region. This is
a predeclared verification tolerance, not bitwise equivalence to spread.
Do not feed spread labels/response maps to the verifier or tune the radius
to rescue particular failed detections. Generalizing `ceil(T/2)` to arbitrary
odd T also needs a new positional analysis; the current experiment fixes T0=4.

## 4. Low-feature and other false-rejection risks

The design correctly rejects a requested-feature-count cutoff: every saved
tiny-development TP has L1 fewer than requested 16 features. Actual feature
counts must be report strata, not a new minimum, and they must not change
the core denominator, training features or bank membership.

Dense validation has related risks even without an explicit count cutoff:

- A small or low-contrast template can have few strong validation points or
  few occupied cells. A single missing point/cell then has high weight.
  Record N, occupied cells and cell-count distribution; do not impose a
  silent minimum and do not equate low count with low quality.
- Interior-mask sampling with a strict strong threshold can produce no
  trusted validation points. Preserve the candidate as unverified with a
  reason. A high unverified fraction makes the test inconclusive.
- Warped-mask inclusion differs from the core's eroded inclusion, and edges
  near a crop/canvas transition can be photometric artifacts. Mask membership
  alone does not establish real-scene visibility.
- Blur, contrast reduction, reflections, changed 3D viewpoint, partial image
  truncation and occlusion may remove real dense edges. Equal cell weighting
  deliberately prevents one dense edge dominating, but also penalizes a
  single occluded region strongly. Report losses among existing TPs and
  visibility strata; do not call FP reduction alone an improvement.
- Low-feature/high-score core candidates may be geometrically wrong. The
  gate can reject them, but cannot recover a hypothesis excluded by coarse
  strict thresholding, scale/view coverage or pyramid geometry.
- Canonical core consolidation retains the smallest template ID for equal
  class/position/score before this gate runs. A retained ID may fail dense
  validation even if a discarded ID would pass. Record that limitation;
  testing alternate IDs requires a separate change to core output semantics.
- Never truncate the large magnet set, infer an upper point limit from the
  T-LESS feature setting, or apply the T-LESS warped-mask recipe to unknown
  SMD masks. Dynamic counts/storage and the separate SMD coordinate/rounding
  mode remain necessary.

## 5. Postprocessing integration and cache rules

The pipeline should be `canonical core output -> unchanged post-score filter
-> candidate-independent verification -> unchanged class-aware NMS -> unchanged
evaluation`. Use `canonicalLess` ordering exactly; the helper comparator
currently has the same score/class/template/y/x/box tie sequence. Keep score,
class, ID, match coordinates and NMS boxes bit-for-bit for retained candidates.

Full verification followed by NMS is the correctness oracle. Lazy verification
is equivalent for **retained output** only when it skips a candidate solely
because an already accepted passing/pass-through candidate suppresses it.
A rejected candidate must never suppress a lower-scoring one. Full and lazy
audit streams will differ: lazy skipped candidates have no V, and must not
be reported as verified/rejected or as metadata-unverified pass-through.

Run each predeclared V>=0.50/0.65/0.80 policy from complete cached per-candidate
V values or execute lazy processing separately for every threshold. A cache
from one lazy policy is incomplete for the other policies: the candidate that
suppressed a skipped row may fail a stricter gate. Do not fill skipped V with
zero, pass-through, or a guessed score. The first diagnostic full pass should
save every post-score candidate's V/cells/reason/identity, not just kept rows.

Raw candidate reuse requires identical core revision, bank, image SHA,
padding, actual matcher threshold, post-score policy and coordinate/box recipe.
The tiny coarse-50/post-85 cache and new actual-85 expanded baseline are
different protocols. Preserve exact fallback/fused candidate equality checks
before coverage so a new gate cannot hide a core mismatch.

Timing must include any new reconstruction/preparation, scene gradient pass,
8 support maps and scratch, point queries, verification/NMS and total external
call cost. Padded 768x640 maps alone occupy 3.75 MiB for eight byte maps,
larger than the 2.34 MiB 640x480 example, before scratch. Worst-case lazy work
still checks every post-score candidate. No static speed claim follows.

## 6. Necessary integration cases before development quality claims

| Case | Required assertion |
| --- | --- |
| All 8 single-bit values, zero, multibit value | Decode to labels0..7/invalid; reject spread input; an all-zero core field remains a blank helper field |
| Histogram disagreement and gradient threshold equality | Use the core histogram-selected label; exactly 40² is excluded, just above included; do not directly round `angle_ori` |
| Known asymmetric training image, 0°/30°/90°, all frozen scales | Reconstructed warped image/mask hashes and dense points agree; no extra pose rotation; same canvas/crop/interpolation |
| Failed training attempts and repeated image IDs in different classes | Cache keys remain `(class,id)`; subsequent IDs neither shift nor alias |
| Different L0/L1 feature extrema | Use actual L0 `tl_x/tl_y` from the saved bank, not mask bbox or recomputed L0-only extrema |
| Nonzero tl and padding, negative validation coordinates | Known transformed queries land at exact expected pixels; subtract origin and padding exactly once |
| Odd/non-square crop and image dimensions; non-contiguous Mat ROI | Warp center, alignment and matrix steps are respected; no row flattening assumption |
| Original-image edge/corner with zero padding | Padded quantization matches the matcher context; demonstrate the unpadded recomputation difference; record original-domain vs map in-bounds fractions |
| Point just inside/outside map; radius2 halo across original border | No coordinate clamping or denominator loss; padded-halo policy is explicit; direct-loop support oracle agrees |
| Declared template width equals an actual feature coordinate | Preflight uses real extrema and +1 coverage where needed, not extent metadata alone |
| Grid phase and positions around all T0=4 residues | Radius rule is applied in L0 pixels; distinguish [-1,+2] core spread from symmetric [-2,+2] coverage |
| Low-feature 5-point template, empty validation, 1214 and 8191 points | No requested-count/size rejection or truncation; empty/untrusted passes with reason; verified blank rejects at positive V threshold |
| High-score failing candidate overlaps lower-score passing candidate | Lower candidate survives both full and lazy paths; original fields/order agree |
| Class-aware overlap, equal scores/IDs, exact IoU=.3 | Existing class-aware NMS and strict `>` boundary remain unchanged |
| Three V policies with a threshold-dependent suppressor | Complete-cache and separate lazy runs agree per policy; skipped rows never become fabricated unverified evidence |
| Missing trusted source, mismatched bank hash and invalid label | Per-template unavailable validation passes with explicit reason; run-integrity mismatch prevents invalid experiment; no silent cache fallback |

These are prospective integration requirements, not newly executed tests.
After they pass, start with the declared existing development-only diagnostic
protocol and report every V policy, original TP retention, FP/FN changes,
unverified fraction and costs. Expanded development is a later generalization
check under a frozen recipe. Heldout scenes and reserved objects remain
sealed throughout design and policy selection.

## Review outcome

No core change is required for the proposed first adapter experiment. The
important blockers are explicit bitmask-to-label conversion, exact warp and
template-origin association, and one declared padded-scene evidence domain.
Low-feature templates should continue to pass through unchanged unless a
trusted dense set is available and that candidate's measured V fails the
declared policy. The outcome of that policy remains an empirical question.

### Frozen recipe follow-up

The subsequently written `COVERAGE_PROTOCOL.json` version
`dense_coverage_actual85_development_v1` declares the conversion, padded evidence
domain, exact training recipe, original-frame fraction, complete per-candidate
cache, three independently evaluated policies and source/raw provenance needed
above. Its stated data-recovery plan is appropriate for the isolated adapter:
recover complete actual-85 fallback/fused rows, prove exact equality, verify
bank/config/source/data/raw identities, reconstruct only allowed training and
development inputs, and preserve all rows before any coverage NMS. This is
approval of the declared static contract, not evidence that an implementation
has met it or that the image experiment has run.

When validating training reconstruction, compare every **serialized** pyramid
field and each ordered feature's `(x,y,label)`. `Feature::write/read`
(`line2Dup.cpp:66-76`) does not serialize `theta`; a bank loaded from YAML has
no trusted continuous `theta` to compare. Comparing it would read unavailable
state and could reject a perfectly reconstructed bank. Dense labels must come
from reconstructed warped-image hysteresis output, not loaded feature theta.
