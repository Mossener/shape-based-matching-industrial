# Static review V1 — supplied-graph ordered matching core

Date: 2026-10-23. Scope: `weighted_ordered_match.py` and
`CORE_DECISIONS_V1.json`, against sections 4 and 5 of
`docs/superpowers/plans/2026-10-23-ordered-contour-verifier-contract.md`.

**No material findings.** The supplied-graph prototype is statically consistent
with the reviewed mathematical contract. No implementation or test was edited.
This review did not execute tests, Python, native code, Git, or image/data reads.

| Check | Source location | Review conclusion |
| --- | --- | --- |
| Four open/closed cases | [weighted_ordered_match.py:285](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:285), [CORE_DECISIONS_V1.json:10](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/CORE_DECISIONS_V1.json:10) | Open/open uses fixed template order and both scene directions. Closed/open enumerates incident template cuts. Open/closed enumerates incident scene cuts. Closed/closed fixes template cut zero and enumerates incident scene cuts. A singleton scene has only the positive direction. |
| Cut and reversal transformation | [weighted_ordered_match.py:201](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:201) | Template rotation and the scene formulas implement the contract's strict linearized orders. Each physical ID occurs once per linearization; modular indexing does not duplicate an endpoint or permit a second circuit. |
| Strict template and scene order | [weighted_ordered_match.py:224](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:224) | The Fenwick query begins at compressed rank, excluding the current column stored at rank + 1. Every edge in one transformed template row queries before any row update. Thus neither template samples nor scene pixels can be reused inside a correspondence. |
| Exact weighted recurrence | [weighted_ordered_match.py:239](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:239), [weighted_ordered_match.py:277](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:277) | Each state adds the supplied sample weight to the best strict predecessor. All arithmetic and comparisons use Python integers; there is no float conversion, saturation, or epsilon. The full supplied weight sum is retained even when points have no support. |
| Colexicographic witness tie | [weighted_ordered_match.py:178](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:178), [weighted_ordered_match.py:166](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:166) | The terminal-edge shortcut is valid because duplicate original edges are rejected and each case creates exactly one state per edge. The predecessor is already canonical; the proof is given below. |
| Case priorities precede witness priorities | [weighted_ordered_match.py:173](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:173), [weighted_ordered_match.py:291](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:291), [CORE_DECISIONS_V1.json:17](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/CORE_DECISIONS_V1.json:17) | Scenes and cuts are sorted; positive direction precedes negative direction. Updating the winner only on a strictly larger score preserves the first case by the declared tuple priority. Witness comparison occurs only within a case. |
| One-scene choice and permitted reuse | [weighted_ordered_match.py:278](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:278), [weighted_ordered_match.py:298](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:298) | Independent support counts each template sample once across all scenes. B takes the maximum single-scene result. Separate calls do not reserve pixels, so different template chains may reuse scene chains and pixels as required. |
| Snapshot and full validation | [weighted_ordered_match.py:107](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:107), [weighted_ordered_match.py:128](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:128) | Nested supplied collections are copied into tuples before solving. Validation rejects non-builtin integer IDs/weights, booleans used as integers, nonpositive sample weights, duplicate physical IDs/scene IDs/edges, unknown endpoints, length mismatches, and invalid flags. It validates unused and empty chains before the no-edge shortcut. Physical pixels shared across distinct scene chains remain allowed. |
| Work counters and sparse state | [weighted_ordered_match.py:217](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:217), [weighted_ordered_match.py:223](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:223), [weighted_ordered_match.py:280](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/weighted_ordered_match.py:280) | Every enumerated nonempty case contributes one state, query, and update per input edge; visit counters increment at the actual tree visits. Rank compression preserves order. Each case retains its predecessors for witness recovery, using sparse state rather than a dense template-by-scene matrix. |

Cut completeness follows the contract's argument. For closed/open, cut the
template at the sample paired to the first matched point in the chosen open
scene direction. For open/closed, cut the scene at the point paired to the first
matched template sample. For closed/closed, list the matching in fixed canonical
template order and cut the selected scene direction at the first paired scene
point. Each required cut is incident to an edge, so the implementation enumerates
it. Conversely every enumerated result has strict template and scene order and
uses each physical ID at most once. This depends on the current absence of gap
penalties or cut-dependent rewards.

For the witness tie, use induction over processed template rows. At a fixed
terminal edge, the score addition is constant; therefore the best predecessor
score is necessary, and among equal scores its smallest reversed witness gives
the smallest reversed complete witness. Between two different terminal-edge
states, the first reversed-witness element is already different and decides the
lexicographic comparison. Equal terminal edges identify the same unique state,
so no recursive witness traversal is needed inside `_better`. Strictly positive
weights ensure a nonempty state cannot tie the zero sentinel.

The decision file's acceptance is explicitly limited to synthetic core
implementation ([CORE_DECISIONS_V1.json:3](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/CORE_DECISIONS_V1.json:3)).
Its future quality gates do not authorize real-pixel execution or production
promotion ([CORE_DECISIONS_V1.json:27](D:/h/shape_based_matching-master/artifacts/ordered_contour_verifier_experiment/CORE_DECISIONS_V1.json:27)).

Validation limits: this is source inspection, not an independent exhaustive
oracle or a runtime result. Supplied weights and compatibility edges are trusted
mathematical inputs after structural validation; their 4-by-4 derivation, pixel
provenance, chain extraction, coordinate construction, and full-template
aggregation are outside this module and this review. Work counters are
structural diagnostics, not wall-time, RSS, or complete interpreter-operation
measurements. `maximum_integer_bits` includes the total supplied weight and
state scores; it does not measure every integer object or bit operation. Budget
enforcement and production integration were not inspected. No pixel accuracy,
end-to-end quality, latency, or production-readiness conclusion follows.
