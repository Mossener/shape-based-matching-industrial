# V31 Final Candidate Collection Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans for the later root-owned collection. The checkboxes describe future work, not checks executed by this document's author.

**Goal:** Collect the complete accepted V31 experiment evidence into an explicit public selection without changing frozen evidence or claiming an accuracy or speed improvement that the results do not support.

**Architecture:** Preserve the committed source checkpoint and union its exact allowlist with receipt-driven actual evidence. Expand only named inventories and fixed source roles; deduplicate identical canonical paths and reject conflicting pins. Large payload verification, independent export restore, final selection generation and Git checks belong to the root after native timing releases the single heavy execution slot.

**Tech Stack:** Existing JSON receipts, the lossless training export, and the frozen Python publication successor.

**Spec:** `ACTUAL_EVIDENCE_PUBLICATION_PLAN.md`, `PUBLIC_SELECTION_SUCCESSOR.md`, `PUBLIC_SELECTION_VALIDATION.json`, `../SOURCE_CHECKPOINT_SELECTION.json`, and `../independent_quality_v2/SOURCE_HANDOFF_V2.json`.

## Global constraints

- This is a new planning document. Do not edit the existing proposal, source, source checkpoint, verifier, receipts, reservations or failed attempts.
- Repository root is `D:/h/shape_based_matching-master`. Except for the final section's repository-level design documents, paths below are relative to `artifacts/rgb_stratified_features_experiment/` under that root.
- This planning pass read only source, small receipts and directory metadata. It did not run Git, tests, native programs, export restore, payload hashing or final selection generation.
- Keep private magnetic/SMD images and the sealed heldout set out of public evidence. Published numeric evidence does not imply public permission for its source images.
- Keep numeric consistency, primary accuracy hypothesis, speed and production promotion as separate fields. Production remains V11; V31 is an experiment.
- Select individual canonical repository-relative POSIX paths. Do not use a directory, glob, prefix or recursive filesystem traversal as the final allowlist.
- Each public file must be strictly smaller than 104,857,600 bytes. The accepted training export additionally limits each stored member to at most 99,614,720 bytes. Preserve original bytes; do not reformat historical JSON or normalize line endings.
- Do not auto-follow every `input_pins` or `source_pins` reference: these also name external runtime binaries, private images, inherited evidence and raw training originals. Classify each reference before collection.

## Observed state and remaining gates

| Scope | Current evidence and permitted claim |
|---|---|
| Source checkpoint | Root reports commit `5acb270`; selection has 2,304 files and 21,082,467 selected bytes. Preserve it unchanged. |
| Public successor | `PUBLIC_SELECTION_VALIDATION.json`: synthetic source tests 20/20; targeted mutants rejected 9/9. This does not validate a real final selection or Git index. |
| Independent quality V2 | Root acceptance and runner report numerical audit passed, primary accuracy hypothesis failed, production promotion false. |
| Actual quality outcome | C0 TP/FP/FN 215/42112/185; P 178/10102/222; B 187/11116/213. B preserves 156 C0 identities, loses 59 and gains 31. Preserve the complete result, including regressions. |
| Native timing | `quality/run_timing_v1/QUALITY_STAGE_FREEZE.json` was absent at the latest metadata inspection. Timing and speed claims remain pending. |
| Training transport | Actual `public_training_export_v1/EXPORT_MANIFEST.json` reports passed: 46 members, 235,876,886 stored bytes, 690,835,424 original physical bytes. Root confirms the package operation streamed decoded members back against original SHA256/bytes. |
| Independent transport restore | No saved independent restore acceptance yet. Root plans a fresh `PUBLIC_EXPORT_RESTORE_CHECK` and `PUBLIC_EXPORT_ACCEPTANCE.json` after timing. These are future outputs, not present candidate inputs or completed checks. |

## Task 1: Preserve and extend the source allowlist

**Inputs:** Existing checkpoint, public successor validation, independent V2 source handoff and their cited source-test receipts.

**Output:** An in-memory set of exact source/evidence paths for the root's later candidate builder. This task does not create a second source checkpoint.

