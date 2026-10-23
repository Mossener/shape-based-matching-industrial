# V35 retained-evidence checkpoint static review

Date: 2026-10-23. No remaining blocking finding in the reviewed release source.
This is source and retained-metadata review; it does not claim that the release
script, its `--check` branch, or the final selection has executed successfully.
Actual publication checks and Git operations remain the coordinator's work.

Reviewed `prepare_native_candidate_checkpoint_v35.py`: 17,581 bytes,
SHA-256 `650dab0fb157ebad71c585d2421ba39ab95ed8b9a75dd44b986c05b2ba28374e`.
Changing this source requires a corresponding review/update of this statement.
The reviewer read source, reports, receipts and logs, enumerated explicit
retained directories and hashed their selected metadata/source/numeric output
files using PowerShell. No Python script, test, compiler, native executable,
benchmark or Git command was executed for this final review. No original
image, raw candidate, bank, GT or dataset-index payload was opened.

## Complete retained whitelist

The fixed `V35_RETAINED_EVIDENCE_MANIFEST.json` is 72,645 bytes, SHA-256
`9602d4a9b7139f7a1fe9751e4685be10d289f4115324b1b8fddc5b09a9427d4b`.
An independent metadata enumeration and per-file SHA/size pass found exactly
24 declared directories, 285 non-build files and 52,744,024 bytes. There were
zero member-set or byte-pin differences and no observed reparse points.
This is an inventory/hash pass, not a second semantic algorithm.

The C0 portion has 11 actual run directories and three derived-output
directories, totaling 141 files. Its exact directory whitelist is:

- `c0_inventory_whitelist_green_v1`
- `c0_inventory_whitelist_green_v2`
- `c0_inventory_whitelist_green_v3`
- `c0_inventory_estimate_v1`
- `c0_inventory_windows_red_v2`
- `c0_inventory_windows_green_v2`
- `c0_inventory_estimate_v2`
- `c0_inventory_hash_v2`
- `c0_numeric_binding_red_v1`
- `c0_numeric_binding_green_v1`
- `c0_raw_binding_green_v1`
- `c0_inventory_estimate_v2_payload`
- `c0_inventory_hash_v2_payload`
- `c0_raw_binding_green_v1_payload`

`SOURCES` includes all 19 current C0 inventory/binding source, decision, test,
runner, result and acceptance files. The already published C0 input plan and
pure numeric/parser dependencies also remain in the historical source
archives; older V1 sources are retained as their actual archived bytes.
No historical source snapshot is replaced with its current successor.

The native portion has ten actual run directories and 144 files: candidate
RED/GREEN/oracle, pixel RED/GREEN, compiled-scene RED/GREEN/benchmark, and
geometry RED/GREEN. The explicit current sources, protocols, frozen tests,
decisions, runners and available component reviews/reports are included.
The retained numerical/identity reports are derived outputs; the original
raw gzip, template banks, annotation CSVs and image inputs are excluded.

## Completed runs and preserved failures

Receipt/log inspection confirms all 21 required actual runs have completed;
the three derived directories are outputs rather than additional runs.
Expected assertion-failing RED gates have top-level `passed=true` while their
child guards preserve exit 1. The original V1 estimate remains an actual
failed run with top-level `passed=false`, child exit 1 and `Opened file changed`.

| Component | Actual RED | Actual GREEN |
| --- | --- | --- |
| Candidate | 35 tests / 307 checks / 204 failures / 0 errors | 35 / 611 / 0 / 0 |
| Pixel | 22 / 970 / 338 / 0 | 22 / 8,452 / 0 / 0 |
| Compiled scene | 28 / 8,556 / 8,437 / 0 | 28 / 8,557 / 0 / 0 |
| Geometry | 7 / 35 / 24 / 0 | 7 / 4,660 / 0 / 0 |
| Windows file stamp | 3 methods / 1 failure / 0 errors | 3 methods / 0 failures/errors |
| C0 numeric mapper | 28 methods / 35 failures / 0 errors | 28 methods / 0 failures/errors |

