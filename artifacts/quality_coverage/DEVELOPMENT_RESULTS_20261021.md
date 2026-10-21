# Dense oriented coverage: development results, 2026-10-21

The frozen recipe reduces some false positives, but does not justify a default
production gate. V>=0.65 keeps the detected ground truths in both development
sets while leaving almost every negative image with a false alarm. V>=0.80
removes substantially more false positives and loses recall. No threshold was
added or adjusted after seeing these results. The matcher core, template banks,
match/post-score thresholds, bounding boxes and public evaluator are unchanged.

## Scope and frozen inputs

- Recipe: `COVERAGE_PROTOCOL.json`,
  `dense_coverage_actual85_development_v1`; V>=0.50/0.65/0.80, radius 2,
  exact-or-adjacent modulo-8 directions, balanced 4x4 occupied cells.
- Exact padded grayscale scene input; strict squared magnitude >1600;
  strongest valid point per fixed 2x2 canvas cell inside the official warped
  mask. No feature-count cutoff or point cap.
- Match threshold 85 **at the actual matcher call** and post-score >=85;
  class-aware NMS with strict IoU>0.3; correctness IoU>=0.5. Each policy starts
  from the complete post-score candidate set and runs independent lazy NMS.
- Raw candidate reuse only: verified complete fallback/fused exact equality,
  canonical identity, score bits, boxes, archives, bank, source and dataset/image
  SHA. The coverage program calls no matcher. It does reconstruct the existing
  bank from the frozen training images and checks all serialized pyramid fields
  and ordered feature `(x,y,label)` values before evaluating any scene.
- Tiny has 16 development images, 8 target GT and 8 target-negative images.
  Its historical bank was extracted at V10, core `c41f047`; its actual-85 raw
  matching run used frozen V11 `b25df46`. This historical-bank limitation is
  preserved explicitly. Expanded object 1 has 400 development images, 50 target
  GT, 350 target-negative images, and a V11-extracted bank.
- No tiny heldout, expanded heldout, object 25 or object 29 image is read.
  Development images are permitted for design diagnosis; these are not heldout
  accuracy estimates or a claim of general industrial accuracy.

## Detection metrics

All-GT metrics use the unchanged public IoU matching and greedy assignment.
Precision, recall and F1 below are percentages. All three predeclared policies
are reported, including no-gain and recall-loss outcomes.

| Tiny, 16 frames | TP | FP | FN | Precision | Recall | F1 | Negative FP | Negative frames with FP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 5 | 338 | 3 | 1.4577% | 62.50% | 2.8490% | 177 | 8/8 |
| V>=0.50 | 5 | 335 | 3 | 1.4706% | 62.50% | 2.8736% | 175 | 8/8 |
| V>=0.65 | 5 | 279 | 3 | 1.7606% | 62.50% | 3.4247% | 145 | 8/8 |
| V>=0.80 | 4 | 59 | 4 | 6.3492% | 50.00% | 11.2676% | 35 | 8/8 |

Tiny visibility>=0.5 metrics equal all-GT metrics because all 8 GT qualify.
At V>=0.65, FP falls 17.46% and all 5 baseline GT/detection identities survive.
At V>=0.80, only 3/5 baseline GT survive and 2/5 original TP identities survive;
one newly detected GT and alternative template assignments give 4 total TP.
In scene 5, original GT at images 293 and 436 are lost, image 127 gains a TP,
and image 7 uses a different TP template. Reporting only the net TP drop of one
would conceal this turnover.

| Expanded object 1, 400 frames | TP | FP | FN | Precision | Recall | F1 | Negative FP | Negative frames with FP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 37 | 7842 | 13 | 0.4696% | 74.00% | 0.9333% | 6874 | 350/350 |
| V>=0.50 | 37 | 7782 | 13 | 0.4732% | 74.00% | 0.9404% | 6825 | 350/350 |
| V>=0.65 | 37 | 6397 | 13 | 0.5751% | 74.00% | 1.1413% | 5640 | 350/350 |
| V>=0.80 | 32 | 1195 | 18 | 2.6080% | 64.00% | 5.0117% | 962 | 286/350 |

