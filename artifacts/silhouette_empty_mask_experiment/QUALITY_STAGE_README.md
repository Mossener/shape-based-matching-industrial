# Fixed development quality and timing stages

This is new work after the frozen V20 training/planning milestone. It uses
separate `quality_eval.cpp`, `quality_support.hpp`, `build_quality.py` and
`run_quality.py`; no completed training source/build/evidence is changed.

The static checks described below were the pre-execution gate. The
fixed stages later completed with 96 old-gate, 192 pilot and 9,600 development
matcher calls. See [QUALITY_RESULTS_V22.md](QUALITY_RESULTS_V22.md) and the
independent numeric audit for the actual quality result. The timing stage was
not run; no quality-stage speed claim is made.

`QUALITY_INPUT_FREEZE.json` SHA-256 is
`398a0185588e7d73a0a1cccdf62a3172e29861742de3475316680258585dc40c`.
It binds the fixed original closure, complete new training freeze, full-bank
common-padding freeze and root closure-bound training and plan audit receipts.
Its schedule is copied from the unchanged original input closure. Preparation
and static verification access numeric metadata only, without dataset images.

| Stage | Objects | Frames per object | Arms | Paths | Rounds | Matcher invocations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `old_gate` | 6 | 8 fixed pilot frames | RGB only, original padding | 2 | 1 | 96 |
| `pilot` | 6 | 8 fixed pilot frames | 2, common padding | 2 | 1 | 192 |
| `development` | 6 | all 400 | 2, common padding | 2 | 1 | 9,600 |
| `timing` | 6 | fixed 64 | 2, common padding | 2 | 8 | 12,288 |

The total remains 22,176. Before a matching stage starts, an exclusive-create
reservation persists under `quality_stage_reservations/`. Each stage can be
reserved once; a failure never silently reruns unknown/partial calls or turns
missing frames into negatives. Every prior stage must have complete outputs,
the exact same quality build and input freeze, expected call count and
before/after provenance. Native selftest is a separate zero-matcher stage.
Each invocation runs exactly the one root-authorized stage and then stops.

Native selftest checks all six object schedules, the actual common-padding
source origin, float32 sign-bit and ordered-row distinctions, a 2,048-row full
pose/box/score-bit gzip roundtrip and an empty archive. It checks arm-specific
actual `tl` in official-box conversion. It reads numeric index metadata but
does not decode any dataset image or call the matcher.

The original-padding gate compares all canonical ordered fields and score bits
against both preserved RGB paths. Subsequent stages retain complete raw gzip
archives for both arms and paths. Same-arm fallback/fused raw and selected
ordered fields must match; full development additionally rechecks pilot frames
against their own pilot archives. The only changes between quality arms are
training source and feature-selection-mask policy; shared 848×832 padding,
origin, thresholds, NMS, GT evaluation, feature extractor and matcher stay fixed.
No causal quality attribution is made to the mask argument alone relative to
RGB. No pilot gain selects parameters or objects.

Numeric outputs include per-frame allGT/eligible counts and IoU sums, selected
predictions with float score bits and training pose, GT identities/visibility,
per-object and per-scene summaries, negative-frame errors, and new/lost GT
identity records. Cross-arm pose retention compares object/view/angle/scale,
never numerical template IDs. Full raw archives allow a separate auditor to
recompute NMS, greedy counts and GT-subset DP diagnostics without trusting
native summary labels.

Every timing call is compared against its own full-development arm/path raw
reference. Each frame has one warmup and seven measured rounds; four variants
rotate by round. Samples retain object/frame/round/order/path identity. Native
summaries use nearest-rank median/p95 and paired binary/RGB ratios. External
call timing includes padding allocation/copy, matching, box conversion and NMS;
decode and per-arm metadata/bank load are separately recorded and excluded.
Timed calls archive counts and the native exact-content result; an independent
numeric clock/count audit alone cannot reconstruct each timed raw set.

Limits remain 2,048 per input axis, 2,097,152 pixels, 512 estimated bytes/pixel,
1 GiB estimated dynamic memory, 1.5 GiB peak RSS, one million raw candidates per
frame/arm/path and 1 GiB new raw output per quality stage (actual gzip and raw
manifest bytes). Soft checkpoints are 20/20/180/60 minutes by stage; a single
native call is not interruptible. A resource/content/provenance error preserves
partial output and the reservation and marks the stage incomplete. Output is
never silently truncated into valid metrics.

After a root static review and CPU assignment, commands are sequential:

```powershell
py -3.10 artifacts/silhouette_empty_mask_experiment/build_quality.py --output artifacts/silhouette_empty_mask_experiment/build_quality_v1 --cpu-slot-granted
py -3.10 artifacts/silhouette_empty_mask_experiment/run_quality.py --mode selftest --build-manifest artifacts/silhouette_empty_mask_experiment/build_quality_v1/build_manifest.json --output artifacts/silhouette_empty_mask_experiment/run_quality_selftest_v1 --cpu-slot-granted
py -3.10 artifacts/silhouette_empty_mask_experiment/run_quality.py --mode old_gate --build-manifest artifacts/silhouette_empty_mask_experiment/build_quality_v1/build_manifest.json --selftest-run artifacts/silhouette_empty_mask_experiment/run_quality_selftest_v1 --output artifacts/silhouette_empty_mask_experiment/run_quality_old_gate_v1 --cpu-slot-granted
```

Only continue to `pilot`, `development` and `timing` after their root CPU grant,
passing each prior run as `--previous-run`. Heldout images and reserved objects
25/29 remain sealed. No default promotion or industrial generalization claim
follows from this development experiment.

The completed run directories are immutable evidence. The first independent
full-audit attempt is also retained: it stopped at object 5 because the audit
assumed `selected_detections.csv.gz`, while that historical preservation copy
is plain `selected_detections.csv`. The auditor now resolves each copy from the
manifest and passed 17 synthetic serialization/provenance/NMS tests before the
pilot and development reruns. This correction changed only the independent
reader, not native outputs or metrics.
