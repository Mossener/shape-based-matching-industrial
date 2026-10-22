# V28 numerical diagnosis of V27

The full replay in `run_20261022_b` passes. It validates 4,800 frame/arm
combinations and both raw paths, including all negative frames. The verified
control/treatment raw counts per path are 457,279/150,247; complete selected
counts are 42,327/10,202, with TP 215/183 and FP 42,112/10,019. No new matching
or image access occurs.

| GT stage | RGB control | RGB empty mask |
| --- | ---: | ---: |
| Matched | 215 | 183 |
| No saved raw hit at IoU ≥0.5 | 162 | 207 |
| All raw hits suppressed by NMS | 23 | 10 |
| Surviving hit assigned to another GT | 0 | 0 |
| Total GT identities | 400 | 400 |

The unchanged cross-arm identities are 156 retained, 59 lost, 27 gained and
158 detected by neither arm. The net 32-TP decrease comes from 59 losses and
27 gains.

| Cross-arm group | RGB control stage | RGB empty-mask stage |
| --- | --- | --- |
| 156 retained | 156 matched | 156 matched |
| 59 lost | 59 matched | 53 raw gaps, 6 NMS losses |
| 27 gained | 16 raw gaps, 11 NMS losses | 27 matched |
| 158 neither | 146 raw gaps, 12 NMS losses | 154 raw gaps, 4 NMS losses |

For the six treatment NMS losses inside the lost group, every direct first
blocker is an all-GT FP. These identities are `(object, scene, image, gt)`:
`(1,7,166,0)`, `(1,7,219,0)`, `(1,7,239,0)`, `(2,12,221,1)`,
`(2,12,249,1)`, `(12,6,145,4)`. Their 27 suppressed-hit edges are preserved
individually. This is an identity-level observation, not a proposal to tune
those objects or scenes.

Across all ten treatment NMS-loss GTs, 40 suppressed-hit edges have FP first
blockers. Among the 23 control NMS-loss GTs, 22 have only FP first blockers;
one has both FP and TP blockers. Control NMS-loss edges contain 80 FP and 4 TP
blockers. All arms/groups together have 15,179 suppressed-hit edges: 15,030 TP
and 149 FP first-blocker labels. Most edges belong to GTs that were eventually
matched, so these edge totals cannot be used as recoverable-TP counts.

The next accuracy investigation should focus first on why valid raw hits
disappear: 53 of the 59 lost treatment identities have no saved hit before
NMS. A whole-bank feature-location comparison over all fixed training poses
can test whether the empty selection mask moves descriptors toward the crop
boundary/background or removes useful official-object features. The same
diagnostic must include control, treatment and the prior binary arm without
choosing per-object settings. These results do not establish that explanation;
they identify a falsifiable next investigation. NMS changes alone cannot
recover a candidate absent from the frozen raw output.

The evidence starts at score 85. A raw gap cannot distinguish a descriptor
mismatch, score just below threshold, coarse proposal pruning, or placement
failure. An exact blocker is provenance, not proof that removing it improves
net TP/FP. Assignment competition would not by itself prove maximum-matching
capacity loss. No accuracy benefit, industrial generalization or new detector
is claimed.

Sources were strengthened after run_b to assert the protocol constants and
recheck recorded algorithm-origin SHA pins; this does not alter classification
arithmetic. `tests_20261022_d` freezes the final source. A fresh root replay
can use the CLI in README and must preserve a separate output directory.

The root reran all 13 tests in `tests_root_20261022` and the complete replay
in `run_root_20261022`, both successfully. The latter binds the final source,
replays all 4,800 frame/arm combinations including negatives and both raw
paths, and reproduces every total and identity classification above. Explicit
zero-count categories are retained in its summary. These are numerical
rechecks of the original V27 outputs, with no image decode or matcher call.

The separately implemented standard-library review in `independent_review/`
recalculates all selected assignments and numeric frame totals, and replays
the fallback raw NMS for all 700 positive frame/arm combinations. Its raw
replay excludes negative frames and fused streams; the full diagnostic above
covers both. Fresh review receipts bind the saved and live sources as well as
every consumed numeric input, with before/after hashes. See that directory's
README for the exact coverage and reproduction command.
