# Broader validation and deterministic match results

**Goal:** Honor the request for larger and more varied tests, and fix the duplicate-output bug exposed by the first public dataset before optimizing further.

**Architecture:** Acquire a fixed multi-object T-LESS slice from official archives without using matcher success to select frames. Separate development and unseen scenes, plus objects reserved for later generalization checks. Keep the original tiny heldout untouched. At the matcher boundary, group the existing equality key `(class,x,y,exact score)` and retain its smallest template ID, then sort by existing score/ID priority with complete class/spatial tie breakers. All local scoring and candidate search remain unchanged.

**Tech stack:** C++14 sorting and independent map-based oracles, OpenCV, frozen V10 matcher/MIPP, Python standard-library ZIP Range acquisition and SHA/CRC manifests.

**Evidence before implementation:** On all 16 tiny development images, fallback/fused semantic sets matched exactly but raw counts and some strict template sets differed. Frozen V10 repeated the *same* variant with four threads and changed counts (s5/i70: 75044→74668); one-thread repeats remained 74934. The old score/template-only comparator cannot make position-equal duplicates adjacent for `unique`. A literal shuffled-order test failed against that exact old sort/unique sequence before the fix.

- [x] Preserve all original failed development results; do not use or rerun heldout to tune the fix.
- [x] Add RED/GREEN literal tests for complete duplicate removal, smallest ID, independent class/score keys, deterministic order and idempotence over 300 shuffled orders.
- [x] Independently compare semantic sets with frozen V10/V4 and full results with a separate map oracle on LED/case1 and the 16 real development images, repeated under several thread counts and both local paths. The 25-case matrix made 475 calls; all 400 current calls were ordered-oracle equal and all 75 frozen V10/V4 calls were canonical equal.
- [x] Increase kernel stress coverage across every legal feature count and random stream patterns, reporting seeds, sample counts and exact failures rather than only known LED sizes. The independent runner passed all 8,191 legal feature counts plus 1,024 seeded random streams and 262,144 scalar patch positions.
- [x] Freeze expanded sampling before matching: 800 real test frames from 16 new scenes, 576 training views across eight objects, positive/negative instances, diverse training views and scene/object separation. Record coverage, license, hashes and acquisition bytes; no expanded matcher result has entered parameter selection.
- [x] Record the deliberate output-contract change, actual postprocessing cost, limits, independent review and source/test provenance. The remaining commit/tag/push step is performed only after the reviewed artifacts are staged and their hashes are checked.
- [ ] Resume local-result caching only after stable output and broader evaluation gates pass.

The prior local-center cache is saved as an uncommitted draft. It is not part of this correctness fix or its measurements. This is ongoing authorized iteration; no new approval checkpoint is needed.
