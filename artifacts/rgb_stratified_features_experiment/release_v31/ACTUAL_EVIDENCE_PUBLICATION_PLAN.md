# V31 actual-evidence publication plan

Planning snapshot: 2026-10-23. The existing source checkpoint was committed and
pushed as `5acb270`, as reported by the root. Its
`SOURCE_CHECKPOINT_SELECTION.json` and the frozen publication verifier must
retain their exact bytes. This document neither creates a final selection nor
publishes files. Paths below are relative to
`artifacts/rgb_stratified_features_experiment/` unless stated otherwise.

Only directory metadata, small receipts and source were inspected for this
plan. No bank, raw archive, dataset image, large JSONL or 71 MB geometry report
was opened. File sizes below are observations, not new SHA verification.
The root's full development run was still running when this plan was written;
independent quality, timing and lossless export results remain conditional.

## Selection rules

The final root-owned selection should combine the reviewed source-checkpoint
scope with concrete accepted evidence additions. Expand each inventory into
individual canonical repository-relative POSIX paths with exact byte counts
and SHA256. No directory recursion or wildcard is a final allowlist. Check
every selected file is strictly smaller than 104,857,600 bytes (100 MiB),
including manifests and logs. The training exporter has the tighter stored
member ceiling of 99,614,720 bytes (95 MiB).

Retain failed attempts and stage-local status flags. In particular, the
independent training runner is not the root execution acceptance, and the
scanner's `numeric_audit_passed: false` is not the later combined acceptance.
Do not rewrite either historic receipt to match a later aggregate decision.
Numeric pass, primary B accuracy pass, measured speed and production promotion
must stay separate. A failed accuracy hypothesis is a valid published outcome;
pending stages are never reported as passing.

## Training and exact-geometry additions already present

These are candidate additions backed by currently present small receipts;
the final root gate must recheck their pins against the trusted acceptance.

| Scope | Concrete candidate paths |
|---|---|
| Root execution acceptance | `TRAINING_ACCEPTANCE.json`; `run_training_v1_PROVENANCE.json`; `TRAINING_INPUT_FREEZE.json`; `TRAINING_SOURCE_FREEZE.json` |
| Independent complete training v2 | `independent/evidence/full_training_audit_v2/RUNNER_RECEIPT.json`; `OUTPUT_PINS.json` in that directory; `audit_output/INDEPENDENT_RECEIPT.json` |
| One-shot training/audit reservations | Exact accepted `execution_reservations/train.json` and `independent_full_audit_v2.json`, plus their actual consumption records if recorded by the corresponding runner |
| Native training guard | Exact six files in `run_training_v1_execution/`: `guard_reservation.json`, `guard_latest.json`, `guard_telemetry.jsonl`, `guard_receipt.json`, `stdout.txt`, `stderr.txt` |
| Independent training guard | Exact six corresponding files in `independent/evidence/full_training_audit_v2/execution/` |
| Joined training and geometry | `GEOMETRY_INPUT_FREEZE.json`; `ACCEPTED_TRAINING_GEOMETRY_REPORT.json`; `quality/TRAINING_GEOMETRY_ACCEPTANCE.json` |
| Exact scanner declaration | `geometry/real_scan_20261023_v1/GEOMETRY_FREEZE.json`, `common_padding_plan.json`, `receipt.json`; the complete report, or its verified reversible transport, as described below |
| Guarded scanner launch | `geometry/real_scan_20261023_v1_RUNNER_RECEIPT.json`; `real_scan_20261023_v1_RESERVATION.json`, its `.consumed.json` and `.guard_launch.json` records; exact six files in `real_scan_20261023_v1_EXECUTION/` |
| Independent geometry | `geometry/real_independent_20261023_v1/RUNNER_RECEIPT.json`; `audit_output/INDEPENDENT_GEOMETRY_AUDIT.json`; `geometry/real_independent_20261023_v1_RESERVATION.json` and its `.consumed.json`; exact six guard files in `real_independent_20261023_v1_EXECUTION/` |

The root training acceptance names the independent training report as 21,963
bytes. The independent geometry result is 47,860 bytes. The joined root
report is 6,188 bytes. Include the exact source files/snapshots named by these
receipts through the unchanged source scope, rather than assuming the newest
file at the same path is the accepted source.

The earlier full-training-audit v1 attempt remains a failed attempt. Retain its
compact reservation, available guard/failure records and
`AUDIT_ENTRYPOINT_FAILURES.md` under an explicitly reviewed failure scope.
Do not select an entire failed directory or replace the successful v2 records
with a source-test receipt. Retain the root training provenance and existing
attribution/license and public-dataset source declarations.

