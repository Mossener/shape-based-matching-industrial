# Independent numeric oracle

This is a standard-library-only implementation of the frozen V31 pool, mask,
quota and selection semantics. It does not import the matcher, sampler,
OpenCV or NumPy. Only synthetic numeric tests have been executed here.

Run from any directory:

```powershell
python D:/h/shape_based_matching-master/artifacts/rgb_stratified_features_experiment/independent/test_numeric_oracle.py
python D:/h/shape_based_matching-master/artifacts/rgb_stratified_features_experiment/independent/run_selftest.py
python D:/h/shape_based_matching-master/artifacts/rgb_stratified_features_experiment/independent/numeric_oracle.py numeric_pool.json
```

The CLI accepts one self-contained JSON pool:

- `candidate_hex`: complete little-endian `<IiiBII` records, 21 bytes each:
  ordinal, absolute x, absolute y, label, magnitude bits, opaque theta bits.
- `mask_hex`, `width`, `height`: complete uint8 mask array in row-major order.
- `candidate_sha256`, `mask_sha256`, `expected_count`: expected acquisition
  manifest pins. The integration caller must bind these to its frozen origin.
- `budget`: requested positive K. Production levels use 32 and 16.
- Optional `claims`: exact complete `P` and `B` result objects. Missing, extra
  or changed fields are rejected. Without claims the CLI recomputes results.
- Optional `resize_fixtures`: objects containing `mask_hex`, `width`, `height`,
  `expected_hex`; they check an exact floor-half nearest uint8 layer.

The module API exposes `Candidate`, `encode_candidates`, `decode_candidates`,
`validate_real_pool`, `nearest_resize`, `floorhalf_nearest`, `signed_chebyshev`,
`classify`, `sample`, `verify_claim`, `audit_numeric` and `verify_resize_fixture`.
Pure `sample` accepts unique uint32 ordinals in arbitrary input order and allows
duplicate positions. Canonical real pools additionally require dense accepted
ordinals 0..N-1 and strictly increasing unique `(y,x)` positions.

Selection results contain `status` (`ok` or `insufficient_features`), `selected`,
`selected_indices`, `trace` and `diagnostics`. Selected records include the
original six candidate fields plus `stratum` (`S` or `I`). Trace records have
`ordinal`, `stratum`, `has_distance`, `minimum_squared_distance`. Seed distance
is 0 with `has_distance=false`; subsequent distances use checked signed int64.
Diagnostics use the native sampler's named fields; the native boundary must
translate status enum 0/1 and stratum enum 0/1 into these strings.

All nonzero mask bytes count as inside. Signed Chebyshev distance uses zero
exterior: inside boundary +1, adjacent outside -1. An all-zero mask has no
finite distance to object; its outside distances are `None` and its domain is
empty. Radius4 dilation is intersected with the original two-pixel NMS canvas
margin. `S` includes accepted candidates with signed distance <=4; `I` has >4.
Nearest resize preserves raw bytes. For the actual floor-half path, both odd
and even source sizes select source indices `2*j`; general nearest resizing
uses the source/destination ratio. A contrary odd-size statement in an earlier
design draft must not be treated as a different algorithm.

Each selection step recomputes every eligible candidate's distance to every
selected candidate, with no incremental minimum cache. Magnitude is the native
observed finite float32 squared-gradient magnitude, not its square root. Theta
is preserved as opaque uint32 bits, including NaN payloads. The oracle cannot
independently reconstruct true RGB gradients or prove omitted gradient/NMS
candidates absent from the acquired pool. Payload hashes/counts prove integrity
only relative to their separately trusted manifest; replacing data and its pins
together is outside this one-pool check.

This v1 is not a full training acceptance gate. It does not read shards, banks,
images or real datasets; reconstruct crop/bank serialization; prove pool
acquisition or stage/resource counts; or audit quality/timing. Those checks
require the integration format and complete run manifest. Independent literal
gradient/NMS collector tests are owned by the collector component.

`run_selftest.py` creates a new evidence directory for each invocation. It
copies the exact sources, runs fresh GREEN tests from that isolated copy, and
runs deliberately incorrect copies for ordinal ties, scheduler, cross-stratum
distance, nearest resize, nonzero mask membership, small-pool diagnostic quotas
and unsigned distance overflow. Every mutation must produce a targeted failing
test. Receipts record interpreter identity, source/input hashes, commands,
exit codes, outputs and unchanged original source pins. No Git/index operation
is performed.

The later training-core extension is documented in `TRAINING_SCHEMA.md`.
`training_audit.py` adds independent fixed schedule and original-CSV pin checks,
two-layer byte relationships, full layer claims and attempt rows, raw dilation
sidecars, original crop arithmetic, strict serialized feature and metadata
comparison, and exact bank inventory. `run_training_selftest.py` preserves its
synthetic GREEN and real mutant RED records. The complete run summary/config
observer boundary is pinned from `NATIVE_OUTPUT_SCHEMA_V1.md` and has passed
full CLI acceptance of the actual native synthetic literal; no real training
audit has been executed by these selftests.
