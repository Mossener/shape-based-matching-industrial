# V30 quality and timing results

## Decision

The RGB official-mask dilation arm is **not promoted**. The independent numeric audit accepted the execution evidence, but the pre-registered accuracy gate failed: dilation produced 185 allGT true positives, below the required 215, although false positives fell from 42,112 to 10,461. No production default or industrial-generalization claim is supported.

## Accuracy evidence

The full development stage used 6 objects, 400 frozen frames, 2 arms, and fallback/fused path pairs (9,600 matcher calls).

| allGT metric | RGB control | RGB dilation |
|---|---:|---:|
| TP / FP / FN | 215 / 42,112 / 185 | 185 / 10,461 / 215 |
| precision | 0.50795% | 1.73774% |
| recall | 53.750% | 46.250% |
| F1 | 1.00639% | 3.34963% |
| mean TP IoU | 0.720582 | 0.744303 |

The dilation arm reduced false positives by 75.1591% and negative-frame false positives from 35,089 to 8,549, but lost 30 true positives and 7.5 recall points.

## Timing evidence

The fixed timing stage used 64 frozen frames, 6 objects, one warmup round and seven measured rounds: 12,288 native calls in total and 10,752 measured samples (2,688 per arm/path). Every call matched its frozen development raw reference exactly. Matching and external-call timings exclude image decoding and bank loading.

| arm/path | match median (ms) | match p95 (ms) | external median (ms) | external p95 (ms) |
|---|---:|---:|---:|---:|
| control / fallback | 32.5722 | 97.2542 | 32.7572 | 97.4878 |
| control / fused | 30.7185 | 85.8253 | 30.8767 | 86.1878 |
| dilation / fallback | 26.4578 | 91.2492 | 26.5836 | 91.3786 |
| dilation / fused | 25.4531 | 78.0461 | 25.5619 | 78.1205 |

The table uses the frozen native nearest-rank median and p95 definitions,
independently recomputed from all formal samples. It does not average the two
middle samples for an even-sized pool. The object medians below use the
conventional average of the two middle values; they are descriptive summaries
and are not the native pooled quantiles.

Paired dilation/control median ratios were 0.790239 for fallback and 0.805801 for fused, equivalent to lower median match time on this fixed benchmark. The ratio p95 values were 1.309281 and 1.316173, showing substantial long-tail variability; this is benchmark evidence only, not a general speed guarantee.

| object | control fallback/fused median ms | dilation fallback/fused median ms |
|---|---:|---:|
| 1 | 42.4944 / 41.3501 | 46.0020 / 43.3744 |
| 2 | 48.0009 / 44.9670 | 41.7457 / 40.4484 |
| 5 | 26.1481 / 24.7826 | 17.8307 / 17.6608 |
| 8 | 17.7297 / 17.1752 | 16.8822 / 16.9616 |
| 12 | 22.5470 / 21.7660 | 16.9311 / 16.6997 |
| 17 | 39.5314 / 35.8873 | 19.3623 / 20.1346 |

Object 1 is slower under dilation, so pooled timing does not establish a universal per-object improvement.

## Frozen evidence

- Development: [`run_quality_development_v1`](run_quality_development_v1/)
- Timing: [`run_quality_timing_v1`](run_quality_timing_v1/)
- Timing stage summary SHA256: `345d095baa99c18f71cb8ce7fbd188800c254e638aab8075939c014ab36e9f1b`
- Timing samples SHA256: `c5c25998a5c3a8aa79794b4624131c815f4bc55115562ba140bebfedf940883f`
- Timing execution provenance SHA256: `0c1587640ba41097e2bba4de4deec74eec41e95b10279e5e880ba141d5355872`

All timing freeze pins and before/after input verification passed. The timing reservation is single-use and its output is preserved.

Root independently ran 25 synthetic audit checks and the real timing audit in
`artifacts/independent_reviews/rgb_dilated_mask_timing_v1/run_real_root_20261022_a/`.
The real audit checked 12,288 timing rows, 10,752 formal rows and 1,568 input
pins. It did not decode images, start the matcher or reparse the timed calls'
unstored raw output payloads. Result SHA256:
`4f1b0b53cda22899be399b664145ed78d1451aa3ecaea70e1462898d481f5a2c`.
