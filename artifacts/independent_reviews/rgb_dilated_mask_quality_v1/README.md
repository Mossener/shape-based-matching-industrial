# Independent RGB dilated-mask quality audit

This is a source-prepared successor of the V27 independent standard-library
checker in rgb_empty_mask_quality_v1. ORIGIN.json pins all five predecessor
sources. numeric.py and the original nine-test test_audit.py are byte-identical
copies. The full raw parser, score-bit/order/multiplicity checks, metadata box
conversion, NMS and GT arithmetic are reused. No target trainer, native matcher,
quality evaluator, OpenCV or target Python helper is imported.

The explicit adaptations are the rgb_dilated_mask arm and retention schema;
new quality-input/closure/protocol bindings; separate accepted original
training/plan freezes and independent receipt; all 23 original/control/private
source members with the single per-layer official-mask erode-to-dilate change;
independent object/scene aggregates and object macro; and the V22/V27/current
GT identity cross-groups. The accepted marker does not modify either freeze.

The checker reads numeric evidence and source only. Its Reader refuses image
suffixes and dataset access except datasets/tless_expanded/index.json. It pins
the actual numeric index to the frozen closure and uses that index to rederive
GT geometry and visibility. Control metadata and serialized banks are pinned to
the inherited closure; accepted treatment and planner output files are checked.
It does not independently re-extract bank features from image pixels.

For development it requires the complete frozen native output inventory and all
2400 object-frame pairs, both arms, both full fallback/fused raw streams and
their manifests. That is 4800 arm-frame records and 9600 complete raw archives,
including empty streams. Candidate equality uses canonical ordered records,
exact float32 score bits and multiplicity. Official boxes use each arm's actual
metadata origin. Selected rows, allGT/eligible assignments and GT/pose retention
are recomputed, rather than accepting target labels or equality flags alone.

The policy is fixed: threshold 85, NMS IoU greater than 0.3, matching IoU at
least 0.5, eligible visibility at least 0.5. Eligible targets precede ignores;
each low-visibility target may ignore at most one remaining detection. AllGT
empty frames remain negatives and contribute FP. Per-frame, per-object,
per-scene, object-scene and pooled micro metrics are recomputed and checked
against the native summaries. Object macro is independently reported across
all six objects, including zero-denominator objects.

The same independently recomputed current GT identities are crossed with the
frozen V22 and V27 retention tables. The checker requires the historical allGT
four-stratum counts 148/67/59/126, eligible counts 147/62/56/109 and V27 allGT
retained/lost/gained/neither counts 156/59/27/158. It checks that the current and
V27 RGB controls preserve each historical RGB identity. Both allGT and eligible
results include per-object/scene cross-groups and explicit zero cells.

The fixed hypothesis is represented separately as result.quality_gate:
current treatment allGT TP >= 215 and FP < 42112, after checking the RGB control
baseline is exactly TP 215 / FP 42112. result.passed means numeric evidence
checks passed; it does not mean that hypothesis passed. A failed hypothesis
remains a valid reported experiment. No speed claim follows from this audit.

Run the source-only and synthetic suite from the repository root:

    python -B artifacts/independent_reviews/rgb_dilated_mask_quality_v1/run_synthetic.py --output artifacts/independent_reviews/rgb_dilated_mask_quality_v1/tests_FRESH

The runner snapshots its exact sources, retains stdout/stderr, and records
before/after source equality and the source-only repository path. Tests include
literal score/box/GT/NMS boundary oracles, every selected-field mutation,
missing/duplicate frame evidence, zero detections, metadata origins, image
refusal, acceptance binding, exact morphology change, negative/group summaries,
macro zero objects and changed/missing historical identities. The one source
test opens the prepared closure/protocol-related source and 23-member core seam;
it opens no real bank or quality output.

Retained preparation runs are tests_red_20261022_a (seven expected missing
successor requirements), tests_red_20261022_b (three expected aggregate/history
requirements), tests_red_20261022_c (one expected missing source-only entry),
tests_green_20261022_a (17 passing synthetic tests), and subsequent green runs
with 18 passing tests including the actual source-only seam. No native program,
image or new real quality output is used in these preparation runs.

After root authorizes a completed real development stage, use its exact freeze
path and a fresh output directory:

    python -B artifacts/independent_reviews/rgb_dilated_mask_quality_v1/audit.py --stage-freeze artifacts/rgb_dilated_mask_experiment/run_quality_development_v1/QUALITY_STAGE_FREEZE.json --output artifacts/independent_reviews/rgb_dilated_mask_quality_v1/run_real_FRESH

If the actual run directory has a different name, replace only the stage-freeze
directory argument. The current arm/path evidence comes from that freeze;
V22/V27 history uses their existing run_quality_development_v1 numeric tables.
The audit produces result.json, per_frame_audit.json,
historical_identity_strata.json and identities.csv. Failures retain failure.json.
All read evidence is rehashed before success. It never starts matching, changes
freezes, writes acceptance markers, tunes thresholds or promotes production.

Limits: this is replay of retained serialized and numeric evidence. It cannot
observe unrecorded native calls, independently prove feature extraction or SIMD
memory safety, validate image annotation correctness from pixels, establish
paired speed gains, or prove generalization to industrial/private/heldout data.
Source-only and synthetic success is readiness for a separately authorized real
numeric audit, not a claim that real quality results have been accepted.
