# Count-only local center diagnostic

This separate artifact copies the saved `search_profile/source` V9 snapshot at
6b7be69 and adds a per-template/per-level frequency dictionary keyed by the actual
`(x/T, y/T)` center after clamping. It does not refresh or modify the original V9
snapshot, manifest, or run. Generated copy hashes and their source hashes are in
`source_manifest.json`.

The fixture builder freezes the `6b7be69` version of
`search_optimization/fixtures.hpp` as `fixtures_v9.hpp` and compiles it against
the isolated V9 namespace. The executable links its isolated matcher and
the immutable V4 reference; it does not link current production matcher objects.
Each image runs exactly one V4 call and one instrumented V9 call. Exact semantic
sets and raw counts are required to match; strict sets are also recorded. All
template banks, poses, preprocessing options, thresholds and CV1/OMP4 settings
are the established fixture values.

Compile/configuration smoke only, without image matching:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/local_center_profile/run_profile.ps1
```

Coordinate exclusive CPU use before the count-only run; the formal V10 paired
benchmark has priority:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/local_center_profile/run_profile.ps1 -SkipCompile -Run -OutputDirectory artifacts/local_center_profile/run_v9_centers
```

Outputs include image/level total calls, scoped unique centers, repeated calls,
duplicate centers, maximum frequency and the complete frequency distribution.
Per-template totals are retained. `summarize.py` independently reconciles the
frequency and template totals, validates V4 comparisons, and checks that call and
clamp counts agree with the prior V9 profile. It writes a count-only report and
an audit JSON with raw evidence hashes. Dictionaries are scoped to a single
template/level/image, exactly matching potential result-cache scope.

No performance claim follows from counts. Repeated calls represent the maximum
number of identical-window evaluations a full-lifetime cache could avoid;
lookup/storage overhead and memory behavior still need an uninstrumented paired
benchmark. The old stage clocks remain in the copied diagnostic code, but this
harness does not publish timing data or add a production API.
