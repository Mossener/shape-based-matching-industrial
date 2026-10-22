# V22 empty-mask lost-GT numeric diagnosis

This is a read-only diagnosis of the fixed V22 development evidence. It compares
the common-padding RGB arm with the binary empty-mask arm for objects
`1, 2, 5, 8, 12, 17`, using 400 development frames and 400 annotated GT
identities. It opens no dataset image, starts no matcher or native process, and
does not process held-out scenes or objects 25/29.

The independent development audit is pinned by SHA256
`38f9025da7c7320f2e42eb632381f9995c6718d64eaa40d7378e205d73047e68`.
The runner rechecks the preserved raw archives, selected detections, metrics,
ground-truth projection, and the audit output before and after the calculation.
The implementation and its fixed protocol are in this directory; the saved run
is `run_20261022_v1/`.

## What was isolated

The RGB-to-binary all-GT identity comparison is:

| Identity outcome | Count |
| --- | ---: |
| retained by both arms | 148 |
| RGB TP lost by binary | 67 |
| binary TP new relative to RGB | 59 |
| neither arm detects the identity | 126 |

For the 67 lost RGB identities, the binary arm has these mutually exclusive
provenance categories:

| Binary raw/NMS provenance | Count |
| --- | ---: |
| no binary raw candidate with IoU >= 0.5 | 57 |
| every binary raw candidate with IoU >= 0.5 suppressed by NMS | 10 |
| surviving candidate assigned to another GT | 0 |

The 10 NMS losses are directly witnessed by the saved blocker ranks. Each
blocker is a selected binary FP, with blocker IoU to the lost GT between
`0.4252` and `0.4952`; each valid overlapping raw candidate is therefore removed
by a higher-scoring candidate that is not a TP for that GT. The lost GTs have
between 3 and 186 overlapping raw candidates before NMS, with best raw IoU from
`0.6397` to `0.9175`.

The 57 no-raw losses have no candidate at or above IoU 0.5. Their best binary
raw IoU is at most `0.4961`. This is a statement about the saved candidate list
after the fixed matcher score cutoff of 85; it cannot distinguish a score below
85, proposal pruning, descriptor mismatch, or placement error.

The independent one-to-one capacity check agrees with this split at the arm
level:

| Arm | GT | Actual TP | Raw capacity | Selected capacity | Raw deficit | Raw-to-selected loss | Assignment loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RGB | 400 | 215 | 238 | 215 | 162 | 23 | 0 |
| Binary | 400 | 207 | 231 | 207 | 169 | 24 | 0 |

Thus GT assignment is not the cause of the 8-TP binary decrease. The binary
arm's additional seven raw-capacity deficits and one additional raw-to-selected
capacity loss are consistent with the identity diagnosis; capacity numbers are
not treated as seven or one guaranteed recoverable detections.

## Cross-object and cross-scene counts

| Object | Lost RGB identities | Lost: no raw | Lost: NMS |
| ---: | ---: | ---: | ---: |
| 1 | 12 | 6 | 6 |
| 2 | 14 | 10 | 4 |
| 5 | 2 | 2 | 0 |
| 8 | 1 | 1 | 0 |
| 12 | 17 | 17 | 0 |
| 17 | 21 | 21 | 0 |
| **Total** | **67** | **57** | **10** |

| Scene | Lost RGB identities | Lost: no raw | Lost: NMS |
| ---: | ---: | ---: | ---: |
| 1 | 4 | 3 | 1 |
| 4 | 3 | 3 | 0 |
| 6 | 17 | 17 | 0 |
| 7 | 33 | 27 | 6 |
| 8 | 0 | 0 | 0 |
| 10 | 0 | 0 | 0 |
| 12 | 10 | 7 | 3 |
| 13 | 0 | 0 | 0 |

The concentration in objects 12 and 17, and in scenes 6 and 7, is descriptive
only. No subset was selected for tuning or for a performance claim.

## Geometry and pose checks

All 67 lost RGB TP poses (training-image ID, angle, scale) exist in the binary
template bank. No lost identity has a binary raw hit at the same RGB TP pose;
only three lost identities have any binary raw row with that exact pose, and all
three still miss IoU 0.5. Across all six objects, the binary banks have no
missing RGB training poses. Translation-only template-box size upper bounds are
compatible with every lost identity: the minimum best binary-bank size bound
over these 67 identities is `0.8324`. The saved per-GT rows retain the exact
bound used for each identity.

These checks rule out a simple explanation of “the binary bank has no pose or
usable box size.” They do not prove that a binary template has the correct
appearance or that the pose should score well in the target image.

## Reproducible examples

The details below are selected as the first saved row in each category, in
object/scene/image/GT order. They are numeric rows only.

* **No raw candidate:** object 1, scene 7, image 366, GT 0. RGB's TP scored
  `92.3611` at pose `(481, 0°, 1.0)`. That pose exists in the binary bank. The
  best binary raw row scored `95.0` but had IoU `0.4238`; no binary raw row
  reached IoU 0.5. The binary bank's best box-size upper bound for this GT is
  `0.9474`.
* **NMS suppression:** object 1, scene 7, image 219, GT 0. Binary raw rows
  contain 124 candidates with IoU >= 0.5; the best has IoU `0.8068`, but no
  such row survives NMS. The first blocker is a selected FP with score
  `98.9130` and IoU `0.4268`, while the best valid raw row scores `87.9310`.

## Single testable hypothesis and next diagnostic

The dominant observed change is loss of **candidate support** rather than a
missing training-pose identity, incompatible bank box size, or GT assignment:
the post-consolidation raw list contains no >=0.5 candidate for 57 identities,
and in 10 more cases valid candidates lose to nearby FP responses under the
unchanged NMS rule. The fact that all 67 RGB TP poses exist in the binary bank,
while only three have any same-pose binary raw row, motivates investigating the
descriptor and search path. It does not isolate which of them caused absence.

The single improvement hypothesis is that a fixed mixture of contour-derived
and grayscale-gradient template features can improve candidate support and
ranking, with poses, score cutoff, feature budget, NMS IoU, and search geometry
held fixed. Such a hybrid has not been implemented or validated. Before changing
the descriptor, the next diagnostic should score the existing binary templates
at the physical placements of all 215 RGB TPs (67 losses plus 148 controls),
then trace coarse admission, local maxima, and cross-template consolidation.
This separates descriptor score insufficiency from search/consolidation effects
without changing matcher behavior. See `NEXT_SINGLE_POINT_DESIGN.md`.

## Limits

The raw archives begin after matching and cross-template consolidation, at the
fixed matcher score cutoff of 85. Consequently, “no raw candidate” is not proof
that no lower-scoring response or pre-consolidation candidate existed. The
diagnosis does not read pixels, rerun matching, infer 3D pose correctness, or
measure industrial generalization. It preserves the fixed numeric scope in
`run_20261022_v1/result.json` and `PROTOCOL.json`.
