# Isolated hash consolidation prototype

Latest result: the fixed real capture, separate replay verification and
4250-row replay measurement are complete. The parent independently recomputed
all routes and statistics. See [V21 results](REPLAY_RESULTS_V21.md) for the
benefits, case1 regression and limits. Production V11 remains unchanged.
The following sections retain the chronology of the earlier gates.

Status: both isolated hash candidates and binary trace I/O passed correctness
tests on 2026-10-21. Six intentional semantic mutations were also rejected.
No production file is modified and no performance measurement has run. The plan is in
`docs/superpowers/plans/2026-10-21-hash-consolidation-prototype.md` at the
repository root; the semantic design is `../POSTPROCESS_DESIGN.md`.

The standard-library-only prototype compares owning-string keys with immutable
input-index keys. Input remains const while a map exists, the complete record
at the minimum template ID represents a duplicate group, and a separate result
gets the exact V11 final ordering. An independent numeric-key `std::map`/tuple
oracle and the unchanged committed V11 helper check complete ordered fields
and float bits. Record layout mirrors all five core Match fields without
depending on OpenCV.

Any nonfinite input is rejected before hashing. Any finite zero score invokes
the exact V11 sort/unique path on the entire input copy and records
`zero_score_fallback`. This correctness fallback preserves V11's exact signed
zero representative, including equal-minimum-ID ties that its unstable first
sort does not specify. It is not a small-vector performance threshold.

The first RED test required duplicate reduction and minimum-ID selection from
three literal records. The stub returned unchanged input and failed semantically.
The unchanged tests then passed, including actual `bad_alloc` at each allocation ordinal,
throwing hash, forced collisions, 400 shuffled duplicate sets, long/embedded-NUL
class strings, adjacent finite float bits, signed-zero V11 comparisons and
synthetic size pressure up to 486045 records. The pressure vectors are not real
captured matcher traces.

Hash GREEN performed 13,671,101 field/bit/contract checks; trace GREEN performed
139 checks and rejected 106 malformed inputs. These are assertion counts, not
independent image counts. `CORRECTNESS_RESULTS_20261021.md` identifies every run
and the preserved initial compile failure. Correctness establishes neither
industrial detection accuracy nor a speed improvement. Trace byte bounds limit
encoded data; they are not a hard heap or resident-memory cap.

