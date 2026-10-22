# V31 shared-pool training progress

This experiment tests exact-budget pooled RGB sampling (P) and a fixed 50/50
contour-support/interior sampler (primary B) against the original official-mask
RGB control (C0). Both new arms consume one immutable candidate pool per pose
and layer. C0 is inherited without retraining. The production V11 core remains
unchanged. The frozen design and protocol define all decisions before quality
results; a passing P cannot replace a failing primary B.

## Observed native training

The single `run_training_v1` execution completed and its original runner
returned success. It saved 46 numeric files (690835424 physical bytes;
4182693421 logical bytes including the summary), with these native observations:

| counter | observed |
|---|---:|
| shared poses | 20736 |
| complete shared pools | 41472 |
| P/B attempt rows | 41472 |
| P/B layer-status rows | 82944 |
| grayscale RGB / mask imread calls | 432 / 432 |
| matcher calls | 0 |
| native peak working set | 64565248 bytes |

P and B report identical successful template counts in object order
`[1,2,5,8,12,17]`: `[3432,3456,3456,3456,3456,3456]`. The 24 unsuccessful
poses of object 1 remain in the complete attempts and both layer records.
These observations are not an independent regeneration of RGB gradients or
an accuracy measurement.

## Acceptance boundary

Literal sampler, collector, integration, packing and guarded-execution tests
have separate retained evidence. Full numerical acceptance reconstructs all
pool membership/strata, quotas, pairwise selections, crop arithmetic, complete
banks, official metadata and byte accounting. Root separately checks the
original build/runtime closure, training image allowlist and execution logs.

The first actual full audit reached final receipt serialization but failed
because its receipt directory was absent. It remains failed. The corrected
v2 audit is a distinct one-shot reservation over the same unchanged training
bytes. See `AUDIT_ENTRYPOINT_FAILURES.md`; neither audit failure nor successful
native training can be used as a quality acceptance.

At this checkpoint no development quality stage, timing stage, private
magnetic/SMD regression or production promotion has been performed for V31.
Public evidence export is gated on complete training acceptance and preserves
the original bytes losslessly. Held-out scenes and objects 25/29 remain sealed.
