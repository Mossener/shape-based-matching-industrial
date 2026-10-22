# Preserved development failures

- `tests_20261022_a` failed one of twelve tests because the source snapshot's
  fixed parent-depth expression resolved a different repository root. Its
  original sources, result and complete test stderr are retained. Repository
  discovery now walks to the `.git` ancestor, so frozen source snapshots can
  run the same artifact-only reader. `tests_20261022_b` passed all twelve.
- `run_20261022_a` stopped while composing the suppression-edge output because
  both the explicit edge and the prefixed blocker identity supplied the same
  `blocker_raw_rank` keyword. Its original source, failure receipt and traceback
  remain in place; stdout/stderr are preserved as `execution_20261022_a.*.txt`.
  The prefixed identity now uses `blocker_rank`, while the edge retains the
  authoritative `blocker_raw_rank`. `run_20261022_b` completed the entire scope.
- A thirteenth test rejects protocol scope/threshold mutations. Final source
  tests are captured in `tests_20261022_d`, with exact source pins and complete
  stdout/stderr. No failed directory was deleted or overwritten.
