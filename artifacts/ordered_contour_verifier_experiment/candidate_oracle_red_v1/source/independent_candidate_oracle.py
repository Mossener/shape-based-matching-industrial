"""Test-first independent supplied-label candidate oracle: fixed-empty stub.

This file deliberately performs no coordinate, compatibility, or scoring work.
The coordinating task must capture RED before implementation is authorized.
Its public carriers mirror observable evidence, excluding solver work counters.

The intended reference may use only independent_edge_oracle for supplied-grid
topology/weights and independent_tiny_oracle.brute_force for ordered objectives.
It must not import candidate_compatibility, edge_chains, weighted_ordered_match,
or any of their helpers. It has no image, matcher, filesystem, or runner work.
"""
from dataclasses import dataclass

import independent_edge_oracle as edge_reference
from independent_tiny_oracle import brute_force


ORACLE_PHASE = "FIXED_EMPTY_TEST_FIRST_STUB"


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
    """Independent scene evidence; fixed empty until the parent captures RED."""
    return SceneEvidence(edge_reference.ThinningResult(0, 0, (), (), ()), (), ())


def reference_threshold(numerator, denominator) -> bool:
    """Exact inclusive 13/20 boundary; fixed false in the RED predecessor."""
    return False


def reference_problems(template_grid, scene_grid, tl, match,
                       padding_ltrb=(0, 0, 0, 0)) -> tuple[ChainProblem, ...]:
    """Independent physical compatibility carriers; fixed empty before RED."""
    return ()


def reference_candidate(template_grid, scene_grid, tl, match,
                        padding_ltrb=(0, 0, 0, 0)) -> CandidateScore:
    """Complete candidate evidence; fixed empty before RED is observed."""
    return CandidateScore(0, 0, 0, False, False, (), (), (), (), (), ())