- [ ] Load `SOURCE_CHECKPOINT_SELECTION.json`; retain every existing `files[]` row unchanged and select the checkpoint file itself. Do not replace it with a newly discovered directory inventory.
- [ ] Add `release_v31/PUBLIC_SELECTION_VALIDATION.json` and each of its 13 `files[]` pins. This includes the immutable predecessor, successor sources, origin/plan documents and the specifically cited RED, current GREEN, failed mutation run and corrected mutation run receipts.
- [ ] For cited public RED/GREEN receipts, add exactly `source_snapshot_pins[]` and `outputs[]`. In particular, retain `successor_red_manifest_pool_v1/receipt.json` and `successor_green_manifest_pool_v3/receipt.json` with their run-specific source snapshots and stdout/stderr.
- [ ] For `release_v31/successor_mutations_v1/receipt.json` and `successor_mutations_v2/receipt.json`, expand each `mutants[]` row into its exact `mutant_pin` and `outputs[]`. Retain its persisted sibling `receipt.json`. To retain the original test working directory, derive the finite source-copy paths from that receipt's six `source_pins` basenames under each mutant's `source/`; compare each unmodified copy to its run's historical pin and the changed verifier to `mutant_pin`. Do not use today's top-level test file for v1: v1 records the earlier 17,271-byte test, while the corrected source is 17,628 bytes. The v1 8/9 rejection result remains a failed test-gap record.
- [ ] Add `independent_quality_v2/SOURCE_HANDOFF_V2.json`, its 16 `source_pins[]`, and its `regression_red`, `regression_green` and `full_source_green` receipt pins.
- [ ] Retain `independent_quality_v2/source_role_red_v1/{receipt.json,stdout.txt,stderr.txt}` and the analogous GREEN records. Derive each run's 14 original `source/<basename>` paths from that receipt's `source_pins[]`; later verify their bytes/SHA256 against those historical pins. The metadata check confirmed both snapshots exist. Historical README, run_selftest and SOURCE_ORIGINS pins must not be applied to today's changed top-level files.
- [ ] Expand the full V2 source receipt at `independent_quality_v2/evidence/20261022T181602.533567Z_quality_source/RECEIPT.json`: its 16 `source_snapshot[]` pins; `green.stdout`/`green.stderr`; each of the 18 `mutant_red[]` rows' `mutated_source`, `stdout` and `stderr`. Its immutable base snapshot provides the unmodified source roles. If preserving the original mutant test directories, derive their finite 16 source paths from the receipt's `sources_before` names, using the changed-source pin as the sole override. This is a named snapshot expansion, not a directory scan.
- [ ] Preserve `SOURCE_ORIGINS_V1.json` and the unchanged predecessor-source pins named by V2 origin evidence. Those pins are attribution/lineage, not stale replacement pins.

Public source receipts are synthetic validation evidence. The actual V2 numerical audit is collected separately below. Do not re-label a synthetic source pass as an actual numerical or accuracy result.

## Task 2: Collect accepted training and geometry evidence

**Inputs:** Root acceptances, training provenance, export manifest, independent audit receipts and geometry freeze.

**Output:** Complete numeric transport and original geometry evidence with their execution/source bindings.

Minimum original entry points:

| Scope | Exact entry points to add if absent from the checkpoint |
|---|---|
| Training | `TRAINING_ACCEPTANCE.json`, `run_training_v1_PROVENANCE.json`, `TRAINING_INPUT_FREEZE.json`, `TRAINING_SOURCE_FREEZE.json` |
| Independent training V2 | `independent/evidence/full_training_audit_v2/RUNNER_RECEIPT.json`, `OUTPUT_PINS.json`, `audit_output/INDEPENDENT_RECEIPT.json` |
| Training reservations | `execution_reservations/train.json`, `execution_reservations/independent_full_audit_v2.json`, and the actual recorded consumption records named by their runner |
| Joined geometry | `GEOMETRY_INPUT_FREEZE.json`, `ACCEPTED_TRAINING_GEOMETRY_REPORT.json`, `quality/TRAINING_GEOMETRY_ACCEPTANCE.json` |
| Actual scan | `geometry/real_scan_20261023_v1/GEOMETRY_FREEZE.json`, `common_padding_plan.json`, `receipt.json`, `bank_geometry_report.json` |
| Scan execution | `geometry/real_scan_20261023_v1_RUNNER_RECEIPT.json`, `real_scan_20261023_v1_RESERVATION.json`, its `.consumed.json` and `.guard_launch.json` siblings |
| Independent geometry | `geometry/real_independent_20261023_v1/RUNNER_RECEIPT.json`, `audit_output/INDEPENDENT_GEOMETRY_AUDIT.json`, `geometry/real_independent_20261023_v1_RESERVATION.json` and its `.consumed.json` sibling |
| Lossless training transport | `public_training_export_v1/EXPORT_MANIFEST.json` and all 46 exact stored members from `files[].stored_path` |

