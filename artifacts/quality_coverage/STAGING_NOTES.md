# Coverage experiment handoff for version recording

Numeric outputs are frozen. The recommendation is diagnostic-only, with no
production default change and no speed claim. The result to cite is
`DEVELOPMENT_RESULTS_20261021.md`; both independent reviews and machine-readable
audits agree with the complete outputs. Commit/tag/push belongs to the parent
agent; this helper has not staged or committed shared work.

Suggested stage groups:

1. Helper/adapter sources and runners: `coverage_helper.hpp`, `coverage_nms.hpp`,
   `coverage_test.cpp`, `coverage_eval.cpp`, `run_tests.ps1`, `build_eval.ps1`,
   `run_eval.ps1`, `verify_raw_provenance.py`, `audit_coverage_result.py`.
2. Frozen recipe/design/reviews/results: `COVERAGE_PROTOCOL.json`, `DESIGN.md`,
   `PADDING_POLICY.md`, `INTEGRATION_REVIEW.md`, `README.md`,
   `DEVELOPMENT_RESULTS_20261021.md`, `TINY_ACTUAL85_INDEPENDENT_REVIEW.md`,
   `OBJ1_FULL400_INDEPENDENT_REVIEW.md`, both `*_coverage_independent_audit.json`,
   and this file.
3. Main synthetic evidence: entire `run_20261021_helper_final/`,
   `run_20261021_final_integration_selftest/`, and
   `verify_raw_provenance_selftest_final.json`.
4. Real development evidence: entire `run_20261021_tiny_actual85_coverage/` and
   `run_20261021_obj1_full400_coverage/`, including source snapshots, complete
   point/candidate gzip caches and unchanged execution provenance.
5. Preserve historical synthetic runs and their metadata if the version is
   intended to include the full experiment history. The first helper run has
   an explicitly documented runner metadata shadowing defect, not a reportable
   helper failure. It is superseded by `run_20261021_helper_final/`.

Generated `.exe` files, `build/` executables and `__pycache__/` are Git-ignored.
The main run directories already contain their build manifest, source snapshot,
stdout/stderr and verified input JSON. Top-level `*.stdout.txt`, `*.stderr.txt`,
`*.verified_before.json` and `verified_*_final.json` duplicate this evidence and
need not be staged to reproduce the recorded result; retain locally. Do not
stage decoded T-LESS source datasets or invent a data redistribution grant.

The two complete validation-point gzip caches are approximately 31.8 MB and
31.1 MB; the expanded candidate gzip is approximately 11.9 MB. None exceeds
GitHub's per-file 100 MB limit. Their SHA is part of the frozen provenance;
avoid recompressing them after recording it.

Known metadata limitation: `execution_provenance.dataset_images_evaluated=1`
is an evaluate-mode flag. The actual 16/400 frame counts are recorded in metrics
and per-frame CSV; training images are separately reconstructed. Leave frozen
run evidence untouched and retain this explanation in the version record.

No heldout/reserved object, production core, frozen public evaluator or template
bank was modified by this experiment. Full/lazy and fallback/fused equivalence
are correctness evidence and are not detection-quality measurements.
