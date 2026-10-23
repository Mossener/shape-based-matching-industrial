"""Independent mathematical candidate reference for tiny supplied label grids.

The coordinating task observed 34 methods / 694 assertion failures / zero
errors against this module's frozen fixed-empty predecessor before authorizing
implementation. Its carriers mirror observable evidence without work counters.

Topology and exact sample weights come only from independent_edge_oracle.
Compatibility tests all physical sample/pixel pairs, rather than scanning a
radius window. Ordered values and canonical case/witness ties come only from
independent_tiny_oracle.brute_force, which enumerates partial injections. No
candidate_compatibility, edge_chains, weighted_ordered_match, or helper from
those implementations is imported or called.

Candidate/problem APIs reject more than eight owned points in any template
chain or more than eight physical points in ANY scene chain, even an unused
one. This explicit finite reference domain never truncates or skips inputs.
reference_scene itself exposes supplied-grid evidence without that limit.
Coordinate stages use checked signed-int64 arithmetic; score arithmetic and
the exact 13/20 rational comparison use arbitrary-precision builtin integers.

These APIs accept legal supplied labels and already-warped canvas coordinates.
They do not establish how labels came from RGB, a bank, crop, mask or warp, or
that a supplied candidate belongs to a detector. There is no image, matcher,
native build, filesystem, process runner, accuracy, or performance work here.
The coordinating task owns complete-process time/RSS/output limits.
"""
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

import independent_edge_oracle as edge_reference
from independent_tiny_oracle import brute_force


ORACLE_PHASE = "INDEPENDENT_CANDIDATE_REFERENCE_IMPLEMENTATION_V1"


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
    thinning: edge_reference.ThinningResult
    chains: tuple[edge_reference.Chain, ...]
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
class MatchCase:
    scene_chain_id: int
    direction: int
    template_cut: int
    scene_cut: int


@dataclass(frozen=True)
class ChainResult:
    template_chain_id: int
    numerator: int
    independent_numerator: int
    total_weight: int
    case: MatchCase | None
    witness: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class CandidateScore:
    denominator: int
    independent_numerator: int
    ordered_numerator: int
    independent_accepted: bool
    ordered_accepted: bool
    samples: tuple[SampleSupport, ...]
    chains: tuple[ChainResult, ...]
    outside_padded_sample_ids: tuple[int, ...]
    outside_original_sample_ids: tuple[int, ...]
    independent_witness: tuple[tuple[int, int], ...]
    cross_chain_reused_pixel_ids: tuple[int, ...]


@dataclass(frozen=True)
class TemplateInput:
    chain_id: int
    sample_ids: tuple[int, ...]
    weights: tuple[int, ...]
    closed: bool


@dataclass(frozen=True)
class SceneInput:
    chain_id: int
    pixel_ids: tuple[int, ...]
    edges: tuple[tuple[int, int], ...]
    closed: bool


@dataclass(frozen=True)
class ChainProblem:
    template: TemplateInput
    scenes: tuple[SceneInput, ...]


def reference_scene(grid) -> SceneEvidence:
    """Preserve each surviving physical vertex's complete chain membership."""
    thinning = edge_reference.reference_thinning(grid)
    chains = edge_reference.reference_chains(thinning.labels)
    pixels = sorted({pixel for chain in chains for pixel in chain.pixel_ids})
    memberships = tuple(ScenePixelMembership(pixel, tuple(
        SceneChainMember(chain.chain_id, chain.pixel_ids.index(pixel))
        for chain in chains if pixel in chain.pixel_ids)) for pixel in pixels)
    return SceneEvidence(thinning, chains, memberships)


def reference_threshold(numerator, denominator) -> bool:
    """Compare exact rationals, independently of the candidate's cross product."""
    if (type(numerator) is not int or type(denominator) is not int or
            denominator <= 0 or numerator < 0 or numerator > denominator):
        raise ValueError("exact scores require integers with 0<=N<=D and D>0")
    return Fraction(numerator, denominator) >= Fraction(13, 20)


def _bounded(value):
    if type(value) is not int or value < -(1 << 63) or value >= (1 << 63):
        raise ValueError("coordinate arithmetic requires signed-int64 builtin integers")
    return value


