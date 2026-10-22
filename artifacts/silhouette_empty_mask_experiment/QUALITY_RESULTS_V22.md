# V22: empty feature-selection mask quality comparison

This experiment is now complete on the fixed development split. The matcher,
thresholds, NMS rule, source origin and frame schedule stayed fixed. The two
new arms use the same 848×832 common padding: `rgb` is the original RGB bank
with common padding and `binary_empty_mask` uses the binary source with an
empty feature-selection mask. The retained V15 arm is the original RGB bank
at 848×672 and exists to isolate padding from training policy.

The native stages made exactly 96 old-gate, 192 pilot and 9,600 development
matcher calls. Every fallback/fused pair had equal complete ordered raw fields
and float32 score bits. The development run has 2,400 object/frame pairs, 42.4
MiB of compressed raw output and a recorded peak RSS of 164.5 MiB. These are
resource observations for this run, not deployment limits.

## Development quality

The independent auditor recomputed raw parsing, template metadata, source-origin
boxes, NMS, one-to-one GT assignment, visibility subset, negative-frame errors,
selected labels and all aggregate summaries from the saved numeric files. It
passed all six objects and 400 frames per object without importing the evaluator,
calling the matcher or opening image bytes.

| Arm | TP | FP | FN | Precision | Recall | F1 | Mean TP IoU | Raw | Selected |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V15 RGB, old padding | 215 | 42,098 | 185 | 0.5081% | 53.750% | 0.010067 | 0.72058 | 457,376 | 42,313 |
| RGB, common padding | 215 | 42,112 | 185 | 0.5080% | 53.750% | 0.010064 | 0.72058 | 457,279 | 42,327 |
| Binary source, empty mask | 207 | 11,882 | 193 | 1.7123% | 51.750% | 0.033149 | 0.73498 | 497,740 | 12,089 |

The common-padding RGB arm preserves all 215 all-GT true-positive identities
and their exact detection rows relative to V15. Its raw stream differs in 100
of 2,400 object/frame cases, while selected outputs differ in 15; the aggregate
TP/FN/recall stays unchanged. Padding therefore does not explain the training
policy result.

Relative to common-padding RGB, the binary arm reduces FP by 30,230 (71.8%)
and negative-frame FP by 25,160 (71.7%), while raw candidates increase by
40,461 (8.8%). TP decreases by 8 and FN increases by 8, so recall decreases
2.0 percentage points. Precision rises 3.37× and F1 rises 3.29×; mean TP IoU
rises from 0.72058 to 0.73498. The lower FP count is therefore accompanied by
a small recall loss, not a universal accuracy improvement.

Per-object all-GT counts show the tradeoff clearly:

| Object | RGB TP/FP/FN | Binary TP/FP/FN | RGB F1 | Binary F1 |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 37 / 7,842 / 13 | 28 / 6,382 / 22 | 0.00933 | 0.00867 |
| 2 | 69 / 10,978 / 81 | 97 / 2,807 / 53 | 0.01232 | 0.06352 |
| 5 | 22 / 2,196 / 28 | 29 / 1,920 / 21 | 0.01940 | 0.02901 |
| 8 | 1 / 68 / 49 | 5 / 211 / 45 | 0.01681 | 0.03759 |
| 12 | 36 / 4,665 / 14 | 19 / 275 / 31 | 0.01515 | 0.11047 |
| 17 | 50 / 16,363 / 0 | 29 / 287 / 21 | 0.00607 | 0.15847 |

The binary arm improves F1 for five objects and regresses object 1. It changes
the identity set: for all-GT matching the high-level comparison retains 148
GT identities, adds 59 and loses 67; only one retained identity has the same
training pose under the independent pose comparison. Numeric template IDs are
arm-local and are never used as cross-arm identity.

## Pilot and evidence

The fixed eight-frame pilot independently reproduces native totals: V15/common
RGB TP6/FP670/FN2 and binary TP7/FP224/FN1. It is retained as an early check,
not a parameter-selection or generalization result.

Primary native and independent evidence:

- Development freeze: `run_quality_development_v1/QUALITY_STAGE_FREEZE.json`,
  SHA-256 `ebcb78f1beb5c84d9921a0b3aa3e1a1a51b9fb0ef2f353ae77d7655581f80c91`.
- Pilot independent audit: `../independent_reviews/empty_mask_quality_v1/run_pilot_audit_20261022/result.json`,
  SHA-256 `b21d66a81edc1f8ce5a9e0e00ed1c1103fad06868506f817a5b4587457d85e5a`.
- Development independent audit: `../independent_reviews/empty_mask_quality_v1/run_development_audit_20261022_v3/result.json`,
  SHA-256 `38f9025da7c7320f2e42eb632381f9995c6718d64eaa40d7378e205d73047e68`.
- Independent quality source tests: 17 tests passed; the auditor source fixes
  a historical CSV-versus-gzip preservation-manifest mismatch. Both failed
  attempts (assuming gzip everywhere, then plain CSV everywhere) are retained
  and are not counted as passing evidence. The final auditor follows each
  preservation manifest's declared copy and verifies its exact bytes.

This is a six-object development evaluation, not a held-out-scene or industrial
acceptance test. Held-out scenes and objects 25/29 remain sealed. No timing
stage was run for this quality experiment, so the binary arm has no speed claim.
The result is archived for review; it does not promote the binary training
policy or common padding to the production default.
