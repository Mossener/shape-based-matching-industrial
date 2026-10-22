# Geometry planner test history

## 2026-10-22 — RED: missing implementation

`tests_red_20261022_a` ran the planned literal suite before `planner.py`
existed.  Python failed at the import boundary with `ModuleNotFoundError`.
The receipt is retained as the tests-first RED evidence.

## 2026-10-22 — GREEN: V31 planner

`tests_green_20261022_a` passed all 21 synthetic tests.  The suite covers the
fixed minimum, alignment, both level projection rules, layer-origin checks,
all-bank membership and count evidence, dense IDs, complete pyramids,
duplicate and malformed layers, checked overflow, resource limits, and the
JSON-ready trace.  No native executable, bank payload, image, or matcher was
used.

## 2026-10-23 — source successor V2

The V1 source was preserved under `source_v1_preserved_20261023_a` before
changes. Its receipts and original evidence manifest were not changed.

The V1 planner incorrectly used the query frame's 720×540 dimensions to
validate absolute training-feature coordinates. Training uses a separate
square canvas per pose, so valid large training coordinates could be rejected
and invalid coordinates on a smaller training canvas could be accepted.
`canvas_red_20261023_a` preserved two new tests failing because per-template
canvas input did not exist. The successor adds explicit `BankTemplate.canvas_size`;
the real runner always derives it from the independently pinned original pose
CSV. The query geometry used to plan padding remains fixed.

`runner_red_20261023_a` preserved the missing-module RED for the new one-shot
runner. `source_tests_20261023_a` passed 35 tests, and
`source_tests_20261023_b` passed 37 after adding full-public-schedule validation,
the persistent reservation-consumed marker, and successful freeze-output tests.
The runner tests use a synthetic in-memory 18-bank byte store. No actual bank
payload or dataset image was opened. Every test run writes a fresh evidence
directory; previous receipts are preserved.

`source_tests_20261023_c` and `_d` passed 38 tests after adding an explicit
association test for otherwise internally consistent audit closures, followed
by numeric JSON suffix restrictions. `_d` is the current GREEN source receipt.
`mutation_query_canvas_20261023_a` rejected a source mutant using query size
for training coordinates (two failures and two errors), and
`mutation_ignored_audit_pin_20261023_a` rejected a source mutant skipping the
P/B bank pin association (one failure). Both mutation receipts passed their
expected-RED gate, retained the mutated sources, and confirmed the real sources
did not change during execution.

`source_tests_20261023_final` retained a final 38-case check after the first
documentation handoff. Source review then tightened the physical-file reader:
a stale small pin cannot cause an oversized actual file to be read before its
hash is rejected. `source_tests_20261023_e` is the current 39-case GREEN and
adds a real numeric-file size-bound test (not a bank or image read). Both
mutations were rerun against these changed sources in the fresh `_b`
directories and retained their expected failures. The source-test runner now
also returns failure if source pins change during a passing child test run.


