# RGB empty-mask independent quality audit

`audit.py` replays the numeric quality arithmetic from frozen raw candidate
archives. It reads the dataset `index.json` only; image suffixes are rejected,
and it does not import or execute the native evaluator. The audit binds the
current `rgb_control` and `rgb_empty_mask` arms, uses treatment template counts
from `QUALITY_INPUT_FREEZE.json`, checks the shared 848×832 geometry, and
recomputes NMS, one-to-one GT assignment, per-frame metrics, selected rows,
candidate equality, and GT pose-retention evidence.
