# C0 payload byte inventory results V2

Date: 2026-10-23. The actual V2 hash run completed the exact C0 whitelist: **6,094 unique files, 333,625,244 bytes**. All 6,082 inherited declared pins matched their observed path, byte count and SHA-256; the remaining 12 config/provenance files received explicitly new observed pins. This establishes a byte inventory. It does not freeze a real pixel adapter or establish pixel, candidate, GT, quality or speed correctness.

This report was prepared by static source, metadata, receipt and log inspection and hashing of those artifacts. The reviewer did not execute Python, tests, native code, a build or Git, and did not open image, raw, bank, GT or dataset-index payloads. The payload reads below are the coordinator's retained actual run, not a reviewer rerun. No historical source, test, receipt, V33 selection, production file or retained V31 evidence was changed for this report.

## Actual inventory and pins

Paths in this report are relative to `artifacts/ordered_contour_verifier_experiment/` unless stated otherwise.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `c0_inventory_hash_v2_payload/inventory.json` | 6,349,773 | `59edd80d4c6083286d14044326a665daa41ce999ef11414fb5c9da9cb9ab2ec4` |
| `c0_inventory_hash_v2/receipt.json` | 3,147 | `b896ada0d33663bb86e0ec9c2dac83442eb88df8cf66d71e60be9f45ecfcdcae` |
| `prepare_c0_payload_inventory_v2.py` | 18,854 | `930d4b596ae51ba12efde71f405b2e39f9317494e81bc14c80e59808b216647a` |
| `INPUT_INVENTORY_DECISIONS_V2.json` | 3,049 | `0b73e4ed1be1da1eed226aab74afb8a6b16a2b1318a595494b9ad4755b37f8a3` |
| `C0_INPUT_PLAN_V1.json` | 2,215,868 | `62610add5d6e40c219a3f9929edb1aa2f87c831d8a678ec4848cf282eb8236c0` |
| `run_c0_inventory_checks_v2.py` | 4,960 | `5b9d6528478c69b9a786f57efe041cb715a4fb2ba7cec516f5e845c4242c146c` |

The inventory retains the format identifier `c0_payload_inventory_v1`; it was produced by the pinned V2 source. Its status is `byte_inventory_only`, mode is `hash`, and `payload_hashing_complete` is true. The decisions file's historical `source_prepared_unexecuted` status describes preparation; actual execution is established by the later receipts.

| Whitelisted role | Files | Observed bytes |
| --- | ---: | ---: |
| Training RGB source | 432 | 21,530,422 |
| Training official mask | 432 | 299,259 |
| Development RGB source | 400 | 287,681,675 |
| Original own bank | 6 | 4,938,462 |
| Original own metadata | 6 | 7,062,595 |
| Original own attempts | 6 | 1,697,280 |
| Training config, new pins | 6 | 8,488 |
| Training provenance, new pins | 6 | 30,916 |
| Candidate raw gzip | 2,400 | 8,931,045 |
| Candidate manifest | 2,400 | 1,445,102 |
| **Total** | **6,094** | **333,625,244** |

Inherited declared files account for 333,585,840 bytes; the 12 new observations account for 39,404 bytes. The new observations are not inherited accepted pins. Static fieldwise comparison found zero declared/observed mismatches, zero duplicate paths, and zero observed-size/preflight-size or role-cap violations. All 6,094 entries have an observed pin. JSON object property order was not used for pin equality.

The exact set covers objects 1, 2, 5, 8, 12 and 17, their 432 selected training views, and 400 selected development frames in scenes 1, 4, 6, 7, 8, 10, 12 and 13. The 2,400 raw/manifest pairs include declared zero-candidate combinations. No heldout scenes, objects 25/29, other matcher arms, treatment banks or pooled banks enter this set.

## Preserved V1 failure and actual V2 repair

The two older nine-test whitelist successes belong to different V1 source bytes. They are retained evidence of whitelist construction, not evidence that the final V2 source successfully opened or hashed payloads.

