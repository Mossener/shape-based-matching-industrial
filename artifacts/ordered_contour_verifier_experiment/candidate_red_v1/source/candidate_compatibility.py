"""Supplied-grid coordinate compatibility prototype: fixed API, RED stub.

This module neither decodes images nor generates their direction labels. It
operates on factory evidence from edge_chains.prepare_template and this
module's prepare_scene only. Evidence must come from those factories without
forging/replacing fields; accepting arbitrary hand-built evidence is outside
the API contract. No provenance, detector-accuracy or runtime claim follows.

prepare_scene snapshots/thins a supplied legal label grid, extracts all scene
chains, and records every surviving physical pixel's complete (chain,index)
memberships. These immutable memberships include shared junctions and every
unsampled scene vertex. Empty scenes are legal.

score_candidate uses an already-warped template canvas. For each owned sample
it computes, in this order, p_canvas - tl, match + relative, and q_padded -
(padding.left,padding.top). Every scalar add/subtract is checked as signed
int64 before proceeding, even when later arithmetic could cancel it or when
the center lies outside the scene. No rotation/crop-origin adjustment occurs.
Coordinates are builtin ints in signed-int64 range; bool/float are rejected.
Padding order is left,top,right,bottom. Entries are nonnegative builtin ints,
their opposing sums are checked int64, and each sum must be strictly smaller
than that padded scene dimension. The original image must remain nonempty.

Only centers inside the entire padded grid can receive compatible support in
a clipped Chebyshev-radius-two neighborhood. Label 255 is invalid. Labels
0..7 use unsigned circular difference <=1. An outside center is never clamped
or rescued by nearby pixels. Original-image coordinates/bounds are diagnostic
only: padding-area support is legal. All samples retain their exact weight in
the denominator, including samples outside either coordinate frame.

A is independently supported weight; its witness chooses the smallest
compatible physical pixel for each supported sample. B sums weighted ordered
core results, with owned samples restored to original chain_index order. Each
template chain chooses at most one scene chain; different template chains may
reuse pixels. Only scene chains with compatibility edges are passed to core.
Every original template chain, including one with no owned samples, has a
full MatchResult. Results satisfy 0 <= B <= A <= D and acceptance is exactly
20*N >= 13*D. Integers never convert to float. cross_chain_reused_pixel_ids
describes physical pixels reused by distinct selected B chain witnesses.

Sample rows, outside-ID diagnostics and A witnesses follow physical template
sample ID order. Memberships follow physical scene pixel ID order and member
chain ID order. Chain results follow canonical template chain ID order. All
results are frozen dataclasses containing immutable tuples.

This revision intentionally returns fixed empty stub values. The coordinating
runner must observe and retain RED on the frozen behavior tests before any
implementation is added.
"""
from dataclasses import dataclass

import edge_chains as edge
import weighted_ordered_match as core


@dataclass(frozen=True)
class SceneChainMember:
    chain_id: int
    chain_index: int


@dataclass(frozen=True)
class ScenePixelMembership:
    pixel_id: int
    members: tuple[SceneChainMember, ...]


@dataclass(frozen=True)
class SceneEvidence:
    thinning: edge.ThinningResult
    chains: tuple[edge.Chain, ...]
    memberships: tuple[ScenePixelMembership, ...]


@dataclass(frozen=True)
class SampleSupport:
    sample_id: int
    p_canvas: tuple[int, int]
    relative: tuple[int, int]
    q_padded: tuple[int, int]
    q_original: tuple[int, int]
    padded_in_bounds: bool
    original_in_bounds: bool
    compatible_pixel_ids: tuple[int, ...]
    independent_witness: int | None


@dataclass(frozen=True)
class CandidateScore:
    denominator: int
    independent_numerator: int
    ordered_numerator: int
    independent_accepted: bool
    ordered_accepted: bool
    samples: tuple[SampleSupport, ...]
    chains: tuple[core.MatchResult, ...]
    outside_padded_sample_ids: tuple[int, ...]
    outside_original_sample_ids: tuple[int, ...]
    independent_witness: tuple[tuple[int, int], ...]
    cross_chain_reused_pixel_ids: tuple[int, ...]


def prepare_scene(grid) -> SceneEvidence:
    """RED stub for immutable thinned scene chains and physical memberships."""
    return SceneEvidence(edge.ThinningResult(1, 1, ((255,),), ((255,),),
                                              ((0, 0),)), (), ())


def passes_threshold(numerator: int, denominator: int) -> bool:
    """RED stub: valid scores require builtin ints with 0<=N<=D and D>0."""
    return False


def score_candidate(template: edge.TemplateEvidence, scene: SceneEvidence,
                    tl: tuple[int, int], match: tuple[int, int],
                    padding_ltrb: tuple[int, int, int, int] = (0, 0, 0, 0)
                    ) -> CandidateScore:
    """RED stub; caller supplies unmodified factory template/scene evidence."""
    return CandidateScore(0, 0, 0, False, False, (), (), (), (), (), ())
