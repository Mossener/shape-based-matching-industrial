# Profile audit

Passed 11 independent consistency checks. Snapshot: `6b7be69f96cffc1a914674691c6f20d80ea09106`.

- Snapshot source hashes match the original run environment; all five generated files match their immutable manifest.
- Driver/header hashes match the run environment. No production-source refresh or matching rerun was performed.
- Nine pre-profile current/instrumented comparisons passed semantic sets, strict sets, and raw counts.
- All 90 cold/warmup/measured calls passed semantic, strict, and raw-count checks; phase counts are 9/18/63.
- All 52,927 template rows and 156,254 level rows have aligned CSV fields and unique expected keys.
- Every template has exactly its expected pyramid levels; coarse output equals next-level input and local output equals next-level input.
- Every local call count equals its candidate input count; clamping counts are bounded by calls.
- Per-template region census partitions map = accumulated prefix + zero tail and prefix = valid rectangle + wrapped positions.
- All measured call counts and all five worker stage sums reconcile independently with template/level CSVs.
- Sum of L0 outputs equals pre-sort count; post-unique count equals validated current count.
- Per-image medians, worker-share percentages, census percentages, and dataset equal-weight means were independently recalculated.

Interpretation limits: worker elapsed sums are not process CPU or serial wall time; per-candidate clock overhead disproportionately affects argmax. Kernel intervals include map zeroing/allocation and any conversion. Equal-score ordering is not a detection-accuracy claim. Clamp counts are not unique-center counts. Production files may since have changed; provenance is checked against the run-time hash manifest, not the current working tree.

This audit does not independently verify every SIMD memory access or prove detection accuracy. The existing semantic/count comparison establishes equivalence only on these nine fixed fixtures. A low-level kernel change still needs its own kernel tests and the uninstrumented equivalence/benchmark workflow.

Raw evidence SHA256 values are saved in `audit.json`. `LOCAL_CALLS.md` and `local_call_clamp_distribution.csv` are post-processing only.
