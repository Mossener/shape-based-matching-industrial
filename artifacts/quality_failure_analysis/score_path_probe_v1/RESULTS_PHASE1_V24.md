# V24: exact replay before and after cross-template consolidation

Status: native replay, independent complete archive audit and root checks
passed. This diagnostic changes no production algorithm,
threshold, training template or default. It is not an accuracy improvement or
a performance benchmark.

The fixed scope contains every 215 common-padding RGB true-positive identity
from V22: 67 identities lost by the binary recipe and 148 retained controls.
They occupy 213 object/frame pairs and 175 development images across objects
1, 2, 5, 8, 12 and 17. Both arms were replayed once per object/frame, for 426
original class searches. Held-out scenes, reserved objects and private magnet
images are outside this run.

## Exactness gates

The standalone translation unit directly includes unchanged V11 core code.
It rebuilds the original two-level response memories and calls the original
class search before consolidation. Every emitted fine score is checked with
a separate per-feature linear-memory sum and exact binary32 normalization.
The original consolidation and metadata conversion then reproduce the complete
ordered saved V22 raw list, including all fields and score bits.

An intentional scalar error compiled successfully and failed its native
synthetic test with the expected mismatch. The same-source GREEN build passed
256 native local-map cells, exact score normalization, the strict/inclusive
threshold boundary and the synthetic cross-template geometry-loss example.
The first build's Windows-header ordering failure is retained separately.
The root independently rehashed 560 distinct build closure pins and checked
both synthetic receipts without executing a native process or opening images.

| Arm | Before consolidation | After consolidation | Cross-template groups | Repeated occurrences of the same template/key |
| --- | ---: | ---: | ---: | ---: |
| RGB | 330,473 | 71,178 | 1,861 | 257,230 |
| Binary empty mask | 981,533 | 156,638 | 39,720 | 748,588 |
| Total | 1,312,006 | 227,816 | 41,581 | 1,005,818 |

All 1,312,006 emitted fine score bit patterns passed the scalar gate. All
227,816 converted post-consolidation rows matched the corresponding V22 raw
reference. These totals cover the declared subset, not the full 400-frame
evaluation and not new full-dataset accuracy counts.

## What consolidation explains

For each fixed GT identity, candidate support means at least one box with
IoU >= 0.5. It does not mean the box survives NMS or receives that GT later.

| Arm | Identities with support before | Identities with support after | Complete support losses |
| --- | ---: | ---: | ---: |
| RGB | 215 | 215 | 0 |
| Binary empty mask | 158 | 158 | 0 |

Thus, in this fixed subset, cross-template consolidation does not explain any
of the 57 binary identities without a qualifying saved raw box. They already
lack such a box before consolidation. The other 10 lost RGB identities retain
raw support and were previously traced to NMS. All 67 agree with the existing
V23 per-GT diagnosis.

Consolidation still changes geometry: the best available GT IoU decreases for
4 RGB and 11 binary identities, with maximum decreases 0.0253031 and 0.0395527.
The finding is therefore narrowly about complete loss of candidate support;
it does not establish that consolidation preserves every useful hypothesis or
is harmless on every image.

## Evidence and limits

The immutable run is `probe_phase1_v2/`; its stage freeze has SHA256
`f2be7500b13fbe1cad2bb9bc8d223b7bbf37af71919441f5b2bc2d1251e0d5ed`.
It records 213 grayscale decode operations over the 175 permitted image files,
350 before/after image hashes, exact closure checks and every numeric output.
Native numeric accounting is 23,046,003 bytes; the complete native file set is
23,046,658 bytes after adding its summary and ignore file. Peak working set is
63,762,432 bytes. The 27.563-second watchdog duration is a resource observation
including diagnostic work, not a matcher-speed claim.

`ROOT_SYNTHETIC_RECEIPT_20261022.json` and
`ROOT_PHASE1_TOTALS_20261022.json` record the separate root checks. The latter
verifies all per-arm counts and all 430 support rows against the fixed plan and
prior GT rows. The separate independent standard-library auditor reconstructed
all 426 pre/post/reference triples, 78,372 discarded-template mapping rows,
430 GT support rows, metadata boxes, ordered fields, binary32 score bits and
summary totals. All 17 synthetic numeric/provenance tests passed; the root
freshly reran them. The audit also checked 1,461 distinct pinned files,
including 560 inert build/source/tool/runtime closure members, against their bytes.
Its result is
`../../independent_reviews/score_path_probe_v1/run_phase1_audit_20261022_v1/result.json`,
SHA256 `67ff1b3967e762984bf9a35e358fa2a1a9d039124de88b7fc53c98eb18eacc06`.
The numeric auditor can reconstruct consolidation, representative mappings,
box conversion and IoUs from saved output, but cannot independently reconstruct
the image-derived response values. The native scalar equality gate is recorded
separately and must not be presented as an independent pixel-level audit.

Next, a separate Phase 2 diagnostic will test the existing RGB and binary
templates at the same physical placements and trace every reachable coarse
parent and its local winner. Its source, budget and completion gate are separate;
Phase 1 does not run or authorize a threshold sweep or hybrid descriptor change.
