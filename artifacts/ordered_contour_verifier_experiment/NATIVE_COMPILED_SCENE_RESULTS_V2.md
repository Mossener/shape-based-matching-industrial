# Native compiled-scene v2 results

Status: actual RED, GREEN and paired synthetic benchmark receipts reviewed.
GREEN and all six paired rounds passed their phase gates.
The root coordinator owns all compilation and native execution. The author
performed source reads, metadata/hash reads and source/report edits only.

## Change

`native_candidate_compiled_scene_v2.hpp` owns immutable factory scene evidence
and two lookup indexes in shared storage. The factory calls the frozen v1
scene factory once and constructs the pixel-membership and chain-ID lookup
maps once. Score calls read incident memberships and complete incident chain
topology by stored vector offsets. They do not iterate all scene memberships
or chains and do not call the frozen v1 scoring function.

Copying shares immutable storage, moving transfers its owner, and a moved-from
handle rejects evidence/index/score access with `std::invalid_argument`.
Candidate-local maps, full chain topology, arithmetic order, exact GMP scores,
thresholds, witnesses, diagnostics and every solver work field remain part of
the frozen v1 parity contract. Frozen v1 sources were not edited.

## Actual literal and full parity runs

| Run | Phase | Tests | Checks | Failures | Errors | Compiler exit | Native exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `native_compiled_scene_red_v2` | Actual empty-stub RED | 28 | 8,556 | 8,437 | 0 | 0 | 1 |
| `native_compiled_scene_green_v2` | Actual implemented GREEN | 28 | 8,557 | 0 | 0 | 0 | 0 |

RED completed normally with ordinary assertion failures. The compile job peak
committed memory was 357,392,384 bytes; native wall was approximately 0.281s and
observed peak working set was 6,742,016 bytes. RED runner acceptance exit0 means
the required failing phase was accepted, not that empty stubs passed tests.
GREEN's compile job peak was 355,893,248 bytes; native wall was approximately
0.172s and observed peak working set was 6,959,104 bytes. Its completed receipt
SHA is `7852219d0d55a5a9418e769d008bc6bc6c298cba4f429c20e18d86e70a355c3f`.

The frozen 28-test suite includes literal index counts, all shared ownership
copy/move forms, source/result independence, exceptions, cycles/junctions,
zero-owned chains, physical pixel reuse, origins/padding/int64 arithmetic and
GMP values above uint64. Its full supplied-label domain is 6,144 candidates
over 1,024 scene occupancy/direction profiles, three templates and two
transforms; every profile reuses one compiled scene for six score calls.
Complete scene and CandidateScore fields are compared with frozen v1,
including every MatchResult work field. This is regression parity, not a new
independent oracle.

## Paired synthetic measurements

Actual run directory: `native_compiled_scene_benchmark_v2`.
Status: passed six alternating rounds and all 1,536 complete comparisons.
`NATIVE_COMPILED_SCENE_BENCHMARK_RESULTS_V2.md` records the complete method,
actual counts and receipt/stdout pins.

The fixed synthetic scene is 256x256 with 1,024 separated stem/returning-cycle
components: 5,120 physical membership rows, 6,144 chain memberships and 2,048
complete chains. Six rounds alternate baseline-first/cached-first order, with
256 queries per round. All 1,536 counted-v1/v1/v2 comparisons include the full
score and solver work outside measured regions.

The timed baseline calls the exact frozen v1 function. A SHA-gated generated
copy instruments the two actual scene lookup-build loops afterward, outside
timing; it does not replace the timed baseline or edit v1. The reported
`scene_index_ms_untimed` belongs only to that untimed instrumented copy.

