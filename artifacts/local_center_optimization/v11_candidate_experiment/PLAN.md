# V11 final-level center cache implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether exact reuse of final-level duplicate center results
reduces matcher time while preserving complete V11 ordered output.

**Architecture:** Freeze seven V11 matcher files and sixteen MIPP files from
Git, then maintain a private candidate copy of the seven matcher files.
Independent translation units expose the exact frozen baseline and candidate;
the test harness compares ordered fields and float bits directly.

**Tech Stack:** C++14, OpenCV 4.12, frozen MIPP/SSE, OpenMP, Python standard
library provenance, PowerShell compiler runners.

**Spec:** `SPEC.md`. Earlier design context is
`../../../docs/superpowers/plans/2026-10-21-local-center-cache.md`; its V4/V10
acceptance and default-true assumptions are superseded by this V11 experiment.

## Global constraints

- Only write below `artifacts/local_center_optimization/v11_candidate_experiment/`.
- Freeze exact `b25df46f6ddf9c24fb43f5836f1414dc38c8caed` bytes; never regenerate a differing baseline.
- No production, public frozen or old failed V10 file changes; no heldout image decoding, viewing or matching.
- Cache capacity sixteen, worker-exclusive ownership, template/level reset, post-clamp signed quotient keys, L0/multiple-candidate gate, complete overflow fallback.
- Preserve complete ordered fields and float bits; no candidate deletion/reordering, altered thresholds or reduced features/windows.
- Default false; explicitly select off/on. Finish RED before cache implementation.
- Exclusive CPU before compiling/matching. Parent currently queues magnet padding, then hash prototype, then this experiment.
- No speed claim before independent correctness gates and uninstrumented interleaved measurement.

## Task 1: Freeze V11 and establish a genuine cache RED

**Files:** `snapshot_v11.py`, `baseline/`, `candidate/`,
`tests/cache_contract_test.cpp`, `candidate/line2Dup_local_cache.hpp`,
`run_cache_contract.ps1`, fresh `build/red/` and `red_result.json`.

**Interfaces:** `LocalCenterCache::reset()`,
`bool find(int cell_x, int cell_y, LocalMaximum& out) const`,
`void insert(int cell_x, int cell_y, const LocalMaximum& value)`.
Baseline `LocalMaximum` supplies unsigned raw, float score and int row/col.

- [x] Run `python artifacts/local_center_optimization/v11_candidate_experiment/snapshot_v11.py --mode freeze`.
- [x] Run the same script with `--mode prepare-candidate`; compare every copied core byte with baseline.
- [x] Keep a no-op stub whose `find` returns false without touching `out`, and whose reset/insert do nothing.
- [x] Write literal behavior tests before implementation: exact scores include negative zero and a deliberately non-derived float value; scope/reset and overflow preserve full records and emission order.
- [x] After exclusive CPU release run `run_cache_contract.ps1 -Phase Red`. Require compilation success, executable exit 1 and `stored result was not retrieved`; preserve output/source/executable hashes. A missing include or compile error fails the gate.
- [x] Notify root with the exact RED result path and hashes before changing the stub.

## Task 2: Implement the bounded cache and integrate its independent switch

**Files:** Only `candidate/line2Dup_local_cache.hpp`, `candidate/line2Dup.h`,
`candidate/line2Dup.cpp`, `candidate_change_manifest.json`.

- [x] Replace the no-op stub with `std::array<Entry,16>` and an explicit valid count. A miss leaves `out` unchanged; insert after a miss stores only while count is below sixteen.
- [x] Run `run_cache_contract.ps1 -Phase Green -RedEvidence cache_contract_red_20261021_225358_294.json` into a new directory. Require all literal tests pass and retain RED artifacts unchanged.
- [x] Add `bool reuse_local_centers = false;` to candidate `MatchOptions` and a cache to candidate `SearchScratch`.
- [x] At each local level call `scratch.local_centers.reset()`, then evaluate `const bool reuse = options.reuse_local_centers && l == 0 && candidates.size() > 1;`.
- [x] After the existing clamps compute `const int cell_x=x/T, cell_y=y/T;`. On `!reuse || !cache.find(cell_x,cell_y,best)` run the original dispatch exactly, then insert only when reuse is enabled. Leave coordinate update, filtering and consolidation untouched.
- [x] Record exact changed candidate paths and SHA256; independently review cache reset/key/scope and miss dispatch before matcher runs.

## Task 3: Establish complete ordered V11 reference comparisons

