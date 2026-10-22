# RGB source with an empty feature-selection mask

This directory contains the completed V27 evidence for one isolated accuracy
experiment. Training, geometry, quality, independent audit and timing stages
are recorded here; the production checkout and frozen full-API source tree are
unchanged.

The treatment keeps the existing grayscale RGB training source and changes only
the third argument of `Detector::addTemplate` from the official warped mask to
`cv::Mat()`. Crop, affine warp, black border, pose grid, V11 extractor,
pyramid, thresholds, feature target, source origin and official geometry stay
unchanged. The frozen V22 RGB bank is the control. This fills the missing
source × feature-selection-mask cell without mixing binary source, dilation,
hybrid features, threshold sweeps, or object-specific settings.

The fixed development decision rule is pre-registered: the new arm must reach
at least the V22 common-padding control's 215 true positives and use fewer than
42,112 false positives. Failure of either condition rejects the practical
count-dominance hypothesis, even if another aggregate metric improves. Every
object, scene, negative frame and all four historical identity groups are
reported; no per-object fallback or post-result arm selection is allowed.

Read [DESIGN.md](DESIGN.md), [PROTOCOL.json](PROTOCOL.json), and
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the fixed design and
stage contracts. The measured outcome is in [RESULTS_V27.md](RESULTS_V27.md):
false positives and raw candidates fell, but the pre-registered true-positive
gate failed, so the treatment is not a production default.

Current totals are in [EXECUTION_STATUS.json](EXECUTION_STATUS.json). The
zero counters in `source_status.json`, `PROTOCOL.json` and `STATIC_REVIEW.json`
describe the initial source-only checkpoint published with V26. Those frozen
bytes remain intact because the executed builds pin them by SHA-256.

Run `python artifacts/rgb_empty_mask_experiment/verify_release.py --staged`
from the repository root to check frozen build/stage closures and the exact
published index bytes. Native toolchain/runtime files are local pinned
prerequisites. Absolute Windows paths in historical evidence describe the
original machine; a different checkout needs fresh path-bound runs.
