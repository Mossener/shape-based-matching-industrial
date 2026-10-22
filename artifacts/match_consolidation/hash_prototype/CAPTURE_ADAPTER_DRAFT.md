# Private capture adapter contract

Implementation contract. `capture_adapter.cpp`, `real_capture_build.py`,
`real_capture_build.ps1`, `run_scope_smoke.py` and `run_capture.py` now exist.
The real capture/reference build and all14 native scope checks passed in
`build_20261022_capture_v1` and `run_20261022_scope_smoke`. That smoke run decoded
no image and called no matcher. The later real capture gate passed all25 fixed
cases in `run_20261022_capture_actual85`, with 50 matcher calls and full ordered
field/float-bit equality to independently compiled uninstrumented V11 output.

The adapter will be a single support TU compiled identically for capture and
reference except `SBM_CAPTURE=1/0`. Capture includes `capture_hook.hpp`; reference
must not include it. Both use their own private exact-V11 include roots, one
local workspace, all seven original option flags enabled, CV1/OMP4, dynamic OMP
disabled, passive wait and one full matcher call. No cache candidate is linked.
No internal or wall time is reported as performance evidence.

The parent-generated one-case config must carry exact image, bank, threshold,
class, constructor and padding identity. A Python runner must verify the frozen
case/scope before passing any image path to the adapter. Tiny index metadata is
filtered to development before constructing an image path; objects 25/29 and
heldout images remain excluded. The native adapter must recheck the supported
case/config values rather than trusting arbitrary caller defaults.

Use the unchanged existing fixture construction:

- LED: supplied `ku.smd` reader and pose construction, L3, 900 poses, threshold
  75, grayscale image, padding 64, alignment 32 and class `LED`. Any extracted
  SMD helper is copied byte-for-byte as private `led_demo.cpp`, with only its
  main symbol renamed at inclusion. The helper is in both source/dependency
  inventories and pinned against its original `artifacts/led_match` source.
  Constructor/pose/decode/padding constants were statically checked against
  the V18 fixture by both helper and root; all eight native capture/reference
  comparisons subsequently passed.
- case1: original 361-template class bank, constructor 128/{4,8}/30/60,
  threshold 90, BGR decode, padding 250 then the existing lower-right alignment
  crop to multiples of 16, class `test`.
- tiny: original 2212-template object-1 bank, constructor 32/{4,8}/20/40,
  grayscale decode, padding 64 with only the existing extra lower/right
  alignment to 16, threshold 85, class `tless_object_1`. A threshold-50 stress
  case uses a distinct scenario and is never quality evidence.

Capture arms immediately before the single matcher call, takes the complete
input/output trace afterward and bit-compares its output to the matcher's
returned vector. Any exception cancels the thread-local hook state and leaves
no successful receipt. Reference serializes only returned output. Both preserve
all five fields, raw class bytes, float32 bits and complete vector order.
Serialization occurs after matching and never inside a replay timer.

Native output is written into a newly reserved case directory and must not
overwrite an existing trace. The runner freezes config/source/input/build/runtime
SHA before the call and rechecks them after it. Failed/partial evidence remains
in its new run directory, with no successful capture manifest. A successful
receipt binds exact argv, build identity, output count/bytes/SHA and completion
state; the parent separately audits captured/reference complete output equality.

The build collector must execute two distinct `-c -MD -MF` compile commands,
then an explicit pinned OpenCV import-library link. Preserve command, cwd,
stdout/stderr/exit status, both `.o` files and both `.d` files; pin every actual
dependency listed by each depfile before and after the run. A shared `-MF` on a
multi-source compile can overwrite dependencies and is forbidden. Pin compiler,
the declared four runtime DLLs, executable, fixed source snapshot and adapter
support/provenance. This is an auditable local recipe, not an attestation of all
Windows system resources or a speed/accuracy result.

`CAPTURE_PROTOCOL.json` freezes all25 case IDs/order, bank/index SHA and V18
fixture constants. The runner enforces those before any capture and records the
protocol SHA in its result and before/after source pins. Threshold50 stress is
rejected by this primary protocol and needs a later separate frozen protocol.

The alias/dependency synthetic regression passed eight tests, and the updated
fixed-source/build fixture passed nine. The native build collected separate
pre-M and actual-MD artifacts, preserving ordered dependency occurrences
405/437 for capture and402/434 for reference. These are header occurrence
counts, not images. Both TUs in each executable compiled and linked. Fourteen
scope checks passed before any image capture. The scope-smoke mode returns before
Detector/template construction or image decoding; it checks three valid input
scopes and four invalid cases in both executables, with zero matcher calls.
Parent-reviewed real capture/reference equality subsequently passed all25
predeclared cases. A second independent parser/numeric grouping audit also
passed all25 traces. Every actual85 trace contains duplicates, with N21..2695;
this does not reproduce the historical486k stress vector. Isolated replay
verification and performance measurement are separate pending gates under
`REPLAY_BENCHMARK_PROTOCOL.json`; instrumented wall time is ineligible as speed evidence.
The parent coordinates native CPU slots and owns Git staging/versioning.
