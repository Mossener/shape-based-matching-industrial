# Root whole-API harness review

Reviewed `correctness.cpp`, `benchmark.cpp`, `replay.cpp`, `evidence.hpp`,
the two wrappers, literal source generator and independent correctness/output
contracts. This accepts the reviewed source design; the final runner and build
closure still require their own review before actual fixture execution.

The native correctness loops total2722 API calls and1602 comparisons. They
cover32 inputs, seven option bits, masks, negative controls, shared-detector
workspace lifetime/moves, two concurrent callers with independent workspaces,
legacy/default routes, class filters and seven local magnet regressions.
Concurrent archive IDs describe deterministic buffered output order rather than
wall execution order. Archive IO is confined to the parent thread. This is a
regression matrix, not proof of all possible threading interleavings.

All five Match fields, class bytes, score bits, order and multiplicity reach
the length-delimited archives. Exclusive output creation preserves earlier
evidence. The independent auditor reconstructs schedules and comparisons,
decodes every archive and binds the first-pass common25 baseline outputs to
the historical V21 references. It additionally checks baseline stability,
negative/zero controls, renamed identical class-bank relations and filters.
The current sources do not call extra matchers to establish these gates.

The timing harness implements the fixed950-call schedule and800 formal rows,
with8/8 position balance per variant/fixture. Its API clock encloses the real
Detector call and returned actual vector materialization. Neutral copying,
returned U-vector destruction, archive IO and comparisons are outside that
clock, consistently for both variants. The candidate helper owns finite scans,
hash construction/destruction, representative copies, final sort, swap and
old N-vector destruction before returning into the core timing stamps.
The cold round supplies its existing baseline output as oracle. This timing
scope must be described in the eventual result; no latency claim exists yet.

The independent synthetic native run
`build/root_synthetic_20261022_024520_349733/result.json` passed both literal
output serialization and synthetic fixture ownership/input contracts. The
fixture test reproduces the historical shallow-Mat alias and verifies fresh
destinations, masks and geometry. It performs zero Detector calls, zero image
decodes and zero template-bank reads. Its dependency bytes were checked before
and after compilation; it is not a complete toolchain/loader attestation and
does not establish that the full wrapper build succeeds.

Production code/defaults and V24 evidence remain unchanged. Source/check
receipts alone do not establish an accuracy gain or a whole-API speed gain.
