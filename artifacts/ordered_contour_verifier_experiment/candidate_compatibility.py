"""Supplied-grid coordinate compatibility mathematical prototype.

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

The coordinating runner retained the empty-stub RED before this implementation
was added. This module is a mathematical prototype, not a native-speed claim.
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
    """Thin legal supplied labels and index every surviving chain membership."""
    thinning = edge.thin_labels(grid)
    chains = edge.extract_chains(thinning.labels)
    members_by_pixel = {}
    for chain in chains:
        for index, pixel in enumerate(chain.pixel_ids):
            members_by_pixel.setdefault(pixel, []).append(
                SceneChainMember(chain.chain_id, index))
    memberships = tuple(
        ScenePixelMembership(pixel, tuple(sorted(members_by_pixel[pixel],
                                                  key=lambda row: row.chain_id)))
        for pixel in sorted(members_by_pixel))
    return SceneEvidence(thinning, chains, memberships)


_MIN64 = -(2 ** 63)
_MAX64 = 2 ** 63 - 1


def _int64(value, name: str) -> int:
    if type(value) is not int or not _MIN64 <= value <= _MAX64:
        raise ValueError(name + " must be a builtin int in signed-int64 range")
    return value


def _pair(value, name: str) -> tuple[int, int]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(name + " must be a tuple or list of two coordinates")
    return tuple(_int64(coordinate, name + " coordinate") for coordinate in value)


def _padding(value, width: int, height: int) -> tuple[int, int, int, int]:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise ValueError("padding must be a left,top,right,bottom tuple or list")
    padding = tuple(_int64(entry, "padding entry") for entry in value)
    if any(entry < 0 for entry in padding):
        raise ValueError("padding entries must be nonnegative")
    left, top, right, bottom = padding
    horizontal = _int64(left + right, "left+right padding sum")
    vertical = _int64(top + bottom, "top+bottom padding sum")
    if horizontal >= width or vertical >= height:
        raise ValueError("padding must leave positive original width and height")
    return padding


def passes_threshold(numerator: int, denominator: int) -> bool:
    """Compare N/D >=13/20 exactly; require builtin ints, 0<=N<=D and D>0."""
    if (type(numerator) is not int or type(denominator) is not int or
            denominator <= 0 or not 0 <= numerator <= denominator):
        raise ValueError("score requires builtin ints with 0<=N<=D and D>0")
    return 20 * numerator >= 13 * denominator


def _support(sample: edge.WeightedSample, scene: SceneEvidence,
             tl: tuple[int, int], match: tuple[int, int],
             padding: tuple[int, int, int, int]) -> SampleSupport:
    """Check each coordinate stage before any bounds test or neighborhood scan."""
    p_canvas = (sample.x, sample.y)
    relative = tuple(_int64(position - origin, "p_canvas-tl")
                     for position, origin in zip(p_canvas, tl))
    q_padded = tuple(_int64(position + displacement, "match+relative")
                     for position, displacement in zip(match, relative))
    left, top, right, bottom = padding
    q_original = tuple(_int64(position - pad, "q_padded-padding")
                       for position, pad in zip(q_padded, (left, top)))
    width, height = scene.thinning.width, scene.thinning.height
    x, y = q_padded
    original_x, original_y = q_original
    padded_in_bounds = 0 <= x < width and 0 <= y < height
    original_in_bounds = (0 <= original_x < width - left - right and
                          0 <= original_y < height - top - bottom)
    compatible = []
    if padded_in_bounds:
        for neighbor_y in range(max(0, y - 2), min(height, y + 3)):
            for neighbor_x in range(max(0, x - 2), min(width, x + 3)):
                label = scene.thinning.labels[neighbor_y][neighbor_x]
                if label == 255:
                    continue
                difference = abs(sample.label - label)
                if min(difference, 8 - difference) <= 1:
                    compatible.append(neighbor_y * width + neighbor_x)
    # Row-major enumeration is physical-ID order, including clipped borders.
    compatible = tuple(compatible)
    return SampleSupport(sample.pixel_id, p_canvas, relative, q_padded,
                         q_original, padded_in_bounds, original_in_bounds,
                         compatible, compatible[0] if compatible else None)


def score_candidate(template: edge.TemplateEvidence, scene: SceneEvidence,
                    tl: tuple[int, int], match: tuple[int, int],
                    padding_ltrb: tuple[int, int, int, int] = (0, 0, 0, 0)
                    ) -> CandidateScore:
    """Score unmodified factory evidence with checked supplied pose coordinates.

    Type checks identify the expected evidence containers; they do not validate
    forged/replaced internals. The factory-evidence precondition is essential.
    """
    if not isinstance(template, edge.TemplateEvidence):
        raise ValueError("template must be factory TemplateEvidence")
    if not isinstance(scene, SceneEvidence):
        raise ValueError("scene must be factory SceneEvidence")
    tl = _pair(tl, "tl")
    match = _pair(match, "match")
    padding = _padding(padding_ltrb, scene.thinning.width, scene.thinning.height)
    supports = tuple(_support(sample, scene, tl, match, padding)
                     for sample in template.samples)
    support_by_sample = {row.sample_id: row for row in supports}
    members_by_pixel = {row.pixel_id: row.members for row in scene.memberships}
    scene_by_id = {chain.chain_id: chain for chain in scene.chains}
    samples_by_owner = {chain.chain_id: [] for chain in template.chains}
    independent_numerator = 0
    for sample in template.samples:
        samples_by_owner[sample.owner_chain_id].append(sample)
        if support_by_sample[sample.pixel_id].compatible_pixel_ids:
            independent_numerator += sample.weight

    chain_results = []
    selected_owners_by_pixel = {}
    for chain in template.chains:
        owned = tuple(sorted(samples_by_owner[chain.chain_id],
                             key=lambda sample: sample.chain_index))
        template_chain = core.TemplateChain(
            chain.chain_id, tuple(sample.pixel_id for sample in owned),
            tuple(sample.weight for sample in owned), chain.closed)
        edges_by_scene = {}
        for sample in owned:
            for pixel in support_by_sample[sample.pixel_id].compatible_pixel_ids:
                for member in members_by_pixel[pixel]:
                    edges_by_scene.setdefault(member.chain_id, []).append(
                        (sample.pixel_id, pixel))
        # The entire canonical scene topology stays intact. Only scene chains
        # without any compatible edge for this template chain are omitted.
        scene_chains = tuple(
            core.SceneChain(scene_id, scene_by_id[scene_id].pixel_ids,
                            tuple(sorted(edges_by_scene[scene_id])),
                            scene_by_id[scene_id].closed)
            for scene_id in sorted(edges_by_scene))
        result = core.solve(template_chain, scene_chains)
        chain_results.append(result)
        for _, pixel in result.witness:
            selected_owners_by_pixel.setdefault(pixel, set()).add(chain.chain_id)

    chain_results = tuple(chain_results)
    ordered_numerator = sum(row.numerator for row in chain_results)
    denominator = template.denominator
    if not 0 <= ordered_numerator <= independent_numerator <= denominator:
        raise RuntimeError("factory candidate scores violate 0<=B<=A<=D")
    if sum(row.independent_numerator for row in chain_results) != independent_numerator:
        raise RuntimeError("scene memberships lost independent sample support")
    return CandidateScore(
        denominator, independent_numerator, ordered_numerator,
        passes_threshold(independent_numerator, denominator),
        passes_threshold(ordered_numerator, denominator), supports, chain_results,
        tuple(row.sample_id for row in supports if not row.padded_in_bounds),
        tuple(row.sample_id for row in supports if not row.original_in_bounds),
        tuple((row.sample_id, row.independent_witness) for row in supports
              if row.independent_witness is not None),
        tuple(pixel for pixel in sorted(selected_owners_by_pixel)
              if len(selected_owners_by_pixel[pixel]) > 1))
