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

The green receipt records 21 synthetic tests and explicitly records zero bank
file opens, native executions, image decodes, and matcher calls.


