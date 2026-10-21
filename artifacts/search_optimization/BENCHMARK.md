# Search optimization experiment

This compares the immutable response-optimized V4 baseline with five current
search configurations: all search options false, integer argmax only, direct
8-bit search only, per-worker buffer reuse only, and all three enabled. Every
configuration retains all three preprocessing optimizations. The old historical
original baseline and its calibration harness remain separate.

Compile and smoke-check without running image matching:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_optimization/run_benchmark.ps1
```

Use `-Test` for the independent V4 equivalence suite after coordinating CPU use.
Use `-Run` explicitly to start performance measurement; `-SkipCompile` reuses the
already built executables. Do not combine performance runs with other CPU tests.

The benchmark uses CV1/OMP4, passive OpenMP waiting, dynamic teams off, one cold
call, two warmups and 15 measured calls per image/case. Each measured round rotates
and reverses all six cases in the same process. Current cases own independent
workspaces; the V4 adapter also uses a persistent workspace that is reset for each
image. Cold is not a fresh process or a flushed cache. Default total: 972 calls.

Inputs: eight supplied LED images (gray, padding 64, 896×704, 900 poses, 3 levels,
threshold 75), plus current repository case1 (BGR, padding 250 and crop to multiples
of 16, 1088×960, 361 saved templates, 2 levels, threshold 90). They are separate
workloads and their timing summaries are not averaged together. Template loading,
image I/O, padding, equivalence comparison and CSV writes are outside the timers.

`raw.csv` records the full call and every existing preprocessing/search interval,
best match, dimensions, template count and exact result-set comparisons. For V4,
internal `total_ms` and `search_ms` exclude adapter Match-to-Result vector conversion;
external wall `total_ms` in the CSV includes conversion. Prefer `search_ms` for
search-specific conclusions and `api_total_ms` for comparable core-call totals.
The external wall is retained to expose rather than hide adapter overhead.

`summary_by_image.csv` gives median/interpolated p95 separately for cold, warmup and
measured calls. `summary_rollup.csv` equally weights per-image medians within each
dataset. `paired_speedups.csv` compares corresponding rounds against V4 and current
all-false. Descriptive percentiles are not confidence intervals. Exact semantic
sets, strict sets and raw counts are checked; semantic/count differences fail the
run, and strict differences are recorded separately for equal-score tie review.

The correctness suite checks all eight option combinations against V4, nine
positive fixtures, zero/full/partial masks, thresholds with no candidates,
gray/color and size/Detector switches, worker-count growth/shrink, workspace moves
and two independent concurrent callers. Kernel edge/tie tests are separate in
`tests/search_kernel_test.cpp`. Neither suite establishes broad detection accuracy.
