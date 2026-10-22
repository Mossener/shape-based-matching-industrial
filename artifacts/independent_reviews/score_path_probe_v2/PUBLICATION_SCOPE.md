# V25 base publication boundary

The base inventory follows V24's six-field structure and explicit selection:
`version`, `scope`, `file_count`, `total_bytes`, `excluded`, and sorted `files`
with relative path, size and SHA256. `publication25.py` prepares the inventory
and a separate boundary receipt without invoking Git.

Only these roots are eligible:

- `artifacts/quality_failure_analysis/score_path_probe_v2/`
- `artifacts/independent_reviews/score_path_probe_v2/`

The source and verification filenames are explicit. Each of the three native
RED controls, GREEN selftest and completed Phase2 dataset contributes its full
frozen native files, execution logs, reservation and freeze. Both builds retain
source/preprocessing extraction, generated header, actual command/diagnostic
logs and compiler dependency text, while executable/object bytes are excluded.
All eight frozen numeric CSV gzip streams are included. Both independent audit
attempts, their logs, 39-test GREEN and earlier genuine RED evidence are retained.

Build/plan/receipt references to prior V24 evidence, loaded-layer metadata,
template banks, private source trees and compiler/SDK/runtime members remain
provenance declarations. The helper does not recursively follow or republish
those inputs. No dataset/image/SMD/template-bank bytes, executable, object, DLL,
Python cache, adjacent hash/full-matcher experiment or previously published V24
tree is selected.

The base precedes the separately reviewed classifier. New classifier members
can be added only through explicit repository-relative `--extra-member` values
within the same two roots, followed by independent review and a fresh final
inventory filename. Additional eligible local files appear in the separate
boundary receipt as pending scope review, never silently enter the base.
The new `RESULTS_PHASE2_V25.md` is an explicit base member. Root `README.md` and
`docs/optimization_versions.md` are pinned separately in the boundary receipt
as V24 did; they remain outside this requested two-root base. The separately
owned classifier root is not selected by this helper.

The inventory and boundary receipt exclude themselves to avoid recursive hashes.
They must be attached separately when publishing. The helper's synthetic tests
block outside-root and executable/object/DLL/image/template/cache/private paths,
arbitrary compressed data, duplicates, stale pins and changed member bytes.
