# V28 independent numeric review — 2026-10-22

No substantive scope, numeric-closure, or stage-classification issue was found
in the reviewed diagnostic implementation and final root replay. This is a
diagnosis of frozen V27 outputs; it does not demonstrate an accuracy improvement
or authorize promotion of the RGB empty-mask treatment.

## Reproducible evidence

The reviewer used independent Python standard-library logic, without importing
the diagnostic/evaluator algorithms. The first temporary here-string execution
was not saved as a historical source artifact. Its calculation was then saved
as independent_review/review.py, extended with before/after source and numeric
input pins, and freshly executed twice:

| Fresh independent run | Target | Result |
| --- | --- | --- |
| independent_review/run_20261022_v1/receipt.json | run_20261022_b | passed |
| independent_review/run_20261022_v2/receipt.json | run_root_20261022 | passed |

Each receipt contains 722 unique before-and-after pins: 11 source files and 711
numeric inputs. The pins are equal before and after each run. Every pin in the
final receipt was also rehashed after the process exited and still matched.
No existing receipt, diagnostic source, or frozen numeric evidence was edited.

The final independent receipt SHA256 is:

    d09b09769278a042176775d7786674b2231bca57815d24f0e98c1d7b0cb27834

The independent review script SHA256 is:

    d0956ff6fa2232208f280be84421daa7a6dc1f3f9663819ba73f006319a42a1d

The final target result SHA256 is:

    925d96f04f63a2646ed9cdc1f48bad966d3fff1366c03223b691f407a81041ed

All five final target source snapshots match the corresponding live files.
In particular, run_analysis.py SHA256 is:

    f376bd953f93cc1edee70dd976b980b97a706b4d5af732204a46fec975e1b48f

The earlier run_b honestly retains its older run_analysis.py/test_diagnostic.py
snapshots; v1 records those differences. The five diagnostic CSV outputs in
run_b and run_root_20261022 are byte-for-byte identical. The final summary adds
explicit zero categories and binds the final source checks.

## Independently checked scope

- All 400 unique development frames, six objects and two arms: 2,400
  object-frame pairs and 4,800 unique frame-arm output rows.
- All 400 unique GT identities and all 800 unique GT-arm output rows, with exact
  identity closure against the frozen GT and frame schedule.
- All selected detections' all-GT and visibility-eligible one-to-one assignments,
  every per-frame count, pooled totals, and all four cross-arm identity groups.
- Per-object and per-scene category reports, including scenes with no target GT.
- All 350 positive object-frames / 700 positive frame-arms: 134,524 fallback raw
  rows, canonical order, complete retained candidate identities and score bits,
  raw NMS acceptance/suppression against earlier retained candidates, every GT
  category, best raw IoU/rank, raw/selected hit counts, and all suppression edges.
- All 15,179 suppression edges: full candidate/blocker identity, exact first
  retained blocker, GT/blocker IoUs, and all-GT/eligible blocker assignments.

The other 2,050 negative object-frames / 4,100 negative frame-arms are covered
through complete selected assignment and per-frame closure. Their raw archives
are not independently replayed or recounted by this review; their raw counts
are compared with frozen native numeric metrics. This review also does not
independently replay fused raw archives or template-metadata box reprojection.
The root's separate complete replay is broader; it must not be conflated with
this independent review's narrower raw coverage. The reviewer did not rerun the
root's 13-test suite.

## Verified results and interpretation

| Identity group | Count |
| --- | ---: |
| Retained | 156 |
| Lost | 59 |
| Gained | 27 |
| Neither | 158 |

The treatment's 59 lost GT identities split into 53 raw gaps and six NMS losses.
All 27 direct suppression edges for those six NMS-loss identities have all-GT FP
first blockers. The six identity tuples listed in RESULTS.md were independently
checked. The 27 gained identities correspond to 16 control raw gaps and 11
control NMS losses.

Across both arms, stage counts are control matched/raw-gap/NMS-loss/competition
215/162/23/0 and treatment 183/207/10/0. All-GT first-blocker labels across the
15,179 edges are TP 15,030 and FP 149. The ten treatment NMS-loss GTs have 40 FP
blocker edges; the 23 control NMS-loss GTs have 80 FP and four TP blocker edges,
with 22 GTs blocked only by FP and one by both FP and TP. These details agree
with RESULTS.md.

Most suppression edges belong to GTs that were ultimately matched. Their count
is not a count of lost or recoverable GT. Raw-gap means there is no saved
score-85-or-higher candidate with GT IoU >= 0.5; it cannot identify a
below-threshold, descriptor, pyramid-pruning, or placement cause. First-blocker
provenance does not prove that removing that blocker improves net TP/FP.

No matcher, native binary, image decoder, dataset image, held-out scene, or
reserved-object image was run or opened during this independent review.