Expanded visibility>=0.5 has 49 eligible GT. TP/FP are the same for every policy;
FN is respectively 12/12/12/17 and recall is 75.5102/75.5102/75.5102/65.3061%.
The one lower-visibility GT is not detected by any variant. At V>=0.65, FP falls
18.43%, all 37 detected GT survive, and 36/37 original TP identities survive.
The changed identity at scene 7/image 155 is an NMS reassignment: the original
template 540 has V=0.69588 and passes the gate, but another passing candidate is
now accepted earlier. At V>=0.80, only 31/37 original detected GT and 19/37
original TP identities survive; 32 total TP therefore do not mean all original
detections were retained.

## Separation limits and low-feature guard

The expanded baseline's V distributions overlap:

| Baseline selected label | Count | V min | V median | V max | L1 feature count min/median/max |
| --- | ---: | ---: | ---: | ---: | --- |
| TP | 37 | 0.650769 | 0.821187 | 0.963888 | 5 / 6 / 9 |
| FP | 7842 | 0.408905 | 0.689164 | 0.998798 | 5 / 6 / 20 |

All 37 TP use fewer than the requested 16 coarse-level features. No count cutoff
is applied. The highest FP coverage exceeds the highest TP coverage: a single
coverage threshold cannot cleanly separate these detections. The dense check
adds omitted template edges and spatial balance, but uses the same unsigned
gradient evidence and still does not penalize extra observed edges. High dense
coverage alone does not establish the target object's identity among similar
textureless parts or clutter. The resulting specificity remains inadequate.

All 2939 tiny and 78600 expanded post-score candidates are verified; unverified
pass-through count is zero in each run. No candidate is silently discarded for
too few/many validation points, missing evidence, frame borders or template size.
Point centers outside the map stay unsupported in their original denominators.
Original-frame in-bounds fraction is recorded separately from padded-map
in-bounds fraction; padded edge evidence can contain artificial border contrast.

## Full and lazy validation

For every frame and every policy, full verification followed by NMS matches
independent lazy verification in retained input identity/order and every retained
coverage field. Both paths also match the existing public NMS in original
detection fields/order. Rejected candidates cannot suppress later candidates.
The complete per-candidate cache is retained, not a cache populated by only one
policy's lazy pass.

| Dataset / policy | Lazy attempted | NMS skipped | Point queries |
| --- | ---: | ---: | ---: |
| Tiny V>=0.50 | 343 | 2596 | 199152 |
| Tiny V>=0.65 | 397 | 2542 | 228747 |
| Tiny V>=0.80 | 1219 | 1720 | 759694 |
| Expanded V>=0.50 | 7946 | 70654 | 5429414 |
| Expanded V>=0.65 | 10175 | 68425 | 6976015 |
| Expanded V>=0.80 | 46504 | 32096 | 32335340 |

The full tiny cache costs 2394890 point queries; expanded costs 63825092.
Stricter gates can increase lazy work because rejected candidates stop acting
as suppressors. These are query counts, not measured speedups.

The standalone helper has a separate scalar support/coverage oracle and
independent interval-geometry/index-sort NMS oracle. The image-output independent
review reruns scalar coverage from cached points/cells, reconstructs NMS and
metric assignments from complete rows, and verifies all recorded output/input
hashes without decoding an image or calling the matcher. See the separate
independent audit/review artifacts for their precise scope. Neither helper
equivalence nor raw core equivalence is an accuracy measurement.

The independent image-free numeric reviews completed with exit 0:
`TINY_ACTUAL85_INDEPENDENT_REVIEW.md` and
`OBJ1_FULL400_INDEPENDENT_REVIEW.md`, with corresponding
`tiny_actual85_coverage_independent_audit.json` and
`obj1_full400_coverage_independent_audit.json`. The helper owner then rechecked
every audited output SHA and the audit-script SHA against those reports; both
sets remained unchanged. The numeric audit does not independently recompute
pixel-to-edge support from the images.

