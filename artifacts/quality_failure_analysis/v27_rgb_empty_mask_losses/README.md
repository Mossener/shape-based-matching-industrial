# V28: stage provenance for frozen V27 matching results

This is a numerical diagnosis of the unchanged V27 development evidence.
It replays every one of the 2,400 object-frame pairs for both arms and both
raw search paths. It verifies complete candidate identities, float32 score
bits, multiplicity, canonical ordering, independent NMS, all-GT and eligible
GT assignment, selected fields and per-frame counts. Empty negative frames
are part of the scope.

The classification for every GT/arm is ordered: matched, raw gap, NMS loss,
assignment competition. A raw gap means no saved candidate at score ≥85 has
IoU ≥0.5. An NMS loss means such candidates exist but none survives. Assignment
competition means surviving hits all belong to another GT in the final greedy
one-to-one assignment. A surviving FP hit for an unmatched GT is an error.

`suppression_edges.csv` records every suppressed GT-hit candidate, the exact
first canonical kept blocker, both full identities and score bits, their
mutual and GT IoUs, and the blocker's final all-GT/eligible labels. It includes
matched GTs and multiple edges per GT; edge counts are not missed-GT counts.

`ORIGIN.json` pins the V23 diagnostic and independent V27 numerical audit
sources used as references. The native evaluator is never imported. The
reader accepts only hash-pinned artifact JSON/CSV/GZIP evidence; dataset and
image access is refused. Output directories must be fresh. Every failure
retains its sources, traceback and incomplete receipt.

Run from the repository root:

```powershell
python artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/run_tests.py --output artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/tests_fresh
python artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/run_analysis.py --output artifacts/quality_failure_analysis/v27_rgb_empty_mask_losses/run_fresh
```

The stdout/stderr for the captured development attempts are preserved beside
their run directories. No image is decoded, no native matcher is run, no
threshold is changed and no detector is promoted by this diagnostic.
