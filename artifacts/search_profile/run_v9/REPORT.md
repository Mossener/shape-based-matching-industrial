# Search composition profile

This is an instrumented composition diagnostic. All stage intervals inside template workers are summed elapsed intervals; they are neither serial wall time nor process CPU time. Percentages use only the five worker stages as their denominator. Final sort/unique and search wall use serial elapsed time and are reported separately.

All fixtures passed exact semantic-set and raw-count checks against current production code before profiling; every collected call rechecked those comparisons. Strict sets are retained separately for equal-score template tie review.

| Dataset | Coarse similarity | Candidate collect | Local similarity | Local argmax | Local filter | Search wall median | Sort median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LED | 1.57% | 0.61% | 92.48% | 5.24% | 0.11% | 36.380 ms | 0.020 ms |
| case1 | 68.49% | 20.12% | 10.65% | 0.47% | 0.18% | 1.773 ms | 0.003 ms |

Dataset rows equally weight image-level medians; LED and case1 are kept separate. These descriptive summaries do not estimate confidence intervals.

| Dataset / image | Coarse candidates | Local calls | Zero tail scanned | Wrapped prefix scanned | Zero-tail candidates | Wrapped candidates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LED/1.bmp | 10484 | 20782 | 10.84% | 7.08% | 0 | 0 |
| LED/2.bmp | 12533 | 25016 | 10.84% | 7.08% | 0 | 0 |
| LED/3.bmp | 10917 | 21675 | 10.84% | 7.08% | 0 | 0 |
| LED/4.bmp | 12764 | 25048 | 10.84% | 7.08% | 0 | 0 |
| LED/5.bmp | 13642 | 27179 | 10.84% | 7.08% | 0 | 0 |
| LED/6.bmp | 17772 | 35501 | 10.84% | 7.08% | 0 | 0 |
| LED/7.bmp | 13703 | 27404 | 10.84% | 7.08% | 0 | 0 |
| LED/8.bmp | 14416 | 28563 | 10.84% | 7.08% | 0 | 0 |
| case1/case1 | 123 | 123 | 33.40% | 18.91% | 0 | 0 |

The coarse scan covers H×W entries. Kernels zero that whole map but accumulate only the prefix `span_y*W + span_x + 1`. Tail entries therefore remain zero; geometrically invalid row-wrapped origins occur inside the accumulated prefix. Removing the latter can change existing output and needs a separate correctness decision.

Timer calls, per-template vectors, counter bookkeeping and candidate-region census add overhead. Kernel timings include map allocation/zeroing and any conversion, not just SIMD adds. Per-candidate timings perturb short argmax operations proportionally more. Instrumented search wall is not an optimization speedup result. Validate any proposed kernel change with the uninstrumented benchmark and existing equivalence suites.
