# Isolated Hash Consolidation Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Compare immutable-input-index and owning-string hash consolidation against exact V11 output without modifying production code.

**Architecture:** All new code lives in `artifacts/match_consolidation/hash_prototype/`. Both candidates accept a const input vector, preserve the complete minimum-template-ID record and sort only a separate output vector. A standalone map oracle and the committed V11 helper independently check semantics and exact ordered fields.

**Tech Stack:** Standard-library-only C++14, GCC 15.1, PowerShell runner, JSON/CSV evidence.

**Spec:** `artifacts/match_consolidation/POSTPROCESS_DESIGN.md` and parent task authorization on 2026-10-21.

## Global Constraints

- Only create new files; no production core, frozen public source, bank or dataset mutation.
- Never execute `postprocess_optimization/instrument.py`.
- Finite scores only; reject NaN and both infinities before any map operation.
- Duplicate equality is exact `(class_id,x,y,similarity==)`; minimum template ID supplies the complete record.
- Final order is similarity descending, template ID, class, y, x ascending.
- Pre-scan any zero score and use exact V11 sort/unique for the whole input; record `zero_score_fallback`. This is a correctness fallback, not a chosen small-N performance threshold.
- The zero fallback preserves V11's otherwise unspecified bitwise representative when the same minimum ID has both signed-zero score records.
- Input remains unchanged through success and every exception; index map functors dereference only immutable input.
- Coordinate CPU exclusivity with `expanded_quality` before compiling or running tests/benchmarks.
- Implementation validation and performance measurement are separate phases. No speed claim, small-N threshold or production promotion is authorized by correctness alone.

---

### Task 1: Write the contract tests and capture RED

**Files:** Create `record.hpp`, `hash_consolidation.hpp` (API stubs), `hash_consolidation_test.cpp`, `run_correctness.ps1` in the new prototype directory.

**Interfaces:**

```cpp
struct Match { int x, y; float similarity; std::string class_id; int template_id; };
struct Options { bool reserve_input = true; float max_load_factor = 1.0f; };
struct Diagnostics { std::size_t input_count, unique_count, bucket_count; bool zero_score_fallback; };
struct Result { std::vector<Match> matches; Diagnostics diagnostics; };
template<class FieldHasher=DefaultHash>
Result owning_hash(const std::vector<Match>&, FieldHasher = {}, Options = {});
template<class FieldHasher=DefaultHash>
Result index_hash(const std::vector<Match>&, FieldHasher = {}, Options = {});
Result v11_sort_unique(const std::vector<Match>&);
```

- [x] Write literal expected-field cases before hash implementation. The first test supplies duplicate records with minimum ID last and requires a smaller exact ordered result; the API stub returns unchanged input and must fail this assertion.
- [x] Add an independent `std::map<tuple<string,int,int,float>,index>` oracle and independently expressed final tuple ordering. It must not call the candidate hash, equality or sort comparator.
- [x] Test all key fields, adjacent float bits, maximum finite values, 400 shuffled input orders, distinct classes/positions, long/near-equal/embedded-NUL class strings, empty/singleton/idempotence and observed vector sizes.
- [x] Test zero-score fallback against the actual committed V11 helper bit for bit, including unique minimum IDs, same minimum ID signed-zero ambiguity, and different sequence positions.
- [x] Test nonfinite rejection before an injected hash is called, forced constant-hash collision correctness, and throwing-hash/actual allocation-failure input preservation.
- [x] Preserve source snapshots, compiler/version/flags, compile/test stdout/stderr/exit codes and SHA in a fresh RED output directory. Expected failure is semantic duplicate/representative mismatch, not a compilation error.

### Task 2: Implement and capture GREEN independently

**Files:** Modify only the new `hash_consolidation.hpp`; tests from Task 1 are frozen for the first GREEN run.

- [x] Pre-scan finite scores and zero occurrence. For a zero call the V11 helper on a full input copy and return explicit fallback diagnostics before constructing any map.
- [x] Implement a canonical-zero/exact-nonzero-bit field hash, exact owning-key equality, and owning-key map to minimum input index.
- [x] Implement an input-index map whose hash/equality functors keep a pointer to the const input. Update mapped representative indices only; copy complete representatives out and destroy the map before sorting output.
- [x] Both variants expose N/U/bucket diagnostics and reserve/no-reserve options; no guessed unique ratio or small-N fallback is added.
- [x] Run the unchanged tests after exclusive CPU confirmation, require compiler warnings treated as errors and exit 0, and preserve the GREEN source snapshot and hashes.
- [x] Add targeted mutation RED runs for omitted key fields, wrong representative, wrong final order, missing finite guard and missing zero fallback. Each mutation must compile and fail semantically; keep snapshots.
- [x] Ask an independent reviewer to inspect implementation/oracle/tests and recheck evidence without editing production files.

### Task 3: Prepare replay and measurement separately

**Files:** Create a replay/benchmark protocol and loader/benchmark sources only after Task 2 correctness passes.

- [x] Inventory existing pre-consolidation trace availability without executing the old sandbox. The recorded stage CSVs contain counts, not automatically replayable complete records; do not fabricate raw traces from them.
- [x] If full input traces are absent, propose a new isolated source copy that captures exact pre-consolidation vectors with frozen source/input provenance. Coordinate and obtain parent dispatch before any matcher run; keep instrumented timings out of performance claims.
- [ ] Preserve tiny/small/no-duplicate/heavy-duplicate, long-class and large real vectors. Label synthetic duplicated real output accurately instead of calling it a real pre-consolidation trace.
- [ ] Freeze benchmark matrix/order/warmup/repeat/environment/copy-cost accounting before running it. Include normal-hash reserve/no-reserve variants and V11, with every regression retained.
- [ ] Report exact output equality before timings, median and tail, bucket/allocation coverage limits, and zero-score fallback. Do not select a small-N threshold or claim a full matcher speedup.

The parent owns staging, version records, commit, tag and push. Coverage V14 handoff is already complete in `artifacts/quality_coverage/STAGING_NOTES.md` and is separate from this unmeasured prototype.
