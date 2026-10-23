# Static Native Batch Review V1

Date: 2026-10-23. Static inspection found no remaining material defects within the supplied-graph contract in the current native header, bounded batch driver/protocol, fixture generator/auditor, and revised coordinator. This review read sources, hashes, and retained receipts; it did not compile or execute code, rerun tests, use Git, read images, or change production code. Only this report was written.

The native header preserves supplied topology, strict scene prefixes, whole-row query batching, prescribed cyclic cases, case priority, and colexicographic original-edge witness ties. Its cyclic index arithmetic avoids unsigned underflow/overflow; GMP scores are materialized before state-vector growth; zero has bit length zero; diagnostic counter increments are checked. The batch adapter validates bounded decimal tokens, positive weights, graph uniqueness/endpoints, and complete records before calling `solve`. It bounds line accumulation, checks complete serialized responses against per-record and cumulative byte budgets, emits signed directions, and flushes LF-framed records. The protocol accurately describes fallback request IDs, fatal exits, and possible physical truncation on an I/O failure.

The fixture source requires all 25,024 comparisons: 24,912 exhaustive small graphs, 100 seeded cases, and 12 additional abstract cases. Expected B, A, total, canonical case, and original-ID witness come from independent partial-injection enumeration and the original open/circular-order predicate. Public Python data carriers are shared; optimized Python matching does not provide those expected values. During audit, optimized Python supplies only the seven work-counter expectations. Counter agreement is therefore not an independent counter oracle. Full record counts and input pins prevent accepting a sampled or truncated successful audit.

The retained [RED receipt](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/coordinator_exit_red_v1/receipt.json) records two coordinator tests with one assertion failure and test-process exit 1: the injected final pin failure made the receipt fail, but the old return inside `try` had already selected coordinator exit 0. The [GREEN receipt](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/coordinator_exit_green_v1/receipt.json) records the same two tests passing, exit 0, with unchanged test SHA-256 `d72b657dc4dc7ae9fffe62dff519a00f7b0c548bdb7e3ca59be04f4cfb0f5788`. The current coordinator returns success only after `finally` completes its stability checks. These receipts establish mocked coordinator control flow, not compilation or numerical correctness; no regression tests were rerun for this review.

Resource statements have a limited scope. Generation, native execution, and audit use observed per-process peak working-set, wall, and output watchdogs; these are not an OS allocation sandbox or an aggregate RSS bound. Compiler-job committed memory includes GCC children, while the helper's observed working set is a separate measurement. Compiler-tool queries, PE-import inspection, hashing, and metadata preflight occur outside those child watchdogs, so the whole coordinator has no claimed end-to-end watchdog bound. Provenance covers declared dependencies and resolved non-system static PE imports, with the documented OS/dynamic-import limitations. No image accuracy, production readiness, or native matching performance conclusion follows.

Reviewed current-source SHA-256 pins, obtained read-only:

| Source | SHA-256 |
| --- | --- |
| `native_ordered_match.hpp` | `1236a5555c781f639be34beef95ea187d5e57de6d629df1c96805029bc8b85a3` |
| `native_ordered_match_batch_v1.cpp` | `28de3849fd1d8a1da4610424295eb7e704971ae91e64d68d8869bcf1e1af4f33` |
| `NATIVE_BATCH_PROTOCOL_V1.json` | `1012a3811f26e46f3aa94a73742feea46c54b91087fe8882d69348b39de784ba` |
| `native_oracle_fixtures_v1.py` | `8bb0c5a047a46e204507ba6e7194b41b5bb5a1777a9ba22130ab5780663f7079` |
| `run_native_oracle_checks_v1.py` | `16652e0c973b8f83fb2c793852dc2ce6a2bcdddea685d7c7269953fdcbcabf98` |
| `independent_tiny_oracle.py` | `47fd4bb9545d64e72de03d78aa917c479e6909d316eb6a40a01f2db372b16e68` |
| `weighted_ordered_match.py` | `190204b69ea3646b836ac216bc4254c2f2c7c7f11a4517b434659ddd1ea18a64` |