Coordinate exclusive CPU before these commands and always choose a new output:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/match_consolidation/hash_prototype/run_correctness.ps1 -OutputDirectory artifacts/match_consolidation/hash_prototype/my_red -ExpectedExit 1
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/match_consolidation/hash_prototype/run_correctness.ps1 -OutputDirectory artifacts/match_consolidation/hash_prototype/my_green -ExpectedExit 0
```

Each run preserves a full source snapshot including the exact V11 consolidation
header, source/compiler/executable SHA, compiler flags and complete logs. The
runner checks that the current production header equals its committed V11 Git
blob, but never edits it. The parent owns staging, versioning and commit/push.

Real input vectors were captured on 2026-10-22 after the gates below.
`TRACE_CAPTURE_PLAN.md` defines the immutable-format/capture/replay phase.
The old sandbox is not used.
Correctness, replay and measurement remain separate; do not infer a speedup
from algorithm complexity or a lower output count.

The next phase's independent Python parser and generic declared-pin audit,
plus exact-Git snapshot generator, passed 21 synthetic tests in
`run_20261021_manifest_source_green` after semantic RED. A stronger fixed-source
audit then passed nine synthetic tests in `run_20261021_real_closure_green`:
it requires both exact 23-file core/MIPP snapshots, support/provenance sources,
two saved build manifests, compiler/runtime/executable pins and an exact command.
The initial nine-test version did not pin compiler header dependencies or the
OpenCV import library; preserve that limitation for its original GREEN run.

The later `dependency_closure.py` phase rejected a no-op stub in seven synthetic
tests, then passed all seven in `run_20261022_dependency_green`. It parses each
TU's separate `-MD -MF` Make depfile, preserves complete ordered dependency
pins, and checks object/depfile/import-library bytes. Repository dependencies
are scope-checked before hashing. `run_20261022_real_dependency_green` passed
the nine integrated fixed-source/build tests with this stronger protocol.
Two compile commands plus one explicit-import-library link prevent a shared
multi-TU depfile from silently overwriting one TU's dependencies.

The alias/dependency phase then passed eight tests in
`run_20261022_dependency_alias_green`, followed by nine updated fixed-source
tests in `run_20261022_real_adapter_green`. Real native capture/reference builds
passed in `build_20261022_capture_v1`, including separate pre-M and actual-MD
dependency artifacts and four successful TU compiles/two links. All14 native
scope checks passed in `run_20261022_scope_smoke`, with zero image decodes and
matcher calls in that smoke run. Native MinGW output
showed valid lexical aliases for the same header; the parser now preserves all
ordered occurrences. Earlier synthetic GREEN snapshots retain their original
duplicate-rejection limitation and are not overwritten.
This is local compiler dependency and
project/toolchain/runtime provenance, not proof that every OS resource is
unchanged. See `CAPTURE_ADAPTER_DRAFT.md` for the remaining adapter contract.

The capture hook is implemented and passed 44 synthetic checks across two
translation units in `run_20261021_hook_green`, after a semantic RED stub failed
on complete ordered input copying. Checks cover exact V11 pass-through, one-shot
arming, cancellation, complete fields/score bits and failed nonfinite captures.
No real matcher was called. These two GREEN runs may overlap another agent's
native compilation; all wall times are ineligible as performance evidence.
These files belong to a separate capture-integrity phase from the initial C++
hash correctness handoff described in `STAGING_NOTES.md`.

The subsequent `run_20261022_capture_actual85` completed all 25 fixed cases:
eight LED frames, case1 and sixteen object-1 tiny development frames. It made
50 matcher calls, one capture and one independently compiled uninstrumented
V11 reference per case. Complete ordered fields and float32 bits matched for
every case, with input/build/source/runtime provenance checked before and after.
Inputs have N=21..2695 and U=7..641, and all contain duplicates. These traces
are neither the historical 486k pressure vector nor real empty/no-duplicate
coverage. No heldout image or reserved object 25/29 was accessed.

The parent's independent standard-library reader/grouping audit also passed
all 25 traces and four synthetic checks in
`artifacts/independent_reviews/consolidation_trace_v1/root_trace_audit_20261022.json`.
It does not import the prototype parser, decode images or call the matcher.
Instrumented capture time is not performance evidence; source production code
and templates remain unchanged.

`REPLAY_BENCHMARK_PROTOCOL.json` was frozen before replay implementation or
measurement. `replay_benchmark.cpp` and `run_replay.py` implement separate build,
verify-only and measurement gates, with independent prepared input copies and
ownership/destruction costs included consistently. `summarize_replay.py` checks
all expected rows before deriving 31 paired ratios per trace and aggregates
only within a declared scenario. Four synthetic summary tests failed against
the no-op RED stub, then passed in `run_20261022_replay_summary_green`. One
literal fixture has paired-ratio median 2 while the ratio of latency medians
is .5, so those statistics cannot be interchanged.

Native replay build and separate verify-only gates subsequently passed in
`build_20261022_replay_v1` and `run_20261022_replay_verify_v1`. Discovery,
compile and link exited zero; all 25 immutable traces reproduced captured V11
output and all five methods matched complete ordered fields/float32 bits.
The wrapper's before/after real-capture and build/input audits passed. Native
receipt records sizeof(Match)=56, 25 traces, zero timing rows, zero matcher
calls and zero image decodes. This is replay correctness only. Measurement
remains pending the parent's separate review and exclusive CPU assignment.

The parent's subsequent independent saved-artifact review passed 356 unique
file pins, exact Git helper bytes, raw discovery/actual-MD ordered dependencies,
all25 case identities/order and native verify counts in
`artifacts/independent_reviews/consolidation_trace_v1/root_replay_build_verify_20261022.json`.
It reran no matcher or replay timing. Measurement is approved in principle but
has not started; the parent must assign its exclusive CPU slot first.

The frozen measurement schedule is 25 traces x (3 warmup + 31 measured) x
5 methods = 4250 rows, including 3875 measured rows. Each method receives an
independent prepared input copy outside the consolidation timer; common copy
cost is reported separately. For each trace, summarize 31 same-round
candidate/V11 ratios, then aggregate per-trace medians with equal trace weights
only within the same declared scenario. Keep every ratio and regression; the
protocol does not select a small-N threshold or promote a production method.
No whole-matcher latency, industrial accuracy or measured-memory gain follows
from isolated replay timing.

The frozen measurement subsequently completed in
`run_20261022_replay_measure_v1`: native replay, all25 post-capture provenance
audits and the row-by-row numeric summary passed. It contains all4250 rows,
including all3875 measured rows, with every timed output checked against the
complete ordered V11 oracle. `summary.json` preserves every paired ratio,
separate common-copy distributions and all regressions. Its arithmetic is
pending the parent's independent raw-CSV recomputation. No production matcher,
template bank, parameter default or small-N threshold is changed.
