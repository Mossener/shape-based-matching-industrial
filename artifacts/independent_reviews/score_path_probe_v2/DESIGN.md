# Independent Phase2 numeric audit

This sibling owns a standard-library Python implementation of the Phase2 numeric
contract. It does not import the probe, evaluator, matcher, budget preparer, or
their geometry helpers. It never builds or executes native code and never opens
image or SMD/template-bank bytes. Existing Phase1, V24, and native RED/GREEN
evidence is read-only.

The approved numeric plan is `PHASE2_INPUTS_V1.json`, SHA256
`830a77d629ad766df998aa59fbd1b6cf6bc207c900263afd04b890560eb9215a`.
Real output auditing uses only a completed immutable Phase2 freeze and root
authorization. The root supplied that authorization on 2026-10-22. The first
attempt stopped in provenance preflight before reading any Phase2 CSV because
the historical `numeric_pins` field also contains serialized bank files. Its
failure is retained. A separately authorized fresh attempt compares those 12
bank pins only as immutable declarations inherited from the pinned passed
Phase1 audit. It never opens the bank files, including for hashing.

The auditor independently checks:

1. Exact CSV schemas, job keys and target anchors; native job IDs are joined by
   identity rather than equated with the preparer's job order.
2. Complete coarse flattened spans including zero tails, whole-stream skip
   bounds, actual-feature denominators, binary32 arithmetic, strict coarse and
   inclusive fine thresholds.
3. Every local cell, first strict row-major maximum, all-zero sentinel and full
   tie mask, with deduplicated window ownership reconstructed from geometry.
4. Complete point-parent reachability, clamp order and C++ truncation, window
   joins, physical-anchor contribution sums, and all 215 original RGB controls.
5. Parent emissions and multiplicities against complete Phase1 pre occurrences;
   representative-template boxes, IoUs and full-frame NMS ranks/blockers.
6. NMS over every full-class Phase1 post record and greedy allGT/eligible GT
   assignment against preserved V22 selected records.
7. Provenance pins, complete output membership, immutable source/build closure,
   native RED/GREEN receipts and bounded stage counts. Build bytes are inert.

Feature contribution digits are numeric observations from the frozen native
probe. This audit independently recomputes their sums, score arithmetic and
downstream decisions, but cannot independently derive digits from image pixels
or serialized SMD features. The native independent scalar gates and fixed build
closure remain necessary. No recall, precision, speed or accuracy improvement
claim follows from a same-pose diagnostic.
