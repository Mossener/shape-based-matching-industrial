# RGB official-mask dilation experiment

An isolated test of one per-layer template-selection change: replace V11's
3x3 mask erosion with same-argument 3x3 dilation. Grayscale RGB, official mask
input, geometry, all poses, thresholds and matching remain fixed.

Source derives from V27's SHA-bound private V11 snapshot at
`b25df46f6ddf9c24fb43f5836f1414dc38c8caed`, its source-pinned adapter/build
plumbing and the original official-mask RGB helper. `SOURCE_ORIGINS.json`,
`PRIVATE_SOURCE_FREEZE.json` and `TRAINING_VALIDATOR_ORIGIN.json` distinguish
unchanged copies from generated/adapted sources. No historical execution output
was copied as a new result; no private dataset is included.

`control_v11/` preserves original bytes for literal tests; `private_v11/` has
only one changed source line. Neither changes the production checkout.

Current evidence covers source, synthetic behavior, all 20,736 training
attempts and the strict complete-union geometry gate. See
`RESULTS_PRE_QUALITY.md`, `toy_verification_20261022_b.json`,
`FAILURE_HISTORY.md` and static-test receipts. Independent acceptance and
quality remain pending; these results do not claim accuracy or speed improvement.

Run pure standard-library verification into a fresh output directory:

```powershell
python -B artifacts/rgb_dilated_mask_experiment/run_static_tests.py --slice all --output artifacts/rgb_dilated_mask_experiment/tests_new
python -B artifacts/rgb_dilated_mask_experiment/verify_toy_receipts.py --output artifacts/rgb_dilated_mask_experiment/toy_verification_new.json
```

The second command checks saved toy evidence and does not run a native program.
Native commands in `IMPLEMENTATION_PLAN.md` require a fresh coordinated root
CPU grant. Training, geometry, quality and timing each stop at their own gate.

`source_status.json` is an immutable initial source-only checkpoint already
pinned by historical builds. Later actual counters belong in separate execution
status/receipts; do not rewrite the checkpoint.
