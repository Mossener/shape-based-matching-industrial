# RGB empty-mask experiment implementation plan

> **For agentic workers:** Use a subagent-driven or executing-plans workflow only after the parent reviews this plan. Every native or dataset stage requires a new explicit root grant.

**Goal:** Build an isolated, auditable comparison of the existing grayscale RGB template source with the V11 feature-selection mask versus the same source with `cv::Mat()`.

**Architecture:** A sibling experiment owns its adapter, private V11 snapshot,
source transformation, training evidence, geometry gate, quality runner and
independent numeric auditor. It consumes only frozen metadata and declared
input pins until root separately authorizes each native stage. The production
checkout and the frozen full-API 85-source closure remain untouched.

**Spec:** `artifacts/rgb_empty_mask_experiment/DESIGN.md`

## Global constraints

- The only detector-factor change is the third `addTemplate` argument: `cv::Mat()`.
- Keep the grayscale RGB source, ROI, affine, nearest-neighbor mask warp, black border, pose grid, V11 extractor, thresholds, requested targets, NMS and GT rules fixed.
- Train all 20,736 poses; record failures and actual feature counts; never omit or fabricate a pose.
- Require exact 848×832 geometry before the first development-image decode.
- Do not read held-out scenes, objects 25/29, private magnet images or SMD data.
- Do not tune from object, scene, identity or negative-frame results.
- Preserve every failed stage and use exclusive fresh output directories.

## Task 1: Freeze the static protocol and source transformation

**Files:**

- Create: `rgb_empty_mask_experiment/PROTOCOL.json`
- Create: `rgb_empty_mask_experiment/rgb_empty_mask_policy.hpp`
- Create: `rgb_empty_mask_experiment/rgb_empty_mask_source_test.cpp`
- Test: `rgb_empty_mask_experiment/test_static_contract.py`

**Interfaces:**

- `add_template(detector, warped_gray, class_id)` calls exactly
  `detector.addTemplate(warped_gray, class_id, cv::Mat())` and returns the
  detector's ID.
- The source test's spy verifies source pointer/type/shape and an empty third
  argument; it performs no dataset or bank IO.
- The Python contract verifies the literal one-seam transform, complete fixed
  metadata keys, and zero execution counters.

The source of record is `artifacts/silhouette_empty_mask_experiment/frozen_helpers/tless_eval.cpp:128-159` for the grayscale crop/warp and original call, plus `silhouette_eval.cpp:41-192` for complete pose/feature diagnostics. The new policy must not route the grayscale source through `silhouette_source.hpp`, which is the binary-source predecessor.

Steps:

- [ ] Write the RED spy test with a nonempty grayscale matrix and a detector
  that fails if the source is cloned, converted or replaced.
- [ ] Run the RED test and preserve its expected failure before adding the
  policy header.
- [ ] Add only the policy wrapper and run the GREEN source test.
- [ ] Freeze the protocol and source hashes in an origin record. Reject any
  second algorithmic seam, binary-source conversion, dilation, threshold or
  pose-list change.

## Task 2: Prepare private source and input closure without reads

**Files:**

- Create: `private_v11/` source snapshot, helper copies and source-origin JSON
- Create: `INPUT_CLOSURE.json` and `source_status.json`
- Test: `test_static_contract.py`, `test_input_scope.py`

**Interfaces:**

- The closure lists every source/config/metadata/reference member needed by a
  later stage and records role, size and SHA-256 for ordinary metadata files.
- Dataset image and SMD/template-bank member hashes remain declarations until
  the authorized stage; preparation must not open their content.

Steps:

- [ ] Copy the exact private V11 Git-byte set and verify it against the retained
  V11 origin before any compilation.
- [ ] Copy unchanged adapter helpers only after checking their existing frozen
  hashes; record the policy wrapper as the sole new source.
- [ ] Validate all paths before hashing, reject held-out/reserved paths and
  verify the closure before any dataset reader is reachable.
- [ ] Keep declared image, SMD and serialized-bank members as metadata-only
  declarations in this preparation step. Do not invoke the inherited closure
  creator/verifier, because it reads compressed banks and raw archives; that
  byte verification belongs to an explicitly authorized later stage.
- [ ] Run static source/closure tests and retain their output as a pure-data
  receipt.

## Task 3: Train every treatment pose and write diagnostics

**Files:**

- Create: `train_rgb_empty_mask.cpp`, `build_training.py`, `run_training.py`
- Create: `training_attempts.csv`, `feature_geometry.csv`, per-object bank and
  metadata outputs during the authorized run
- Test: `test_training_contract.py`, native source-test executable

**Interfaces:**

- `run_training.py --mode selftest` does zero matcher calls and checks all
  3,456 pose keys per object.
- `run_training.py --mode training` writes one row per fixed attempt, dense
  successful IDs, actual layer counts and failure reasons.
