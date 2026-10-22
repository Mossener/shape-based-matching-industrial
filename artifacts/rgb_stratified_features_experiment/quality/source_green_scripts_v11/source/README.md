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
geometry acceptance pins are supplied.  The Python receipt under
`source_green_scripts_v8/` proves source/schedule checks only; it contains no
C++ compilation, image decode, bank payload read, matcher call, accuracy or
performance result.
