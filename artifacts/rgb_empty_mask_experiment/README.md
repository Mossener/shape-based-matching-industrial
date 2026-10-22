# RGB source with an empty feature-selection mask

This directory is a static design checkpoint for one accuracy experiment. It
has no native build, matcher call, image decode, SMD read, template-bank read,
or production change. The experiment is intentionally isolated from the frozen
full-API source tree.

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
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) before any implementation or
dataset-stage authorization.
