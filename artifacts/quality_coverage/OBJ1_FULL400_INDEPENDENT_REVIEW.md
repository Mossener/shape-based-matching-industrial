# Independent review: expanded object 1, 400 development frames

`audit_coverage_result.py` exited 0 against the frozen
`run_20261021_obj1_full400_coverage` output. Evidence is
`obj1_full400_coverage_independent_audit.json`; the script SHA is
`165f22f7a5282a201ede1fa1ef1bc63e35b85df64573a1572934a318d1da52c3`.

This is the same image-free numeric procedure described in
`TINY_ACTUAL85_INDEPENDENT_REVIEW.md`. It verified every output SHA before/after
streaming, seven frozen source files, all 800 fallback/fused raw archives and
78,600 candidates per variant, 2,153 template records, 3,414,126 dense points,
63,825,092 full point queries and the complete three-policy NMS/GT evaluation.
It independently reproduced each selected original field, label, retention
count and lazy-work counter for all 400 frames and every policy. It did not
open RGB/mask files, decode images, invoke coverage or match, or repeat actual
pixel-to-edge support computation. The earlier runtime assertions and synthetic
oracle tests are separate evidence for those operations.

| Policy | TP | FP | FN | Precision | Recall | Original GT retained | Original TP detection retained | Negative FP | Negative frames with FP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 37 | 7,842 | 13 | 0.470% | 74% | 37/37 | 37/37 | 6,874 | 350/350 |
| V >=0.50 | 37 | 7,782 | 13 | 0.473% | 74% | 37/37 | 37/37 | 6,825 | 350/350 |
| V >=0.65 | 37 | 6,397 | 13 | 0.575% | 74% | 37/37 | 36/37 | 5,640 | 350/350 |
| V >=0.80 | 32 | 1,195 | 18 | 2.608% | 64% | 31/37 | 19/37 | 962 | 286/350 |

AllGT has 50 targets in 50 positive frames. The eligible visibility subset has
49 targets; it has the same TP/FP and one fewer FN for each policy. The table
above uses allGT, not a mixture of the two denominators.

V >=0.65 retains every baseline-covered GT but replaces one original TP
detection. V >=0.80 retains only 31 of the 37 old GT, adds one previously
uncovered GT, and retains only 19 exact original TP detections. Consequently,
the total TP difference of -5 hides six lost old GT and one newly covered GT.
The retained original GT measure and the retained detection identity measure
answer different questions and must both remain visible.

The independent lazy counts are respectively:

| Policy | Attempted | Skipped by accepted NMS | Point queries |
| --- | ---: | ---: | ---: |
| V >=0.50 | 7,946 | 70,654 | 5,429,414 |
| V >=0.65 | 10,175 | 68,425 | 6,976,015 |
| V >=0.80 | 46,504 | 32,096 | 32,335,340 |

The fixed experiment demonstrates the same limitation on a larger slice:
the strict gate removes many FP but loses old positives, while the middle
gate retains GT recall and still leaves 6,397 FP, including errors on every
target-negative frame. It does not establish a production-ready acceptance
rule. All three predeclared policies are reported; this review chooses no
new threshold and changes no default.

No paired end-to-end performance benchmark is present. Lazy query reductions
are work counts, not measured speedups. The source reconstruction and padded
evidence-domain limitations in the tiny review apply here as well. This is
development data, not a heldout or industrial deployment accuracy estimate.
