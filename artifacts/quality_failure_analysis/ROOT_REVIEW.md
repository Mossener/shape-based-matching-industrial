# V17 numeric diagnosis review

The independent GT-bitmask DP and the original augmenting-path analysis agree
on every one of the 2400 development object/frame pairs. Their per-frame CSV
SHA is `c5070812a3e0d5722d11f83d0da5b606e978183274007a2479b6449715240f8e`.
The frozen baseline therefore has raw/selected assignment capacities 238/215
for 400 GT, with 185 FN decomposed into 162/23/0. This diagnosis changes the
next experiment, not detector output or accuracy.

Root read the independent DP implementation, adjacency multiplicity handling,
GT reassignment, raw metadata conversion and selected-precision correction.
The algorithm extends each reachable GT subset by at most one unoccupied
neighbor per candidate. Capping identical adjacency multiplicity at the GT
count preserves maximum cardinality. The observed maximum is two target GT
per frame; the implementation rejects more than twenty.

The original root analysis checks selected class/template/box membership but
does not bind selected score bits. The independent implementation adds that
check by recovering full scores from frozen metrics JSON, validating the
six-significant-digit CSV projection, and requiring the complete binary32 raw
identity multiset. A literal collision test rejects two different binary32
scores that print identically. The first failed precision assumption is retained
with its original source and protocol; no old evidence was overwritten.

Fresh root verification passed in `root_review_20261021_v1/`: 56 recorded
source/input files, source/protocol snapshots, full per-frame bytes, 215 unique
effective TP identities and the size-analysis row SHA were rechecked. The
eleven root synthetic tests, independent DP literals and selected-precision
fixtures each exited zero. The verifier is `verify_independent_review.py`.
It reads numeric bytes and GT metadata only; no image is decoded and no matcher
is called. It does not represent a second full DP execution.

The box-size upper bound follows maximal rectangle intersection under ideal
translation. Its formula was checked against all 81 pairs of small rectangle
dimensions using independently enumerated translated pixel sets. The full
size diagnostic has at least one compatible existing box for all 400 GT.
An upper bound does not establish matching edges, pose or feasible grid origin.

No production core, template, scale range, threshold, NMS or runtime default is
changed. Raw capacity is an optimistic oracle; its chosen boxes need not survive
NMS simultaneously, and the 23 lost opportunities are not proven recoverable
TPs. FP overlap categories do not establish visual identity or pure background.
Heldout scenes and reserved objects remain sealed. This version establishes
neither speed gains nor an accuracy improvement.