- [ ] Add each training/geometry runner's exact source and execution provenance records, plus the six named guard files for each accepted execution: `guard_reservation.json`, `guard_latest.json`, `guard_telemetry.jsonl`, `guard_receipt.json`, `stdout.txt`, `stderr.txt`. Accepted execution directories are `run_training_v1_execution/`, `independent/evidence/full_training_audit_v2/execution/`, `geometry/real_scan_20261023_v1_EXECUTION/` and `geometry/real_independent_20261023_v1_EXECUTION/`.
- [ ] Retain the compact failed full-training-audit v1 reservation, failure/guard records and `AUDIT_ENTRYPOINT_FAILURES.md` named by existing provenance. Keep failure status unchanged. Do not substitute it for successful V2 evidence or retry a consumed reservation.
- [ ] Select the original geometry report, 71,295,252 bytes, SHA256 `47839b4d886781769cb406d325d7fc54b40315841088587b9ac7697ccf165ff9`. Root chose this original report; no new gzip transport is required. The size/hash here comes from an existing pin, not a fresh read.
- [ ] Load the actual export manifest, 22,826 bytes, SHA256 `9094d4f4fde321b1c1099bd9f762cc3de9522e8e8894a026555812376323d10f`. For every row, select `stored_path` with the exact `stored` bytes/SHA256, preserving its original mapping and encoding. Select the manifest's `training_provenance`, `training_acceptance` and exporter `source` pins as well. Do not select the raw 419 MB JSONL or recursively collect `run_training_v1/`.
- [ ] Keep both identity numeric pools: `pools_000000.bin.gz` (67,106,398 bytes) and `pools_000001.bin.gz` (60,784,541 bytes). Compressed JSONL names, bank files and metadata are equally mandatory: all 46 stored members must be present.
- [ ] After timing releases the heavy slot, root performs its planned independent restore into a fresh, empty directory and writes an acceptance that binds this exact manifest. Verify the complete restored-name inventory, count, each original byte count and SHA256, and reject extras/missing members. Add the saved acceptance and its exact validation/source records once present. Do not publish the redundant restored directory or claim this check has already passed.

The final selection must contain this explicit trust anchor:

```json
"accepted_training_export": {
  "path": "D:\\h\\shape_based_matching-master\\artifacts\\rgb_stratified_features_experiment\\public_training_export_v1\\EXPORT_MANIFEST.json",
  "bytes": 22826,
  "sha256": "9094d4f4fde321b1c1099bd9f762cc3de9522e8e8894a026555812376323d10f"
}
```

Only the successor's exact manifest-bound `pools_[0-9]{6}.bin.gz` identity exception is allowed. This does not authorize arbitrary binary archives, build products or a broader suffix exception.
The absolute pin above uses Windows' resolved backslash form because the verifier requires `str(Path(path).resolve()) == path`; selected `files[].path` values still use repository-relative POSIX form.

## Task 3: Collect complete quality evidence and preserve the V1 failure

**Inputs:** Completed stage inventories, root quality acceptance and the V2 actual runner.

**Output:** All evidence needed for the accepted numerical audit, including full raw rows and identity losses.

- [ ] Select these four completed freezes and expand each exact `files[]` and `execution_files[]` inventory: `quality/run_selftest_v1/QUALITY_STAGE_FREEZE.json` (6,045 bytes), `quality/run_old_gate_v1/QUALITY_STAGE_FREEZE.json` (75,405), `quality/run_pilot_v1/QUALITY_STAGE_FREEZE.json` (209,933), `quality/run_development_v1/QUALITY_STAGE_FREEZE.json` (9,086,309). Preserve every raw `.csv.gz`, its manifests, complete metrics and execution guard records. Do not collect a sampled subset of development evidence.
- [ ] Add each stage's exact non-null external reservation binding, including `quality/quality_stage_reservations/{old_gate,pilot,development}.json`, and the accepted input/build/source freezes. The root later reads inventories; this planning pass did not open the 9 MB development freeze.
- [ ] Add `quality/QUALITY_AUDIT_ACCEPTANCE.json`, `complete_quality_evidence.py` and `QUALITY_RESULTS_V31.md`. The acceptance pins the helper at 10,420 bytes / SHA256 `c7a6d51b1985576c35fec8ec7c5cab116abad9beda635494266f4717f3d1f1dd`. Pin the result document only after root finishes its explanatory/link edits; an earlier observed document size is not an immutable numerical receipt.
- [ ] Add `independent_quality_v2/real_development_audit_v2/RUNNER_RECEIPT.json`, its `execution_provenance.json`, the exact six guard files in `execution/`, its `reservation` and `consumed` pins, and all three `evidence_files[]`. Those are the complete `audit_output/per_frame_audit.json` (2,748,079 bytes), `result.json` (12,323,462) and `retention.json` (22,078). The runner's `independent_audit` pin duplicates `result.json`; require equality, not a second path/version.
- [ ] Keep the V1 actual failure: `independent_quality/real_development_audit_v1/RUNNER_RECEIPT.json`, `execution_provenance.json`, the six `execution/` guard files, its exact `reservation`/`consumed` pins, and `evidence_files[]` (`audit_output/failure.json`, 129 bytes). The runner reports `passed: false` and no result. V2 is a source-corrected successor, not a rewrite of this failed run.
- [ ] Collect build manifests and only their declared textual command/dependency/diagnostic records from `build_training_v1/` and `quality/build_native_v1/`. Preserve accepted source binding and origin snapshots. Do not select either directory wholesale: `.exe` and `.o` are present.

