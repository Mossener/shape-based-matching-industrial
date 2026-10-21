Run from the repository root. Compilation and configuration smoke checks only:

```powershell
powershell -ExecutionPolicy Bypass -File artifacts/response_optimization/run_benchmark.ps1
```

Start the benchmark explicitly after other CPU-intensive tests have stopped:

```powershell
powershell -ExecutionPolicy Bypass -File artifacts/response_optimization/run_benchmark.ps1 -Run
```

The executable imports the same 900 three-level SMD templates into the immutable
reference adapter and current matcher. It compares `original`, `all_false`,
`spread_only`, `fusion_only`, `reuse_only`, and `all` in one process, with OpenMP
fixed at four threads and OpenCV at one, two, then four threads. Each of the eight
LED inputs and both full-search/empty-template modes gets independent workspaces,
one cold call, one warmup, and seven measured calls per case. Measured case order
rotates and reverses; original cold establishes the correctness reference.
The runner explicitly sets `OMP_WAIT_POLICY=PASSIVE`, `OMP_MAX_ACTIVE_LEVELS=1`,
`OMP_DYNAMIC=FALSE`, and `OMP_NUM_THREADS=4`; these settings are recorded in
`environment.json`. Python defaults to the Windows launcher `py -3.10`.

Cold means the first call for that image/configuration/thread/mode and a fresh
workspace. It does not mean a fresh process, empty OS cache, or cold CPU cache.
Warmup and cold samples are recorded and summarized separately from measured
samples. Input decoding, padding, template generation/import, match key comparison,
and CSV writing are outside the wall timer. Empty-template mode still executes
preprocessing and the matcher call; it is not a separate hand-written kernel timer.

`raw.csv` contains wall and available internal stage times for every invocation.
The original adapter captures its two log timings (`preprocess_ms`, `search_ms`);
finer original stages are blank. Original external total includes the adapter's
stream capture and Match-to-Result vector allocation/copy conversion overhead.
`all_false` provides a useful comparison without that adapter overhead.
Fused `response_ms` includes the fused linearization work;
its `linearize_ms` can therefore be zero. Compare `preprocess_ms` for a complete,
consistent construction interval; do not add overlapping stage timers blindly.

Every call is checked against an original semantic set `(x,y,score_bits,class)`.
The strict set additionally includes template ID; strict differences and raw count
differences are recorded separately because original equal-score duplicate pruning
can select different template IDs under OpenMP. Semantic differences fail the run.
This is equivalence to the original matcher, not a ground-truth LED accuracy test.

`summary_by_image.csv` gives median and interpolated p95 for each phase and stage.
`summary_rollup.csv` averages per-image medians, weighting images equally.
`paired_speedups.csv` uses baseline/variant ratios from the same image, thread count,
mode and round. A p95 from seven samples is descriptive, not a reliable tail-latency
estimate. Raw samples and source hashes are retained for review.
