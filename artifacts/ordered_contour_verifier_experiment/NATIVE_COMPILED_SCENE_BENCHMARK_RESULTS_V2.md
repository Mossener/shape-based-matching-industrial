# Compiled-scene v2 paired synthetic benchmark

Actual root-coordinated run `native_compiled_scene_benchmark_v2` passed:
six alternating rounds x256 candidates, with all 1,536 complete score and solver
work comparisons passing. Index lookup pairs fell from 256 per round to one.
The median paired total-time ratio was **5.8533x** for this 256x256 artificial
scene only. This is not an end-to-end matcher, original-pixel or real-C0 speed
result and supplies no full-run runtime projection.

## Method

The fixed scene contains 1,024 separated stem/returning-cycle components:
5,120 physical membership rows, 6,144 chain memberships and 2,048 complete
chains. A small synthetic template is queried at 256 fixed positions per round.
Rounds alternate baseline-first and cached-first; none is discarded.

The timed baseline calls the exact frozen `candidate::score_candidate`.
Cached preparation calls the same v1 scene factory and additionally constructs
the two immutable lookup indexes; its full preparation cost is included in
the reported total. Both scoring regions retain their complete returned
CandidateScore records.

After both timed paths, a generated counted copy of v1 is called for the same
queries. Its source comes from the fixed v1 SHA with unique function/map-block
anchors; only naming, an extra counter parameter and the two real lookup-map
loops are instrumented. The counted result is compared with both timed results,
including every sample, case, witness, diagnostic and seven solver work fields.
These calls and comparisons are outside both timing regions.

`scene_index_ms_untimed` times only the later instrumented index loops. It is
neither added to baseline timings nor subtracted from them. It can vary from
the earlier uninstrumented region because it occurs separately and includes
source instrumentation.

## All six actual rounds

All values below are milliseconds. Total is preparation plus scoring, before
the untimed count/parity phase.

| Round | Order | V1 prepare | V1 score | V1 total | V2 prepare including indexes | V2 score | V2 total | V1/V2 total | Index timer, untimed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | baseline first | 13.4540 | 183.3311 | 196.7851 | 15.8446 | 11.9763 | 27.8209 | 7.0733 | 103.6248 |
| 1 | cached first | 12.3089 | 126.9468 | 139.2557 | 15.3623 | 10.0031 | 25.3654 | 5.4900 | 93.5236 |
| 2 | baseline first | 13.9343 | 129.3884 | 143.3227 | 13.1125 | 9.7602 | 22.8727 | 6.2661 | 89.0718 |
| 3 | cached first | 14.1266 | 131.0586 | 145.1852 | 14.8429 | 12.6332 | 27.4761 | 5.2841 | 122.4916 |
| 4 | baseline first | 15.2760 | 178.3147 | 193.5907 | 17.8007 | 16.1796 | 33.9803 | 5.6971 | 106.5468 |
| 5 | cached first | 18.2451 | 144.8310 | 163.0761 | 15.2241 | 11.9123 | 27.1364 | 6.0095 | 99.1571 |

The median of the six paired `V1 total / V2 total` ratios is
5.853320790117911. The median score-only paired ratio is 12.424425678192963.
For each even-sized median, the third and fourth sorted ratios are averaged;
these are not ratios of pooled times. No timing ratio is a pass or promotion
gate. Report calculations read the completed six measurement records only;
there was no new native execution or timing rerun.

## Actual lookup construction counts

Every round reported the same counts; these gates passed in C++ and in the
coordinator's receipt checks.

| Count per round | V1 untimed instrumented calls | V2 compiled scene |
| --- | ---: | ---: |
| Index lookup pairs constructed | 256 | 1 |
| Lookup maps constructed | 512 | 2 |
| Membership-row insertion iterations | 1,310,720 | 5,120 |
| Member records referenced by indexed rows | 1,572,864 | 6,144 |
| Complete-chain insertion iterations | 524,288 | 2,048 |

Membership-row/chain counts instrument actual map-building loop iterations.
Member counts sum each indexed row's membership-vector size; they describe
the records covered, not individual member-object traversal or allocation.
These counts concern the additional scoring lookup indexes. Canonical
thinning/chain/membership evidence construction in the shared v1 scene factory
is separately included in both preparation times.

## Actual process and build evidence

The native process exited0 and the coordinator accepted the run. Whole-process
wall was 2.125s and observed peak working set was 11,206,656 bytes. This wall
includes all six pairs, untimed instrumented calls and complete parity checks.
The one process peak covers both paths and cannot be reported as separate
baseline/cached memory measurements.

The compiler job peak committed memory was 384,303,104 bytes and its guarded
wall was approximately 7.688s. Three compiler commands completed successfully.
The retained build guard used a 1GiB Windows job cap including GCC children;
the native guard used 120s/512MiB observed working-set/64MiB output limits.
Source snapshots, actual precompile/compile dependencies, tools/link libraries,
executable and recursively resolved non-system static PE imports remained
pinned through the completed run.

| Completed evidence | SHA-256 |
| --- | --- |
| `native_compiled_scene_benchmark_v2/receipt.json` | `05365e9dc69596fa0b5841253cfda372b2e0aada13d53b11b746e293b33c353f` |
| `native_compiled_scene_benchmark_v2/benchmark_execution/stdout.txt` | `ea9a5884e41d58f2a33b89116c84d5c31f17294f2939f2f355d9e5ff5f19768d` |
| `native_compiled_scene_benchmark_v2.cpp` | `03d25c9136802bed5a84d58b74996a413a8c320ccdc66502b298ef51793a1196` |
| `run_native_compiled_scene_benchmark_v2.py` | `2580b8ead1255ad2cc1d5e561c76e9ff07eb74cd6a76058dc311b117d941613b` |

OS/API-set DLLs and dynamic imports retain inherited provenance limits.
Metadata/tool queries occur outside child watchdogs; working-set observations
are not aggregate RSS or an OS allocation sandbox. No image, decoder,
training replay, bank, raw candidate, dataset index or matcher was accessed.
No machine-wide speed or real-image quality claim follows from this workload.
