# Independent V31 timing audit

Source-only numeric replay for C0/P/B, each with fallback/fused. No native
evaluator, feature sampler, OpenCV or NumPy is imported. The unchanged V30
timing source is retained as `frozen_v30_timing.py`; only its numeric parsing,
nearest-rank quantile, tolerance and error definitions are used. `ORIGIN.json`
records its exact bytes/SHA. All routes and experiment constants are local V31
definitions.

The fixed replay checks 29,952 calls, 64 timing frames per object, rounds
0..12, warmup 0, 27,648 formal samples and 4,608 samples per variant. It checks
the frozen frame ordinal and `(order + frame_ordinal + round) % 6` route.
Every measured frame/variant must occupy each order position twice. Full
`timing_pairs.csv` coverage is 27,648 same-frame/round/path P/C0, B/C0 and B/P
ratios. Pair names and direction remain part of their identity.

The audit recomputes six pooled median/p95 clock summaries, six paired ratio
summaries, frame medians/p95, equal-frame then equal-object means, and counts
of frame/tail ratio regressions. It never substitutes a ratio of medians for
a median of same-round ratios. The V31 native summary has no inherited V30
two-arm paired-summary array.

`evidence.py` checks exact four-file native timing inventory, nested execution
and watchdog inventory, current writer source pins, one-shot native stage
reservation, pre/post verification, guard limits and accepted development
bindings. Own-arm/path raw manifests and archive signatures must be pinned by
both the completed development stage and the complete independent three-arm
quality audit. Raw gzip payloads are not reopened here. `exact_own_reference`
is a native observation: each timed call's full unretained raw output cannot
be independently reconstructed from timing CSV.

The externally supplied input JSON has schema
`rgb_stratified_independent_timing_inputs_v1` and full canonical absolute pins
named `timing_stage`, `development_stage`, `quality_inputs`, `build_manifest`,
`selftest`, `development_audit` and `quality_acceptance`. No actual input
declaration is generated or guessed during source preparation.

Use `run_audit.py --reserve-only` with the external input path/SHA/bytes,
fresh output and reservation paths. This creates the output parent and a
single persistent `audit_reservations/timing.json` lock. Actual execution
requires `--execute --reservation ... --cpu-slot-granted`; it consumes the
reservation once, invokes only the Python numeric audit as a foreground
guarded child, and preserves a runner failure receipt on child/watchdog
failure. RSS is bounded at 1.5 GiB, wall time at 90 minutes, total output at
4 GiB and guard logs at 64 MiB. Failed budgets require an explicit successor.

`source_freeze_v1/receipt.json` runs discovery across both synthetic test
modules. It includes a full generated 29,952-row route and 27,648-row pair
replay, field/route/clock/pair mutations, frozen-origin verification, evidence
inventory, acceptance, current native-writer execution schema and mocked
watchdog/reservation failure tests. Real inputs, images, banks and raw
archives have not been read; no native code was compiled or executed.

Actual numeric replay with accepted pins remains necessary. Source tests do
not establish measured speed, accuracy, complete Python dynamic-module
attestation, cold-start performance or industrial generalization.
