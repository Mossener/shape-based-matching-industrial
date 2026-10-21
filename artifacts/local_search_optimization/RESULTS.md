# Paired local search results

Two complete runs are retained. `paired_run_20261021` measured the first implementation with the default disabled. `final_run_20261021` rebuilt after the default was enabled, the fallback block was formatted, and historical fixture options explicitly disabled the new flag. Every measured current case explicitly sets the flag, so both runs compare the same fallback/fused configurations. The first run was not replaced or selected out of the report.

Windows, i5-13500HX, GCC 15.1, OpenCV 4.12, `-O3 -mssse3 -msse4.1 -fopenmp`, CV1/OMP4 with passive waiting. Each of nine inputs has cold1/warm2/measured15 per case, with V4/fallback/fused rotating and reversing each round. CPU access was coordinated with the other agents; no simultaneous matching benchmark or C++ compilation was scheduled. Per-run environment and source/input hashes are in each `environment.json`; successful source stability checks are in `completion.json`.

The table uses internal milliseconds. LED is the equal-weight mean of eight per-image measured medians; case1 is its single measured median. Fallback enables the six previous optimizations. Fused changes only the new local-search flag. V4 is the independent immutable response-optimized matcher, without the later search changes.

| Run | Dataset | Case | Search ms | API total ms |
| --- | --- | --- | ---: | ---: |
| Initial | LED | V4 | 36.800 | 47.410 |
| Initial | LED | Fallback | 34.479 | 45.464 |
| Initial | LED | Fused | 25.723 | 36.818 |
| Final | LED | V4 | 32.117 | 42.629 |
| Final | LED | Fallback | 31.835 | 42.153 |
| Final | LED | Fused | 20.463 | 30.823 |
| Initial | case1 | V4 | 2.809 | 18.417 |
| Initial | case1 | Fallback | 2.865 | 18.475 |
| Initial | case1 | Fused | 2.757 | 18.119 |
| Final | case1 | V4 | 2.198 | 18.039 |
| Final | case1 | Fallback | 1.940 | 17.861 |
| Final | case1 | Fused | 1.806 | 17.580 |

LED fallback-to-fused search reductions are **25.39% initially and 35.72% finally**; API total reductions are **19.02% and 26.88%**. All eight LED per-image search medians improve in both runs. Against V4 within the same runs, the corresponding search reductions are 30.10% and 36.29%, and API total reductions are 22.34% and 27.69%. Comparisons across different runs are not optimization effects.

Same-image/same-round fallback-to-fused ratios provide a second view. Values above one favor fused. p05/p95 are descriptive interpolated sample quantiles, not confidence intervals.

| Run | Dataset / metric | Pairs | Median ratio | p05 | p95 | Pairs >1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Initial | LED search | 120 | 1.514 | 0.952 | 2.179 | 111 |
| Final | LED search | 120 | 1.564 | 1.130 | 1.965 | 117 |
| Initial | LED API total | 120 | 1.337 | 0.957 | 1.744 | 110 |
| Final | LED API total | 120 | 1.376 | 1.047 | 1.633 | 117 |
| Initial | case1 search | 15 | 1.009 | 0.642 | 1.636 | 8 |
| Final | case1 search | 15 | 1.080 | 0.992 | 1.370 | 14 |
| Initial | case1 API total | 15 | 1.010 | 0.885 | 1.083 | 9 |
| Final | case1 API total | 15 | 0.995 | 0.948 | 1.152 | 6 |

The LED improvement repeats, but its magnitude varies and several images have wide duration distributions. The initial run's final three LED inputs have especially broad distributions. These observations do not establish a fixed speedup on other machines or images. Case1 has a smaller search benefit in the final run, while its final API-total paired median is slightly below one; a stable complete-call benefit for case1 is not established. Preprocessing was unchanged, and fluctuations in that phase are not attributed to the local-search kernel.

Both runs independently pass **486 timed calls plus nine float-path sanity calls** against V4, with zero exact semantic-set, strict-template-set, raw-count or fingerprint differences. Each has 405 measured calls, 81/81 expected phase groups, all required sample counts, and no internal total/preprocess-plus-search timing overlap. The float request deliberately follows the existing float path and is excluded from timing CSVs. This checks output equivalence on these fixtures; it is not a broad recognition-accuracy claim.

Raw evidence is under both run directories: `raw.csv`, `float_sanity.csv`, `summary_by_image.csv`, `summary_rollup.csv`, `paired_speedups.csv`, `summary_validation.json`, `environment.json`, and `completion.json`. The harness, source-stability guards, CSV smoke check and independent summarizer remain beside this report. `REVIEW.md` records the correctness argument and scope.