Metadata hashes separately confirmed that both archived copies and current
test bytes match for all six RED/GREEN pairs above. The 9-test whitelist
runs v1/v2/v3 all completed successfully, but they bind different preparer
versions. Their successes do not erase the subsequent V1 opened-file failure
or establish success for another source version. The V2 stamp regression and
successful final-source whitelist/estimate/hash evidence remain complete.

The candidate oracle receipt reports all 6,144 complete comparisons and
6,144 per-chain brute-force comparisons with zero skips. The cached-scene
benchmark completed six alternating rounds and all 1,536 complete parity
comparisons. These are the coordinator's retained actual runs, not reruns by
this reviewer. Component reports retain the distinction between synthetic
correctness, inherited numerical GT projection and real-image evaluation.

## Release-source checks and corrections

The final source fixes the following initial-review issues:

1. Final-source C0 windows/estimate/hash/numeric receipts must retain stable
   source/archive equality and their source pins are rechecked. Final whitelist
   source-after pins and its nine-test count are checked. Windows RED exit 1,
   GREEN guard success, numeric mapper 28-method/35-to-0 failure counts and both
   C0 test archives are checked without treating historical V1 successes as
   evidence for V2 bytes.
2. C0 acceptance's two mapper receipt pins and five evidence pins are checked
   before selection. An independent metadata hash pass confirmed all seven
   current pins match the prior acceptance, including complete result,
   per-combination and original-identity outputs.
3. The retained manifest's size/SHA is fixed in source. Each of the 24 explicit
   directories must match its exact non-build relative-path set, and every
   member must match its fixed size/SHA. Suffix checks supplement this exact
   set; they do not decide publication by themselves. Additional JSON/text
   files cannot silently join the selection.
4. Benchmark measurements use `benchmark_rows`, while publication pins use
   `selection_rows`. The normal publishing branch therefore computes its
   median from measurement records. The earlier shared `rows` variable would
   have raised `KeyError` only after `--check` returned; no output from that
   earlier source was accepted.

Static tracing of the normal branch confirms that complete receipt gates,
fixed-test comparisons, source/evidence pins, original C0 numerical totals,
seven authoritative V11 production files and retained-member checks precede
creation of acceptance/selection/pathspec. `--check` performs those checks
without writing them. Normal output uses exclusive creation; the Git helper
only reads state. Selection sorting and NUL-delimited pathspec creation use
the selected relative paths. The acceptance itself is added before final
selection pinning; selection is intentionally not self-hashed.

The roots and members examined here contain no original real input payload,
private magnet/SMD image or derivative, build binary, or pending full-attempt
replay source/output. The fixed source list excludes the unfinished replay
adapter/schedule. Declared input paths and their byte pins remain visible in
retained inventory metadata, as do host/toolchain paths in receipts.

## Claim boundary

The original C0 control exactly reproduces 2,400 combinations, 457,279 raw
rows, 390 zero combinations, 42,327 selected candidates and 215/42,112/185
TP/FP/FN. Its GT authority remains the inherited projection. This publication
does not reconstruct official annotations or regenerate raw matcher output
from pixels.

The benchmark uses one supplied-label 256x256 artificial scene. Its cached /
baseline total-time ratio includes both preparations; it does not establish
real-image matcher speed, memory improvement or an industrial runtime bound.
The acceptance explicitly keeps real pixel/attempt replay complete, new
real-image quality tested, real end-to-end speed improvement and production
promotion false; heldout scenes/objects remain sealed. All 20,736 original
training attempts, 36,398 saved layers and real new-verifier scoring remain
later gates. Watchdog, toolchain and OS/runtime provenance limits in the
component reports continue to apply.

This review accepts the finite checkpoint scope above, subject to the root's
subsequent actual `--check` and publishing-branch execution. It is not an
accuracy or end-to-end performance acceptance.
