# Static C0 plan and native runner review V1

Date: 2026-10-23. This review found no material C0 selection mismatch or unsupported payload-audit claim. The native runner's recorded build/test resource claims are supported within their stated phase scopes. Its metadata subprocesses run outside those guards, so the phase ceilings do not establish an overall coordinator resource ceiling.

This review used source, JSON metadata, saved receipts and file hashes only. It did not execute Python, tests, native binaries, compilers or Git; read image, raw candidate or bank payloads, dataset indexes or heldout inputs; or modify production, V31/V32 evidence, existing sources/tests, or the accepted `PIXEL_ADAPTER_PRECHECK_V1.md`. The only file written for this review is this document. The supplied-label fault tests were authored separately; their subsequently reported execution belongs to the coordinator.

## C0 input plan

Reviewed `prepare_c0_input_plan_v1.py` in full and parsed `C0_INPUT_PLAN_V1.json` and the selected V31 stage metadata. Verified the current bytes/hashes of the plan's four observed metadata sources and preparer against the plan. Compared every plan manifest/raw pin to the corresponding selected stage entry. This pass did not reopen the 2,400 small manifests; their actual-file checks were performed by the preparer and by the earlier static precheck. No compressed raw or bank content was opened in either review.

| Current artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `prepare_c0_input_plan_v1.py` | 6,182 | `2ea49b774ca2aeec25f78a708334f6c3b29417282e61a7654831ff1d5cd32155` |
| `C0_INPUT_PLAN_V1.json` | 2,215,868 | `62610add5d6e40c219a3f9929edb1aa2f87c831d8a678ec4848cf282eb8236c0` |

The preparer selects only the actual V31 `quality/run_development_v1/QUALITY_STAGE_FREEZE.json`, SHA `6070b474d29b112c822d7f6a94a2ec920e454d104c511c42c29bf78a1d77b47a`, and only `rgb_control/fallback` manifests for objects `[1,2,5,8,12,17]`. It checks the completed/post-verification state, denies heldout image allowance, requires agreement between the frozen development lists, checks all 400 unique frame identities per object, and retains zero-candidate combinations. Its supplied 848×848 grid and LTRB `[64,64,64,244]` agree with the accepted actual-V31 precheck, rather than the historical V30 equality-reference padding.

| Object | Plan records / unique frame keys | Declared candidates | Zero combinations |
| ---: | ---: | ---: | ---: |
| 1 | 400 / 400 | 78,590 | 0 |
| 2 | 400 / 400 | 74,574 | 0 |
| 5 | 400 / 400 | 8,417 | 45 |
| 8 | 400 / 400 | 93 | 345 |
| 12 | 400 / 400 | 19,778 | 0 |
| 17 | 400 / 400 | 275,827 | 0 |
| Total | 2,400 / 2,400 object-frame keys | 457,279 | 390 |

All 2,400 `manifest_observed` pins and all 2,400 `raw_declared` pins match their selected actual-V31 stage entries. Each object retains the complete development key set. The six `own_banks_declared` records select `arm=C0` original frozen `rgb_training` banks beneath `rgb_empty_mask_experiment/frozen_inputs`, consistent with the earlier precheck; this directory location does not select the empty-mask treatment. The six attempts declarations are original C0 attempt-file pins. The plan inherits 432 training-member declarations and records expected 20,736 attempts and 18,199 successes, without claiming to have verified those payloads here.

The preparer reads only its four metadata sources, its own source and the selected small manifests. The plan correctly labels itself `metadata_selection_only`, calls raw counts declared and bank/training pins inherited, and leaves `real_input_freeze`, `real_pixel_execution` and `production_promotion` false. Its post-score85/pre-NMS consolidated scope comes from the earlier source/metadata precheck; the preparer does not numerically audit raw rows. Native replay, all-attempt outcomes, actual source-image pixels, eligible grids and full payload closure remain separate requirements.

## Native runner resource and provenance scope

Reviewed `run_native_core_checks_v1.py`, `native_compile_child_v1.py`, `NATIVE_CORE_DECISIONS_V1.json`, and the inherited `native_provenance.py` and `execution_guard.py`. Read the saved RED/GREEN receipts and part of the saved invocation. This is a runner/claim review, not a static algorithm review of `native_ordered_match.hpp` or a rerun of the native tests.

