# Independent V28 numeric review

This directory is owned by the independent reviewer. The review.py script uses
only the Python standard library and does not import numeric.py, run_analysis.py,
or the target evaluator. No native matcher, image decoder, dataset image,
held-out scene, or reserved object is used.

The reviewer first executed temporary here-string logic without saving its
source. This newly saved script retains that calculation, adds source/input
before-and-after pins, and is executed afresh. Its receipt is evidence of that
new execution; it is not a fabricated source snapshot of the earlier execution.

Run from the repository root, choosing an output directory that does not exist:

    python artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/independent_review/review.py --target artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/run_20261022_b --output artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/independent_review/run_20261022_v1

The review checks all 400 development frames, six objects, two arms (4,800 unique
frame-arm rows), all 400 GT identities, and all 800 GT-arm rows. It independently
recalculates all selected detections' all-GT and visibility-eligible one-to-one
assignments, per-frame totals, pooled totals, all four cross-arm identity groups,
per-object/per-scene category reports, and output closure.

Raw NMS replay has a narrower, explicit boundary: all 350 positive object-frames
(700 frame-arms), covering all 400 GT identities and 134,524 fallback raw rows.
For those frames, it checks canonical order, retained candidate identities and
score bits, NMS acceptance/suppression against earlier retained candidates,
every GT stage category, and every suppression edge's candidate identity,
first blocker, IoU, and all-GT/eligible blocker labels.

The other 2,050 negative object-frames (4,100 frame-arms) are covered through
complete selected assignment and per-frame closure. Their raw archives are not
independently replayed or recounted here: raw counts are compared with frozen
native numeric metrics. Fused raw archives and template-metadata box reprojection
are also outside this review's independent replay. The parent performs its own
full diagnostic replay.

The receipt pins both the target run's saved diagnostic sources and the current
live diagnostic sources; it explicitly records whether they match. It also pins
this review script and every numeric input actually read. All pinned files are
read again before the receipt is written. A changed source or input fails the
review.

Interpretation limits: raw_gap means no saved score-85-or-higher candidate
overlaps that GT at IoU >= 0.5. It does not isolate a threshold or pyramid-pruning
cause. Suppression edges include redundant hits belonging to already matched GT,
and first-blocker provenance does not establish that removing the blocker would
fix accuracy.

The saved script was also freshly run against the final source-bound root replay:

    python artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/independent_review/review.py --target artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/run_root_20261022 --output artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/independent_review/run_20261022_v2

Both saved runs passed, with 722 unique before/after input pins per receipt.
The final v2 run has all five target-source snapshots equal to live diagnostic
sources. See ../REVIEW.md for exact receipt/source hashes and findings.
