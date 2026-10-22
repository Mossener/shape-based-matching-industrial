# RGB official-mask dilation implementation plan

> **For agentic workers:** Execute the bounded source slices in this task,
> respecting root's exclusive CPU grants. No commit or production changes.
> Every native stage has its own explicit budget; do not continue automatically.

**Goal:** Test one per-layer mask-operation change against frozen RGB control
without changing source pixels, geometry, poses, thresholds or result selection.

**Architecture:** This directory owns a pinned original V11 control snapshot,
an exact one-line treatment snapshot, official-mask policy, literal/spy tests,
training/planning runner and separate quality adapter. Frozen V27 control
inputs remain at their declared origin; existing byte pins are declarations
until a granted execution verifies them. All new execution evidence is fresh.

**Tech stack:** Python standard library, C++17, MinGW GCC, OpenCV 4.12, OpenMP.

**Spec:** `artifacts/rgb_dilated_mask_experiment/DESIGN.md` and `PROTOCOL.json`.

## Global constraints

- Production stays at `b25df46f6ddf9c24fb43f5836f1414dc38c8caed`.
- Only `erode` to `dilate` in the exact private extractor line changes algorithm behavior.
- The third argument remains the original nonempty official warped mask.
- Six objects `[1,2,5,8,12,17]`, all 20,736 poses and all failures are retained.
- Targets 32/16 do not cap actual features; both actual layers are retained.
- Exact geometry gate: 848x832, padding `[64,64,64,228]`, no enlargement/filtering.
- Development: all 400 frames per object, threshold 85, NMS .3, GT .5, visibility .5.
- Decision: `TP >= 215 AND FP < 42112`, no object/scene/group fallback.
- Heldout `[11,14,15,16,17,18,19,20]`, objects 25/29 and private magnet/SMD are sealed.
- At most one heavy native task; every failed receipt and reservation survives.

## Source and toy slice

- [x] Preserve initial expected standard-library RED in `tests_red_20261022_a`.
- [x] Generate/check the one-line private snapshot and original literal control.
- [x] Restore original official-mask forwarding and pre-call mutation snapshot.
- [x] Fix literal expectations before native RED in `TOY_TEST_EXPECTATIONS.json`.
- [x] Compile/run old erosion sanity, erosion-vs-dilation expected RED,
  treatment dilation GREEN and official-mask spy GREEN, sequentially.
- [x] Verify every recorded build pin, actual C++ `-MD` dependency, exact RED
  stderr and raw logs in `toy_verification_20261022_b.json`.
- [x] Preserve post-toy stale static-test failure; replace it with actual
  no-CPU rejection checks. `tests_all_20261022_c` has 15 passing tests.

The original four toy builds did not separately pin the transitive Python
`source_contract.py` import. Do not describe their Python execution closure as
complete. Their actual C++ dependency closure and recorded pins were verified.
`build_training_v2.py` adds the missing Python source pin and pins itself;
the original builder and its historical receipts remain unchanged.

## Training slice, after root grant

Interfaces: `build_training_v2.py --target training` produces an actual
two-translation-unit executable and dependency/provenance manifest.
`run_training.py --mode train` consumes that manifest and fixed input closure,
writes native output at `run_training_v1` and logs beside it at
`run_training_v1_execution`. Validation reuses source-pinned standard-library
bank/attempt readers and is explicitly not an independent audit.

- [x] Implement new builder closure and one-shot train/plan runner source.
- [x] Build, exactly once under a fresh root CPU grant:

```powershell
python -B artifacts/rgb_dilated_mask_experiment/build_training_v2.py --target training --output artifacts/rgb_dilated_mask_experiment/build_training_v1 --cpu-slot-granted
```

- [x] Train all fixed poses under its separately explicit grant:

```powershell
python -B artifacts/rgb_dilated_mask_experiment/run_training.py --mode train --build-manifest artifacts/rgb_dilated_mask_experiment/build_training_v1/build_manifest.json --output artifacts/rgb_dilated_mask_experiment/run_training_v1 --cpu-slot-granted
```

Require 3,456 attempts per object, 20,736 total, original pose/crop/affine/mask
geometry, dense successful IDs, exact serialized features versus diagnostics,
two actual layers and zero extraction exceptions. Insufficient-feature poses
remain with their failure reason. Stop if any object has zero successes.
The completed native loop implies 864 `imread` calls: 432 RGB and 432 masks.

## Complete-union plan and independent acceptance

- [x] After the separate root grant, scan all twelve banks:

```powershell
python -B artifacts/rgb_dilated_mask_experiment/run_training.py --mode plan --build-manifest artifacts/rgb_dilated_mask_experiment/build_training_v1/build_manifest.json --training artifacts/rgb_dilated_mask_experiment/run_training_v1 --output artifacts/rgb_dilated_mask_experiment/run_plan_v1 --cpu-slot-granted
```

- [ ] Root's independent reader must rederive all attempts, origins, actual
  features, counts and geometry from complete saved evidence. It must not
  import this runner or depend on a quality-input freeze.
- [ ] Write `AUDIT_ACCEPTANCE.json` only after that independent audit passes,
  with `accepted_independent_audit=true`, `scope="training_and_exact_geometry"`
  and full `{path,sha256,bytes}` pins named `training_freeze`, `plan_freeze`
  and `independent_audit`. Do not mutate either freeze after its audit.

## Quality source and later execution

Interfaces: `prepare_quality_inputs.py` binds the separate acceptance marker,
dynamic treatment success counts, inherited control directories and fixed
schedules. `quality_eval.cpp` retains complete ordered raw candidates, score
bits, selected labels and GT/pose identities for both arms/paths.

- [x] Finish the quality execution Python source closure before its
  first actual build; include `source_contract.py` explicitly.
- [ ] Complete independent quality-source review and obtain the next root grant.
- [ ] Create a fresh quality-input freeze only after training/geometry and
  independent acceptance. Verify declared bank/numeric/image byte pins in
  the authorized execution stage, not in static source preparation.
- [ ] Under separate grants run selftest, old gate (96 calls), pilot (192),
  full development (9,600), retaining reservation on every failure.
- [ ] Independently rederive all-GT and eligible metrics, per-object/scene,
  negative-frame FP, V22 historical groups and V27 identity groups from the
  saved records. Compare raw ordering, multiplicity, score bits and both paths.
- [ ] Apply the simultaneous TP/FP decision without result-dependent changes.
- [ ] Only after quality audit, consider the separately fixed 12,288-call
  timing stage. Fewer FP alone is never a speed result.

The unexecuted quality/timing scripts are source preparation, not completed
evidence. Passing literal tests cannot establish extraction coverage, accuracy,
runtime speed, industrial robustness or production readiness.