## Training lossless export: required before full public replay

`run_training_v1/` is not a directory that can be published wholesale. Metadata
shows `layer_selections.jsonl` is 419,000,062 bytes. Other sizable members are
`progress.jsonl` (72,434,232), `pools.jsonl` (23,202,297),
`pools_000000.bin.gz` (67,106,398) and `pools_000001.bin.gz` (60,784,541).
The accepted provenance lists the original complete 46-file numeric output.
The export must retain every listed member, including failed pose records,
pool candidates, strata/selections, complete banks and official metadata.

After a coordinated actual export, select every `EXPORT_MANIFEST.json`
`files[].stored_path` member and the manifest itself, plus explicit full
restore/round-trip validation receipts, exporter source pin and execution logs.
The root chooses a fresh export directory; none is asserted to exist here.
`preserve_training_evidence.py package` already requires the accepted original
provenance, exact source inventory, per-member original and stored pins,
complete decoded-byte readback, and a 2 GiB export budget. Its `restore`
requires a fresh directory and checks the complete stored inventory before
reconstructing the original names and bytes. A failed export is not a release
bundle. There is no current chunking fallback if one stored member exceeds
95 MiB; a separately tested successor would be required.

There is a real publication-verifier incompatibility to resolve separately:
the frozen `verify_selection.py` rejects any suffix chain containing `.bin`,
whereas the existing lossless exporter preserves the legitimate numeric
`pools_*.bin.gz` names and bytes. Preserve that verifier and the old checkpoint.
A reviewed successor must allow only exact manifest-bound identity pool
members, require the accepted export manifest itself to be selected with its
full pin, and keep rejecting bare `.bin`, arbitrary `.bin.gz`, path mixing and
changed original/stored pins. Do not omit pools or silently rename an accepted
bundle merely to pass the old suffix rule. Root review and synthetic rejection
tests must precede using any successor for a real selection.

## Geometry report transport

`geometry/real_scan_20261023_v1/bank_geometry_report.json` is 71,295,252 bytes
(about 68 MiB), so its original file is already below the hard 100 MiB limit.
The accepted `GEOMETRY_FREEZE.json` records its original SHA256 as
`47839b4d886781769cb406d325d7fc54b40315841088587b9ac7697ccf165ff9`.

Recommend publishing a deterministic outer gzip transport to reduce repository
and clone bytes if a dedicated exporter/restore check is reviewed first. No
compression ratio or compressed size has been measured here. Preserve the
original file locally and every existing receipt/freeze unchanged. The transport
manifest must bind the original relative and absolute provenance path,
71,295,252 original bytes and accepted SHA256, compression method/version,
stored path/bytes/SHA256, exporter source, and exact accepted geometry freeze.
Create it only from the accepted source bytes; stream-decode the entire stored
file and compare byte count and SHA256 against that accepted pin. A real
restore to a fresh directory must reproduce the original report byte for byte.
Use a decode ceiling of the accepted original length, reject extra/truncated
streams and unexpected inventory members, and preserve failure evidence.

Compression must not parse/reserialize or round numeric coordinates. A summary,
sample or pretty-printed reconstruction is not a replacement. The existing
training exporter is training-provenance-specific and is not automatically a
geometry exporter. Until a complete reversible transport is accepted, selecting
the untouched 71,295,252-byte original is the working compatible option.
Do not publish both copies without a reason; the manifest must explain where
the exact original is restored for the historic audit.

## Quality build, staged execution and complete raw evidence

`quality/build_native_v1/build_manifest.json` is present (257,248 bytes), as
are `attempts.json`, compile/dependency/link logs and dependency files. Select
those individual text records, together with accepted sources. Exclude
`quality_eval.exe`, `core.o`, `adapter.o`, all runtime libraries and build
caches. The analogous `build_training_v1/` contains `train_shared_features.exe`
and object files; only its manifest, `commands.json`, text logs and dependency
files belong to the evidence scope. Runtime binaries may stay referenced by
hash without being redistributed.

Current input declarations to retain are `quality/QUALITY_INPUT_FREEZE.json`
(3,071,298 bytes), `quality/COMMON_PADDING_FREEZE.json` (146 bytes), and the
joined acceptance above. Their full pins bind bank inputs, public dataset
frame identities and inherited C0 reference files. They are declarations, not
quality results.

