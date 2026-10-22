# Fixed design: RGB source with an empty feature-selection mask

## Status and objective

This is a source-only design checkpoint. The only objective is to test whether
the V22 grayscale RGB training source benefits from allowing the unchanged V11
feature selector to consider the full valid canvas. No source file in the
production checkout or frozen full-API closure is changed here. At this
checkpoint the new directory has zero native compilations, matcher calls,
dataset image decodes, SMD reads and serialized template-bank reads.

The treatment is the exact missing factorial cell:

```cpp
// control: frozen V22 RGB training
detector.addTemplate(warped_gray, class_id, warped_official_mask);

// treatment A: this experiment
detector.addTemplate(warped_gray, class_id, cv::Mat());
```

`warped_gray` is the existing grayscale RGB warp. The official mask still
determines the source ROI, affine, nearest-neighbor warped geometry and
official silhouette box. The empty matrix is only a feature-selection argument;
it is not an empty source image and does not remove object geometry.

The implementation source of record is the frozen RGB trainer in
`artifacts/silhouette_empty_mask_experiment/frozen_helpers/tless_eval.cpp`
(the crop/warp and original `addTemplate` call), together with the diagnostic
and coverage structure in `silhouette_eval.cpp`. The private V11 implementation
is the 23-file snapshot bound by `PRIVATE_SOURCE_FREEZE.json` at revision
`b25df46f6ddf9c24fb43f5836f1414dc38c8caed`. The mutable production checkout and
the full-API generated sources are not valid implementation inputs.

## Fixed training recipe

Train every one of the 72 official views for objects 1, 2, 5, 8, 12 and 17,
with scales `0.75, 1.0, 1.5, 2.0`, angles `0..330` by 30 degrees, border 16,
pyramid `T={4,8}`, weak threshold 20, strong threshold 40 and requested layer
targets 32 and 16. That is 3,456 attempts per object and 20,736 attempts in
total. The original source-only and V22 pose keys are controls for geometry and
coverage; template IDs are arm-local and are never joined across arms.

Every attempt is retained, including a failure reason. A successful attempt
records both actual layer feature counts, actual `tl_x/tl_y`, extents, canvas
dimensions and minimum distance from each selected feature to the real layer
canvas edge. Requested 32/16 are targets, never upper bounds: an actual count
such as 44/23 must be retained. No feature is filtered, padded, capped or
assigned to a missing pose after extraction.

The frozen RGB control has arm-local successful-template counts
`[2153, 2646, 3416, 3456, 3372, 3156]` for objects
`[1, 2, 5, 8, 12, 17]` respectively. The treatment counts are unknown until
the one-shot training stage and must be read from its own freeze. No runner or
auditor may assume 3,456 successful templates for a treatment object.

For every pose, the source crop, affine matrix, canvas side, official warped
mask box and pose key must equal the frozen RGB control. The new template's
actual `tl_x/tl_y` is used later in box conversion:

```text
box = match - left_top_padding + official_warped_mask_origin - actual_template_tl
```

The official mask width and height remain the box dimensions. A feature box is
never substituted for the official silhouette box. If any pose is missing,
any extraction exception occurs, any object has zero successful templates, or
any geometry differs, the training stage is incomplete and all later image
quality stages are forbidden. The failed attempts stay in the evidence.

## Fixed 848×832 geometry gate

Before any development image is decoded, load metadata for all six frozen RGB
objects and all six new treatment objects. The union must fit exactly in the
pre-registered 848×832 padded image: source 720×540, left/top 64, 16-pixel
alignment, and right/bottom 64/228. The gate checks every layer's declared
extent and every actual selected-feature coordinate after its pyramid scaling.
It also checks the declared one-billion-byte dynamic-memory and one-million
raw-candidate ceilings.

If 848×832 does not contain the complete union, the experiment stops. It does
not silently enlarge padding, drop a large template, change the source origin,
or continue with a partial bank. A later larger-padding experiment would be a
new, symmetric protocol with fresh RGB controls.

The tight rectangular crop and zero-valued warp border are retained exactly.
Therefore an empty selection mask can admit gradients at the crop-to-black
boundary or background inside the rectangle. Those artificial-edge risks are a
declared limitation and are not removed after seeing results.

## Quality scope and pre-registered decision

Only if training and the 848×832 gate pass, compare the frozen V22 RGB bank and
the new RGB-empty-mask bank on all 400 development frames for each of the six
objects. Keep match/post threshold 85, NMS IoU 0.3, GT IoU 0.5 and visibility
eligibility 0.5. Run both fallback and fused paths, retain complete raw ordered
records and score bits, and verify that the two paths agree for each arm.

The primary practical hypothesis is **count dominance**:

```text
TP(treatment) >= 215  AND  FP(treatment) < 42112
```

The two comparisons are simultaneous; meeting only one does not pass. Report
precision, recall, F1, mean matched IoU, raw candidate count and selected count
for all-GT and visibility-eligible subsets. Report negative-frame FP count,
negative frames with FP, and FP totals separately.

The fixed identity report has four historical V22 strata over 400 GT
identities: 148 retained by both prior arms, 67 prior RGB-only, 59 prior
binary-empty-mask-only and 126 detected by neither prior arm. These strata are
diagnostics, never tuning subsets. For each stratum report RGB versus the new
treatment, every object and every scene, including object 1's known regression
in the prior binary experiment. A new result must not be called a recovery of
the 67 prior losses unless the full identity and pose mapping supports that
statement.

## Independent checks and timing boundary

The quality stage is separate from its independent standard-library audit. The
audit must reparse every raw archive, score bit, ordering and multiplicity;
recompute NMS, all-GT/eligible assignment, IoU and identity strata; and verify
the saved summaries without importing the evaluator or running a matcher.
Any audit disagreement stops publication of the quality result.

The quality loader obtains each treatment object's expected template count from
the accepted treatment training freeze and checks that loaded metadata and
serialized classes agree with that count. Successful-pose coverage differences
are reported as treatment observations and are never equalized by dropping RGB
templates or inventing treatment poses.

Timing is a later, separately reserved stage. Use a fixed 64-frame schedule,
one warmup round, seven measured rounds and four rotating arm/path positions.
Each timed call must equal its own frozen quality reference. Report matcher
time and external call time separately; decoding, bank loading, archive IO and
comparison are outside those clocks and reported separately. The V22 finding
that fewer selected FP can coexist with more raw candidates is retained, so
FP reduction alone cannot be described as a speedup.

Held-out scenes and objects 25/29 remain sealed. The result is development
evidence only; it cannot promote a default or establish industrial
generalization without a separately frozen confirmation protocol.
