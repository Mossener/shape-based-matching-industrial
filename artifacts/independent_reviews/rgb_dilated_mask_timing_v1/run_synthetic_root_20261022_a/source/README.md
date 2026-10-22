# RGB dilation timing audit

`timing_audit.py` is a read-only, standard-library checker for the fixed RGB
dilation/control timing stage. It reads only frozen JSON, CSV and raw-manifest
numeric evidence. It rejects image/private suffixes, dataset traversal, missing
rows, changed hashes, duplicate or reordered calls, and output inventory drift.
It never imports the matcher, starts a native process, decodes images, or runs
Git commands.

The fixed scope is six objects, the 64 `timing=true` frames from the frozen
400-frame schedule, eight rounds, and four rotating variants per frame. Round
zero is warmup; the remaining seven rounds provide 2,688 formal samples per
variant and path, for 12,288 calls total. The audit validates route/order,
warmup flags, positive clocks, raw/selected count equality with development,
all four variants per frame, exact bank template counts, nearest-rank medians
and p95 values, same-round paired ratios, and equal-frame/equal-object
summaries. It also binds each timing-frame raw manifest and its gzip archive to
the development freeze and the completed independent quality audit by the
frozen SHA/size pins, without reopening raw gzip payloads.

The native summary retains the inherited JSON key `paired_empty_mask_over_rgb`.
For this experiment the native arms are `rgb_control` and `rgb_dilated_mask`,
so that key means **rgb_dilated_mask / rgb_control**. The audit preserves the
key in its validation and records the corrected interpretation explicitly; it
does not rewrite the frozen native summary.

After the coordinated timing stage is complete, run:

```powershell
py -3.10 artifacts/independent_reviews/rgb_dilated_mask_timing_v1/timing_audit.py `
  --stage-freeze artifacts/rgb_dilated_mask_experiment/run_quality_timing_v1/QUALITY_STAGE_FREEZE.json `
  --development-freeze artifacts/rgb_dilated_mask_experiment/run_quality_development_v1/QUALITY_STAGE_FREEZE.json `
  --output artifacts/independent_reviews/rgb_dilated_mask_timing_v1/run_real_unique_name `
  --cpu-slot-granted
```

The output directory must be fresh and inside this review directory. A timing
result is a speed-evidence audit only; the V30 acceptance record remains the
source of truth that the numeric quality audit passed while the accuracy
hypothesis and production promotion both remained false.

Only tiny synthetic checks should be run while native timing uses the CPU:

```powershell
py -3.10 artifacts/independent_reviews/rgb_dilated_mask_timing_v1/run_synthetic.py `
  --output artifacts/independent_reviews/rgb_dilated_mask_timing_v1/run_synthetic_unique_name
```