**Files:** `v11_reference.hpp/.cpp`, `ordered_records.hpp`,
`tests/ordered_records_test.cpp`, `fixtures.hpp`, `tests/matcher_contract_test.cpp`,
`run_correctness.ps1`, fresh correctness CSV/JSON.

**Interfaces:** `Record=(class string,x,y,score_uint32,template_id)` in a
vector preserving order. Reference `Options` maps all seven computational
flags to its frozen `MatchOptions`. Candidate options additionally take cache.

- [x] Literal comparator tests reject changed order, missing/extra records, each changed field and one-bit float differences. They compare direct records, not hashes or sets. Written; first execution remains part of the matcher stage.
- [x] Compile frozen `baseline/line2Dup.cpp` in a separate namespace/TU, include only `baseline/` and its MIPP. Compile candidate separately against its own header and frozen MIPP. Use no root matcher include paths.
- [x] Generate existing LED 900-pose and case1 361-template fixtures using the existing SMD parser included through candidate include resolution; export the identical bank to the baseline adapter. Keep source/input hashes.
- [x] Load all sixteen tiny development frames only, using the fixed legacy bank and actual threshold 85. Never load an entry whose split is not development.
- [x] Include a two-class same-bank LED Detector, a larger same-Detector image and a separate legal one-feature blank-image fixture at threshold -1. The latter retains actual zero local maxima without reducing any existing bank or threshold; its known plane reach stays within storage.
- [x] Baseline creates expected records for every fixture/options case. Compare candidate off and on at every index, and repeat the independent baseline to verify stability under thread passes 1/4/2/4.
- [x] Run all 128 computational flag combinations on the ordered route LED positive, zero mask, case1 BGR/size switch, another LED frame, restoring the original. Run baseline and both cache settings; do not assume flag combinations share one expectation.
- [x] Test empty/full/partial masks, threshold 101 empty results, defaults/legacy overloads, populated workspace moves and reuse of moved-from objects. Run two concurrent callers with separate workspaces and shared immutable detectors; generate expected baseline records serially beforehand.
- [x] Preserve every failing row and first mismatching index/complete record, and stop before benchmarking on any mismatch. Record no accuracy-improvement claim from exact equality. All three stages passed, so no failure records occurred.

## Task 4: Independently review and measure the isolated change

**Files:** `benchmark.cpp`, `run_benchmark.ps1`, `summarize.py`,
`BENCHMARK_PROTOCOL.json`, raw timings and review/report files.

- [x] Predeclare nine existing fixtures plus the sixteen tiny development frames, actual fixture thresholds, all template/features/padding retained, CV1/OMP4/passive waiting, cold1/warm2/measured15.
- [x] Rotate three uninstrumented cases: exact frozen V11, candidate off and candidate on. Alternate forward/reverse order by round and image. Use the on/off pair to attribute the cache effect; baseline detects unintended candidate-copy overhead.
- [x] Check every output against frozen expected ordered records outside internal timers. Record API/search time and adapter-inclusive wall separately; no cache counters or correctness serialization inside timed matcher code.
- [x] Keep all samples and compute per-image paired ratios, medians and equal-weight image rollups, retaining no-gain/regression cases. Quantiles are descriptive, not confidence intervals.
- [ ] Root independently reviews candidate diff, RED/GREEN evidence, ordered equality, lifetime/thread matrix, measurement provenance and limitations. Only root stages/commits/tags/pushes accepted results; production adoption is a separate decision.

## Current execution state

The exact V11 snapshot was created and verified using file/Git IO; baseline
manifest SHA256 is
`505c0ccd0ebad8b2db6b51b0e341433f6fb44849dd8dd3adbe42899692491aa2`.
Literal RED compiled successfully and exited1 with the expected missing-hit
failure; `cache_contract_red_20261021_225358_294.json` retains full original
stub/test source bytes and has SHA256
`ae56731ab7c1cc38b1c33d18a6e9b36e0b6402eeb81b8e9eb0a9be2b350b4439`.
The same test bytes passed after the bounded cache implementation;
`cache_contract_green_20261021_225524_029.json` has SHA256
`47b533bf04ea73282b3a76cbac58a70c401c43d41cec8c83bd14dab4d09aaca6`.
Protected production/old-draft files and all tested sources stayed unchanged
during both runs.

Only the private candidate .cpp/.h were then integrated. The five other core
headers remain exact V11 bytes, and the cache header remains byte-identical
to GREEN. `candidate.patch` and `candidate_change_manifest.json` record the
scope. Frozen-reference adapter, matcher tests and separate Build/Run runner
are written. Neither matcher compilation nor matcher execution has started;
no ordered-equivalence, speed or accuracy result was claimed. CPU was formally
released to coverage_helper for its hash/trace GREEN before this static work.

