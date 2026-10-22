# Actual independent quality audit entrypoint failure

The completed native development stage is immutable:

- `quality/run_development_v1/QUALITY_STAGE_FREEZE.json`
- 9,086,309 bytes
- SHA256 `6070b474d29b112c822d7f6a94a2ec920e454d104c511c42c29bf78a1d77b47a`
- 14,400 matcher calls; no heldout image reads.

The first independent audit, `independent_quality/real_development_audit_v1`,
exited 1 after 75.485 seconds. Its consumed reservation, watchdog logs,
failure output and runner receipt are retained. It is **not** a numeric PASS.

The worker stopped in `contract.bindings()` at the strict `pin_map()` call,
with `ValueError('duplicate declared numeric pin')`. Read-only inspection of
the frozen input declaration found exactly one repeated numeric pin:
`artifacts/rgb_dilated_mask_experiment/INPUT_CLOSURE.json`, appearing twice
with identical canonical path, bytes and SHA256. The bank and raw-reference
pin lists have no duplicates. The preparer concatenates its inherited closure
role with the accepted training dependencies, which contain the same closure.
The native preparer's role checks accepted this declaration; the independent
auditor had incorrectly required uniqueness across those two roles.

The original input freeze, preparer, native executable, development raw output,
independent v1 source and consumed registry are preserved without edits.
A separately versioned independent audit successor is required. Its narrow
rule may accept one or two identical occurrences of the exact inherited V30
closure pin; conflicting pins, another duplicated file, more than two
occurrences, and bank/raw/stage duplicates remain failures. Synthetic RED,
GREEN and deliberately weakened-source tests must precede a new reservation.
The existing native training and quality stages will not be rerun for this
audit-entrypoint correction.

The preliminary native quality result does not meet the primary hypothesis
(B TP 187 versus required 215). Correcting an input contract cannot turn that
accuracy failure into a success; the independent numeric conclusion remains
pending until its successor executes.