The directories `quality/run_selftest_v1`, `run_old_gate_v1` and `run_pilot_v1`
are present. Their stage-freeze sizes observed were 6,045, 75,405 and 209,933
bytes respectively. Selection must use each completed freeze's exact `files`
and `execution_files` inventory after the root checks successful completion,
source/input closure, exact call budget, and resource guard. Include the
freeze itself, `execution_provenance.json`, `verified_before.json`,
`verified_after.json`, all exact nested guard records/logs, and the matching
`quality/quality_stage_reservations/{old_gate,pilot}.json` records. The selftest
includes its small synthetic raw files and `selftest_result.json`; do not
select `.gitignore` as new numeric evidence.

For old gate, pilot and later development, include the complete numeric native
inventory rather than metrics alone: stage summary, bank-load timings,
candidate equality, GT, retention, per-frame metrics, selected detections,
per-object metrics and every C0/P/B fallback/fused raw `.csv.gz` plus its
`_manifest.json`. Inspect each final stored file's size before selecting it;
an oversized member requires a separately verified reversible transport.
Complete raw archives are necessary to rerun numeric equality/NMS/GT checks;
hashes or previews alone cannot replace them.

`quality/run_development_v1` was active at this planning snapshot. Do not freeze
or select its growing files. When it completes, apply the same exact inventory
gate and retain `quality_stage_reservations/development.json`. A partial or
failed stage may contribute explicitly labeled failure evidence only.

## Conditional independent quality and timing additions

No successful actual result is asserted for the following pending scopes.
Use the later receipts' concrete paths, not invented filenames:

| Conditional scope | Required complete evidence |
|---|---|
| Independent quality | Trusted development stage pin; one-shot reservation and consumed marker; `RUNNER_RECEIPT.json`; runner execution provenance; all exact guard logs; complete `audit_output/result.json`, `per_frame_audit.json`, `retention.json`; source snapshot/origin pins |
| Root quality acceptance | Exact `quality/QUALITY_AUDIT_ACCEPTANCE.json` that pins the complete development stage and independent numeric result, copies the actual primary B accuracy boolean, and retains `production_promotion: false` |
| Native timing | A fresh completed timing `QUALITY_STAGE_FREEZE.json`, exact input/build/selftest/development/quality-audit bindings, `quality_stage_reservations/timing.json`, full nested execution/guard inventory, and exactly four native files: `bank_load_timings.csv`, `stage_summary.json`, `timing_samples.csv`, `timing_pairs.csv` |
| Independent timing | External `rgb_stratified_independent_timing_inputs_v1` declaration with its seven full accepted pins; one-shot reservation/consumed marker and persistent lock; complete `result.json`; sibling runner receipt/execution guard files; numeric/source origin snapshots |

Independent quality's success schema is
`independent_three_arm_quality_audit_v1`; independent timing's is
`independent_three_arm_timing_audit_v1`. A runner receipt is not a substitute
for the numeric result. Timing remains unavailable until the fixed run and
independent replay complete. Its full target is 29,952 native calls, 27,648
formal rows and 27,648 paired rows; a planned count is not an observation.
Private magnetic/SMD regressions and heldout industrial generalization remain
separate work and cannot be inferred from this development evidence.

## Recomputable origin and final root gate

Every published transport needs a reverse mapping from selected stored bytes
to the exact historic original path, byte length and SHA256. Preserve absolute
paths inside historic evidence; use an explicit restoration/path-map document
for another checkout, without rewriting a pin to fit the new machine.
Retain `.gitattributes` byte-preservation rules. Do not normalize line endings,
CSV fields, JSON ordering or floats in accepted records.

The 46-file P/B training export does not itself provide inherited C0 banks or
old/common-padding C0 references. For every inherited pin, identify the exact
already-published prior selection/member or add a reviewed complete lossless
transport. Public dataset images remain external: document the existing
dataset source/version and exact frame/index pins. Local source/data hashes
alone do not make unavailable dependencies downloadable. Exclude private
magnetic/SMD captures, all raster images, sealed heldout inputs, native
binaries, caches and broad archive containers.

Before final publication, the root should record each prerequisite's actual
status in a new result/completion document, preserve failure history, and write
an explicit final selection. Do not edit `SOURCE_CHECKPOINT_SELECTION.json`
or revise checkpoint-era pending statements into fabricated historic passes.
The final description should state purpose, usage, upstream source, actual
ability and measured limits; it should not emphasize personal maintenance.
Run the reviewed offline selection verifier, stage only that scope, then
verify exact indexed blobs and cached whitespace using the authorized root
workflow. This plan performs none of those actions.
