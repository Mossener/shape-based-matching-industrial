# V31 pure sampler v2

This explicit successor fixes the v1 distance-bound mismatch documented in
`../FAILURE_HISTORY.md`. Include this directory's `stratified_sampler.hpp`.
The component uses only the C++14 standard library; it does not inspect images,
derive strata, use OpenCV, train templates, or call the matcher.

`industrial_stratified::sample(pool, budget, Mode::pooled|balanced)` consumes an
immutable `std::vector<Candidate>` and returns original pool indices, ordered
unchanged candidate copies, selection trace and quota diagnostics. `N<=4`
returns `Status::insufficient_features` with no descriptors. Other valid inputs
select exactly `min(budget,N)` candidates.

Pooled sampling chooses greatest finite float32 magnitude then smallest ordinal
as seed. Later choices maximize minimum squared Euclidean distance to the
**entire** selected set, breaking ties by descending magnitude then ascending
ordinal. Balanced sampling initializes contour/interior quotas with
ceil(target/2) and floor(target/2), transfers capacity deficits, and alternates
contour/interior starting contour while skipping fulfilled quotas. Its distance
also includes every selected stratum.

All required distances are checked against **INT64_MAX** before multiplication
and addition. `squared_distance`, running minima and
`trace.minimum_squared_distance` use signed int64. The seed has
`has_distance=false` and stored distance 0. Only distances required by the
running-minimum O(N*K) selection are computed; this is not the independent
full-distance oracle.

Pure API fields are `ordinal` uint64, `x/y` int32, `label` uint8 in [0,7],
`magnitude_bits/theta_bits` uint32, and `stratum` enum (contour=0, interior=1).
Ordinals must be unique; distinct ordinals may have duplicate coordinates.
Magnitude bits must decode to finite float32, including negative finite values
and signed zero. Theta is an opaque payload: all uint32 bit patterns are copied
without validity checks or conversion. The canonical pool format's uint32
ordinal range is checked by its external serializer, not this API.

Diagnostics fields are `input_candidates`, `requested_budget`, `target`,
`contour_candidates`, `interior_candidates`, `empty_contour`, `empty_interior`,
`quotas_apply`, `initial_contour_quota`, `initial_interior_quota`,
`final_contour_quota`, `final_interior_quota`, `borrowed_into_contour`,
`borrowed_into_interior`, `selected_contour`, `selected_interior`.
Result fields are `status`, `diagnostics`, `selected_indices`, `selected`, `trace`.
Every trace entry holds `ordinal`, `stratum`, `has_distance`,
`minimum_squared_distance`. JSON conversion belongs to the caller; S/I labels
must map to the two native enum values.

## Literal evidence

The v2 signed-contract tests first ran against the unmodified v1 header and
failed at its erroneous acceptance of full signed-int32 axial extrema. After
the v2 fix, **19 cases / 169 assertions** passed. A separate isolated header
mutant reversing only the ordinal tie failed as expected. Source snapshots,
full stdout/stderr, compiler/executable pins and receipts remain in fresh run
directories. `SOURCE_AND_LITERAL_EVIDENCE.json` pins this successor evidence.

With a separately coordinated small literal CPU slot, use fresh output paths:

```powershell
python -B artifacts/rgb_stratified_features_experiment/sampler/v2/run_literal.py --mode signed-limit-v1-red --output artifacts/rgb_stratified_features_experiment/sampler/v2/run_signed_limit_v1_red_FRESH --cpu-slot-granted
python -B artifacts/rgb_stratified_features_experiment/sampler/v2/run_literal.py --mode green --output artifacts/rgb_stratified_features_experiment/sampler/v2/run_green_FRESH --cpu-slot-granted
python -B artifacts/rgb_stratified_features_experiment/sampler/v2/run_literal.py --mode wrong-ordinal-red --output artifacts/rgb_stratified_features_experiment/sampler/v2/run_wrong_ordinal_red_FRESH --cpu-slot-granted
```

These commands authorize no images, training, matching or benchmarking. They pin
the actual compiler executable/version, without claiming a complete transitive
toolchain closure or independent geometry verification. No quality/performance
or production-promotion claim follows from literal sampler correctness.
