# Next diagnostic: exact scores before changing the descriptor

Status: static proposal only. No images, response maps, native programs, or
matcher calls were accessed or executed for this design. A future run requires
its own pinned inputs, source snapshot, call budget, and coordinated CPU slot.

## Why score first

A hybrid template changes feature origins, contrast, texture contribution,
orientation distribution, and potentially the number and spread of usable
features. An accuracy change would not isolate which of those factors mattered.
The current raw lists cannot establish the reason for absence: their score
cutoff is 85, and they are already consolidated across templates.

The next diagnostic should leave training banks, matcher source, source image
processing, thresholds, and NMS untouched. Use a separate translation unit with
the pinned private V11 source and public template accessors. It may call the
unchanged internal scoring functions for diagnostics; no production matcher
source should be edited. Its output is an oracle diagnosis, not a deployable
detector or an accuracy gain.

## Scope and controls

Fix all 215 common-padding RGB all-GT TP identities, consisting of the 67 lost
and 148 retained identities, across all six objects. Probe both RGB and binary
templates at each RGB TP's training-image/angle/scale identity and physical
placement. The retained identities are controls; the experiment must not tune
on the losses or search for a favorable subset. Also verify a fixed set of
known emitted raw rows against their exact saved score bits before interpreting
an absent response.

Existing response maps were not saved in V22, so the existing CSVs alone cannot
produce these counterfactual scores. A future run must recreate the original
grayscale response-map pipeline from the pinned development images, after the
formal timing run finishes. It must never process held-out scenes or reserved
objects. This document itself does not authorize or perform that execution.

## Coordinate and score requirements

Map templates by `(object, training image, angle, scale)`, never by numeric
template ID across arms. Preserve the RGB official-box placement. For a binary
metadata record with `warped_mask_bbox=(sx,sy,w,h)` and cropped feature origin
`(tl_x,tl_y)`, the corresponding encoded match anchor is:

```
x_binary = rgb_official_box_x + 64 - sx + tl_x
y_binary = rgb_official_box_y + 64 - sy + tl_y
```

Using identical `match_x/match_y` across arms is wrong when feature-crop origins
differ. The desired anchor can be off the native grid. Record that fact and
probe the predetermined floor/ceiling native-grid neighbors independently of
the oracle point; do not call an off-grid high score a pruning failure.

For each level, record actual serialized feature count and per-feature integer
response contributions. Preserve the exact binary32 operation order
`(raw_sum * 100.f) / (4 * feature_count)`. The configured feature budget of 32 is
not the denominator for every level: `ColorGradientPyramid::pyrDown` halves
the requested feature count, and the serialized level count is authoritative.

The native output coordinate has an offset
`T/2 + (T%2 - 1)`; a score lookup must use the corresponding response-map origin,
not simply add the returned `Match.x/y` to each feature. At level 0, `T=4` and
the match grid has offset 1. At level 1, `T=8` and offset 3. The scalar oracle
must first reproduce saved emitted scores and the existing optimized path,
including clipping, adjusted-feature checks, LUT values, and spread rules.

## Trace the complete admission path

For each fixed anchor and its legal native-grid neighbors:

1. Record exact fine-level scalar score and whether it satisfies `score >=85`.
2. Enumerate **every** coarse seed whose actual clamped 16x16 fine window
   contains that legal grid point. A single nearest coarse seed is insufficient:
   overlapping refinement windows can reach the same point. Preserve native
   coarse domain/zero cells and the exact `x=2*coarse_x+1` clamping rules.
3. Record each parent coarse score and strict admission `score >85`.
4. For every admitted parent, record the exact 16x16 winner and first row-major
   tie winner. A fine point can score well and still not be emitted because a
   stronger or tied local maximum is selected elsewhere.
5. Record the pre-consolidation output, then the representative selected by
   unchanged `consolidateMatches`. Its equality key is class/x/y/score and
   ignores template ID. The smallest template ID represents a collision;
   different templates can map that same match coordinate to different boxes.
   Therefore a valid pre-consolidation box can disappear before the saved raw
   CSV and before NMS.
6. When an emitted post-consolidation candidate exists, record NMS rank/blocker
   and GT assignment as in the current numeric diagnosis.

This produces a deterministic path explanation: fine score insufficient,
off-grid anchor, no admitted coarse ancestor, local winner displacement,
cross-template representative loss, NMS suppression, or GT assignment.
Categories that depend on an anchor's bbox must explicitly state the IoU being
tested. Score sufficiency at one RGB placement is not proof that all viable
binary placements or all possible templates fail.

A synthetic counterexample explains the consolidation caveat: two matches have
the same class, match x/y, and score 90, but template IDs 1 and 2 map to official
boxes `(0,0,4,10)` and `(0,0,10,10)`. For GT `(0,0,10,10)`, their IoUs are 0.4
and 1.0. Keeping only the smallest template ID removes the valid box even
though both had an admitted score. This is a possibility implied by the source,
not a claim that any of the 57 observed losses has that cause.

## Interpretation and follow-up gate

If the binary fine score is consistently insufficient at placements where the
RGB control matches, a template-feature experiment is justified. If fine scores
pass but coarse ancestors fail, test the coarse admission rule as a separate
single variable. If fine/coarse pass but local maxima or consolidation remove
the valid box, change only that stage in a later isolated experiment.

Do not start the hybrid experiment until these categories are measured. Any
subsequent change must be evaluated on the full fixed 400-frame/six-object
schedule, preserve the 59 binary-only identity gains in its regression report,
and report negative-frame false positives. No threshold sweep, subset tuning,
or generalization claim follows from this diagnostic.
