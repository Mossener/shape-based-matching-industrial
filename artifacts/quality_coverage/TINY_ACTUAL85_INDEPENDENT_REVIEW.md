# Independent review of tiny actual85 coverage

The frozen run is
`run_20261021_tiny_actual85_coverage`, completed with exit code 0 on
2026-10-21 at 20:08:25 +08:00. The independent numeric audit also exited 0:

```powershell
py -3.10 artifacts/quality_coverage/audit_coverage_result.py --run artifacts/quality_coverage/run_20261021_tiny_actual85_coverage --output artifacts/quality_coverage/NEW_independent_audit.json
```

Its saved evidence is `tiny_actual85_coverage_independent_audit.json`.
The audit script SHA-256 is
`165f22f7a5282a201ede1fa1ef1bc63e35b85df64573a1572934a318d1da52c3`.
It uses Python's standard library and neither imports the matcher/coverage
code nor starts either executable. It opens no dataset RGB or mask file and
decodes no image. Reading `index.json` includes annotation metadata; it does
not open heldout image members.

## What was independently checked

- All 12 output-file hashes in `execution_provenance.json`, before and after
  the streamed audit; the build-manifest and verified-input hashes; all seven
  copied source files against the frozen build manifest.
- All 32 original fallback/fused raw-archive SHA values, gzip CRCs and full
  CSV streams. The two variants and every coverage row have exactly the same
  retained original identity/box fields and float32 score bits: 2,939 rows
  per variant across the same 16 development frames.
- All 2,212 validation-template records and 3,487,590 serialized validation
  points: sequential indices, labels, subtraction of the saved template
  origin once, inclusive-span 4x4 cell assignment, per-cell denominators,
  and candidate query bounds. The points include 169,785 negative relative
  offsets; those were retained, not clipped. The frozen bank's 4,424 geometry
  rows report no feature-extent, local-interval or coarse-placement failure.
- Every candidate's cell/support sums, balanced and unweighted ratios,
  original/map-domain fractions and the total 2,394,890 full point queries.
- Independent full and lazy NMS on the complete cached candidate set for all
  three declared thresholds; every retained original field/order and every
  selected detection's GT/eligible label. This covers 48 coverage-policy
  frame evaluations plus 16 baseline frame evaluations. Independent lazy
  attempt/suppression/query counts agree with every per-frame record.
- One-to-one IoU evaluation and aggregate/per-scene TP/FP/FN, precision,
  recall, F1, mean TP IoU, negative-frame errors and both retention measures.

Actual pixel-to-edge support and reconstruction of saved pyramid features
were performed by the frozen C++ adapter. This image-free numeric audit
does not independently repeat those operations. Its full/lazy check uses the
complete cached scores; agreement of freshly recomputed lazy coverage fields
is supported by the frozen adapter's assertions and clean exit, not a second
independent image pass. The earlier helper/oracle and integration selftests
remain distinct evidence.

## Observed results

All numbers below use the frozen actual matcher threshold 85, post-score
threshold 85, NMS IoU >0.3 and one-to-one GT IoU >=0.5. The 16 frames contain
eight target-positive and eight target-negative frames, and eight target GT.
All GT happen to satisfy the eligible visibility rule in this slice, so its
allGT and eligible totals are equal.

| Policy | TP | FP | FN | Precision | Recall | Original GT retained | Original TP detection retained | Negative FP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 5 | 338 | 3 | 1.458% | 62.5% | 5/5 | 5/5 | 177 |
| V >=0.50 | 5 | 335 | 3 | 1.471% | 62.5% | 5/5 | 5/5 | 175 |
| V >=0.65 | 5 | 279 | 3 | 1.761% | 62.5% | 5/5 | 5/5 | 145 |
| V >=0.80 | 4 | 59 | 4 | 6.349% | 50.0% | 3/5 | 2/5 | 35 |

Every policy still produces at least one FP on **all eight negative frames**.
The respective total FP reductions are 0.89%, 17.46% and 82.54%. Those are
candidate-output observations on a development slice, not industrial quality
or generalization estimates.

The V >=0.80 aggregate of four TP must not be described as merely losing one
old positive. In scene 5, it loses the previously covered GT in images 293
and 436; image 127 becomes newly covered. Image 7 keeps the same GT using a
different candidate/template (baseline template 209 is replaced by 128).
Images 215 and 353 keep their original TP detections. Thus only three of
five old GT, and two of five original TP detection identities, are retained.

V >=0.65 retains the five existing GT and detection identities but leaves
279 FP and does not increase recall. V >=0.50 is almost neutral. The fixed
recipe cannot recover core-excluded candidates; this experiment evaluates
rejection and its interaction with NMS. These results do not meet the
protocol's evidence needed for promotion to a production default.

## Work and evidence-domain limits

| Policy | Lazy candidates attempted | Skipped by accepted NMS | Lazy point queries |
| --- | ---: | ---: | ---: |
| V >=0.50 | 343 | 2,596 | 199,152 |
| V >=0.65 | 397 | 2,542 | 228,747 |
| V >=0.80 | 1,219 | 1,720 | 759,694 |

All skipped candidates still have measured coverage in the separate complete
full cache. The three lazy paths were evaluated independently. The stricter
policy creates more work because more prospective suppressors fail coverage.
The counts do not establish a measured latency gain.

The adapter reports 396.382 ms for the second gradient/map pass over 16
frames (24.774 ms/frame arithmetic mean), 85.7641 ms for complete verification
including CSV work, and 17.5134 ms for all three policy checks and metrics.
Bank reconstruction is 8,756.6473 ms. These are diagnostic phases of an
isolated run with serialization and repeated checks, not a paired end-to-end
performance benchmark. No speedup claim is supported.

Every queried point is inside its padded map, but 396/2,939 candidates have
at least one point outside the original frame; the lowest original-frame
point fraction is 0.634146. Baseline retains 96 such detections; the three
coverage policies retain 95, 76 and 16 respectively. All TP point centers
are inside the original frame. A center being inside the frame still does
not prove that its radius-2 support avoids an artificial padding transition.
The predeclared padded evidence domain must remain explicit.

The tiny bank was originally trained under V10 (`c41f047`), while its actual85
raw matching uses V11 (`b25df46`); both bytes and that distinction are preserved.
The original historical runner did not pin every raw manifest or attempt CSV,
so later semantic/SHA audits are not historical attestations for those files.
The new coverage build pins all MIPP source members, but this does not change
the historical public build's narrower dependency record.

One metadata naming caveat: `execution_provenance.json` contains
`dataset_images_evaluated: 1`, which the frozen PowerShell runner writes as
an integer boolean for evaluate mode. It is not an image-count claim. The
verified frame set, CSVs and numeric audit establish 16 evaluated frames.

No frozen output, source, policy, threshold, baseline core or public evaluator
was modified by this audit. Further experiments need their own preserved
protocol and full reporting; heldout data remains sealed.
