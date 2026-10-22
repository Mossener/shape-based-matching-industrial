# Shared V31 training bridge

`shared_training.hpp` links the unchanged frozen V11 gradient pyramid to the
candidate collector and signed-int64 sampler v2. Link
`control_v11/line2Dup.cpp` as its own translation unit and include `line2Dup.h`
through that snapshot's include path. The integration header never includes the
core `.cpp`. The small literal adapter includes `candidate_collector.cpp`, so
the captured build has exactly two native translation units: core and adapter.

The production entry point is:

```cpp
namespace rgb_stratified::integration {
using CandidatePool = std::vector<industrial_stratified::Candidate>;
using LayerHook = std::function<void(
    std::uint64_t pose_id, unsigned level,
    const collector::Result& original,
    const CandidatePool& immutable_pool,
    const industrial_stratified::Result& pooled,
    const industrial_stratified::Result& balanced)>;

PoseResult train_pose(const cv::Mat& source, const cv::Mat& official_mask,
                      std::uint64_t pose_id, const LayerHook& hook = {});
}
```

It constructs one `ColorGradientPyramid` with weak20/strong40/K32, collects L0
once, uses the identical immutable sampler vector for P then B, and invokes the
hook before releasing the full pool. It then calls the original `pyrDown` once
and repeats for L1/K16. An insufficient L0 still collects, samples and records
L1. P/B status disagreement throws. Actual nearest-resized uint8 masks remain
inside the original pyramid; integration does not resize or fold mask bytes.

The hook is synchronous and its references expire at the end of that layer.
Serialize full masks/candidates and complete sampler results there. Do not keep
references or retain all pools. `PoseResult` contains only small selections,
template pyramids and counts, with no full candidate/mask pools:

- `pose_id`, `layers[0..1].pooled/balanced`: complete sampler `Result` values.
- `arms[0=P,1=B]`: `success`, two `uncropped` templates, `cropped` templates
  only when both layers succeed, and the shared full-resolution `crop` rectangle.
- `counts.gradient_pyramids`, `pyramid_downs`, `collector_calls[level]`,
  `sampler_calls[level][arm]`: actual invocation counts in the bridge.

Uncropped dimensions are explicitly -1, origins0, and levels0/1. Feature order,
labels and opaque theta bits survive conversion. Each successful arm copies its
own uncropped pyramid, then applies the original cross-layer crop body unchanged.
The runner checks the complete copied function text against the frozen source
in addition to independent literal crop coordinates.

`SharedDetector` derives from the unchanged core detector with fixed
32/{4,8}/20/40 settings. `inject(class_id, arm)` returns -1 for a failed arm
without creating a class or consuming an ID. A successful arm must have two
nonempty cropped layers with levels0/1; insertion returns the next dense ID
within that class. In-memory theta is preserved. The native bank serializer
still follows the inherited x/y/label format; complete theta evidence belongs
in the hook's sampler result output.

`train_pose_with(source, mask, id, collect, sample, hook)` is an explicit
dependency seam for literal fixtures. `CollectorFunction` takes the four real
magnitude/quantized-angle/theta/mask Mats, and `SamplerFunction` takes the
immutable pool, budget and mode. Production `train_pose` always binds the real
collector and sampler v2.

## Verification evidence

The header was absent for the preserved initial compile RED. Current source
then passed **5 cases / 191 assertions**, using three numeric synthetic pose
calls and no image decoding, dataset access, matcher calls, or timing work.
Coverage includes failed-L0 continuation, collector/sampler call counts,
P/B/hook pool identity and digest, actual odd floor-half mask bytes, exact
feature/label/theta order, independent cross-layer crop coordinates, successful
two-layer-only dense IDs, and one actual frozen-gradient/collector numeric toy.

The actual toy is a fixed 256x256 three-channel checkerboard with 32-pixel
blocks. Its complete observed pool sizes were L0=924 and L1=350. These are
fixture observations, not tuned thresholds or recognition results. An earlier
8-pixel-block fixture failed at L1 due to downsampling/blur; its original
failure and diagnostic RED remain recorded in `FAILURE_HISTORY.md`.

With a separately coordinated small native CPU slot, run GREEN into a fresh
directory:

```powershell
python -B artifacts/rgb_stratified_features_experiment/integration/run_tests.py --mode green --output artifacts/rgb_stratified_features_experiment/integration/run_green_FRESH --cpu-slot-granted
```

The historical small-checker diagnostic mode expects its preserved pre-repair
test source; replay it from that run's source snapshot rather than treating the
current larger checker as an expected failure. Mutation options are available
for future bounded runs but were not executed in this integration stage.

Receipts include precompile and actual GCC dependency files, exact source
snapshots, declared compiler tools, static non-system PE import closure, link
library, executable hash, actual loaded-module observations and complete stdout/
stderr. OS/API-set imports are named rather than fully attested. Inherited
MIPP SSE macro-redefinition warnings are preserved; frozen files were unchanged.
These local receipts are not cryptographic execution attestation and do not
establish real-data training, industrial accuracy, speed, or production promotion.
