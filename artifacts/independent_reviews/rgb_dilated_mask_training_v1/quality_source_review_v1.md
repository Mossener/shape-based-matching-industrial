# Independent static quality-source review

Reviewed on 2026-10-22 after the implementation agent froze the seven quality
sources. This review opens source and declaration/test JSON only. It does not
open real banks or images, compile, execute native code, run the quality stages,
accept their future results, or change any V27/V28 evidence.

The reviewed source supports the requested fixed development experiment. The
previous actual-bank byte-verification gap has been closed. No additional
algorithm factor was found in the quality adapter: quality_eval.cpp,
quality_support.hpp and quality_contract.py equal their V27 predecessors after
the declared experiment/namespace/error-text renames. The separate source-seam
review and v2 synthetic suite check the sole core erode-to-dilate change; this
document does not claim a quality or speed improvement before measurement.

## Reviewed bytes

quality_source_review_v1_pins.json records all 17 reviewed sources and source
dependencies before and after, the predecessor comparisons, contract literals,
and implementation test receipt pins. Its SHA256 is
98d31e9d6f4f9b4b8fbb0f24fdb38d28d202d22d116504a8faa831b576259c24.
The bytes were unchanged across the static checks. Python files were parsed
without importing their executable workflows. The seven primary files exactly
match tests_all_20261022_f/source. That retained implementation run reports
16 tests passed; this review inspected its result and stderr and did not rerun it.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| prepare_quality_inputs.py | 5156 | 6d8e66597ce854ccdb7dceafe862cffc31d6ab60d814c7208b079b4581dc7bab |
| quality_eval.cpp | 17844 | 4d88c28887a8cba26b58d56fc02c8364de34c1eb6b946ead5901f7f12e5c515f |
| quality_support.hpp | 10802 | 4400541896c9c46b7d31c333c996e2955492ca2d7b59964b7442a1759a313adc |
| build_quality.py | 6644 | 997724089d1814f0442c87ed2d56acc11ec2fa065f317c5330bb46f3055aa0a3 |
| run_quality.py | 9518 | 564f1ee60a0967d925275574011b567b8adc7600416566a7d3cebfda47f328f8 |
| quality_contract.py | 1719 | daf56c7a9dbbc050dcfc7e2aa03297736542d01ca6571fe0b0df7ce05f600a52 |
| quality_execution_inputs.py | 4753 | 898a6dcdbee3d80eb0511b69da92056d1eeb11d6877b11ba0861ff6f238b8fa0 |

## Input and actual-build closure

prepare_quality_inputs.build requires separate AUDIT_ACCEPTANCE.json with a
passing independent receipt and exact pins for the original BANK_FREEZE and
COMMON_PADDING_FREEZE. It retains the inherited RGB-control directories and
historical reference paths, uses run_training_v1/objN for treatment, and reads
treatment counts from the bank freeze. It never edits acceptance into either
original freeze. The quality input numeric pins bind the separate acceptance,
receipt, both freezes and runner validations.

quality_execution_inputs.verify expands the accepted training/plan files,
execution_files and reservation pins. It checks containment, duplicate members
and complete output membership. It additionally hashes all six inherited control
metadata/bank pairs against the original closure. old_gate also hashes every
scheduled historical fallback/fused raw archive and manifest. The actual dataset
index is pinned to the frozen index bytes. Scheduled RGB bytes are checked for
0/8/8/400/64 physical files for selftest/old_gate/pilot/development/timing.
No training image, development mask, private magnet/SMD image, held-out image,
or reserved object image is included by that fixed schedule.

run_quality invokes that complete check before and after native execution,
requires equal verification records, rechecks current scripts and build/input
pins, and rechecks previous stages. The Python byte verifier reports zero
decodes; that does not describe the C++ image decodes. C++ decodes once per
object-frame and reuses the decoded image across variants: 48 object-frames for
old_gate/pilot, 2400 for development, and 384 for timing.

build_quality compiles exactly private_v11/line2Dup.cpp and quality_eval.cpp in
two translation units, with the private core and unchanged frozen public
evaluation helpers. Each unit has precompile dependency pins compared to actual
-MD dependency bytes/list, followed by post-build pins for objects, dependencies,
project sources, compiler tools/link libraries and resolved runtime imports.
The five retained commands are two dependency queries, two compilations and a
link. The new supporting-source list includes source_contract.py and
quality_execution_inputs.py. run_quality also pins its transitive local Python
sources, including freeze_private_sources.py. This is source review of those
checks, not attestation of a future build's executable or runtime behavior.

## Fixed schedules and call budgets

| Stage | Objects x frames x arms x paths x rounds | Calls |
| --- | --- | ---: |
| old_gate | 6 x 8 x 1 x 2 x 1 | 96 |
| pilot | 6 x 8 x 2 x 2 x 1 | 192 |
| development | 6 x 400 x 2 x 2 x 1 | 9600 |
| timing | 6 x 64 x 2 x 2 x 8 | 12288 |