def _pose_pair(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("a pose needs exactly two coordinates")
    return tuple(_bounded(coordinate) for coordinate in value)


def _padding(value, width, height):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("padding needs left,top,right,bottom")
    result = tuple(_bounded(entry) for entry in value)
    if any(entry < 0 for entry in result):
        raise ValueError("padding must be nonnegative")
    horizontal = _bounded(result[0] + result[2])
    vertical = _bounded(result[1] + result[3])
    if width - horizontal <= 0 or height - vertical <= 0:
        raise ValueError("padding must leave a nonempty original image")
    return result


def _all_pairs_supports(template, scene, tl, match, padding):
    """Compare each checked center with every surviving physical scene pixel."""
    width, height = scene.thinning.width, scene.thinning.height
    physical = tuple((y * width + x, x, y, label)
                     for y, row in enumerate(scene.thinning.labels)
                     for x, label in enumerate(row) if label != 255)
    left, top, right, bottom = padding
    supports = []
    for sample in template.samples:
        canvas_x, canvas_y = _bounded(sample.x), _bounded(sample.y)
        relative_x = _bounded(canvas_x - tl[0])
        relative_y = _bounded(canvas_y - tl[1])
        padded_x = _bounded(match[0] + relative_x)
        padded_y = _bounded(match[1] + relative_y)
        original_x = _bounded(padded_x - left)
        original_y = _bounded(padded_y - top)
        inside_padded = 0 <= padded_x < width and 0 <= padded_y < height
        inside_original = (0 <= original_x < width - left - right and
                           0 <= original_y < height - top - bottom)
        compatible = tuple(pixel for pixel, x, y, label in physical
                           if inside_padded and
                           max(abs(x - padded_x), abs(y - padded_y)) <= 2 and
                           (label - sample.label) % 8 in (0, 1, 7))
        supports.append(SampleSupport(
            sample.pixel_id, (canvas_x, canvas_y), (relative_x, relative_y),
            (padded_x, padded_y), (original_x, original_y),
            inside_padded, inside_original, compatible,
            min(compatible) if compatible else None))
    return tuple(supports)


def _candidate_inputs(template_grid, scene_grid, tl, match, padding_ltrb):
    """Build a complete finite independent problem without using core helpers."""
    template = edge_reference.reference_template(template_grid)
    scene = reference_scene(scene_grid)
    tl, match = _pose_pair(tl), _pose_pair(match)
    padding = _padding(padding_ltrb, scene.thinning.width, scene.thinning.height)
    supports = _all_pairs_supports(template, scene, tl, match, padding)
    if any(len(chain.pixel_ids) > 8 for chain in scene.chains):
        raise ValueError("tiny candidate reference permits at most eight points per scene chain")
    support_by_id = {support.sample_id: set(support.compatible_pixel_ids)
                     for support in supports}
    problems = []
    for chain in template.chains:
        owned = sorted((sample for sample in template.samples
                        if sample.owner_chain_id == chain.chain_id),
                       key=lambda sample: sample.chain_index)
        if len(owned) > 8:
            raise ValueError("tiny candidate reference permits at most eight owned points per template chain")
        template_input = TemplateInput(
            chain.chain_id, tuple(sample.pixel_id for sample in owned),
            tuple(sample.weight for sample in owned), chain.closed)
        scene_inputs = []
        for scene_chain in scene.chains:
            edges = tuple(sorted((sample.pixel_id, pixel)
                                 for sample in owned for pixel in scene_chain.pixel_ids
                                 if pixel in support_by_id[sample.pixel_id]))
            if edges:
                scene_inputs.append(SceneInput(scene_chain.chain_id,
                                                scene_chain.pixel_ids, edges,
                                                scene_chain.closed))
        problems.append(ChainProblem(template_input, tuple(scene_inputs)))
    return template, supports, tuple(problems)


def reference_problems(template_grid, scene_grid, tl, match,
                       padding_ltrb=(0, 0, 0, 0)) -> tuple[ChainProblem, ...]:
    """Expose every template chain and complete incident scene-chain topology."""
    return _candidate_inputs(template_grid, scene_grid, tl, match, padding_ltrb)[2]


def reference_candidate(template_grid, scene_grid, tl, match,
                        padding_ltrb=(0, 0, 0, 0)) -> CandidateScore:
    """Enumerate exact tiny-chain optima and retain all coordinate diagnostics."""
    template, supports, problems = _candidate_inputs(
        template_grid, scene_grid, tl, match, padding_ltrb)
    chain_results = []
    for problem in problems:
        optimum = brute_force(problem.template, problem.scenes)
        chain_results.append(ChainResult(
            problem.template.chain_id, optimum.numerator,
            optimum.independent_numerator, optimum.total_weight,
            MatchCase(*optimum.case) if optimum.case is not None else None,
            optimum.witness))
    chain_results = tuple(chain_results)
    supported = {support.sample_id for support in supports
                 if support.compatible_pixel_ids}
    independent = sum(sample.weight for sample in template.samples
                      if sample.pixel_id in supported)
    ordered = sum(chain.numerator for chain in chain_results)
    denominator = template.denominator
    if not 0 <= ordered <= independent <= denominator:
        raise AssertionError("independent candidate objective violates B<=A<=D")
    if sum(chain.independent_numerator for chain in chain_results) != independent:
        raise AssertionError("independent scene memberships lost physical support")
    pixel_owners = {(pixel, chain.template_chain_id)
                    for chain in chain_results for _, pixel in chain.witness}
    owner_counts = Counter(pixel for pixel, _ in pixel_owners)
    return CandidateScore(
        denominator, independent, ordered,
        reference_threshold(independent, denominator),
        reference_threshold(ordered, denominator), supports, chain_results,
        tuple(support.sample_id for support in supports if not support.padded_in_bounds),
        tuple(support.sample_id for support in supports if not support.original_in_bounds),
        tuple((support.sample_id, support.independent_witness) for support in supports
              if support.independent_witness is not None),
        tuple(sorted(pixel for pixel, count in owner_counts.items() if count > 1)))
