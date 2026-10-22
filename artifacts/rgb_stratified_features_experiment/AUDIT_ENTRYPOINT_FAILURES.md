# Training audit entry-point failures

The shared native training completed once and is unchanged. The failures below
belong to the independent audit's orchestration, not to a new native training
attempt. A failed audit is never an accepted training result.

1. Root's temporary audit wrapper failed before creating a child because
   `execution_guard` was outside its Python module path. The attempted stage
   record remains in `independent/evidence/training_audit_reservation_v1.json`.
2. Root's explicit temporary successor added the module path but omitted the
   actual import. It also failed before starting a child. Its stage record is
   `independent/evidence/training_audit_reservation_v2.json`. These two records
   are wrapper-start failures, not completed full numeric audits.
3. `independent_full_audit.json` started one actual numeric audit. It ran for
   4485.125 seconds, peaked at 199004160 bytes, and exited with code 1. The
   traceback reaches the successful-result receipt write after the numerical
   function and source-pin checks returned, but `audit_output/` did not exist.
   The original calculated result was not saved. Consequently this stage
   remains failed, with no numeric acceptance. Its complete logs, guard and
   runner receipt remain in `independent/evidence/full_training_audit_v1/`.

The correction creates the receipt parent in `training_audit.main` after
freshness/outside-run validation, before either success or failure receipt
write. A full synthetic CLI fixture verifies a previously absent nested
receipt directory. A separate `independent_full_audit_v2.json` pins the
corrected sources and reserves one successor run over the exact same original
training bytes. All candidate-selection, mask, crop, bank and numerical rules
remain unchanged. The v1 source is preserved in its earlier source snapshots;
the original v1 reservation and failure receipts are not rewritten.

No quality or performance claim follows from reaching the final write in v1.
Only a complete accepted v2 receipt can satisfy the training gate.