The total is 22176. C++ validates object order, exact frame counts,
object-frame totals and started matcher-call totals. schedule reads only the
development index, preserves every frame regardless of target-GT presence, and
checks frozen scene/image identities and RGB paths. selftest checks schedules
and synthetic numeric/raw/origin/padding behavior with zero matcher calls and
zero dataset-image decodes.

old_gate uses only the original RGB bank and original 848x672 padding
[64,64,64,68], comparing both paths against each historical raw reference.
pilot and development use both banks with common 848x832 padding
[64,64,64,228]. Development's pilot subset compares against that arm's own new
pilot archives. Arm-specific template origins map the official boxes back to
the shared source origin; no guessed equal treatment/control origin is used.

Each non-selftest stage has a persistent exclusive reservation. A failure keeps
partial evidence and the reservation, and cannot silently rerun the stage.
The runner requires the fixed previous completed stage and matching build/input
pins, and hashes all its files and checks complete native-output membership.
Unknown partial calls remain incomplete instead of being counted as negatives.

## Full candidate and accuracy evidence

Every quality matcher call retains the complete raw candidate vector. convert
uses deterministic canonical ordering; exactRows compares that full order,
multiplicity, class/template IDs, match coordinates, float32 score bits and
official boxes. It does not reduce candidates to top-K or merely compare counts.
Both fallback and fused full raw vectors are archived before equality failure
can abort the stage. Empty candidate vectors still receive valid archives.

The frozen writer records all rows with 17 significant score digits and a
raw_manifest with counts and compressed/uncompressed sizes. That manifest does
not itself contain a raw SHA; the Python stage freeze hashes both archive and
manifest files. The selftest checks full-field/score-bit roundtrip and empty raw
roundtrip. A candidate ceiling above 1000000 or total new raw output above 1 GiB
aborts without truncation or valid completed metrics.

Both paths must have identical raw and selected results. One selected vector per
arm is then written in full, with score bits, pose/training-image/angle/scale,
match coordinates, official boxes and allGT/eligible labels plus GT identities.
ground_truth.csv retains target GT identities, visibility and boxes.
per_frame_metrics.csv retains raw/selected counts, allGT/eligible TP/FP/FN/GT,
ignored counts, matched-IoU sums and negative FP. gt_retention.csv records both
arms' detection of each allGT/eligible identity and same-pose agreement if both.
Per-object, per-scene and pooled summaries are emitted.

The policies remain threshold 85, post-threshold 85, class-aware deterministic
NMS IoU greater than 0.3, matching IoU at least 0.5, and eligible visibility at
least 0.5. Eligible GT are matched before low-visibility ignores; each ignored
GT consumes at most one remaining detection and duplicates remain FP. A
negative frame means no target allGT, rather than no eligible GT. Empty-GT frames
remain in scheduling, evaluation and per-frame evidence, with negative-frame
counts, frames with FP and negative FP in the summaries.

## Timing and explicit reporting limits

Timing runs one warmup and seven measured rounds, rotating variant order by
(order+round)%4. It emits all 12288 timing rows, 2688 measured samples per variant
and 2688 treatment/control pairs per path. Both clocks exclude decode, bank
load, reference reads, raw archive writes and reference comparison. The external
clock includes padding, matcher, conversion, post-threshold and NMS. Every timed
raw vector is checked against that arm/path's complete development reference.
Timing retains counts and equality flags, not an archive of every timed vector.
Median/p95 use the inherited nearest-rank definition; ratios are treatment over
control for each paired object/frame/round/path, so less than one means faster.

The following inherited labels/limits must be explicit in later reports:

- contract.old_gate declares arms=['rgb'], while actual C++ output is
  rgb_control. Its one-arm call calculation is correct.
- The timing summary key paired_empty_mask_over_rgb is stale; its actual values
  are rgb_dilated_mask/rgb_control. CSV arm labels and ratio arithmetic are clear.
- The four historical identity strata are not directly grouped by native C++.
  Ground-truth and retention identities permit an independent numeric join to
  the frozen historical evidence; the final quality audit still must do it.
- PROTOCOL requires independent quality acceptance before timing. The runner
  enforces a completed development stage, not a separate quality-audit receipt.
  Root must keep timing authorization separate and wait for that audit.
- Retained source, JSON, counters and byte checks do not prove pixel-based
  extraction independently, SIMD safety, every dynamically loaded OS/plugin
  resource, industrial generalization, or absence of all possible native bugs.

This static review finds the requested bank/dependency checks, fixed counts and
complete quality evidence paths present in the reviewed sources. Actual build,
selftest, old gate, pilot, development and the independent output audit remain
root-owned execution work. No native quality outcome is asserted here.
