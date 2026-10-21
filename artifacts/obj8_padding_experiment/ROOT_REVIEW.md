# Parent review and fresh verification

The parent reviewed `padding_eval.cpp`, `padding_plan.hpp`, `verify_inputs.py`,
`run_eval.ps1` and the independent numeric auditor. The matcher and public
evaluator remain at the frozen V11 bytes. Each padding arm compares its two
search paths by original fields and float32 score bits. Both left and top stay
64, so the original single-padding coordinate conversion applies unchanged.

Before the pilot, review requested separately reported image decoding/bank
loading and post-run executable/build-manifest SHA checks. These were added,
then the adapter was rebuilt and a fresh native synthetic selftest passed.
All original failed attempts remain preserved.
Frozen third-party source snapshots retain their original trailing whitespace;
the scoped Git whitespace attribute preserves these attested bytes unchanged.

The parent freshly executed the complete independent Python audit against
pilot, full400 and timing64. Exit code was 0; the report is
`independent_audit_root_recheck.json`. It reconstructs numeric results without
opening images or calling the matcher. Full400 raw candidates match the
original baseline on all 400 frames, including float32 bits and ordering.

The geometry audit independently recomputes constraints from exported CSV;
native loaded-bank scanning and pinned source/bank bytes bind that CSV to the
bank. It does not separately parse the serialized template YAML to recompute
every feature extreme. The audit cannot reconstruct all timed candidate
contents from timing CSV alone; native exact comparisons checked those calls,
while the independent audit verifies their retained counts and statistics.
Soft resource checkpoints cannot interrupt one in-progress matcher call.

The result supports retaining the experiment and its negative finding:
geometry becomes feasible, accuracy stays unchanged, and paired calling time
increases. It does not support promoting automatic padding as a default
accuracy or speed improvement or claiming physical SIMD-read safety.