The current GREEN C++ source pins and the current runner, compiler child and decisions hashes equal the GREEN receipt's saved pins. The RED header intentionally differs from the current GREEN header; the RED test source and runner/child/decisions pins still match their current counterparts.

| Current file | SHA-256 |
| --- | --- |
| `run_native_core_checks_v1.py` | `d373712862df4bf6bfd6cc8894f37d908ffaeddd05cf198727c91e8274233f66` |
| `native_compile_child_v1.py` | `afa5b370b12d73d771591f2f6e16f6cf2ca7e937758e90d6244b1def3578d03c` |
| `NATIVE_CORE_DECISIONS_V1.json` | `cabd9e4324023f170898137678fb042f4ca9a2c579728eee30ef794ad620012c` |
| `native_ordered_match.hpp` | `1236a5555c781f639be34beef95ea187d5e57de6d629df1c96805029bc8b85a3` |
| `native_ordered_match_test.cpp` | `04cd9243597d43a82582e2e05d252ff0247e725fc8a712241f2bf75869275e75` |

The build helper assigns itself to a Windows job before launching GCC. `JOB_OBJECT_LIMIT_JOB_MEMORY` caps committed memory at 1 GiB across the job, including GCC children, and `KILL_ON_JOB_CLOSE` supports compiler-child termination when the helper terminates. The parent guard separately observes the helper's peak working set, wall time and designated output directories. These are different memory measures; the decisions and receipt correctly avoid calling the job measurement aggregate RSS. The test executable uses the inherited single-process watchdog with 60 s, 512 MiB observed peak working set and 64 MiB designated output limits. That watchdog polls at about 50 ms and is not an OS allocation sandbox.

| Saved phase | Suite result | Build guard wall | Build job peak committed | Build helper peak working set | Test guard wall / peak working set |
| --- | --- | ---: | ---: | ---: | ---: |
| RED | 40 tests, 265 checks, 174 failures, 0 errors; expected exit 1 | 2.516 s | 234,987,520 B | 22,454,272 B | 0.093 s / 6,520,832 B |
| GREEN | 40 tests, 365 checks, 0 failures, 0 errors; exit 0 | 3.515 s | 296,566,784 B | 22,339,584 B | 0.078 s / 6,533,120 B |

These are saved historical observations, not new execution or production speed measurements. The test counts and runner parsing support the supplied-graph native gate only. No real pixels, quality, full-image cost or promotion conclusion follows.

The runner snapshots both C++ project sources and builds with the snapshot directory as cwd. GCC's predeclared and actual dependency-file pins must match, including ordered occurrences, and project dependencies are restricted to the approved two source snapshots before their content is hashed. Current sources and snapshots are compared after execution; executable, dependencies, declared tooling/libraries and resolved runtime pins are rechecked. This supports a useful local evidence chain. Static PE imports identify the non-system dependency candidates; OS/API-set imports are named without hashing and dynamic imports are explicitly outside the claimed attestation.

Two scope limits must be retained in subsequent documentation:

1. `compiler_tools()` and both `import_closure()` calls run outside `run_guarded()`. Their `g++ -print-prog-name` and `objdump -p` subprocess calls use `capture_output` without a timeout or output ceiling. The 256-node import-closure bound limits file count, not elapsed time or captured output bytes. The build/test limits therefore do not cover all coordinator metadata work, nor do the designated payload/execution directory quotas include source snapshots and all coordinator JSON files.
2. The coordinator inherits the ambient environment and pins declared link libraries and tool paths. It does not retain a complete environment or prove actual link-library resolution from a linker map, actual loaded DLL paths, Python's full runtime closure, or every OS resource. Its current qualified language about declared pins, static imports and absence of execution attestation is appropriate; a hermetic-build or complete-runtime-attestation claim would exceed this evidence.

No existing artifact was changed to strengthen the historical evidence. A future real-input execution freeze still needs its own accepted source/build/input/resource/replay closure.
