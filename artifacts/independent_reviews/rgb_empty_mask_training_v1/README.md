# Independent RGB empty-selection-mask training and geometry audit

This standard-library audit reads frozen numeric evidence and gzipped integer
class banks. It does not import the RGB trainer, evaluator, OpenCV or their
helpers, open image content, or invoke native tools. `ORIGIN.json` records the
prior independent V20 bank reader and pose/diagnostic helpers used as the
starting point; `training_numeric.py` is the retained helper-only portion.

`audit.py` explicitly binds the RGB V27 protocol, input closure and quality
freeze, checks all 20,736 attempts against frozen RGB control geometry, dense
successful IDs, metadata, training config and both layers' actual integer
features. Requested 32/16 feature targets are never treated as maxima.
Every treatment layer is compared field-by-field with feature diagnostics.
All twelve control/treatment banks are re-read and every layer is compared
with `loaded_layers.csv`, then checked against the fixed 848x832 canvas and
the saved memory estimate. All consumed numeric inputs and audit sources are
pinned before/after. Frozen training and plan member sets are checked.

Run from the repository root (output must be new):

```powershell
python -m unittest discover -s artifacts/independent_reviews/rgb_empty_mask_training_v1 -p 'test_*.py' -v
python artifacts/independent_reviews/rgb_empty_mask_training_v1/audit.py --experiment artifacts/rgb_empty_mask_experiment --output NEW_AUDIT.json
```

`run_20261022_v2.json` is the completed audit after the 21 synthetic tests.
The initial v1 run is retained. The historical native BANK_FREEZE's
`image_decodes=432` counts RGB training views; the source also reads 432 mask
images, making 864 native training decode calls. The independent audit's own
decode count is zero. Historical frozen evidence is not rewritten.

This validates serialized numeric records, not feature extraction from pixels,
unsuccessful partial features, SIMD memory safety, quality improvement or speed.
