# Search optimization plan

User approved integer local maxima, direct 8-bit scans and reusable per-worker search buffers, with independent verification and local Git version records. They also requested an explanation of the historical README 360-template/7-ms result versus the current 900-template LED workload.

The immutable V4 sources are under `artifacts/search_optimization/baseline/`; original pre-optimization sources remain under `artifacts/response_optimization/baseline/`. Do not alter thresholds, template banks, search area, feature counts, floating-point score formula or tie order.

- [x] Calibrate original case1 and LED on the same machine and explain differences without treating README hardware/timing as directly comparable.
- [x] RED/GREEN test integer local maxima against the old float scan, including ties, all-zero maps, legal score extremes, strides and exact threshold boundaries.
- [x] Independently select integer maxima, direct 8-bit access and per-OpenMP-worker search cache through MatchOptions; preserve the old match and protected matchClass interfaces.
- [x] Compare all eight option combinations with immutable V4 for LED, case1, masks, empty results, worker counts, size/type changes and concurrency.
- [x] Alternate independent cases and the combination in one process with raw search/preprocessing/total times; no simultaneous performance runs.
- [x] Independent review, final evidence, result equivalence, local Git commits and version tags recording measured results. Exact result-set comparisons preserve existing overlay inputs; no broad detection-accuracy claim.

Evidence: `artifacts/search_optimization/README.md`, `CALIBRATION.md`, `REVIEW.md`, `search_test_results.json`, and `search_benchmark/AUDIT.md`. V5 isolates the kernel, V6 integrates independent switches, V7 records measurement and calibration. The LED combined search reduction is 3.87% in this run; case1 and standalone direct8/reuse do not establish stable benefits. No thresholds, pose bank, search area or score formula were changed.
