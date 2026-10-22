# Parent handoff

The parent owns staging, versioning, commit/tag and push. This new directory and
`docs/superpowers/plans/2026-10-21-hash-consolidation-prototype.md` are isolated
prototype work. No production core file belongs to this change.

Keep source/tests/runner, plans, README/results/static review, and each run's
source snapshot, validation and text logs. Generated `.exe` binaries are local
build outputs; their SHA256 is preserved by validation, so they need not be
staged. Preserve failed evidence, including the initial compile failure and all
semantic RED/mutation runs; do not relabel them as GREEN.

First GREEN sources: `record.hpp`, `hash_consolidation.hpp`,
`hash_consolidation_test.cpp`, `trace_io.hpp`, `trace_io_test.cpp`,
`run_correctness.ps1`. Compiler uses standard-library-only C++14; tests do not
require OpenCV. Run directories are immutable. Later capture preparation must
be reported separately until its own correctness evidence is available.

Next-phase `capture_manifest.py`, `test_capture_manifest.py`, `capture_source.py`,
`test_capture_source.py` and `run_manifest_tests.py` passed 21 unchanged
synthetic tests after semantic RED. `real_capture_audit.py` and its tests then
passed nine synthetic tests in `run_20261021_real_closure_green` after RED.
This stronger audit requires fixed Git core/MIPP snapshots, support/provenance,
two build manifests, compiler/runtime/executable pins and the exact command.
That initial GREEN did not pin compiler headers or the OpenCV import library.
Later `dependency_closure.py`/`test_dependency_closure.py` passed seven synthetic
RED-to-GREEN tests (`run_20261021_dependency_red`,
`run_20261022_dependency_green`); the strengthened real-audit fixture passed
nine tests in `run_20261022_real_dependency_green`. It binds two distinct
`-MD -MF` depfiles, complete ordered local compiler dependency pins, objects,
explicit import library and the two-compile/one-link recipe. That synthetic
phase did not collect real depfiles; the later adapter/build gate is below.
The later alias-aware eight-test GREEN and updated nine-test fixture GREEN
are `run_20261022_dependency_alias_green` and `run_20261022_real_adapter_green`.
The native builds in `build_20261022_capture_v1` compiled four TUs and linked
two executables, preserving pre-M and actual-MD dependency artifacts. All14
native config-scope checks passed in `run_20261022_scope_smoke`; image decodes
and matcher calls were zero in that smoke run.
This records local project/compiler/runtime provenance, not all OS resources.
These belong to the capture-integrity phase, not the initial hash result.

`capture_hook.hpp` is now implemented. `run_20261021_hook_green` compiled the
two-translation-unit tests and passed 44 checks after semantic RED. These are
synthetic exact-V11/state/serialization checks, with zero image decodes or
matcher calls; cross-thread and allocation-failure behavior is not tested here.
The new real-closure and hook GREEN runs may overlap another agent's native
compilation. Their wall times must never be used as performance measurements.
Preserve both RED and GREEN evidence, and do not stage the directory blindly.

Real capture subsequently passed 25/25 fixed actual85 cases in
`run_20261022_capture_actual85`, with 50 matcher calls and complete ordered
field/float-bit equality against independent uninstrumented V11 reference.
The parent separately audited every trace with its own parser and numeric
grouping in `artifacts/independent_reviews/consolidation_trace_v1/`.
N=21..2695; all actual inputs contain duplicates. Preserve the capture binaries
locally if replay audits will be rerun: their receipts require original bytes.

The frozen replay protocol, C++ benchmark, Python wrapper and summary validator
are a subsequent isolated-replay phase. Four synthetic summary tests passed
after no-op RED; the final source GREEN is
`run_20261022_replay_summary_green_final`. Native replay then built and passed
all25 verify-only cases in `build_20261022_replay_v1` and
`run_20261022_replay_verify_v1`, with zero timing rows and no matcher/image
access. Build/verify receipts bind every declared input before and after;
all five methods preserve complete ordered V11 fields/float32 bits.
Measurement is pending a separate parent CPU assignment. The build now pins
all `SOURCE_NAMES` listed in `run_replay.py`; avoid changing those files before
measurement or rebuild/reverify under a new receipt. Do not stage output
directories blindly or remove failed evidence.
The later parent-assigned frozen measurement and own numeric summary passed
in `run_20261022_replay_measure_v1`, with all4250 rows/3875 measured and full
ordered oracle checks. Native and all25 post-capture audits exited zero.
Preserve CSV, native/wrapper receipts, summary and complete source/build pins;
parent independent arithmetic review is pending. Earlier pending statuses
describe the prior gates, not the final measurement run.
Candidate speed, whole-matcher latency and industrial detection accuracy are
unmeasured by this handoff. Capture/instrumented timings, asymptotic complexity
and assertion counts do not establish a performance or accuracy gain.