After root and magnet formally transferred the exclusive CPU slot, the isolated
matcher compiled successfully in `build/matcher_20261021_230741_506/`, with all
four compile/link steps exit0 and no protected/source changes. Full warnings,
commands and source hashes are retained in
`matcher_build_20261021_230741_506.json` (SHA256
`1A0821B1A7F41B68EE3BA6A38A9F2CD35F140E57DAF2E57992BC763945FB730D`).
The executable SHA256 is
`0042DA4C53D66E17F1A0AA2FCE3289EAAC0616A36FEC2F9C3E73FF8BECF350BA`.
The Run phase now checks the build-manifest SHA256 receipt before parsing,
checks source/protected/executable identity against Build, and records manifest,
receipt and executable SHA256 before and after execution. CPU was temporarily
returned to root for V16 numeric-provenance archiving; no matcher run has started.

The benchmark protocol, adapter, separate Build/Run runner and paired summary
are written and awaiting independent static review. They cannot compile or run
until all three independent correctness stages pass. Root explicitly removed
the redundant combined `all` rerun because its cases duplicate the three stages;
no unique cross-stage state requirement was identified. Benchmark input is exactly
the existing nine LED/case1 fixtures and sixteen tiny development frames, with
all banks, features, thresholds and padding retained. No benchmark timing or
accuracy-improvement result is claimed.

## Matcher regression result

The three independent stages passed without a redundant `all` rerun:

| Stage | Direct ordered CSV comparisons | Declared matcher calls |
| --- | ---: | ---: |
| core | 1280 | 1536 |
| flags | 1562 | 2343 |
| lifetime | 38 | 106 |
| total | 2880 | 3985 |

There are 2624 candidate comparisons and 256 repeated-baseline comparisons.
Every vector length, class/x/y/template-ID field, float32 score bit pattern and
record order agreed. All result/build/executable hashes remained unchanged;
source/protected files also remained unchanged. Results are in
`correctness_acceptance_manifest_20261021_233133.json`, SHA256
`E187123138849ACA3B7C8256AD125BEF3F000DD0DF432B896C287116C79283E0`.

`audit_correctness.py` performs an independent byte/CSV recheck without invoking
the matcher or decoding images. Its first fresh pass checked 113 pinned files,
all CSV phase/thread/flag counts, build/compiler/source/protected/input/executable
identities, cache RED/GREEN bytes and exact 23-file V11 Git snapshot. Evidence is
`fresh_correctness_audit_20261021_233133.json`, SHA256
`D87C0DB1CE17831A5F350A16508EFE573B0567A34224D503D2E9375F86944CD7`.
It reports the limitation that CSVs retain each complete-vector equality result
and first-mismatch slot, while successful vectors themselves are not serialized.
This fixed matrix does not prove equality on every possible input.

The summary/provenance validator passed fourteen synthetic cases, including
actual source/protected/protocol/build/receipt/executable/gate-CSV byte changes,
case-order/template-bank/threshold/dimension/image-identity defects and mutation
during the CSV read. `summary_validator_green_20261021_232935_467000.json`
has SHA256 `15076E5B215A25E688BA15D037BAE2401D3432039D7504E6F08BF0BAF8D14C64`.
These synthetic checks made zero matcher calls and decoded zero images.
Coverage helper independently reviewed the benchmark protocol/adapter/runner/
summary and reported no remaining static blockers after the fixes. Root will
perform its fresh review before the separately scheduled benchmark Build/Run.
No controlled speed result, accuracy improvement or production adoption is
claimed at this point. CPU has been explicitly returned to root.

Root independently reran the fresh byte/CSV audit and then explicitly assigned
the benchmark CPU slot. Separate benchmark compilation succeeded with no source
changes. The declared 25-image protocol completed all 1350 matcher calls and
complete ordered comparisons with zero mismatches or hash changes. Summary
verification also passed the actual complete hash closure.

`RESULT.md` records all 25 image medians, raw/evidence/build/summary paths and
hashes, and limitations. Candidate on/off search image-median ratio was0.99775,
equal-weight geometric mean0.84391; internal-total ratio median0.99907 and
geometric mean0.91084. LED/case1 benefited, while twelve tiny images regressed
in search (worst1.14644) and twelve in total (worst1.13020). Keep explicit off
as the default; do not claim universal speed improvement or accuracy gain.
CPU was again explicitly returned to root after benchmark and summary.