| Actual retained run | Source SHA-256 | Actual result |
| --- | --- | --- |
| `c0_inventory_whitelist_green_v1` | `3ef11fdcf64cf647c61225a0ebfc5216b0c46a2399fcd1aa11ee47ab0a1480c9` (18,187 B) | 9 tests passed; exit 0 |
| `c0_inventory_whitelist_green_v2` | `69e922321c68781f48767d946a8a5db738c13642467558457992c914548b6ddb` (18,606 B) | 9 tests passed; exit 0 |
| `c0_inventory_estimate_v1` | `69e922321c68781f48767d946a8a5db738c13642467558457992c914548b6ddb` | **Failed**; exit 1, `process_exit_nonzero`, `ValueError: Opened file changed` |

The V1 estimate failed in `main -> read_json(PLAN_PATH) -> inspect_file`, at the first opened-handle `fstat` comparison. That comparison precedes the first `stream.read`: no plan content and no real input payload content had been read. Its observed wall was 0.125 s and peak process working set was 19,320,832 B. Source stability/archive equality remained true. This actual failure is not converted into a success by later results.

The diagnosed incompatibility was the Windows interpreter's different meanings of path-stat and handle-stat `st_ctime_ns`: the path value represented birth time while the handle value represented modification time. Device, inode, size, modification time and explicit birth time agreed. The V2 successor initially retained the faulty stamp, allowing an actual regression test to reproduce the failure before the fix.

The frozen `test_c0_inventory_windows_stat_v2.py` is 3,518 B, SHA-256 `32a6597b1915dfbf5fcacbc59ca920abfa1cff7f5d4740eed8d8a636624a4e4b`. Its three temporary-file tests require unchanged bytes to hash when mtime differs from birth time, and reject replacement or size change after preflight.

| Actual retained run | Source | Tests and process result | Wall / peak working set |
| --- | --- | --- | --- |
| `c0_inventory_windows_red_v2` | 18,606 B, `2f2ba2b25fd59a4a8612977de0dea949cffc119dc7f9a3e1118d6f42cb82a56e` | 3 run, 1 assertion failure, 0 errors; exit 1 | 0.172 s / 23,433,216 B |
| `c0_inventory_windows_green_v2` | Final V2, `930d4b596ae51ba12efde71f405b2e39f9317494e81bc14c80e59808b216647a` | Same frozen 3 tests passed; exit 0 | 0.172 s / 24,363,008 B |

The RED error explicitly states `Unchanged literal regular file was rejected: Opened file changed`. Its top-level receipt `passed=true` means the expected failing RED gate was satisfied; its child guard still records `passed=false`, exit 1. The repair requires explicit `st_birthtime_ns` and compares `(dev, ino, size, mtime_ns, birthtime_ns)` consistently. It retains the preflight, opened-handle, post-read handle and after-path checks and all byte caps. V1 sources and RED evidence remain separate and unchanged.

## Final-source checks and resource observations

| Actual final-source run | Result | Wall | Peak process working set |
| --- | --- | ---: | ---: |
| `c0_inventory_whitelist_green_v3` | 9 tests, 0 skipped/failures/errors; exit 0 | 1.953 s | 32,653,312 B |
| `c0_inventory_estimate_v2` | Exact 6,094 files / 333,625,244 B; exit 0 | 11.188 s | 70,168,576 B |
| `c0_inventory_hash_v2` | All 6,094 observed pins complete; exit 0 | 18.234 s | 80,683,008 B |

The directory suffix `whitelist_green_v3` names a run, not a third preparer version: it imports the final V2 source. `test_c0_inventory_whitelist_v2.py` (2,421 B, SHA-256 `f35750b60311171b155141e62fa0a66598c227a8da2f9bfc23a39ac7301dde7d`) changes only the module import from the V1 tests. The nine tests cover full counts/bytes and rejection of missing zero combinations, foreign raw arms/banks, heldout identities, duplicate training inputs, invalid hashes and V30 padding. They construct the whitelist without reading real payloads; the subsequent hash receipt supplies the byte-read evidence.

The dedicated whitelist runner is 6,259 B, SHA-256 `fc97acfa2e34ad3868cba940c733e5f954bdaf1b1923eedf2098798f56e2d6d2`. Its `-E -B` child explicitly records actual flags `optimize=0, ignore_environment=1, debug=true` and requires exactly nine tests with no skips. The hash inventory independently records the same actual interpreter flags. Both tests and preparer execute from the workspace experiment directory using `F:/mysys2/ucrt64/bin/python.exe`; retained source archives are equality/stability snapshots, not the executed working directory. The whitelist receipt explicitly states `archive_is_executed_snapshot=false`; the hash receipt records `sources_stable=true` and `source_archive_equal=true`.

