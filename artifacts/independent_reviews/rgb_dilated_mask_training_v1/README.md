# Independent RGB official-mask dilation training and geometry audit

This is prepared audit source with synthetic tests. No real dilation training
bank has been accepted by this directory's preparation. The audit uses the
Python standard library and its own strict integer OpenCV-YAML subset reader;
it does not import the trainer, evaluator, OpenCV, their helpers, or execute a
native program. ORIGIN.json records the prior independent RGB audit sources
used as the starting point.

The intended real-evidence audit checks all 20,736 attempts, including failures,
72 views per object, the full fixed angle/scale schedule, arm-local dense
successful IDs, exact RGB-control crop/ROI/canvas/official warped bbox and pose,
successful metadata, both layers' actual feature counts, coordinates and
origins, and all serialized diagnostics. Requested 32/16 feature counts are
targets, never maximum permitted actual counts. Treatment success counts are
read from the new BANK_FREEZE and independently recounted; no dilation success
count is predicted or hardcoded.

It re-reads all twelve control/treatment banks, compares every loaded layer to
loaded_layers.csv, rejects missing/duplicate layers and missing arms/objects,
and independently derives the fixed canvas. Fine-layer bounds include the
64-pixel local-search margin; coarse bounds include the actual max coordinate
plus one. LCM alignment is 16, source is 720x540, fixed output 848x832, padding
is [64,64,64,228], pixels are 705,536, and estimated dynamic bytes are
705,536 x 512 = 361,234,432. Enlarging the canvas is a failure, not an automatic
repair. The numeric peak working-set report is checked against 1.5 GiB; this
audit does not independently observe native memory use.

Before reading banks, source-seam verification independently compares all 23
original/control/private source members against the pinned V27 source freeze.
Only the exact per-layer erode-to-dilate line is allowed to differ. The original
RGB helper remains byte-identical. The audit does not import the seam generator.

The inherited RGB-control paths must be the exact frozen_inputs/obj*/rgb_training
directories beneath the declared sibling RGB-empty-mask experiment. Every
inherited numeric file actually read must have its frozen private_files hash.
No image, private magnet/SMD, held-out dataset or raw scene archive is needed.
Own audit sources and all read numeric/source evidence are rehashed at the end.

Run the literal/mutation suite:

    python -B -m unittest discover -s artifacts/independent_reviews/rgb_dilated_mask_training_v1 -p "test_*.py" -v

After root has produced the real training and plan freezes, choose a fresh
directory inside this independent-review directory:

    python -B artifacts/independent_reviews/rgb_dilated_mask_training_v1/audit_v2.py --experiment artifacts/rgb_dilated_mask_experiment --output artifacts/independent_reviews/rgb_dilated_mask_training_v1/run_FRESH

The CLI snapshots the audit sources in run_FRESH/source and writes receipt.json
only if every check passes. A failure preserves failure.json and traceback.txt.
It never edits BANK_FREEZE, COMMON_PADDING_FREEZE or acceptance flags. Root
records any acceptance separately in AUDIT_ACCEPTANCE.json, pinning the original
freezes and independent receipt. No QUALITY_INPUT_FREEZE or accepted flag is
required to run this audit, avoiding an acceptance/dependency cycle.

The freeze schema follows the V27 numeric fields: run_training_v1/BANK_FREEZE.json
binds training_summary.json, the full training file membership, and success
counts; run_plan_v1/COMMON_PADDING_FREEZE.json binds that bank freeze, its full
plan membership and common_padding_plan.json. Original internal-audit records
may be read as evidence but are never imported or treated as the independent
decision. If the future runner intentionally changes this schema, the audit
must be adjusted explicitly and its synthetic suite rerun before real use.

Limits: serialized numeric validation does not independently reproduce feature
extraction from pixels, failed intermediate features, image hash correctness,
SIMD memory safety, full native/Python execution provenance, accuracy, speed,
or industrial generalization. The source seam and recorded counts do not
cryptographically prove how an already serialized bank was produced.

Historical synthetic runs are retained:

- tests_red_20261022: six expected failures among eight new requirements on the
  copied predecessor audit (duplicate/incomplete union, missing object/arm,
  missing protocol/seam/inherited-reader checks).
- tests_green_20261022_a: 24 synthetic tests passed after the first adaptation.
- tests_red_20261022_b: one expected failure when malformed CSV row-width
  rejection was newly required. Its stdout/stderr were captured, but that run
  did not preserve a separate historical source snapshot; no such snapshot is
  claimed retroactively.
- tests_green_20261022_b: all 26 tests passed, including a source-only check of
  the actual prepared protocol, private/control source bytes and mask seam.
  That test does not read any real serialized bank.
- tests_green_20261022_c: all 26 tests passed on the final audit sources after
  adding explicit before/after input-pin records; source bytes remained
  unchanged and all five ORIGIN parent-source pins were rechecked.

No real bank, image, matcher or native compilation was used in those runs.

The original audit.py and its historical test sources remain frozen. audit_v2.py
is the explicit schema successor recorded in ORIGIN_V2.json. The actual
run_training.py writes training_audit.json before collecting BANK_FREEZE.files;
v1 wrongly excluded that member from its expected set. v2 requires the runner
validation file to exist, appear in files, and match its frozen SHA and size.
It compares the full training member set, excluding only the root BANK_FREEZE
and .gitignore files. The runner's validation is numeric evidence and is never
treated as independent acceptance. No accepted flag or quality freeze is added.

tests_v2_red_20261022_a executes the frozen v1 membership statements, isolated
from its audit function with Python AST, on a temporary literal directory. The
actual-runner schema produces the expected single test failure. The source,
stdout, stderr and receipt are retained. tests_v2_green_20261022_a then runs all
35 tests in a fresh interpreter, binding the original tests' audit import to
audit_v2. All pass, including nine schema tests for required audit inclusion,
omissions, corruption before and after validation, surplus and duplicate members,
and paths outside training. Original audit.py retains SHA256
43f6cf5329cfeaca6560185cd7f9dce4de04057e626f72f5f9991d0223b31d63.
These successor tests read only synthetic numeric fixtures and the existing
source/protocol seam; they do not read real training banks or execute native code.
