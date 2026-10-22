# V31 source publication plan

Status: source preparation only. The final selection is a root-owned artifact
to be created after numeric training acceptance, complete lossless export and
quality results exist. This document does not select or publish any file.

## Implementation and validation

- [x] Migrate the V30 verifier into `verify_selection.py`, with an explicit
  `--selection` argument and a V31 default. Treat the manifest's `files[]` as
  the path allowlist; do not discover files recursively.
- [x] Validate canonical contained relative paths, duplicate entries, declared
  sizes/SHA256, total bytes, forbidden image/SMD/native/build suffixes and a
  strict per-file bound of less than 100 MiB before reading selected bytes.
- [x] With `--staged`, preserve SHA1/SHA256 Git blob calculation over exact
  bytes, including the selection itself. Require every allowed path in stage
  zero, refuse unmerged entries and unrelated changed staged paths, and run
  Git's cached whitespace check. Use only read-only Git commands.
- [x] Exercise synthetic path escape, duplicate, SHA change and index-byte
  mismatch cases in temporary directories, with mocked Git. Preserve a small
  source snapshot, command outputs and a source-only validation receipt.

## Publication scopes

**Source code and documentation.** The root may explicitly select the V31
sampler/training source, source-provenance and execution tools, independent
numeric/geometry/quality/timing auditors, their focused synthetic tests,
publication/export tools and explanatory documents. Source snapshots and
receipts carry their exact source hashes. Attribution and upstream licensing
remain in the project documents. Source availability does not establish a
successful experiment, speed gain or industrial accuracy.

**Failed and incomplete evidence.** The root may explicitly select compact
reservation, guard, provenance, failure and source-test receipts that explain
an attempt's actual outcome. V1's completed computation but failed receipt
write must remain distinguishable from the separately reserved V2 attempt.
Deliberate source-mutant failures remain synthetic evidence. Failed/partial
actual output is never relabeled as an accepted numeric run, a negative frame
or a successful quality/timing test. Do not recursively sweep evidence or
publish raw private inputs while assembling this scope.

**Lossless exported training evidence.** The original large training directory
is outside direct Git selection. After root acceptance, use the separately
reviewed exporter to preserve every original provenance-listed numeric member
with original/stored byte counts and SHA256. The export must complete its
full decode/round-trip verification and inventory check, with stored members
under its 95 MiB bound. Select the complete accepted export, manifest and
validation receipts explicitly; retain original provenance and input bindings.
Neither previews, hashes alone, sampled rows nor truncated JSONL substitute
for the lossless export. A failed export retains its failure status and is
not used as a completed public evidence bundle.

**Later quality and timing results.** These become selectable only after their
respective actual stages and independent audits complete. Keep numeric
consistency, primary B accuracy hypothesis, speed measurements and production
promotion separate. A failed accuracy hypothesis remains a publishable result
with its actual status. Unavailable results stay unavailable.

## Exclusions and final root gate

Private magnetic/SMD captures, dataset images, heldout matching inputs, native
executables/libraries/objects, build caches, Python bytecode and unreviewed
archives are excluded. The source verifier enforces the explicit path list,
forbidden suffixes and file-size ceiling; it does not infer semantic content
from an arbitrary renamed file. The root reviews the semantic scopes before
creating the final selection.

This preparation opens no actual raw archive, template bank, dataset index,
image or large training output; it does not create the final selection, read
the real Git index, stage, commit, push or export data. Once the prerequisites
are accepted, the root creates `PUBLISH_SELECTION_V31.json` from concrete
reviewed paths, verifies bytes, stages exactly that scope, verifies exact
indexed blobs including the inventory, and then publishes using the already
authorized GitHub workflow.