The policy limits are 512 MiB total whitelisted input, 64 MiB generic single-file input, 1 MiB config, 16 MiB provenance, 1 MiB streaming hash chunks and 16 MiB output. The hash run's pre-hash estimate records 268,699,762,688 B free disk against 83,886,080 B required headroom. Its external child guard records a 180 s wall limit, 512 MiB process working-set threshold, 16 MiB output threshold, 348 samples, exit 0 and no stop reason; observed execution output was 6,355,977 B. The whitelist child instead uses a 60 s wall limit with the same working-set/output thresholds.

These watchdog measurements apply to the recorded process and polling interval. They are observations with termination after detection, not an OS allocation barrier, aggregate coordinator RSS bound, filesystem lock, or execution attestation. Path/stamp checks and source pins reduce accidental change risk but do not establish an adversarially immutable filesystem. The 18.234 s hash wall includes startup and inventory writing and is not an algorithm or matching benchmark.

## Remaining boundary and shortest route to real scoring

The inventory records zero image decodes, image-header parses, decompressions, dataset-index opens, native calls, gradients and edge scores. `real_pixel_input_freeze`, `real_pixel_execution`, `quality_claim`, `performance_claim` and `production_promotion` remain false. Raw rows, bank fields, attempts, masks, image dimensions, transforms and semantic candidate identities have not been validated by byte hashing. All frozen GT/result/metrics payloads remain unopened declarations; aggregate metrics JSON cannot supply complete per-frame GT or selected-detection identities.

The existing pixel contract and newly completed supplied-label native-edge synthetic checks are sufficient to start implementation. No further general metadata inventory is needed. The shortest remaining route is:

1. Finish the existing native candidate adapter and a bounded real C0 replay pilot. Replay recorded attempts in order, check success/failure status and both saved native layers/features/IDs, and derive template origins from the two-layer feature crop. Decode the RGB source using the specified grayscale mode, retain the exact crop/canvas/decode/interpolation/border settings, six affine-double bit patterns, and hashes of full warped image/mask row bytes. Derive the prescribed eligible orientation grids and connect them directly to the accepted thinning/chain/ownership/cell-weight evidence. The pilot checks adapter correctness and output/resource sizing; it does not support a quality claim.
2. Scale the same guarded adapter to all 20,736 attempts (18,199 successes and 2,537 failures), 36,398 saved layers and all 400 development frames. Use the actual C0 padded scene grid **848 x 848**, padding LTRB `(64,64,64,244)`, rather than the historical V30 comparison grid. Bind every attempt, template, grid and candidate to the accepted input identities and byte pins. The native recipe replay itself is not an independent raw-pixel gradient oracle; independently verify derived grids/evidence and complete scoring outputs under the established contract.
3. Score all 457,279 declared raw candidates across 2,400 object/frame combinations, retaining all 390 zero-candidate combinations. Preserve `canvas point - template origin -> match-relative padded point -> original point` with int64 checks, the full denominator, radius-two square search, circular unsigned-eight orientation distance at most one, and rejection when the query center lies outside the padded grid. Apply the exact gate `20*N >= 13*D`, record complete candidate identities/numerators/denominators/statuses, and audit against the independent reference rather than summary counters alone.
4. Bind the scores to NMS and GT using the three already declared CSV sources `ground_truth.csv`, `per_frame_metrics.csv`, and `selected_detections.csv` (7,983,802 B total) through a narrow C0-only reader. Verify full-file pins and exact schemas, then process only the six objects and selected frames; retain explicit negative and zero rows. Reconstruct stable ordering, NMS, GT assignment, selected identities and per-frame counts using the numerical contract. This requires the later explicit GT-source acceptance stated by the current inventory; it does not require opening the dataset index or replaying other arms. It validates the retained GT projection, not completeness against original annotations.

The next deliverable should therefore contain executable pixel-to-evidence/candidate adapters and bounded actual replay results. Existing synthetic chain correctness, byte pins and source reviews should be reused rather than expanded into another metadata-only checkpoint. Production promotion, heldout access and end-to-end accuracy/speed claims remain separate later decisions.