## Costs: diagnostic timings only

Runs used the same executable, four OpenMP threads, and no concurrent matcher.
The adapter deliberately recomputes the L0 gradient; it cannot reuse private
core fields. Phase boundaries contain audit work and I/O. This is not a paired
end-to-end performance benchmark and it establishes no latency gain.

| Phase | Tiny total / mean per frame (ms) | Expanded total / mean per frame (ms) |
| --- | --- | --- |
| One-time exact training reconstruction/verification | 8756.65 / n/a | 10056.72 / n/a |
| Second gradient + eight support maps | 396.38 / 24.7739 | 8615.27 / 21.5382 |
| Full candidate verification + CSV | 85.76 / 5.3603 | 1848.20 / 4.6205 |
| Baseline + three full/lazy/public NMS comparisons + metrics | 17.51 / 1.0946 | 397.15 / 0.9929 |

Gradient and map construction are timed together; no separate gradient-only or
map-only speed claim is available. The last row includes all policies and
equivalence checks, so it is not one production policy's NMS cost. Reducing point
queries does not remove the new preprocessing pass or one-time bank work.

## Evidence and provenance

Frozen numeric outputs:

- `run_20261021_tiny_actual85_coverage/`: exit 0,
  16 development frames, finished `2026-10-21T20:08:25+08:00`.
- `run_20261021_obj1_full400_coverage/`: exit 0,
  400 development frames, finished `2026-10-21T20:14:03+08:00`.
- Each directory contains complete `all_post85_coverage.csv.gz`,
  `validation_points.csv.gz`, `validation_templates.csv`, exact bank geometry,
  per-frame metrics/detections, scene preparation, stdout/stderr, verified
  input hashes, build/source snapshot, and execution provenance.
- Shared executable SHA256:
  `5D08F5722EB022F9F34743A152882592BD7DF244FCB0D86CE77BF711BB450645`.
- Shared build manifest SHA256:
  `CD477C0942AC615F29DC5485A5C6DDAD7B550CEFF47732A65F62F4661E248768`.
- Tiny metrics SHA256:
  `D235F6B6A7D2740DA27EA2D28FC140A5E3C30BC8A398B5F91F6F355A1BF3E828`.
- Expanded metrics SHA256:
  `2A047312B1DE37BA6233AE6E4CF2FE2A523D1F6C1960867E6CA079EBBF7E66EE`.

The original runner field `dataset_images_evaluated=1` is an evaluate-mode
boolean, despite its misleading name; it is not the number of decoded images.
The authoritative evaluated-frame count is `coverage_metrics.frames` and the
matching number of unique rows in `scene_preparation.csv`. Training images are
also decoded for reconstruction. Frozen evidence is preserved without editing
that field after the run. Both runs record unchanged input/source hashes and
zero heldout reads; the read-only provenance audit explicitly enumerates the
allowed selected development/training members.

## Decision and further work

Keep this check as an isolated diagnostic experiment. Do not change the default
matcher or adapter pipeline, select a new V threshold, claim a general accuracy
improvement, or claim a speedup from these results. V>=0.65 offers a modest FP
reduction at retained detected GT, but industrial use still cannot tolerate
hundreds/thousands of false positives. V>=0.80 is an explicit precision/recall
tradeoff with newly lost GT. The magnetic positive regression is a separate SMD
adapter/scale-coverage result, not evidence for this T-LESS gate; SMD mask and
subpixel coordinate semantics must remain separate.

The fixed recipe can be evaluated on additional already-authorized development
objects to expose generalization failures. A new verifier using different
evidence, better search/view/scale coverage or a new preprocessing architecture
requires a separately declared experiment and independent validation. Existing
heldout and reserved objects stay sealed during that work.
