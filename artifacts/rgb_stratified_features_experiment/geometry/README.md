# Common geometry planner

This directory contains a source-only Python implementation of the V31 common
canvas planner.  It mirrors the checked arithmetic and validation in
`frozen_helpers/padding_plan.hpp` while adapting the inherited limits and the
18-bank union (`C0`, `P`, and `B` for objects `1, 2, 5, 8, 12, 17`).

The planner receives already parsed `Bank`/`BankTemplate`/`BankLayer` records
and an accepted template-count map.  It scans every accepted layer, validates
feature extents against each layer's own origin and source-pyramid canvas, and
projects the complete geometry through the two levels.  It expands only the
right and bottom padding after the fixed 848×832 minimum and 16-pixel
alignment.  A count mismatch, missing bank, malformed layer, duplicate pose,
resource-limit failure, or arithmetic overflow is an error; no feature or
pose is filtered to make a plan fit.

Example:

```python
from planner import plan_all

plan = plan_all(all_eighteen_banks, accepted_counts)
print(plan.to_dict())
```

`bank_from_records` adapts the strict reader's raw dictionaries without
opening files itself.  Actual bank reads, native execution, image decoding,
quality evaluation, and timing are intentionally outside this source-only
stage.  The training acceptance pins must be supplied before a caller reads
the real C0/P/B banks.

Run the literal suite with:

```text
F:/mysys2/ucrt64/bin/python.exe -B geometry/run_tests.py
```

The original `tests_green_20261022_a` receipt records 21 synthetic tests.
Source version 2 adds per-template training canvases and the pinned one-shot
runner described in [INPUT_SCHEMA.md](INPUT_SCHEMA.md). Its current successor
suite has 39 tests, including complete synthetic 18-bank scans from an
in-memory byte store and success/failure reservation tests. It opens no real
bank payloads, images, native executables, or matchers.

Every new invocation of `run_tests.py` creates a new timestamped evidence
directory by default. `--output` can name a fresh directory explicitly. An
existing evidence directory is rejected. Current source snapshots and receipts
are listed in `SOURCE_AND_LITERAL_EVIDENCE_V2.json`; original evidence is kept.

Two targeted mutants are rejected: using query dimensions for training feature
validation, and skipping the audited P/B bank-pin association. Their receipts
and mutated source snapshots are retained separately. These checks exercise
numeric/source behavior only; no real bank scan or quality result is claimed.


