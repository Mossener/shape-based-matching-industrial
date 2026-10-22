# Full-bank feature-region observer

The frozen [DESIGN.md](DESIGN.md) and [PROTOCOL.json](PROTOCOL.json) define a
diagnostic over three completed public template families. This directory is
currently **source-only**: no native build/run or image byte read has occurred.
Do not treat source checks as successful observation of pixels or accuracy.

The C++ observer is one isolated TU using FileStorage integer bank parsing and
OpenCV geometry. It does not include/link the matcher implementation, retrain
templates, extract gradients or change defaults. It uses an explicit 432-mask
allowlist, hashes each mask before/after its sole decode, and preserves complete
RLE maps for all 20,736 shared poses. Binary source content uses grayscale
pyrDown; official selection reference uses nearest resize. Float alpha maps
retain exact bits. Output and RSS ceilings fail without sampling.

The independent Python audit uses the standard library and its own copied
strict bank parser. It replays every feature coordinate, map value, exact
distance, region, orientation bin and actual count; the complete failed-layer
table stays explicit. It also replays complete fallback/fused raw, NMS and both
GT conventions for all 7,200 family/object/frame cases, checks the repeated
historical RGB stream, and joins all 64,618 selected events to descriptor
measurements. Raw usage means post-consolidation representative IDs. Numeric
replay does not independently reproduce OpenCV warp/pyrDown pixels or establish
causation from feature location.

Run source-only checks from the repository root:

```powershell
python -B -m unittest discover -s artifacts/quality_failure_analysis/template_feature_regions_v1 -p 'test_*.py' -v
python -B artifacts/quality_failure_analysis/template_feature_regions_v1/static_check.py --output artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_STATIC.json
python -B artifacts/quality_failure_analysis/template_feature_regions_v1/prepare_inputs.py --output artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_INPUTS
```

Only after root grants the native CPU slot, use fresh directories:

```powershell
python -B artifacts/quality_failure_analysis/template_feature_regions_v1/build_observer.py --output artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_BUILD --cpu-slot-granted
python -B artifacts/quality_failure_analysis/template_feature_regions_v1/run_selftest.py --build artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_BUILD/BUILD_FREEZE.json --output artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_SELFTEST --cpu-slot-granted
python -B artifacts/quality_failure_analysis/template_feature_regions_v1/verify_selftest.py --native artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_SELFTEST/native --output artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_SELFTEST_AUDIT.json
python -B artifacts/quality_failure_analysis/template_feature_regions_v1/run_observer.py --build artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_BUILD/BUILD_FREEZE.json --inputs artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_INPUTS/INPUT_FREEZE.json --selftest-audit artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_SELFTEST_AUDIT.json --output artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_RUN --cpu-slot-granted
python -B artifacts/quality_failure_analysis/template_feature_regions_v1/audit_numeric.py --observation artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_RUN/OBSERVATION_FREEZE.json --output artifacts/quality_failure_analysis/template_feature_regions_v1/NEW_AUDIT
```

The first real compile and native geometry fixture gate remain outstanding.
The predeclared native gate contains seven fixtures and 35 complete maps:
rectangle, hole, diagonal, concave, odd crop, 90-degree rotation and 2x scale.
The separate Python oracle checks every map pixel, including nearest half
resize, grayscale pyrDown and exact float support values.
Full image observation must wait for that gate; the source-only preparer opens
public bank/numeric bytes but never verifies image bytes itself. Build sources
and prepared-input sources must remain identical through execution; any change
requires new freezes. Every stage preserves failures in a new directory.
`inputs_source_20261022_v1` is retained as historical preparation; later source
changes invalidate its execution-source pins. Use a fresh matching freeze.

`ORIGINS.json` names the byte-exact independent bank reader and PE/compiler
provenance helper origins. Initial missing-function RED failures and subsequent
numeric GREEN evidence are retained in `red_*`/`green_*` directories. Some RED
stub cases fail with missing-return errors; those are not native or semantic
extractor RED tests. Production sources, V27/V28 evidence and Git are untouched.
