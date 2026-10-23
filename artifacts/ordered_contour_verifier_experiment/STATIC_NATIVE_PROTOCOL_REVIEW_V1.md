# Static native protocol check review V1

Date: 2026-10-23. Static inspection found no material false-success or control-flow defect in the reviewed malformed-record gate under its ordinary Python invocation. The saved evidence supports 33 specific rejection cases against the already audited native batch executable. It does not establish exhaustive protocol coverage or numerical correctness by itself.

Reviewed `run_native_protocol_checks_v1.py`, the batch parser/driver and frozen protocol; parsed the saved `native_protocol_green_v1/receipt.json`, all 33 saved stdout files and all 33 guard receipts; checked current source/reference/executable pins and the saved request/stdout pins. This review did not execute Python, tests, native binaries, compilation or Git, access real-input payloads, images, banks, dataset indexes or heldout inputs, or modify existing sources/evidence. Only this document was written.

| Reviewed artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `run_native_protocol_checks_v1.py` | 6,962 | `ef299d21a401d769c4789889ba36f61eb92e7111bfec3daced0c9b55d1a33375` |
| `native_protocol_green_v1/receipt.json` | 61,718 | `3e657d35aee408425a7ad30a329217b6e42ee1bc1a3708ba2969a42822b0b2cd` |
| Referenced `native_oracle_green_v1/receipt.json` | 55,576 | `04fb612e4225bccdf5ba86b516485b2ff2d862fbf8048b93b9e621ff03b6968c` |
| Referenced `native_oracle_green_v1/build/payload/native_batch.exe` | 210,923 | `d674cdd81b44aaee8941ea0188e2fe02bdf3e8bd647fa4d1acdc27a8ff418a18` |

The current runner, reference receipt, executable, inherited guard/provenance helpers, native header, batch source and protocol match the corresponding saved input pins. All 33 request and stdout files match their receipt pins. Each embedded guard result equals its separately saved guard receipt. The native executable was hashed as an artifact; it was not executed by this review.

## Coverage and observed rejection behavior

Each fixture is a three-record input: a valid empty request with ID 1, one malformed record, and a valid suffix request with ID 99. The runner requires exit 1 with guard reason `process_exit_nonzero`, exactly two stdout lines, an initial `R1 1 0 ...` response, and a final three-token `E1` with the specific expected error code. This prevents resource ceilings, an internal exit-2 failure, a missing prefix response, a response to the invalid request, or a later suffix response from counting as detection.

The 33 fixtures exercise these categories:

- Negative, overflowing and overlong request IDs; negative template/sample/unused-pixel IDs and overflowing sample IDs.
- Invalid exact boolean forms and excessive template/scene/pixel/edge counts.
- Zero, signed, fractional and overlong weight tokens.
- Duplicate samples, unused scene chains, unused scene pixels and edges; invalid unused-scene flags; missing edge endpoints and impossible edge capacity.
- Missing/trailing tokens, wrong version, blank/separator-only lines, NUL/non-ASCII bytes and an overlong line.

The saved receipt has `passed=true`, 33 completed detections, and no exception or stability exception. All 33 guards record exit 1 and `process_exit_nonzero`. Every saved stdout has exactly the prefix response and expected final error, and all stderr files are empty. The saved errors use ID 77 after successful parsing of the malformed record's request ID and fallback ID 0 for request-ID/version/empty/character/line errors, consistent with the protocol.

The maximum saved per-invocation wall observation is approximately 0.063 s and the maximum observed peak working set is 6,361,088 bytes. Total saved stdout across the cases is 1,737 bytes. These values describe tiny rejection processes, including startup and protocol I/O; they are not solver performance measurements or a complete coordinator budget.

## Control flow and resource scope

The runner does not rebuild the executable. It first requires a passing reference receipt with 25,024 audit comparisons, verifies current native sources against that reference's snapshots, and checks the executable and inherited runtime pins. Each native invocation is the direct child of `run_guarded()`, with limits of 5 s, 512 MiB observed peak working set and 1 MiB designated output. The inherited guard's approximately 50 ms process/directory polling is observed enforcement, not an OS allocation sandbox or aggregate process-tree RSS cap.

Assertions and process execution occur outside any assertion-catching block that could classify an arbitrary runtime exception as detection. A case is appended only after the expected normal rejection observations. An exception during the loop is retained and re-raised, so it cannot produce successful coordinator exit. Final source/executable/runtime pin failures set `passed=false`, and the final return is evaluated after `finally`, preserving nonzero exit for a stability failure. The runner's preflight and acceptance checks use Python `assert`, so its gate requires an ordinary invocation with assertions enabled.

## Limits on the result

The saved observations are narrower than complete validation of every protocol field or boundary:

1. The runner accepts either error ID `0` or `77` for every fixture instead of asserting the exact expected ID per fixture. It checks only the prefix of the valid `R1` line, not all its numerical fields. The saved outputs have the correct IDs, but these loose assertions would not catch every ID-association or valid-prefix serialization regression. Independent numerical/case/witness comparisons belong to the separate 25,024-record oracle gate.
2. This suite does not test the 100,001st-request rejection; exact successful token/count/line/file boundaries; empty-file or final-without-LF behavior; every spelling of malformed numeric input; per-response/cumulative-output or whole-file stress; or allocation, I/O, solver disagreement and work-counter-overflow failure injection. These omissions do not contradict the 33 specific detections. `TOTAL_EDGE_LIMIT` is a defensive redundant check under the current maximum 16 scenes × 64 edges, so no accepted lower-level counts can exceed 1,024 total edges.
3. The source/protocol's original pre-execution statement remains historical. The later receipt establishes this bounded malformed-input run; it does not retroactively change the frozen protocol or establish image provenance, real-data quality, production integration or native speed.

No real-input gate or production promotion follows from this review.
