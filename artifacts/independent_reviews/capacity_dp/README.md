# Independent six-object capacity audit

`run_six_objects_dp_v2/results.json` passed with exit 0. It independently checks all 2,400 object/frame pairs from the frozen 400-frame development set for objects 1, 2, 5, 8, 12 and 17. It imports neither the original diagnosis nor evaluator, opens no image, and makes no matcher call.

The independent algorithm enumerates reachable GT subsets with a bitmask dynamic program. It differs from the original augmenting-path implementation. The maximum target count observed was 2; a hard limit of 20 prevents an unbounded state space. Duplicate adjacency masks retain bounded multiplicity, so Hall bottlenecks are distinct from GTs without any overlapping raw box.

| Quantity | Independent result |
| --- | ---: |
| Raw / selected detections | 457,376 / 42,313 |
| GT / TP / FP / FN | 400 / 215 / 42,098 / 185 |
| Raw / selected assignment capacity | 238 / 215 |
| FN from raw capacity / selection / assignment | 162 / 23 / 0 |
| GT without an overlapping raw candidate | 162 |
| Negative object/frame pairs | 2,050 |
| FP: target IoU >= .5 | 0 |
| FP: other object IoU >= .5 | 1,225 |
| FP: target IoU >= .1 | 257 |
| FP: other object IoU >= .1 | 6,353 |
| FP: neither overlap >= .1 | 34,263 |

Every per-frame, per-object, per-scene and global value agrees with the original diagnosis. The independently generated `per_frame.csv` is byte-identical to the root result: SHA-256 `c5070812a3e0d5722d11f83d0da5b606e978183274007a2479b6449715240f8e`. `effective_tp_ids.csv` contains the 215 independently reassigned actual TP GT IDs; SHA-256 `373b75dc94d22e8d818bf0d85fe1e03258fc967ad9b298706f58477f91c87005`.

Provenance checks include frozen source/input pins, all six metadata banks, preservation manifests, complete tar SHA/size and all 1,600 numeric members per object. Only 400 fallback raw frames per object enter the capacity calculation. Each raw box is reconstructed from its template metadata and original image origin; training image, angle and scale are checked. Every selected record is bound to its full-precision metrics JSON record, then its class, template, binary32 score and box identity must be a multiset subset of raw. Labels and GT IDs are independently reassigned in preserved selected order. Input and auditor hashes are checked again after calculation.

`run_six_objects_dp_v1/` preserves the first failed audit. Its initial assumption that selected CSV retained raw score precision was false: CSV uses six significant digits, while raw CSV and metrics JSON retain sufficient precision for binary32. The failing example and original auditor source/protocol are retained. The original source was reconstructed and verified against its previously saved SHA; the original protocol was reconstructed byte-identically against its frozen SHA. The correction obtains complete score bits from metrics JSON and checks the exact CSV `.6g` projection, preserving the full raw identity check. It does not accept rounded-score equality as proof of raw identity.

Synthetic evidence: the initial 7 DP literals, 4 invalid graphs and IoU literals; 5 higher-level core oracles; 11 rejecting semantic fixtures; corrupted gzip CRC rejection; and `precision_red/` then `precision_green/`. The precision test rejects distinct binary32 scores that collapse to the same six-digit CSV value, wrong displayed score, wrong template and wrong labels. `fixture_validation_precision_v2/` reruns the existing core fixtures against the corrected auditor.

These are optimistic bounding-box assignment capacities. They do not prove candidates can coexist through NMS, physical contour identity, a detector improvement, or industrial generalization. No heldout frame or reserved object was processed. The analysis covers allGT; eligible labels are cross-checked between CSV and metrics but are not independently reassigned by this audit.

Auditor SHA-256: `2fb0eac39ba64faf2785ca702ac07012657542f7a9943a84d5a6173427d8cd8a`.

Protocol SHA-256: `851a9d08deb3a9b64c3d7bb54288023461e90e6c144e02616dd98e9b7e6d8826`.