| Round | Order | V1 prepare ms | V1 score ms | V1 total ms | V2 prepare including index ms | V2 score ms | V2 total ms | V1/V2 total ratio | V1 index ms untimed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | baseline first | 13.4540 | 183.3311 | 196.7851 | 15.8446 | 11.9763 | 27.8209 | 7.0733 | 103.6248 |
| 1 | cached first | 12.3089 | 126.9468 | 139.2557 | 15.3623 | 10.0031 | 25.3654 | 5.4900 | 93.5236 |
| 2 | baseline first | 13.9343 | 129.3884 | 143.3227 | 13.1125 | 9.7602 | 22.8727 | 6.2661 | 89.0718 |
| 3 | cached first | 14.1266 | 131.0586 | 145.1852 | 14.8429 | 12.6332 | 27.4761 | 5.2841 | 122.4916 |
| 4 | baseline first | 15.2760 | 178.3147 | 193.5907 | 17.8007 | 16.1796 | 33.9803 | 5.6971 | 106.5468 |
| 5 | cached first | 18.2451 | 144.8310 | 163.0761 | 15.2241 | 11.9123 | 27.1364 | 6.0095 | 99.1571 |

Median paired total ratio: 5.853320790117911. Median paired score-only ratio:
12.424425678192963. Each median averages the third and fourth sorted paired
ratios. These apply solely to this artificial 256x256 scene, not a matcher,
pixel pipeline or complete real-C0 runtime. Whole process wall was 2.125s and
observed peak working set was 11,206,656 bytes. Compiler job peak committed
memory was 384,303,104 bytes. No timing ratio was a pass/promotion gate.

Actual operational counts per round, confirmed in every completed round:

| Lookup construction count | V1 untimed instrumented calls | V2 compiled scene |
| --- | ---: | ---: |
| Index pairs built | 256 | 1 |
| Lookup maps constructed | 512 | 2 |
| Membership-row insertion iterations | 1,310,720 | 5,120 |
| Member records referenced by indexed rows | 1,572,864 | 6,144 |
| Chain insertion iterations | 524,288 | 2,048 |

Member counts sum each indexed row's membership-vector size; they are not a
claim that every member object was individually visited while indexing.
Counters measure only the additional score lookup maps, not v1 factory
topology construction. No elapsed-time ratio is a pass or promotion gate.

## Resource and provenance limits

The compiler helper uses a Windows job committed-memory cap of 1GiB including
GCC children plus parent wall/output monitoring. The literal native test uses
60s/512MiB observed working-set/64MiB output limits; the synthetic paired
benchmark uses 120s/512MiB/64MiB. The single benchmark process peak includes
both paths and untimed parity calls, with no per-path peak claim.

Actual GCC dependency lists, declared tools/link libraries, source snapshots
and recursively resolved non-system static PE imports are pinned before and
after successful work. OS/API-set DLLs, dynamic imports and metadata/tool
queries retain the inherited provenance limits. This is not aggregate RSS or
an OS allocation sandbox.

Only supplied synthetic label grids are used. There is no pixel decode,
training replay, raw C0 candidate load, matcher call, real-image quality,
real-input runtime projection or production promotion in these results.

## Source pins

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| `native_candidate_compiled_scene_v2.hpp` | 8,973 | `165eac841a664e6d203c3128fc4dd898acbbd910daa8835dcf3e72b845627fdc` |
| `native_candidate_compiled_scene_v2_test.cpp` | 21,014 | `95f1b5f64603f1d3cfad098779b14e56c2d50fc4c2c55736b3df847fe2addcc2` |
| `NATIVE_COMPILED_SCENE_DECISIONS_V2.json` | 3,962 | `651f14f67f091fe92c45dbcf8ab896415246e2403aafdf6ebdf07fe2969e51e9` |
| `run_native_compiled_scene_checks_v2.py` | 8,429 | `a2a19c6fe4c3066eab35925d91c7ced80e78c81e076bfa030e3182dda50127e4` |
| `native_compiled_scene_benchmark_v2.cpp` | 7,338 | `03d25c9136802bed5a84d58b74996a413a8c320ccdc66502b298ef51793a1196` |
| `run_native_compiled_scene_benchmark_v2.py` | 12,223 | `2580b8ead1255ad2cc1d5e561c76e9ff07eb74cd6a76058dc311b117d941613b` |

The decisions file is the preserved pre-RED decision artifact; its historical
`red_only_source_prepared_unexecuted` status was deliberately not rewritten.
