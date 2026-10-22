# V29 public training evidence release

`publication.py` uses an explicit allowlist of root filenames and completed
training/toy/test directories within the dilation experiment and its independent
training review. It does not descend into later quality execution directories.
The only selected files outside these two roots are `.gitattributes` and
`docs/optimization_versions.md`.

No command stages, commits, pushes, imports the trainer/evaluator, opens image
bytes or executes native code. Build manifests retain external SDK/runtime and
binary pins as declarations; this release verifier does not recheck those
prerequisites. It rechecks the new public training/plan files, complete native
member sets, recorded native exits, project source pins, critical independent
audit bindings and the separate acceptance marker. It does not rerun the
independent numeric interpretation or inherited historical evidence.

After the root freezes its review and all selected documentation, use:

```powershell
python -B artifacts/rgb_dilated_mask_experiment/release_v29/publication.py --check-evidence --audit artifacts/independent_reviews/rgb_dilated_mask_training_v1/run_real_v2_root_20261022_a/receipt.json
python -B artifacts/rgb_dilated_mask_experiment/release_v29/publication.py --prepare --audit artifacts/independent_reviews/rgb_dilated_mask_training_v1/run_real_v2_root_20261022_a/receipt.json
```

Prepare writes `PUBLISH_SELECTION_V29.json` exclusively and refuses overwrite.
Changing a selected byte or selected member afterwards makes verification fail.
Use this read-only check after the root stages the explicit file list:

```powershell
python -B artifacts/rgb_dilated_mask_experiment/release_v29/publication.py --staged
```

The staged check requires exact Git blob bytes for every selected file and the
inventory, supports SHA-1/SHA-256 object formats, rejects unmerged entries and
rejects **any extra changed staged path**. It does not merely verify that the
selected files happen to be staged. The root still owns the human scope review,
`git diff --cached --check`, commit/tag and remote verification.

Run the saved synthetic test harness in a fresh output directory:

```powershell
python -B artifacts/rgb_dilated_mask_experiment/release_v29/run_tests.py --output artifacts/rgb_dilated_mask_experiment/release_v29/tests_green_FRESH
```

Synthetic tests include extra staged files, CRLF conversion, a missing index
member, exact object IDs in both hash formats, private/binary/archive/type
rejection before reads, frozen-file mutation, complete training membership and
exclusion of later quality runs. These fixtures do not modify the actual index.
