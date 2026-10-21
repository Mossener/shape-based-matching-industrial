# Object-8 full-bank minimum padding experiment

This isolated experiment compares the frozen V11 object-8 baseline with enough
right/bottom padding to make its complete existing bank geometrically feasible.
It keeps all 3,456 templates, scales 0.75/1/1.5/2, 30-degree rotations, T=[4,8],
matcher/post threshold85 and the same GT/NMS rules. No production core or public
evaluator source is changed. The protocol does not enable a coverage gate.

`PROTOCOL.json` is fixed before image evaluation. Its SHA-256 is
`ab9207f2dd492622aed8f563997b00ca6d137d5c93fa0f2c99b67f7ec756573d`.
`frame_schedule.json` fixes eight pilot frames, all 400 development frames and
64 balanced per-scene timing frames. `preflight_plan.json` records the numeric
full-bank derivation. Dataset, bank, baseline config/provenance, public build,
geometry and evaluator inputs have fixed SHA values in the protocol.

## Why the proposed size is 848x800

The current 720x540 input becomes 848x672 with left/top64 and right64/bottom68.
Across the complete bank, the largest declared L0 width and height are734;
nonempty refinement intervals require each affected dimension to be at least
734+16*4=798. At L1 the largest actual feature coordinate+1 is368. Thus the
coarse requirement in original-resolution units is736. The common alignment
is lcm(4,2*8)=16. Keeping at least the old total dimensions yields848x800.

Left/top remain64; right remains64; bottom becomes196. The padded pixel area
grows by19.05%. The final source origin and grid phase remain fixed. This does
not imply identical candidates: a formerly infeasible placement or a changed
search extent can change coarse/refined candidates and NMS.

The historical geometry report records630 invalid template levels under its
declared-extent fit flags. The stricter new scan also checks actual maximum
feature coordinates+1 and finds634: 412 refined layers and222 coarse layers.
Four additional L1 cases, IDs566/951/999/1005, have declared height336 and an
actual feature at y336 in a level of height336. A coordinate equal to image
height is outside that image; it requires height337. The old report and its
630 figure remain unchanged. The proposed848x800 satisfies all6,912 declared
layer/actual-feature constraints. This is a geometric statement, not a proof
of physical SIMD tail-read safety or an empirical recognition result.

`static_validation.json` was generated with:

```powershell
py -3.10 artifacts/obj8_padding_experiment/validate_plan.py --output artifacts/obj8_padding_experiment/NEW_static_validation.json
```

The check hashes all15 fixed inputs and both plans, scans all layers, verifies
40 hand-derived boundary/alignment/coordinate assertions and rejects11 invalid
or over-budget cases. It reads no image, invokes no compiler/matcher and does
not load the native bank. Runtime must repeat the scan on the actual loaded
bank and compare it with this derivation before matching.

## Fixed comparison and budgets

The pilot runs both padding arms and both fallback/fused paths on the same
eight frames (32 match calls). Fresh baseline outputs must exactly equal their
old same-padding raw cache, including float32 score bits. Auto versus baseline
candidates may differ. Pilot correctness/resource checks, not a positive
accuracy trend, decide whether full development can run.

Full development runs both core paths with the new padding on all400 frames
(800 calls), comparing with the already preserved fixed baseline only after
all source/bank/image/raw identities are reverified. No new-padding candidate
is read from an old-padding cache. Every fresh raw candidate is retained.

The separate timing stage uses64 predetermined frames, one warmup and seven
measured rounds for both padding arms/core paths (2,048 calls). It rotates the
four variants per round and reports all samples, paired differences, medians
and p95. Input is decoded before the timed external call; that call includes
new border allocation/copy, matching, canonical filtering/NMS and coordinate
conversion. Bank loading and decoding are reported separately. Single quality
calls do not establish a speedup.

The maximum is2,880 match calls. Resource limits include1,048,576 padded pixels,
2,048 pixels per axis, a512MiB conservative dynamic-memory estimate, 1.5GiB
process peak RSS, one million candidates per frame/variant and512MiB new raw
outputs. Stage wall-time limits are10/60/30 minutes for pilot/full/timing. On
overflow or budget failure, preserve incomplete evidence and stop; never
truncate candidates, change thresholds/bank, or count unfinished frames as
negative detections.

Runtime resource limits are checked between matcher calls or completed frames.
They are soft checkpoint limits: a single native matcher call cannot be
interrupted by this adapter. No hard watchdog or different time allowance is
silently substituted. Bank loading and image decoding have separate diagnostic
fields and are excluded from the timed external call.

Report allGT and eligible TP/FP/FN, precision/recall/F1/mean IoU, every scene,
negative-frame errors, lost/new baseline GT IDs and exact original TP detection
retention. Do not interpret a total TP change as the number of old positives
lost. Geometry restoration, quality and timing are separate findings.

## Execution ordering

Execution is complete under the fixed protocol. The planner demonstrated a
compiled semantic RED, then465 assertions,15 invalid-case rejections and seven
independent semantic RED mutations. An initial environment compile failure and
the first GREEN compiler diagnostic remain preserved separately; neither is
reported as a semantic RED. The adapter then passed its synthetic border/origin
and gzip integration check. Both pilot and full quality gates completed before
the64-frame paired timing stage. The experiment used all2,880 declared calls.

See `RESULTS.md`, `independent_audit_attempt1.json` and
`audit_mutation_fixtures/validation.json`. The new padding restored geometric
feasibility but produced no quality gain on these400 development frames and
increased paired external-call time. It is not promoted to a default.

The independent audit imports no C++ evaluator or adapter implementation. It
reconstructs boxes, NMS, GT assignment, retention, geometry and timing summaries
from preserved numeric bytes. It reads no image and performs no matcher calls.
Its11 preserved corrupted-input fixtures all reject. A fresh numeric audit can
be run without repeating the native image stages:

```powershell
py -3.10 artifacts/obj8_padding_experiment/audit_results.py --pilot artifacts/obj8_padding_experiment/run_obj8_pilot --development artifacts/obj8_padding_experiment/run_obj8_full400 --timing artifacts/obj8_padding_experiment/run_obj8_timing64 --output artifacts/obj8_padding_experiment/NEW_independent_audit.json
```

No heldout image or reserved object25/29 belongs to this experiment. No default
changes follow from development results without separate independent review.
