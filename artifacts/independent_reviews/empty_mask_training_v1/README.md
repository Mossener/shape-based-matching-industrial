# Independent binary/empty-mask training and padding audits

These standard-library Python audits do not import the trainer, evaluator,
OpenCV or their helpers. They never open image files or call the matcher.

`audit_training.py` checks all fixed poses against both the frozen RGB and
source-only attempt tables, the new dense template IDs, official boxes and
actual new template origins. `bank_reader.py` parses only the exact integer
OpenCV class-bank YAML subset used here, rejects unknown structure and integers
outside signed 32 bits, then reconstructs every successful layer's full feature
extents and canvas edge distances. Those values must agree with the diagnostic
CSV and attempt counts. Requested feature counts 32/16 are targets, not maxima.
V11 explicitly passes floor-half dimensions to `pyrDown`.

The audit binds every old numeric table it reads to `INPUT_CLOSURE.private_files`
and every generated training member to `BANK_FREEZE`. Source pins cover the
main auditor, independent bank reader and its recorded origin before/after the
audit. `ORIGIN.json` records the prior independent source-only auditor from
which the pose checks were adapted; the trainer is not the implementation
source. The original first audit is retained with its exact main source in
`prior_source/`; the later closure-binding audit adds the direct old-table pin
check without changing the training results.

`audit_plan.py` separately reads all twelve serialized banks, compares every
loaded layer with the planner CSV, reconstructs the union requirement and
alignment, and checks declared resource limits and frozen output inventory.
For L0 it uses declared extent plus 64; for L1 it uses twice the larger of
declared extent and actual feature endpoint plus one. Left/top stay 64.

Run from the repository root:

```powershell
F:/mysys2/ucrt64/bin/python.exe -m unittest discover -s artifacts/independent_reviews/empty_mask_training_v1 -p 'test_*.py' -v
F:/mysys2/ucrt64/bin/python.exe artifacts/independent_reviews/empty_mask_training_v1/audit_training.py --experiment artifacts/silhouette_empty_mask_experiment --run artifacts/silhouette_empty_mask_experiment/run_training_v1 --output NEW_TRAINING_AUDIT.json
F:/mysys2/ucrt64/bin/python.exe artifacts/independent_reviews/empty_mask_training_v1/audit_plan.py --experiment artifacts/silhouette_empty_mask_experiment --training-run artifacts/silhouette_empty_mask_experiment/run_training_v1 --plan-run artifacts/silhouette_empty_mask_experiment/run_plan_v1 --output NEW_PLAN_AUDIT.json
```

These checks validate serialized evidence and geometry. They do not independently
extract image features, observe unsuccessful partial layers, prove SIMD memory
safety, or establish accuracy or speed improvements. Native image-level quality
and performance comparison are separate stages.
