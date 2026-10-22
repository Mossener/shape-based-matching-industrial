# Independent RGB empty-mask timing audit

This directory contains a Python standard-library audit of frozen timing evidence.
It does not import experiment code or execute native programs. It reads numeric
CSV/JSON evidence and pinned text sources, without opening images, template banks,
or raw-output archives. Existing evidence is never written.

From this directory, reproduce with:

```powershell
python -B -m unittest -v test_audit_timing
python -B audit_timing.py
```

Every audit invocation creates a unique directory under `fresh/`, containing
`receipt.json` on success or `failure.json` on failure. The root timing stage
freeze is anchored by its exact SHA-256 and length in the audit script. All
timing stage data/execution pins, linked build/input/previous-stage pins, all
39 build project-source pins, five execution script pins, and private source
freeze entries are checked. Runtime/executable closure bytes are not rehashed.

The auditor checks all calls in exact object/frame/round/rotating-variant order,
round-zero warmup flags, positive finite matcher and external clocks, and both
clocks' independent nearest-rank summaries. Treatment/control ratios pair by
object, scene, image, round, and path before taking quantiles. The median uses
`sorted_values[ceil(0.5*n)-1]`; for even counts, this is the lower middle sample.
Timing raw/selected counts are compared to the same arm's frozen development
per-frame numeric reference. Frozen quality candidate-equality counts and
recorded comparison flags are cross-checked too.

Tests generate small fixtures with missing/duplicate calls, changed rotation,
wrong warmup/frame scope, invalid clocks, bad counts/reference flags, corrupt
summary statistics, and modified pinned source bytes. The initial stub run
failed all 15 tests as expected; the implemented auditor passes all 15.

The timing CSV contains durations, counts and a producer equality flag. It does
not preserve the complete timed-call outputs or float32 score bits. Therefore,
this audit cannot independently reverify full timed-call output equality.
Its receipt records this limitation explicitly.
