# Independent benchmark metadata ratio review

This review reread the completed six measurement records and recomputed both
ratio directions using PowerShell arithmetic only. No compiler, native
benchmark, Python process, image, dataset or real-input execution was run.
Previously fixed reports and all run receipts were left unchanged.

The earlier **5.853320790117911** figure is the median of paired
`baseline total / cached total` factors. It is not `cached / baseline`.
The coordinator's `cached total / baseline total` convention gives a median
of **0.1709649015043006**, approximately **17.0965%** of baseline total time
for this fixed artificial 256x256 workload. These figures do not measure
matcher, original-pixel or real-C0 end-to-end performance.

## All six rows, with explicit direction

Times are milliseconds; each total includes that path's full preparation
plus scoring. Untimed instrumented index timings are excluded from both.

| Round | Baseline total | Cached total | Baseline / cached factor | Cached / baseline proportion |
| --- | ---: | ---: | ---: | ---: |
| 0 | 196.7851 | 27.8209 | 7.073283035415820 | 0.141377065641657 |
| 1 | 139.2557 | 25.3654 | 5.489986359371427 | 0.182149815052454 |
| 2 | 143.3227 | 22.8727 | 6.266103258469705 | 0.159588816007513 |
| 3 | 145.1852 | 27.4761 | 5.284054141599427 | 0.189248628648099 |
| 4 | 193.5907 | 33.9803 | 5.697145110549347 | 0.175526510312737 |
| 5 | 163.0761 | 27.1364 | 6.009496469686473 | 0.166403292695864 |

No row was dropped. Sorted `cached / baseline` ratios are:

```text
0.14137706564165683
0.15958881600751310
0.16640329269586407
0.17552651031273714
0.18214981505245390
0.18924862864809910
```

The even-sized median averages the third and fourth ratios:

```text
(0.16640329269586407 + 0.17552651031273714) / 2
= 0.1709649015043006
```

The median baseline/cached factor separately averages
`5.697145110549347` and `6.009496469686473`, giving
`5.853320790117911`. The reciprocal of that averaged factor is
`0.17084319070437548`; it is slightly different from the median paired
cached/base proportions because reciprocation does not commute with averaging
the two middle values. Use **0.1709649015043006** for the coordinator's
cached/base median, rather than taking the reciprocal of the factor median.

For score-only intervals, the median paired cached/base proportion is
`0.08052361577168862`; the independently averaged baseline/cached factor
median is `12.424425678192963`. This score-only quantity excludes preparation
and must not replace the full-total ratio in a total-cost statement.

## Counts, timing regions and practical limits

Every round's actual lookup construction counts were pairs 256 to 1 and maps
512 to 2; membership-row insertions 1,310,720 to 5,120; referenced member
records 1,572,864 to 6,144; chain insertions 524,288 to 2,048. Member records are counted
via each indexed vector's size, not individual member-object traversal.
These counters concern the extra scoring lookup maps; shared canonical scene
factory work remains included in preparation for both paths.

The timed baseline calls original frozen v1. Counting and its index timer are
in a generated copy called after timing, with all 1,536 complete score/work
comparisons outside both measured regions. Whole process wall 2.125s includes
that untimed phase. No ratio was a native pass or production promotion gate.
The experiment establishes only synthetic lookup reuse and regression parity,
with no basis to project a real C0 runtime or image-quality improvement.

## Metadata pins and unchanged reports

| Reviewed file | SHA-256 |
| --- | --- |
| `native_compiled_scene_benchmark_v2/receipt.json` | `05365e9dc69596fa0b5841253cfda372b2e0aada13d53b11b746e293b33c353f` |
| `native_compiled_scene_benchmark_v2/benchmark_execution/stdout.txt` | `ea9a5884e41d58f2a33b89116c84d5c31f17294f2939f2f355d9e5ff5f19768d` |
| `NATIVE_COMPILED_SCENE_RESULTS_V2.md` | `d1a86137df2e77384e7ce30cec54c138ba30ee7257a6892d53cba43afe351a05` |
| `NATIVE_COMPILED_SCENE_BENCHMARK_RESULTS_V2.md` | `a818581480fdbb8cb4ebeac7bbad46c56bcdf1b74710c3c39ab79937df141480` |
| `STATIC_NATIVE_COMPILED_SCENE_REVIEW_V2.md` | `31c4828dc31c04f7765e4646ca7e8da7b6e6956e22b6b6265fe6fa4d8cafb4f6` |

The fixed benchmark report explicitly labels its direction `V1 total / V2
total`. Its factor calculation is correct. This separate review supplies the
coordinator's opposite-direction cached/base convention without rewriting
the fixed reports.
