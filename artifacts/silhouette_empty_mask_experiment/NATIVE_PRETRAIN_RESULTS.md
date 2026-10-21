# Native preparation results

Root approved the static implementation, then granted an exclusive CPU slot
for exactly RED build/run, GREEN build/run and adapter build. All those stages
are complete and the CPU slot has been returned. No real training, bank
planning, development-image decode or matcher call was run.

| Stage | Compiler commands | Native outcome |
| --- | ---: | --- |
| Wrong selection-mask RED | 5, all exit 0 | Exit 1 at `Feature-selection mask must be empty cv::Mat()`; no toy extraction |
| Empty selection-mask GREEN | 5, all exit 0 | Exit 0; ownership, exact source/class/return policy and four invalid-mask cases pass |
| Training/planner adapter build | 5, all exit 0 | Actual private V11 adapter executable built; not executed |

The GREEN executable used the same fixed 192×192 toys as source-only, without
changing geometry, feature targets or thresholds. It recorded:

| Toy | Success | L0/L1 actual features | L0/L1 tl x/y | L0/L1 nearest canvas-edge distance |
| --- | --- | --- | --- | --- |
| Rectangle | Yes | 59 / 16 | (46,46) / (23,23) | 47 / 23 |
| Diagonal polygon | Yes | 32 / 18 | (40,40) / (20,20) | 41 / 20 |

These actual toy counts also confirm why requested 32/16 must not be treated
as hard actual-count caps. The original source-only toy runs reported
`insufficient_features` for both shapes; the new mask policy restores extraction
for these generated toys. This is an extraction-feasibility result, not an
image-matching accuracy or speed result.

`NATIVE_PRETRAIN_SUMMARY.json` numerically rechecks all recorded source/tool/
runtime/object/dependency/executable pins, each complete ordered GCC `-M`/`-MD`
dependency list, the native RED/GREEN evidence files and the real-adapter run
gate using the local provenance helper. Each build also has `build_summary.json`. All six pairs of raw
precompile/actual dependency files are retained; duplicate aliases remain in
ordered occurrence counts. Compiler diagnostics, commands, native stdout and
stderr are preserved in their original fresh stage directories.

Every actual matcher/feature implementation came from the successor's own
23-file Git V11 snapshot. Resolved non-system static PE imports and compiler
tools/libraries were checked before/after the relevant stage. OS/API-set DLLs
are named but not hashed, and no claim covers every dynamic plugin or OS
resource.

The completed tests used two generated synthetic extraction calls, zero real
training attempts, zero dataset image reads and zero matcher calls. Real-bank
feasibility and the later common-padding RGB comparison still require a new
root CPU assignment. The frozen source-only experiment is untouched.
