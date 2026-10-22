# V2 fixed direct16 cache experiment

The fixed direct-mapped cache did not outperform the frozen linear16 control
across this test set. Keep V2 isolated and off by default; these results do not
justify replacing linear16 or changing a production default. Both cache
policies reduce the search time of the eight LED fixtures substantially, but
neither consistently helps the sixteen T-LESS development images. This cache
experiment establishes no accuracy improvement and includes no magnet image.

## What changed

The only algorithm change from the frozen V18 linear16 control is the cache
header: sixteen direct-mapped slots with a fixed generic unsigned32 hash, full
signed x/y key equality, validity bits and the complete saved local winner.
Collisions execute the entire original local search, then replace the slot.
Each worker resets its cache per template/pyramid level; eligibility is still
level zero with multiple candidates. Capacity, hash, features, banks,
thresholds, padding and image-specific policies were not tuned.

Exact V11 is commit `b25df46f6ddf9c24fb43f5836f1414dc38c8caed`.
The V2 origin manifest SHA256 is
`5d7db6ed5b8e8d43a2b4adf3d3a857c7fa979193cf8494ccf8abf94d497a08f2`.
The seven direct core files remain byte-identical to the frozen linear
control. Diagnostic instrumentation is separate and absent from the benchmark.

## Correctness and measurement scope

The literal genuine RED/GREEN and core/flags/lifetime matrix passed before
measurement: 6609 matcher calls and 5504 complete ordered comparisons.
The comparator checks class, x/y, template ID, float32 score bits, order and
vector length. This shows equivalence on the exercised routes; it does not
measure detection recall or precision.

The single uninstrumented timing run used the same 25 fixed inputs: LED8,
case1, and sixteen T-LESS development images. Every variant loaded the same
immutable banks (900/361/2212 templates). Five cases were exact V11,
linear16 off/on and direct16 off/on. Each case/image had cold1, warm2 and
measured15, with independent retained workspaces and a fixed balanced order.
The actual cold V11 output supplied the oracle, without extra matcher calls.

The run passed with exactly 2250 calls, 450 per case, and 1875 formal measured
rows. All complete ordered outputs matched. Source, input, dependency,
compiler/runtime, build and executable pins remained unchanged. OpenCV used
one thread; OpenMP used four, dynamic disabled, passive waiting and one active
level. No additional timing repetition or image decode was performed for the
summary or independent arithmetic review.

## Relative search and total time

Ratios below are numerator time / denominator time, so less than one is
faster. Each image contributes the median of its fifteen same-round ratios.
The set median and geometric mean give every image equal weight. These are
descriptive values from one local run, without a significance claim.

| Numerator / denominator | Search median | Search geomean | Search slower images | Search worst ratio | Total median | Total slower images |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| direct on / direct off | 0.987631 | 0.828374 | 11/25 | 1.148021 | 0.996630 | 12/25 |
| linear on / linear off | 0.994834 | 0.822131 | 12/25 | 1.075630 | 0.981691 | 11/25 |
| direct on / linear on | 1.010188 | 1.007890 | 15/25 | 1.123625 | 1.037551 | 19/25 |
| direct off / linear off | 1.008965 | 1.010768 | 14/25 | 1.142420 | 1.005572 | 18/25 |
| linear off / exact V11 | 0.964167 | 0.979678 | 10/25 | 1.122236 | 0.978663 | 10/25 |
| direct off / exact V11 | 0.963577 | 0.970556 | 9/25 | 1.117135 | 0.981303 | 9/25 |

Direct on / linear on has a search median of 1.010188 (1.02% slower) and a
total median of 1.037551 (3.76% slower). Its worst search case is LED_6 at
1.123625 (12.36% slower). Direct on / direct off is worst on tiny_s5_i127 at
1.148021 (14.80% slower); its worst total ratio is tiny_s2_i446 at 1.153704
(15.37% slower). Every per-image ratio and regression remains in `summary.json`.

| Search comparison | LED8 median | case1 ratio | T-LESS16 median |
| --- | ---: | ---: | ---: |
| direct on / direct off | 0.524305 | 1.018405 | 1.012165 |
| linear on / linear off | 0.533256 | 1.068487 | 1.024489 |
| direct on / linear on | 1.037677 | 1.010188 | 0.989102 |
| direct off / linear off | 1.005445 | 1.077794 | 1.005968 |

Direct cache activation cuts the LED search paired median by about 47.57%,
with a similar 46.67% reduction from linear cache activation. This benefit
does not transfer uniformly: direct activation has a T-LESS search median
of 1.012165 and total median of 1.021701. The overall geometric mean is pulled
down by the LED benefit, while the overall image median is close to one.
Both are retained to expose that distribution.

For scale, the independent review also computes the following descriptive
means of each image's absolute time median. These absolute means are not used
as denominators for the paired ratios above.

| Group and stage, ms | Exact V11 | Linear off | Linear on | Direct off | Direct on |
| --- | ---: | ---: | ---: | ---: | ---: |
| LED8 search | 25.775 | 25.898 | 13.450 | 26.119 | 13.912 |
| LED8 total | 37.715 | 37.101 | 24.401 | 37.598 | 26.148 |
| case1 search | 2.378 | 2.237 | 2.391 | 2.511 | 2.524 |
| case1 total | 18.851 | 18.085 | 17.684 | 18.633 | 18.813 |
| T-LESS16 search | 16.459 | 15.799 | 16.055 | 15.903 | 16.160 |
| T-LESS16 total | 27.624 | 26.782 | 27.217 | 26.901 | 27.752 |

Off paths differ too, so the enabled comparison cannot isolate cache lookup
cost from code-layout, scheduling, thermal and other local-run effects.
Preprocessing is algorithmically unchanged yet direct on / linear on has a
preprocess paired median of 1.060642, and direct off / linear off has 1.016743.
These observations limit attribution; no post-hoc normalization is applied.
The V11 and linear adapters copy result vectors inside adapter-wall timing,
while direct uses native results. Internal search remains the primary algorithm
comparison, and adapter-wall figures keep that limitation.

## Saved evidence and independent review

All benchmark evidence is under
`benchmark_20261022_012041_421590/`:

| File | SHA256 |
| --- | --- |
| result.json | `f6094fa8db3977aad06f531a623c3e88ac28e28d9c0bd25d66819aa6ce2d621d` |
| samples.csv | `b8ce6d2fc8206ebc8a13bed4c73ea3fe336f4082132bdda17d6217ead716c2f8` |
| summary.json | `58285cdedce84100e378081d9f81d208f67c982652f04e209df3670c78c233af` |

The benchmark executable SHA256 is
`f2a9e70da205726b638a3c865dfb00ac07c8ff7c9d9093ed0bf6dfeb5eebc3c4`.
Its build manifest SHA256 is
`767657b9bbe1b2759d9b28dc0a769d156f6b1ff51b1d12ee5769ce09bb67b206`.

Root review receipts under
`artifacts/independent_reviews/direct16_correctness_v2/` are:

- `root_review_all_stages_20261022.json`: all three native correctness stages.
- `root_benchmark_build_review_20261022.json`: exact build recipe and 4011 pin
  occurrences, zero matcher calls or image decodes in the review.
- `root_benchmark_arithmetic_20261022.json`: independent reconstruction of all
  2250 routes/1875 formal rows, all nine absolute metrics, six comparison pairs
  and four ratio metrics, matching the summary. Zero matcher calls or image
  decodes in the review.

These local receipts do not attest every OS/linker/loader read. The separate
full-compute diagnostic remains source-only and unexecuted; it can explain
locality later but cannot supply timing evidence or tune this fixed experiment.