The V2 acceptance explicitly excludes complete transitive Python runtime attestation and independent gradient regeneration. Publish those limits alongside its successful numeric audit. Do not infer industrial generalization from development evidence.

## Task 4: Finish timing, resolve reference availability, then validate the real selection

**Inputs:** Later completed timing and restore evidence plus the exact candidate set above.

**Output:** A new root-owned final selection and saved real publication validation. These outputs do not exist because this plan names them.

- [ ] Wait for root to establish successful native completion and a fresh timing `QUALITY_STAGE_FREEZE.json`. Only then add the freeze, all its `files[]`/`execution_files[]`, its actual external reservation and accepted input/build/quality bindings. The native timing output contract includes `bank_load_timings.csv`, `stage_summary.json`, `timing_samples.csv` and `timing_pairs.csv`; retain all four.
- [ ] After root runs the independent timing path, collect its exact `rgb_stratified_independent_timing_inputs_v1` declaration with all seven accepted pins, independent result, runner/execution provenance, reservation/consumed marker, persistent lock and guard records. Use actual receipt paths, not invented placeholders. Keep timing pending if any required stage is incomplete; publish no speed ratio before independent acceptance.
- [ ] Resolve each inherited numeric dependency deliberately. The 46-member training transport supplies P/B training evidence, not inherited C0 banks or every historical V30 raw/input closure. For public replay, provide the unchanged prior published numeric selection/member at its exact pin or a separately accepted explicit transport. Record unavailable/external dependencies honestly. A hash reference alone does not supply absent bytes.
- [ ] Treat the V2 fixed V30 shared `INPUT_CLOSURE.json` exception narrowly: canonical path and full pin must match the authorized closure. Do not deduplicate different raw/bank files merely because their hashes match, or generalize this contract exception to arbitrary references.
- [ ] Merge by canonical repository-relative path. If two receipts demand different bytes/SHA256 at one path, retain their actual separate historical snapshots and lineage; do not silently prefer the latest version. Compute a new candidate's exact file count and byte total only during root collection. Include existing checkpoint rows unchanged and add this plan/review only as planning artifacts if root chooses to publish them.
- [ ] Once the heavy slot is free, root verifies each selected payload against its receipt/manifest pin and the per-file ceilings, including the accepted export/restore. Generate a new final selection with an explicit scope/status and the exact export trust anchor above. Do not edit `SOURCE_CHECKPOINT_SELECTION.json` or include a self-referential row for the new selection.
- [ ] Run the frozen successor against the real candidate using `verify_public_selection.py --selection <new-selection-path>`. Save its actual receipt. This is a later real validation, distinct from the already completed synthetic tests.
- [ ] Root stages only the approved selected paths plus the new selection; run the successor again with `--staged --selection <new-selection-path>`. It checks exact SHA1/SHA256 Git blob IDs (according to repository object format), modes, unmerged entries, selected/index path agreement and cached whitespace. It never mutates Git. Existing selected files already in HEAD need not appear in the staged diff, but their indexed bytes must still match.
- [ ] Record the actual source/evidence changes and measured quality/speed outcomes in the root's version record before commit/push. A valid experiment release may report failed accuracy improvement; production promotion stays false unless a separate accepted gate changes it.

The future independent export acceptance and timing completion are the two explicit pending actual-evidence gates in this plan. The four scientific review suggestions are saved separately at repository path `docs/superpowers/plans/2026-10-23-ordered-contour-verifier-review.md`; the neighboring ordered-contour proposal remains proposal-only. Neither document constitutes an implemented or validated algorithm change.
