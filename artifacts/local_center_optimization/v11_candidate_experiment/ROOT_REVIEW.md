# V18 private cache experiment review

The production core stays at V11. The private sixteen-entry cache preserves
complete local winners and recomputes every miss, including full-cache misses.
Root read the candidate diff and header: the cache is worker owned, reset at
each template/level, keyed by the existing post-clamp signed integer quotient,
and gated to the final level with multiple candidates. No candidate is dropped
or reordered, and score, raw value and winning row/column are copied together.

Root freshly ran `audit_correctness.py` against the three executed stages.
It checked 113 source/input/build/executable files, 2880 CSV comparisons,
all 128 flag combinations and the 23 exact V11 Git files. The report is
`root_fresh_correctness_audit_20261021.json`; no matcher was rerun. The 3985
original calls and their direct ordered comparator remain the correctness
evidence. Successful CSV rows do not preserve every match record separately.

Root then freshly ran `summarize.py` on the completed 1350-call benchmark.
`root_benchmark_summary_20261021.json` verifies the actual compiler/runtime,
source, protocol, build, executable, correctness-gate and CSV closure. The
root used Python 3.10; rounding differences of about one last-place unit in geometric-mean arithmetic
can change the summary JSON hash relative to the worker's Python runtime.
Raw timing bytes, per-image medians, pairing and regression identities agree.

The additional `audit_numeric_benchmark.py` imports no summary implementation.
It independently recomputes all 1350 sample pairings and case rotation, each
image's absolute median and all fifteen ratios for each comparison, global
image-median/geometric means and regression lists. Its result is
`root_numeric_benchmark_audit_20261021.json`. It does not independently
recompute the summary's p10/p90/min/max or no-gain list; the complete-closure
summary validates order positions in 0..2. Native pinned comparator assertions
provide output equality, since timing CSVs do not store every output record.

Descriptive dataset groups, using the arithmetic mean of each image's measured
median in milliseconds, show the practical split:

| Group | Off search | On search | Off internal total | On internal total |
| --- | ---: | ---: | ---: | ---: |
| LED8 | 25.0407 | 13.4614 | 36.8619 | 25.7140 |
| case1 | 2.9881 | 2.4044 | 23.9685 | 23.9125 |
| tiny16 | 15.2188 | 16.1171 | 26.7344 | 27.6370 |

These are descriptive group summaries, not new acceptance criteria. Paired
on/off ratios are calculated independently of ratios of absolute medians.
Median paired total ratios across group images are 0.68656/0.98958/1.05306
for LED/case1/tiny respectively. Across all 25 images, the search/total
image-median ratios are 0.99775/0.99907, and twelve images regress in each.
The worst search/total ratio is 1.14644/1.13020. One run cannot establish that
case1's small total change is a repeatable improvement or remove scheduling,
thermal and code-layout effects; candidate off also differs from exact V11.

Keep the cache private and explicitly disabled by default. A new experiment
may examine cheaper lookup with complete collision fallback. Do not select
capacity, thresholds or image/object-specific enablement from this run.
This version establishes no recognition accuracy, memory or industrial
deployment gain. No heldout scene or reserved object is decoded or matched.
