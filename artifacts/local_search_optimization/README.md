# Local search experiment

This harness compares the independently compiled immutable V4 matcher, current fallback with the six previous optimizations enabled, and the same current configuration with `fused_local_search=true`. It uses all nine existing fixtures without changing images, template banks, thresholds, feature counts, or search extent.

Each image receives one cold call, two warmups and 15 measured calls per timed case. Current workspaces are fresh and V4's workspace is reset at the start of each image; cold does not mean a fresh process or empty hardware cache. Three cases rotate each round and reverse direction on alternate rounds. OpenCV uses one thread and OpenMP uses four, with passive waiting.

Expected output comes only from the immutable V4 implementation. Full semantic sets contain class, coordinates and exact float score bits; strict sets also contain the template ID. Every timed call and one final `fused_local_search=true, integer_local_max=false` sanity call per image are checked against V4's cold output, including raw match counts. The float sanity request follows the current original-float dispatch and has no recorded timings. Any semantic, strict or count mismatch fails the run.

Compile and smoke-check without matching or performance measurement:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/local_search_optimization/run_benchmark.ps1
```

After coordinating exclusive CPU access, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/local_search_optimization/run_benchmark.ps1 -SkipCompile -Run
```

The script checks production, immutable reference and harness hashes against the build manifest before running, records image/template hashes, and rejects source changes during measurement. Primary timing fields are the internal `search_ms` and `api_total_ms`; V4's external `wall_ms` includes adapter conversion. Input loading, template construction, padding and result-key construction occur outside internal timing.

`raw.csv` contains per-call timings, comparisons and exact-output fingerprints. `float_sanity.csv` contains only correctness evidence. Summaries report per-image medians and descriptive p05/p95 quantiles; LED rollups are equal-weight means of its eight image medians. Paired ratios join the same image and measured round. The ratio is baseline/case, so values above one favor the case. They are descriptive observations, not confidence intervals.
