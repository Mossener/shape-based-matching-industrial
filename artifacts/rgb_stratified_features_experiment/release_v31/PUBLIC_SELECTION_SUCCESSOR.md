# Manifest-bound numeric pool publication

verify_public_selection.py is a separate successor to the frozen
verify_selection.py. The old verifier, old source checkpoint selection and
their receipts remain unchanged. The only new forbidden-suffix exception is
for exact accepted-export numeric pool members. The root must review this
source and its synthetic evidence before using it with a real selection.

The final selection retains the original files, file_count and selected_bytes
fields. When it publishes a complete accepted training export, it must add:

~~~json
{
  "accepted_training_export": {
    "path": "CANONICAL_ABSOLUTE_EXPORT_DIRECTORY/EXPORT_MANIFEST.json",
    "bytes": 123,
    "sha256": "THE_TRUSTED_ACCEPTED_MANIFEST_SHA256"
  }
}
~~~

This is an externally accepted full pin, not a path discovered by scanning.
The same manifest must be selected with the identical byte/SHA pin. The
verifier checks the manifest's exact bytes before opening any pool. Its schema
must be rgb_stratified_lossless_training_export_v1, passed must be true,
and original/stored inventories, canonical relative names, counts and byte
accounting must agree. Every exported stored member must also be selected
with its manifest pin. Source, training provenance and training acceptance
references require full canonical absolute pins; those external dependencies
are not opened by this verifier.

A selected path with .bin is permitted only when its exact location under
that selected export directory matches a manifest row whose original and
stored names are both pools_NNNNNN.bin.gz, with exactly six decimal digits.
Its encoding must be identity; original and stored bytes/SHA pins must be
identical and match the selected member. Bare .bin, arbitrary .bin.gz,
extra suffixes, differently cased names, nested/escaped/mixed paths, omitted
export members, conflicting pins and unselected manifests are refused.
An accepted export may otherwise contain the existing numeric JSON/JSONL/gzip
members. Their stored SHA256 is still checked; this verifier does not decode
the full export or replace the accepted export/restore audit.

The inherited path safety, duplicate-key/member rejection, strict
less-than-100-MiB bound and exact SHA256 checks remain in force. Export stored
members additionally obey the exporter's 95-MiB limit. Offline mode invokes
no Git. --staged retains the original SHA1/SHA256 index-blob checks for every
selected file and the selection itself, stage-zero coverage, unrelated-stage
rejection and cached whitespace check. The verifier never stages or publishes.

After root review, the CLI is:

~~~text
python -B artifacts/rgb_stratified_features_experiment/release_v31/verify_public_selection.py --selection ABSOLUTE_FINAL_SELECTION
python -B artifacts/rgb_stratified_features_experiment/release_v31/verify_public_selection.py --selection ABSOLUTE_FINAL_SELECTION --staged
~~~

These commands have not been run against any real selection or index during
source preparation.

## Synthetic evidence

run_public_tests.py --output FRESH_DIRECTORY snapshots the successor and the
unchanged predecessor test source, then runs temporary tiny numeric fixtures.
All Git calls in tests are mocked; no real export, bank, raw archive or image
is opened. Twenty test methods include the inherited seven path/size/index
methods and thirteen manifest/pool methods with multiple rejection cases.

- successor_red_manifest_pool_v1/receipt.json: preserved pre-fix RED. The
  byte-identical copied verifier rejected the legitimate tiny accepted pool.
- successor_green_manifest_pool_v1/receipt.json: first 17-method GREEN.
- successor_green_manifest_pool_v2/receipt.json: expanded 20-method GREEN.
- successor_green_manifest_pool_v3/receipt.json: current 20-method GREEN,
  including refusal to read a pool before accepted manifest bytes are checked.
- successor_mutations_v1/receipt.json: preserved 8/9 rejection. The remaining
  mutation exposed a test gap in checking early manifest rejection; the outer
  selected-file hash gate still rejected changed manifest bytes.
- successor_mutations_v2/receipt.json: current 9/9 deliberately weakened
  source copies rejected after that test gap was addressed.

run_public_mutations.py preserves each changed source, exact mutation,
stdout/stderr and receipt. Mutations weaken selected-manifest binding,
manifest byte pin, export schema, encoding, original pin, pool naming,
complete-member selection, selected-pool rebinding and the outer suffix gate.
The scripts mutate only their fresh source copies. Test success establishes
this publication policy on synthetic fixtures, not actual export acceptance,
recognition accuracy, speed or production readiness. No final selection was
created and no Git operation was performed.
