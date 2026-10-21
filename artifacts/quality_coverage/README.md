# Isolated dense oriented-edge coverage experiment

This folder contains standard-library C++14 correctness helpers and an isolated
OpenCV adapter experiment. It does not change the matcher core or the frozen
public evaluator. The fixed recipe has now been evaluated on tiny development
(16 frames) and expanded object-1 development (400 frames), reusing complete
actual-85 raw candidates. The measured false-positive reductions are insufficient
to promote a default gate; the strictest policy also loses recall. No paired
latency improvement has been measured.

See `DEVELOPMENT_RESULTS_20261021.md` for all three policies, TP retention,
negative-image failures, costs, provenance and the promotion decision. The
independent reviewer preserves a separate scalar/NMS/metric audit. Heldout
images and reserved objects remain unopened.

The predeclared recipe is in `COVERAGE_PROTOCOL.json`; the motivation, limitations
and independent integration review are in `DESIGN.md`, `PADDING_POLICY.md` and
`INTEGRATION_REVIEW.md`. No heldout image or reserved object is used here.

## Synthetic correctness evidence

`run_20261021_helper_final/validation.json` is the primary helper evidence:

- 2,317,363 assertions; 1,731,224 support queries compared with a direct per-point
  neighborhood oracle; 609 complete coverage evaluations compared with a scalar
  oracle across five fixed seeds.
- 3,006 retained-output field comparisons spanning full-versus-lazy NMS and an
  independent tuple/index-sort and interval-geometry NMS oracle. The JSON
  counter `full_lazy_cases` counts both categories, including literal, random,
  and mutation-oriented scenarios.
- Dynamic sets of 5, 32, 1214 and 8191 points, negative offsets, nonzero template
  origins/padding, odd and one-pixel image dimensions, extreme integer coordinates,
  0/7 orientation wrap, exact radius boundaries, empty/untrusted validation,
  out-of-bounds denominators and unequal cell densities are included.
- Seven RED cases compile successfully and fail semantically as expected: the
  original missing-functionality stub and six independent mutations removing
  orientation wrap, reducing radius, replacing balanced score, dropping an OOB
  denominator, changing the strict NMS boundary, and inverting lazy rejection.

Each case preserves its source, compiler output, test output and executable hash.
The executable itself is generated and Git-ignored. Compiler/source hashes and
source stability are recorded in the JSON. GCC15.1 used `-std=c++14 -O2 -Wall
-Wextra -Werror`, with no diagnostics. The first `run_20261021_helper` has correct
test outcomes but a runner variable-shadowing defect in case-name metadata;
the final run fixes that defect and is the reportable evidence.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File artifacts/quality_coverage/run_tests.ps1 -OutputDirectory artifacts/quality_coverage/my_new_helper_run
```

## Helper contracts

`build_support` accepts a row-major one-label orientation field: labels0..7 and
255 for no edge. Core bit masks must first be decoded explicitly. Default radius2
and adjacent modulo8 orientation bins produce eight binary maps; separable
rolling counts take O(8*image_pixels) work. Eight byte maps plus two byte scratch
fields are live during construction; the two scratch fields are then released.

`prepare_template` takes integer warped-canvas points and the actual L0 template
origin. It subtracts that origin once and keeps dynamic 64-bit relative offsets.
The fixed4x4 grid divides the complete inclusive integer coordinate span, using
`max-min+1`. `evaluate` adds the padded core match coordinate and reports balanced
occupied-cell coverage, point coverage, in-bounds fraction, and every cell count.
An OOB center is unsupported and stays in the denominator. Empty or untrusted
sets are unverified pass-through; a blank scene is verified and has zero support.
The helper is L0-only and accepts no pyramid-level assumption or point-count cap.

`coverage_nms.hpp` demonstrates candidate-independent full/lazy verification with
the frozen public adapter's ordering and box rules. Lazy skipped rows are marked
as suppressed, never fabricated as verified or unverified. The full and lazy
audit streams intentionally differ; retained original candidate fields and
coverage fields must agree. Callback purity is a caller requirement.

## Adapter status and limits

`coverage_eval.cpp` includes the frozen public evaluator under
a renamed entry point so dataset parsing, NMS boxes and metric rules remain
shared. Its build/run scripts must verify the public build/source hashes and all
raw/bank/config/dataset/image provenance before image evaluation. Synthetic
adapter self-tests and the two development runs have completed; standalone
helper tests alone do not prove training reconstruction, OpenCV quantization or
real-world detector quality. The image runs require a byte-for-byte comparison
of all serialized template fields after reconstruction and preserve complete
candidate results for an independent review.

The protocol fixes padded-scene evidence, rather than recomputing gradients on
the original image: separate preprocessing has different border context. A
padding transition can create artificial edges; the original-frame point fraction
is reported separately. Coverage cannot recover candidates removed by the core,
and can reject real occluded/weak/blurred edges. All three fixed policies must be
reported, including no-gain and recall-loss outcomes.

## Independent raw provenance audit

`verify_raw_provenance.py` is a read-only integrity audit for an already
completed actual-85 development run. It does not invoke the matcher, compute
coverage, select thresholds, decode PNGs, or open heldout RGB. It hashes only
the selected development RGB bytes and the selected object's 72 training RGB/
mask bytes, and checks their dataset-manifest SHA/CRC. It also checks the
frozen V11 public build/source/executable, actual-85/post-85 run configuration,
training metadata and serialized attempt recipe, every gzip raw archive and
per-frame manifest, canonical rank/count/box reconstruction, and exact
fallback/fused candidate equality including float32 score bits.

The training provenance is reported separately. The expanded object-1/object-2
banks were extracted at V11; the tiny historical bank was extracted at V10
(`c41f047`) and is checked as that fact while its actual-85 matching run is
required to use V11. The original runner did not pin `template_attempts.csv`
or every per-frame raw manifest; this audit records their current SHA and
performs semantic cross-checks without pretending those hashes were historical
attestations.

```powershell
py -3.10 artifacts/quality_coverage/verify_raw_provenance.py `
  --dataset datasets/tless_expanded `
  --training datasets/tless_expanded_obj1_f32_train `
  --raw-run datasets/tless_expanded_obj1_f32_pilot `
  --output artifacts/quality_coverage/my_verified_inputs.json
```

The synthetic fixture suite is the first check and intentionally uses non-image
bytes, including a nonexistent heldout path:

```powershell
py -3.10 artifacts/quality_coverage/verify_raw_provenance.py `
  --self-test --output artifacts/quality_coverage/verify_raw_provenance_selftest.json
```

The report's `verified=1` means only that the recorded inputs and raw candidate
evidence satisfy this audit. It is not a detection-quality or coverage result.
