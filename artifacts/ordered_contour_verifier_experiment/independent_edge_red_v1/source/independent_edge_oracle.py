"""Independent edge reference API: fixed-empty stub for coordinated real RED.

This source intentionally implements no thinning, graph, sampling, ownership,
cell, or quality algorithm yet. Tests use hand-derived literals and supplied
grids, so this importable stub must fail assertions rather than import errors.
Root must capture RED before authorizing implementation. No edge_chains helper
is imported or called; its public field schema is the comparison boundary.

Planned independent reference after RED:
* Zhang--Suen Boolean deletion predicates and synchronous active-point sets;
* all-pairs 8-neighbor graph and degree-two induced-component decomposition,
  including pure cycles and trails returning to one junction;
* cumulative integer arclength and direct marker-first-reached sampling;
* lowest-chain ownership and Fraction cell mass before integer scaling.

All work is mathematical on tiny supplied labels. It establishes no RGB pixel
provenance, image experiment, detector accuracy, native timing, or production
authorization. The coordinator owns wall/RSS/output process limits.
"""
from dataclasses import dataclass
from fractions import Fraction

ORACLE_PHASE = "FIXED_EMPTY_RED_STUB"


@dataclass(frozen=True)
class ThinningResult:
    width: int
    height: int
    eligible_labels: tuple[tuple[int, ...], ...]
    labels: tuple[tuple[int, ...], ...]
    round_deletions: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Chain:
    chain_id: int
    pixel_ids: tuple[int, ...]
    closed: bool = False
    returning: bool = False


@dataclass(frozen=True)
class ChainSampling:
    chain_id: int
    pixel_ids: tuple[int, ...]
    arclength: int


@dataclass(frozen=True)
class SampleOwnership:
    pixel_id: int
    owner_chain_id: int
    member_chain_ids: tuple[int, ...]


@dataclass(frozen=True)
class WeightedSample:
    pixel_id: int
    owner_chain_id: int
    chain_index: int
    x: int
    y: int
    label: int
    cell: int
    weight: int


@dataclass(frozen=True)
class TemplateEvidence:
    thinning: ThinningResult
    chains: tuple[Chain, ...]
    samplings: tuple[ChainSampling, ...]
    ownership: tuple[SampleOwnership, ...]
    samples: tuple[WeightedSample, ...]
    cell_counts: tuple[int, ...]
    occupied_cells: int
    lcm: int
    denominator: int


def reference_thinning(grid) -> ThinningResult:
    """Intentionally fixed-empty, without algorithm or validation."""
    return ThinningResult(0, 0, (), (), ())


def reference_chains(grid) -> tuple[Chain, ...]:
    """Intentionally fixed-empty, without algorithm or validation."""
    return ()


def reference_sampling(chain: Chain, width: int) -> ChainSampling:
    """Intentionally fixed-empty, without algorithm or validation."""
    return ChainSampling(chain.chain_id, (), 0)


def fractional_weights(cells) -> tuple[Fraction, ...]:
    """Intentionally fixed-empty, before independent Fraction implementation."""
    return ()


def reference_template(grid) -> TemplateEvidence:
    """Intentionally fixed-empty, without algorithm or validation."""
    return TemplateEvidence(reference_thinning(grid), (), (), (), (), (0,) * 16, 0, 0, 0)
