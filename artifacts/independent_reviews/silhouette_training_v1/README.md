# Independent numeric review of source-only silhouette training

`audit_training.py` imports only Python standard-library modules. It does not
import the training runner/evaluator/helpers, open images or invoke the native
extractor/matcher. Its six synthetic tests reject wrong class, pose, geometry,
success flags, IDs, feature counts, metadata origins, missing/duplicate poses and
missing failure reasons. Failed feature-count fields are checked as serialized
placeholders, not as observations of intermediate extraction features.

The fresh `root_numeric_audit_20261022.json` passes. Each of objects
1/2/5/8/12/17 retains all 72 views × 12 angles × 4 scales = 3,456 attempts;
all 20,736 attempts report `insufficient_features`, with zero successful
templates and zero OpenCV exceptions. New attempt geometry equals the original
RGB attempt geometry for every pose. Metadata is empty for each unavailable
bank. No bank gzip is fabricated. The complete native artifact inventory agrees
with `BANK_FREEZE.json`, including every SHA/byte count.

The audit also checks all six training configs, complete summary counts,
protocol/input-closure binding and the explicit incomplete comparison status.
The training runner returned exit 1 after preserving all attempts; the wrapper
records successful post-run source/input/build/runtime verification. No quality
comparison or matcher call was run for this unavailable arm.

Root separately re-ran the training `build_gate` and numeric `inputs.verify`
before authorizing training: all five actual build commands had exit 0,
229 private numeric files verified, with 402/513 ordered dependency occurrences
for the core/adapter translation units. These local build checks use the
experiment's helper and are separate from the independent table arithmetic.
Their runtime scope excludes OS/API-set attestation and dynamic plugins.

Reproduce the numeric checks from the repository root:

```powershell
python -m unittest discover -s artifacts/independent_reviews/silhouette_training_v1 -p test_numeric.py -v
python artifacts/independent_reviews/silhouette_training_v1/audit_training.py --experiment artifacts/silhouette_template_experiment --run artifacts/silhouette_template_experiment/run_source_only_training_v1 --output artifacts/independent_reviews/silhouette_training_v1/my_fresh_audit.json
```

The second command requires the locally retained numeric frozen inputs. It
refuses an existing output. Paths in the evidence refer to the original local
workspace and are provenance, not a portable dataset download recipe.

This verifies saved numeric evidence and provenance, not the extractor's
intermediate computation, a unique failure mechanism, improved accuracy or
speed. The negative outcome is kept independently of any later empty-feature-
mask experiment; it does not justify silently changing the original arm.
