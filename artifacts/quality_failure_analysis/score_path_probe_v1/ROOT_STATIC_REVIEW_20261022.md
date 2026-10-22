# Root source review before the Phase 1 dataset replay

The root reviewed `probe.cpp`, `build_probe.py`, `prepare_probe.py`,
`run_probe.py`, `runner_gates.py` and their contract fixtures against the frozen
V11 preprocessing, `collectCandidates`, both `matchClass` overloads, local
scoring, consolidation and V22 box/archive helpers. This review does not report
a completed native or dataset run. The actual build and execution receipts
identify the source bytes used.

The adapter includes the frozen core once, reconstructs the same two grayscale
pyramid levels and linear memories, and calls the original protected class
search. It checks every emitted fine score with a separate per-feature memory
lookup, then applies the original consolidation. The V22 comparison occurs
after the original metadata conversion and canonical sorting, so it proves
ordered converted raw equality, rather than preserving the OpenMP merge order
of the pre-consolidation vector.

For these positive scores, grouping by score bits is equivalent to the original
numeric score equality. Cross-template groups retain the minimum template ID;
repeated occurrences of the same template are counted separately from discarded
template identities. GT support before and after consolidation is conditional
on the fixed RGB-TP identity list. Its change does not establish a recovered TP
after NMS or a new full-dataset accuracy result.

The runner requires the exact numeric allowlist, actual single-TU build closure,
deliberate RED scalar failure, same-source GREEN selftest and a fresh one-shot
reservation. Only the declared development images can be hashed and decoded.
It retains partial failures, checks the input/build closure again after native
execution, and binds all numeric output members. Phase 2 has no runnable entry.

An initial RED build failed because Windows headers were included after the
core's global `using namespace cv`, making `ACCESS_MASK` ambiguous. The root
authorized only moving the guarded Windows includes ahead of the core include;
the failed build is retained. Successful fresh builds must pin this corrected
adapter, with no edits to the frozen core. The runner also passes its pinned
absolute plan path to the child process, whose working directory is the probe
directory.

Limits: the synthetic score fixture covers 256 actual native local cells, while
the real replay must still pass the fine-score oracle for every emitted
candidate. A candidate outside the scalar oracle's supported physical bounds
fails the stage; it is never silently skipped. Neither a source review nor the
numeric archive auditor independently reconstructs the image-derived response
values. The native per-feature equality check supplies that additional gate.

The 0.25-second process watchdog complements per-replay native resource checks;
it is sampled monitoring, not a proof that transient peaks cannot exceed a
limit between observations. The output contains numeric diagnostics only.
