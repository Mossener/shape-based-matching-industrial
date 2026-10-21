# Local accumulator test execution

The first compile of `tests/local_accumulator_test.cpp` failed because the new `line2Dup_local.hpp` implementation did not exist. After implementing the accumulator, 288 independent scalar-oracle cases passed. A further 256 literal single-winner cases were added, one for each patch position, to catch missing high lanes, wrong row strides and final-row omissions.

Final execution after promoting the default and formatting the caller is recorded with source and executable SHA-256 values in `test_results_v10.json`:

- 544 accumulator cases: exact raw maximum, original float normalization, first row-major tie, zero/skipped features, byte/word transition and maximum legal count.
- 96 independently addressed preparation cases: odd/even T, negative features, positive/negative and low clamped centers, original total-feature denominator.
- 450 frozen V4 integration calls: existing eight search flag combinations, nine positive fixtures, masks/empty results, thread count 1→4→2→4, legacy-signature default calls, workspace move and independent concurrent calls. Observed strict template-set differences: zero. Concurrent calls and the move check are additional checks beyond the 450-call counter.

The scalar oracle reads the input streams directly and uses the old float-per-pixel maximum scan. The preparation oracle separately derives LM grid and element indexes. Complete matcher expectations come from the separately compiled immutable V4 source, not the optimized helper. Legal per-feature response values are 0/3/4. No new test proves arbitrary malformed template patches readable or validates other ISA backends.

Reproduce with `powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/local_search_optimization/run_tests.ps1`; choose a fresh `-OutputFile` to keep earlier evidence.
