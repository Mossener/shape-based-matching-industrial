# V21: immutable candidate consolidation replay

The isolated five-method replay completed on 2026-10-22. This result covers
consolidation alone; the production V11 matcher is unchanged. It establishes
neither whole-matcher speed nor detection accuracy improvement.

## Inputs and equivalence

The fixed 25 traces comprise all eight LED fixtures, case1 and all sixteen tiny
actual-85 development fixtures. A separately compiled, uninstrumented V11
matcher supplied the complete ordered reference for every captured trace:
50 matcher calls, no heldout scenes or reserved objects 25/29.

Real inputs contain 21–2695 records, reduced to 7–641 records, and every trace
has duplicates. Real empty, duplicate-free and historical 486k pressure traces
are absent. Synthetic pressure tests remain synthetic.

All five replay methods passed separate verify-only execution and every timed
batch's ordered field/float32-bit comparison. Hash zero scores use the exact
V11 fallback to preserve signed-zero representative behavior. Nonfinite input
is rejected. No matcher or image decoder runs in replay.

## Measurement and results

`REPLAY_BENCHMARK_PROTOCOL.json` was frozen before measurement. Five methods
rotate/reverse order for each trace and round. There are three warmup and 31
measured rounds: 4250 rows, including 3875 formal rows. Equal prepared input
copies are outside every timer; hash output replacement and destruction of the
old input are inside its timer. Common input-copy cost is reported separately.

Ratios below are each trace's median of 31 paired candidate/V11 ratios, then
the equal-weight median within the declared scenario. Lower is faster; these
are descriptive local measurements, with no confidence interval.

| Method | LED + case1, 9 traces | Tiny actual-85, 16 traces | Regressions |
| --- | ---: | ---: | --- |
| Owning hash, reserve | 0.530770 | 0.603726 | case1 |
| Owning hash, no reserve | 0.551047 | 0.643065 | case1 |
| Index hash, reserve | 0.510006 | 0.592860 | case1 |
| Index hash, no reserve | 0.553631 | 0.618558 | case1 |

Index/reserve geometric means are 0.562862 and 0.591517 respectively. All
four hash variants regress on case1's 21-record trace; no tiny trace regresses
in this run. No small-input crossover or image-specific switching rule was
selected from these data. Individual absolute times and every regression are
retained in the summary. Small absolute consolidation savings must not be
reported as equivalent complete-call savings. No memory benefit is measured.

## Evidence and independent review

- Capture: `run_20261022_capture_actual85/capture_result.json`, SHA-256
  `94237344067f307f4d6645436200d69d7d219e18a088ea0a88072e3beb67d941`.
- Build: `build_20261022_replay_v1/replay_result.json`, SHA-256
  `6143bfdf9ce73042b90d8a1ab4260b74ac0e49053dcde0b4a8db4a7d492b520c`.
- Verify: `run_20261022_replay_verify_v1/replay_result.json`, SHA-256
  `bf4323caca35eb789d248b58cb451403e0fd17e10349154ce1cb5687799f7f47`.
- Measure: `run_20261022_replay_measure_v1/replay_result.json`, SHA-256
  `c457559ac140576ac0b2529502906a76712ffbf06fd37b6d93af1169e81abf0e`.
- CSV SHA-256:
  `9efeb480d9c68abefdc44edd3d9637eb7012087d1eb0cb0b292a8c6ec24b75ae`.
- Summary SHA-256:
  `e6d2923fe8a8f480f42bc7e5921f786f0dee441cc45e693706e5eb11270dca00`.

The parent independently read every binary trace without importing the
prototype parser, reconstructed V11 grouping/order, and audited build/verify
provenance. A separate standard-library script then reread all traces and the
4250 CSV rows, checked exact schedules/batch rules/diagnostics, and recomputed
all paired, absolute and scenario summaries. The actual audit passed:
`../../independent_reviews/consolidation_trace_v1/root_replay_arithmetic_20261022.json`.
Three synthetic tests check paired medians, zero-copy quantiles, invalid timing
and corrupted summary rejection. Saved CSV equality flags are declarations
from the native comparator, not an independent reconstruction of each timed
output vector.

Reproduce the independent numeric audit from the repository root:

```powershell
& F:/mysys2/ucrt64/bin/python.exe artifacts/independent_reviews/consolidation_trace_v1/audit_replay_statistics.py --result artifacts/match_consolidation/hash_prototype/run_20261022_replay_measure_v1/replay_result.json --summary artifacts/match_consolidation/hash_prototype/run_20261022_replay_measure_v1/summary.json --output artifacts/independent_reviews/consolidation_trace_v1/my_fresh_replay_audit.json
```

Original binaries, compiler/SDK headers and external image caches stay local;
their hashes are recorded, so native provenance checks require the original
local environment or a separately recorded rebuild. Published trace numbers
and CSV arithmetic can be reviewed without image pixels. Earlier failed builds,
semantic RED tests and their source snapshots are preserved as failures.
