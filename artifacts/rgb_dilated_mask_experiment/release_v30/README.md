# V30 publication verification

`verify_selection.py` checks the explicit V30 allowlist, byte hashes, size
limits and forbidden image/native build suffixes. With `--staged` it also
requires exact selected index bytes, including the inventory, and rejects any
unrelated changed staged path; it
does not stage, commit or push anything.

The V30 selection preserves the reviewed V29 file set and adds the quality,
timing and numeric feature-region evidence. The feature-region audit contains
numeric CSV/GZIP data only; private magnetic/SMD images and held-out matching
inputs are excluded.

Run from the repository root:

```powershell
python -B artifacts/rgb_dilated_mask_experiment/release_v30/verify_selection.py
python -B artifacts/rgb_dilated_mask_experiment/release_v30/verify_selection.py --staged
```
