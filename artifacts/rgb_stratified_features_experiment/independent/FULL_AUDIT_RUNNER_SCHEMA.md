# Full training audit runner

`run_full_audit.py` (v2) is the one-shot wrapper for the completed public training
run.  It does not replace `training_audit.py`; it supplies the missing runner
boundary: a persistent stage reservation, resource limits, and a trusted
relative output map.

## Reservation

Run `--reserve-only` once before the heavy audit.  This writes
`execution_reservations/independent_full_audit_v2.json` with exclusive-create
semantics.  The operation pins the auditor, bounded classifier, numeric
modules, input freezes, and runner provenance file.  It does not open the
training output directory and does not construct an output map.

The reservation fixes 20,736 poses, 41,472 pools, 82,944 layer claims, zero
matcher calls, the radius-four `bounded_classifier_v2` implementation, a
5,400-second wall limit, 1.5 GiB RSS limit, 256 MiB audit artifact limit and
64 MiB execution-log limit.  A reservation, output map, evidence directory or
receipt from an earlier attempt makes a later attempt fail instead of retrying.

## Output map

At `--execute`, the wrapper reads only the runner's existing `files[]` pins in
`run_training_v1_PROVENANCE.json`.  Each absolute path must resolve below the
run directory, must be unique, and must still have exactly the recorded byte
count and SHA-256.  The wrapper converts each to a POSIX run-relative key and
writes `OUTPUT_PINS.json`.  It does not discover files by directory walk, so an
unlisted output cannot enter the audit.  Required numeric streams are checked
before launching the child auditor.

## Single attempt and receipts

The child command is the existing independent `training_audit.py` CLI with
the generated map and separately pinned `TRAINING_INPUT_FREEZE.json`.  It runs
under `execution_guard.run_guarded`; the guard records wall/RSS/output
telemetry and kills the child on a ceiling violation.  The child writes
`audit_output/INDEPENDENT_RECEIPT.json`; v2 creates the receipt parent before
the child starts, and the wrapper writes
`RUNNER_RECEIPT.json`.  A child failure, guard failure, malformed receipt or
missing receipt is preserved as failure evidence.  No automatic retry occurs.

The numeric audit can report `numeric_training_audit_passed`; this runner keeps
`real_training_accepted: false` because source/runtime closure, resource
provenance, and accuracy evaluation remain separate gates.
