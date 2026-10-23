# Static compiled-scene implementation and benchmark review V2

No blocking defect was found in the reviewed final cached implementation or
the revised benchmark source. Only source and retained receipt metadata were
read; no compiler, script, test, benchmark or real input payload was executed
or reopened by this reviewer.

| Reviewed final source | Bytes | SHA-256 |
| --- | ---: | --- |
| `native_candidate_compiled_scene_v2.hpp` | 8,973 | `165eac841a664e6d203c3128fc4dd898acbbd910daa8835dcf3e72b845627fdc` |
| `native_compiled_scene_benchmark_v2.cpp` | 7,338 | `03d25c9136802bed5a84d58b74996a413a8c320ccdc66502b298ef51793a1196` |
| `run_native_compiled_scene_benchmark_v2.py` | 12,223 | `2580b8ead1255ad2cc1d5e561c76e9ff07eb74cd6a76058dc311b117d941613b` |

The score implementation was compared section by section to frozen v1. It
preserves support construction, all checked coordinate intermediates, sample
and chain order, owned weights, full incident scene topology, exact solver,
diagnostics, acceptance thresholds and invariant checks. The two v1 full-scene
map loops are replaced by lookups into factory-owned immutable maps. No hidden
full-scene scan/map rebuild or call to the old score function remains. Per-score
template/support/incident maps and copies of complete incident chain vertices
remain; caching does not remove their costs. `require_storage()` precedes
score access. Shared immutable ownership and vector offsets remain valid across
copy/move and surviving handles; returned results own their values.

The benchmark's timed baseline calls the exact original v1 `score_candidate`,
without instrumentation. Cached preparation includes index construction. Both
paths reserve/store complete candidate results inside their timed score region;
scene/template label creation and result destruction are outside the reported
regions. Original-v1/counted-v1/v2 full score and work comparisons happen after
both measured paths. The source-generated counted baseline changes only a
SHA-gated function name/signature and the uniquely anchored two index loops;
it is used only for untimed operational counts and `scene_index_ms_untimed`.
Membership-row/chain counts are insertion-loop iterations; member counts sum
referenced member records, not individually traversed member objects.

The declared scene is 256 by 256 with 1,024 isolated branching components,
5,120 physical membership rows, 6,144 memberships and 2,048 scene chains. Six
rounds alternate baseline-first/cached-first, 256 queries each. Complete parity
is required for all 1,536 query results. Root runtime must still prove the actual
compiled scene topology, counts, elapsed values and summary. No elapsed ratio
is an acceptance gate. The one-process peak includes both paths and untimed
comparison; it cannot identify separate per-path peaks. This is an isolated
supplied-label scene-index benchmark, not pixel processing, whole matcher or
industrial quality/performance evidence.

The runners retain inherited compiler Job committed-memory, foreground working
set/wall/output, GCC dependency and static PE import pins. Preflight queries,
ambient runtime, OS/API-set/dynamic imports and allocation-observation limits
remain as documented in the earlier native resource review. No additional test
expansion or source mutation was needed for this static review.
