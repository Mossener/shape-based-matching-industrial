# V31 quality pipeline

This directory defines the fixed three-arm quality and timing replay for
`rgb_control`, `rgb_pooled_features`, and `rgb_stratified_features`.  The
schedule is deliberately closed: old gate 96 calls, pilot 288, development
14,400, and timing 29,952 calls.  Development evaluates all 400 declared
frames; timing uses 64 frames, six arm/path variants, one warmup round and 12
measured rounds.

`prepare_quality_inputs.py` accepts only an independently audited training and
geometry freeze.  It records observed template counts, the accepted 18-bank
common-padding plan, every bank metadata/template pin, and the inherited C0
raw references.  It never guesses counts or padding.  `quality_execution_inputs.py`
rechecks this allowlist before and after each stage.

`build_quality.py` compiles the exact V11 core and this adapter as separate
translation units after the source closure is pinned.  `run_quality.py` keeps
one reservation per stage and preserves partial evidence.  Timing additionally
requires an independent all-three-arms numeric audit.  An accuracy failure can
be measured but cannot promote an arm.

The current directory is source-only until the independent training and
geometry acceptance pins are supplied. `source_freeze_v3/receipt.json` is the
current complete source-test freeze; it runs discovery across all three test
modules. The earlier `source_freeze_v1/` remains preserved: its 13 limited
tests passed, but missed the runtime schema, field-name, compilation, payload
selection, and accepted-pin closure bugs later reproduced by the RED tests.
It is evidence of that incomplete validation, not an accepted native result.

The retained RED receipts cover runtime closure, source/build gates,
`bank_files` compatibility, the watchdog, the fixed V30 development origin,
and source-test timeout evidence. `source_red_runtime_closure_v1/` was an
incomplete timeout attempt; `source_red_runtime_closure_v2/` contains the
completed 10-failure semantic RED. All fixtures use tiny synthetic text and
in-memory pin records. No real bank or image payloads are used by these tests.

The scripts now require C++17/SIMD/OpenMP flags and exact frozen source
membership. They pin imported provenance/watchdog helpers and the acceptance
envelopes. Declarations are recomputed from their accepted numeric sources;
stage verification opens only the required bank/raw/image allowlist, and the
literal selftest opens no bank/raw/image payloads. Timing byte-checks the
independent three-arm audit and its development binding before and after use.
`EXECUTION_RESOURCES.md` defines the pinned resource watchdog, including fresh
native/guard siblings and retention of failures without a silent retry.

Source tests establish Python behavior and static native contracts only.
C++ compilation, native selftests, actual accuracy, and paired timing remain
required. No accuracy, performance, or production promotion is claimed here.
