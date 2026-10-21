# Numeric failure decomposition

This bounded diagnostic extends the existing six-object numeric audits.
It changes no matcher, template, threshold, NMS or metric. Only the already
published V11 development candidates, selected detections and development GT
metadata are used. It never opens RGB/mask files or evaluates heldout data.
Metadata for other annotated objects is used only for overlap associations;
this is not training or matching objects 25/29.

For every object/frame, compute a maximum bipartite matching between candidate
boxes and same-object GT at IoU >= 0.5. Repeat for the preserved NMS output.
Report three additive capacity deficits: GT minus raw capacity, raw minus
selected capacity, selected capacity minus actual greedy TP. Their sum must
equal baseline FN. The raw capacity is an optimistic oracle bound: its boxes
need not survive NMS simultaneously. It is not achievable detector accuracy.
Also report how many individual GT have no raw overlapping candidate.
The raw deficit can also include competition for the same candidate (Hall's
condition). The raw-to-selected loss describes candidate-pool capacity and
does not establish NMS as the sole cause. The final term compares the frozen
greedy assignment with possible assignments of its same fixed boxes.

Associate each selected FP, in this fixed priority order, with target GT
IoU >= 0.5, other-object GT >= 0.5, target >= 0.1, other >= 0.1, or none >= 0.1.
These are box-overlap associations, not visual or causal object identities.
The last category means no *annotated* GT box has IoU >= 0.1; it is not a
claim that the detection covers only background.
No thresholds are fitted and no new gate will be promoted from these counts.

Tests compare maximum matching against exhaustive partial injections for all
512 three-by-three graphs, plus hand-derived IoU boundaries, additive losses,
exclusive FP categories and invalid inputs. The initial no-op implementation
failed these behavioral tests before implementation. Six-object processing
completed in the exclusive CPU slot and retained input hashes and counts.
Selected class/template/box identities must be a multiset subset of raw;
each frozen TP must retain a distinct, geometrically valid target GT ID.
An independent GT-subset bitmask DP now agrees on every frame and adds complete
selected/raw score-bit identity checks. Its first precision failure is retained.
See [the independent report](../independent_reviews/capacity_dp/README.md) and
[the fresh root review](ROOT_REVIEW.md).

The separate template-box-size upper-bound analysis, results and replay
commands are documented in [RESULTS.md](RESULTS.md). These findings change
the next experiment; they do not change the production matcher.
