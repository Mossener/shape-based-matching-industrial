# Six-object fixed baseline completion

The preregistered V11 actual85 development baseline is complete for objects
1, 2, 5, 8, 12 and 17. This extends the V13 evidence frozen through object8;
it does not alter that historical snapshot or its prepared protocol file.
The matcher core remains `b25df46f6ddf9c24fb43f5836f1414dc38c8caed`.

Each object was trained on the same fixed recipe: 72 official views,
3456 attempted templates, 32 requested features, angles every 30 degrees,
scales 0.75/1/1.5/2, T=[4,8], gradients 20/40, actual matcher threshold 85,
post threshold 85, NMS IoU 0.3 and GT IoU 0.5. Each object was independently
evaluated against all 400 development images. This means 2400 object/image
evaluations and 4800 matcher calls, not 2400 distinct images or a joint scan.

| Object | Successful templates | TP | FP | FN | Recall | F1 | Negative-image FP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2153 | 37 | 7842 | 13 | 0.74 | 0.009333 | 6874 |
| 2 | 2646 | 69 | 10978 | 81 | 0.46 | 0.012325 | 7511 |
| 5 | 3416 | 22 | 2196 | 28 | 0.44 | 0.019400 | 1965 |
| 8 | 3456 | 1 | 68 | 49 | 0.02 | 0.016807 | 63 |
| 12 | 3372 | 36 | 4665 | 14 | 0.72 | 0.015155 | 4169 |
| 17 | 3156 | 50 | 16349 | 0 | 1.00 | 0.006079 | 14494 |

AllGT micro totals are TP 215, FP 42098, FN 185, GT 400: precision 0.00508118,
recall 0.5375, F1=0.01006719 and mean TP IoU 0.72058214. Object macro F1 is
0.01318312. There are 35076 false detections on negative object/image
evaluations. This is an accuracy failure baseline, with no improvement claim.
Visibility>=0.5 results and exact source hashes are in
`baseline_summary_all_six.json`.

Objects 12 and 17 add 800 object/image evaluations and 1600 matcher calls after
V13. Their independent audits reconstructed all compressed raw candidates,
float32 score bits, metadata boxes, NMS, one-to-one GT assignment, visibility
ignores and total metrics. Their pilot and full numeric packages were also
checked by the independent preservation auditor. Original RGB and derived
failure PNG files are not copied into these packages; local raw evidence
remains untouched. All 2400 object/image evaluations have exact fallback/fused
candidate equality, which is regression evidence rather than an accuracy proof.

The 23 frozen MIPP/core files passed the recorded pre/post execution SHA checks.
Object 17 training finished successfully during an interruption; recovery
confirmed exit 0 and no residual process before continuing, without repeating
training. `dependency_checks_obj12_obj17.json` retains the real stage names
and explains the shared boundaries. The already committed dependency history
through object8 is unchanged.

All development PNG headers are 720x540, padded to 848x672 with L1=424x336.
Objects 12/17 have zero inapplicable declared geometry levels and zero actual
feature max+1 extents beyond their input level. Object 8 still retains 630
inapplicable declared levels, including 402 actual feature max+1 extents beyond
an input level; no template, scale or padding was changed. Geometry reports
do not prove complete physical fallback SIMD load safety.

Training wrapper wall times for objects 1/2/5/8/12/17 were respectively
6.713/7.682/12.435/39.710/9.462/19.747 seconds. Full400 wrapper wall times
were 54.493/57.511/47.860/30.556/55.510/69.106 seconds. These include integrity
verification and output work. Single-pass fallback-first matcher timings are
diagnostics, not controlled speed benchmarks; per-object values remain in
the numeric summary.

Heldout RGB was not decoded, viewed or matched, and objects 25/29 were not
trained or matched. Integrity verification may read sealed file bytes and
headers. Fixed parameters were not tuned from these baseline outcomes.
