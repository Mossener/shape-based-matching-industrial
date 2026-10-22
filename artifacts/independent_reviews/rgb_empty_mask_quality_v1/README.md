# RGB empty-mask independent quality audit

`audit.py` replays the numeric quality arithmetic from frozen raw candidate
archives. It reads the dataset `index.json` only; image suffixes are rejected,
and it does not import or execute the native evaluator. The audit binds the
current `rgb_control` and `rgb_empty_mask` arms, uses treatment template counts
from `QUALITY_INPUT_FREEZE.json`, checks the shared 848×832 geometry, and
recomputes NMS, one-to-one GT assignment, per-frame metrics, selected rows,
candidate equality, and GT pose-retention evidence.

`test_audit.py` uses literal independent oracles and synthetic corruptions for
score bits, order, multiplicity, missing frames, selected fields, GT geometry
and attribution, metadata origins, threshold boundaries and pin mutations.
`run_synthetic.py` preserves its exact sources and stdout/stderr.

`identity_strata.py` separately crosses the frozen V22 and V27 GT-retention
tables. It verifies that the RGB control detects exactly the same identities
and reports retained, lost, gained, neither and net TP within every historical
stratum, object and scene. It never opens an image or starts matching.
