# Throwaway search profiler

This directory contains an isolated copy of the current matcher under the
`profiledLine2Dup` namespace. Production files are never patched. The original
source SHA256 values, Git HEAD, and generated source hashes are recorded in
`source_manifest.json`. `generate_profile.py` makes the mechanical instrumentation
patch reproducible and fails when an expected insertion point changes.

The executable links the current matcher and the isolated copy, reuses
`../search_optimization/fixtures.hpp`, exports each exact current template bank to
the isolated detector, and checks exact semantic sets, strict sets and raw counts
for every selected image before any profile call. Semantic/count differences stop
the run. Strict differences are recorded for equal-score tie review. Every
profile call repeats semantic/count checks. This preserves LED's 900 poses,
L3/{4,8,8}/75, and case1's 361 saved poses, L2/{4,8}/90; all six optimization
options are enabled. CV1/OMP4 and passive OpenMP waiting match the existing harness.

Compile and configuration smoke only (no image matching):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_profile/run_profile.ps1
```

After coordinating exclusive CPU use, validate then profile all nine fixtures:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/search_profile/run_profile.ps1 -SkipCompile -Run -OutputDirectory artifacts/search_profile/run_v9
```

`-ValidateOnly` runs correctness without profiles. `-Dataset LED -Image 1.bmp`
selects a fixture without changing its templates, poses or threshold. Defaults are
one cold call, two warmups, and seven measured calls per image after correctness.
`-RefreshSnapshot` intentionally regenerates and recompiles against changed root
sources. Otherwise source drift fails. Use a fresh output directory per run.

`calls.csv` has call wall timings, summed worker stage intervals, serial final
sort/unique, region census and candidate totals. `templates.csv` retains each
measured template's coarse stages and map region counts. `levels.csv` retains each
measured template's coarse candidate output plus local candidate input/output,
accumulation/argmax/filter timings, local call and clamping counts per level.
Summaries retain per-image and per-dataset composition, with LED/case1 separate.

Completed V9 evidence is in `run_v9/REPORT.md`. The separate post-processing
audit reconciles original provenance, every CSV level transition, call totals,
worker sums and summary arithmetic without rerunning matching:

```powershell
py -3.10 artifacts/search_profile/audit.py artifacts/search_profile/run_v9
```

`run_v9/AUDIT.md` records the checks and `run_v9/LOCAL_CALLS.md` reports the local
call/clamp distribution. Keep the V9 snapshot/manifest with this run; a future
intentional refresh requires preserving the old snapshot for its evidence audit.

These are `steady_clock` **elapsed worker intervals summed across workers**, not
process CPU time. They include descheduling and may exceed serial call wall time.
Worker stage percentages use only worker intervals as their denominator. Never
add worker sums to final serial sort or interpret them as wall-time speedups.
Similarity intervals include allocation/zeroing and any 8→16-bit conversion.
Per-candidate clock reads and counter/census work perturb the execution, especially
the short argmax stage. Profiled wall time must not replace the uninstrumented
benchmark; this diagnostic identifies where to investigate next.

The coarse scanner visits all H×W positions. The accumulator fills only the
contiguous prefix `span_y*W+span_x+1`, leaving a zero tail; row-wrapped origins
inside that prefix are a separate issue. Counters report the zero tail, valid
rectangle, wrapped prefix, and candidates from each region without changing the
matcher. At the fixtures' positive thresholds the zero tail cannot become a
candidate. Skipping row-wrapped positions can change outputs and is not a safe
performance-only transformation.

No production algorithm changes or detection-accuracy claims are made here.
