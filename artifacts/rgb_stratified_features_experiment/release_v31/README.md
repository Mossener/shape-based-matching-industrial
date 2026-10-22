# V31 publication verifier source

`verify_selection.py` is a narrow migration of the V30 verifier. It validates
an explicit manifest's exact path allowlist, byte lengths, SHA256, forbidden
image/SMD/native/build suffixes and a strict per-file limit below 100 MiB.
With `--staged`, it verifies exact Git SHA1/SHA256 index blobs for every member
and the inventory itself, and rejects unrelated staged changes or merges.
It never stages, commits or pushes files.

The default is
`artifacts/rgb_stratified_features_experiment/PUBLISH_SELECTION_V31.json`.
That final selection is not created during source preparation. The root will
create it only after the experiment's acceptance/export/result prerequisites.
An explicit selection must be a contained repository JSON file:

```text
python -B artifacts/rgb_stratified_features_experiment/release_v31/verify_selection.py --selection ABSOLUTE_SELECTION_JSON
python -B artifacts/rgb_stratified_features_experiment/release_v31/verify_selection.py --selection ABSOLUTE_SELECTION_JSON --staged
```

The manifest uses `file_count`, `selected_bytes` and `files`, where each row
has canonical repository-relative POSIX `path`, nonnegative integer `bytes`
and lowercase hexadecimal `sha256`. Additional descriptive row metadata is
allowed. The selection itself is checked separately in the index; it need not
appear in its own content list.

`run_tests.py --output FRESH_CONTAINED_DIRECTORY` copies these small sources and
runs temporary numeric fixtures with mocked Git commands. It preserves sources,
logs and a validation receipt. It does not inspect the actual Git index,
experiment outputs, banks, raw archives, dataset index or images. See
`SOURCE_PUBLICATION_PLAN.md` for the root's later publication scopes.
