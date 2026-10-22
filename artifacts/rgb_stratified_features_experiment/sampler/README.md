# Pure V31 farthest-first sampler

`stratified_sampler.hpp` is a C++14 standard-library component. It does not
collect gradient candidates, inspect masks, or call OpenCV/the matcher. The
caller supplies one immutable candidate pool and the stratum of each candidate.
The future independent geometry oracle must validate that membership.

`industrial_stratified::sample(pool, budget, Mode::pooled|balanced)` returns:

- `Status::insufficient_features` with no selected features for pools of size
  zero through four; validation still rejects invalid input.
- Selected original pool indices, ordered byte-preserving candidate copies,
  per-step ordinal/stratum/minimum-distance records, and all quota diagnostics.
- `target=min(budget,N)` with balanced initial quotas `ceil(target/2)` and
  `floor(target/2)`. Capacity deficits transfer to the other stratum before
  alternating S/I requests. Requests whose quota is full are skipped.

The first choice uses greatest finite float32 magnitude then smallest ordinal.
Further choices maximize minimum squared distance to **all** selected features,
then use the same magnitude/ordinal tie rule. Duplicate coordinates are distinct
candidates when their ordinals differ; their zero distance remains valid.
Candidate ordinals must be unique, labels must be in `[0,7]`, mode/stratum must
be valid and budget must be positive. Theta bits are an opaque payload and are
copied without floating conversion. Magnitude bits are decoded for finite
comparison and preserved in output, including signed zero.

Coordinate differences use signed int64 and nonnegative squared distances use
checked uint64. A full signed-int32 axial distance is representable; a diagonal
sum exceeding uint64 is rejected rather than wrapping. Only distances required
by farthest-first selection are computed. This is an O(N*K) running-minimum
implementation, not the independent full-distance oracle.

## Literal evidence

Tests were written before the header. The first isolated compile failed for the
missing header as intended. The green build then passed **16 cases and 153
assertions**, covering exact pooled/balanced order, cross-stratum distance,
target-based quotas, both shortages/empty strata, 16/32/over-budget counts,
float32 ties, duplicate positions, opaque bits, input immutability, translation,
invalid inputs and checked int32-distance arithmetic. A separate isolated
header mutant reversed only the ordinal tie and failed the literal oracle as
intended (compile exit 0, execution exit 1).

Fresh output directories preserve every build/run stdout, stderr, source
snapshot, compiler/executable hash and receipt:

```powershell
python -B artifacts/rgb_stratified_features_experiment/sampler/run_literal.py --mode missing-header-red --output artifacts/rgb_stratified_features_experiment/sampler/run_missing_header_red_FRESH --cpu-slot-granted
python -B artifacts/rgb_stratified_features_experiment/sampler/run_literal.py --mode green --output artifacts/rgb_stratified_features_experiment/sampler/run_green_FRESH --cpu-slot-granted
python -B artifacts/rgb_stratified_features_experiment/sampler/run_literal.py --mode wrong-ordinal-red --output artifacts/rgb_stratified_features_experiment/sampler/run_wrong_ordinal_red_FRESH --cpu-slot-granted
```

The CPU flag records root coordination for these small literal executables.
It grants no training, image decoding, matcher call or performance benchmark.
The captured compiler pin is the actual g++ executable, not a claim that the
entire compiler/runtime dependency closure was independently reproduced.