- A successful training freeze exposes exactly six object banks and binds all
  attempts, metadata, source, build and input evidence.

Steps:

- [ ] Write numeric RED tests for missing pose, duplicate pose, fabricated
  actual count, non-dense ID and geometry mismatch.
- [ ] Run RED and preserve the failure receipt.
- [ ] Implement the unchanged RGB crop/warp loop with the policy wrapper.
- [ ] Run the zero-matcher native selftest under the root's CPU grant.
- [ ] Run the one-shot 20,736-attempt training stage. If any object has zero
  successes, an exception, missing pose or geometry mismatch, retain all
  attempts and stop before quality image access.
- [ ] Bind treatment template counts from the training freeze. Do not use a
  fixed 3,456 bank count; the frozen RGB control counts are
  `[2153,2646,3416,3456,3372,3156]` by object and treatment coverage may
  differ.
- [ ] Independently reparse every attempt, feature coordinate, metadata and
  bank declaration; require complete six-object coverage.

## Task 4: Enforce the 848×832 pre-image geometry gate

**Files:**

- Create: `padding_plan.py`, `geometry_gate.py`, `GEOMETRY_FREEZE.json`
- Test: `test_geometry_gate.py`

**Interfaces:**

- `geometry_gate` consumes metadata only and returns a pass only when the
  complete RGB+treatment union fits exactly in 848×832 with left/top 64.
- It rejects oversized layers, out-of-canvas coordinates, incomplete poses,
  excessive memory estimates and partial-bank substitutions.

Steps:

- [ ] Write RED fixtures for one oversized layer, a missing pyramid level and a
  dropped large template.
- [ ] Run RED and preserve the expected failures.
- [ ] Implement the fixed 848×832 check and pass a complete metadata fixture.
- [ ] Freeze the geometry CSV and plan before any quality image decode.
- [ ] Reject the inherited planner's automatic padding enlargement for this
  experiment; a larger required size is a fixed-gate failure.

## Task 5: Run fixed quality stages and independent audit

**Files:**

- Create: `quality_eval.cpp`, `quality_runner.py`, `quality_contract.py`
- Create: `independent_audit.py`, `test_independent_audit.py`
- Create during authorized run: complete raw archives, metrics, selected rows,
  identity strata and stage freeze

**Interfaces:**

- `quality_runner` has fixed modes `old_gate`, `pilot`, and `development` with
  budgets 96, 192 and 9,600 matcher calls.
- `quality_contract` enforces raw field order, float32 bits, fallback/fused
  equality, 2,400 object-frame pairs, six-object/scene coverage and negative
  frame accounting.
- `independent_audit` recomputes NMS/GT/identity results from saved numeric
  records and does not import or execute native matcher code.

Steps:

- [ ] Write RED archive/audit tests for altered score bits, duplicate rows,
  wrong class, missing negative frame and changed identity assignment.
- [ ] Run RED, then implement the exact decoder and auditor.
- [ ] Run the old-padding RGB gate and fixed pilot only after the training and
  geometry freezes pass.
- [ ] Run all 400 development frames once; retain full raw outputs and stop on
  any path-equality, provenance, resource or audit error.
- [ ] Load each treatment object with the successful-template count recorded in
  its accepted training freeze; reject hardcoded or mismatched counts.
- [ ] Recompute all-GT/eligible metrics, negative errors and the four historical
  identity strata before writing a result summary.
- [ ] Apply the pre-registered `TP >= 215 && FP < 42112` decision without any
  per-object or per-scene exception.

## Task 6: Run the separately frozen timing stage

**Files:**

- Create: `timing_runner.py`, `timing_contract.py`, `timing_audit.py`
- Create during authorized run: timing samples, paired ratios and stage freeze

**Interfaces:**

- The schedule has 64 fixed frames per object, one warmup, seven measured
  rounds and four rotating arm/path positions for 12,288 calls.
- `timing_contract` requires every timed call to equal its own quality raw
  reference and reports matcher and external-call clocks separately.

Steps:

- [ ] Write RED tests for a missing round, unbalanced rotation, nonpositive
  clock, altered output and decode time included in the matcher clock.
- [ ] Run RED and preserve the failures.
- [ ] Implement fixed scheduling and nearest-rank median/p95 auditing.
- [ ] Run only after quality and independent audit acceptance; report speed
  separately from accuracy.

## Completion evidence

- [ ] Static protocol/source/closure hashes and zero-read counters are recorded.
- [ ] Training freeze proves all attempts and actual feature counts.
- [ ] Geometry freeze proves complete 848×832 feasibility.
- [ ] Quality freeze and independent audit agree on every raw/selected field.
- [ ] Timing freeze has complete 12,288 calls and paired clock statistics.
- [ ] No default, production or industrial-generalization claim is made from
  development evidence alone.
