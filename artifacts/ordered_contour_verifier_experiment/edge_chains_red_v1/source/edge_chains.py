"""Tiny supplied-label chain API -- fixed-empty stub for coordinated RED.

No OpenCV, image decode, warp, gradient generation, matcher or file I/O belongs
here. A caller supplies a finite rectangular nonempty list/tuple grid of
builtin-int 0..7 labels or 255 (invalid). Direction labels survive unchanged.

thin_labels(grid) snapshots the eligible grid, runs both Zhang--Suen deletion
subiterations synchronously, and records (subiteration1, subiteration2) counts
for every full round, including the final (0,0) terminating round.

extract_chains(thinned_grid) works on exactly the supplied grid: it does not
thin again or assert that its argument is a fixed point of thinning. Pixel ID
is y*width+x; all eight neighbor edges are decomposed once into maximal trails.
Chain IDs follow sorted canonical sequences. Closed chains do not repeat the
first ID at the end. returning=True identifies a return to one junction.

sample_chain(chain,width) uses exact axis1000/diagonal1414 arclength and fixed
2000 markers. It accepts a unique-ID adjacent chain, but cannot prove it came
from a particular graph without that graph. A closed chain requires >=3 nodes.
Open endpoints and the canonical first closed point are retained. Markers in
the closing edge select the next first point, which is deduplicated. Sampling
order remains chain order, not sorted numerical pixel order.

prepare_template(grid) combines these stages, assigns every shared sampled
physical pixel to its lowest chain ID, and computes global 4x4 bbox cells.
Ownership rows and WeightedSample rows are in physical-ID order; each sample's
chain_index names its original owner's canonical full-chain position. A chain
with no owned samples remains present and contributes zero. A whole template
with no owned samples raises ValueError. Occupied-cell LCM weights are exact
positive Python ints. The output arrays are immutable tuples/frozen dataclasses.

This is only an API stub. Root must observe real assertion failures before
implementation. A later mathematical pass cannot establish pixel provenance,
detector quality, native performance or industrial generalization.
"""
from dataclasses import dataclass

LabelGrid = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class ThinningResult:
    width: int
    height: int
    eligible_labels: LabelGrid
    labels: LabelGrid
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


def thin_labels(grid) -> ThinningResult:
    """Fixed empty RED stub; no validation or thinning implementation yet."""
    return ThinningResult(0, 0, (), (), ())


def extract_chains(thinned_grid) -> tuple[Chain, ...]:
    """Fixed empty RED stub; no graph construction implementation yet."""
    return ()


def sample_chain(chain: Chain, width: int) -> ChainSampling:
    """Fixed empty RED stub; no sampling/validation implementation yet."""
    return ChainSampling(chain.chain_id, (), 0)


def prepare_template(grid) -> TemplateEvidence:
    """Fixed empty RED stub; no ownership/cell implementation yet."""
    return TemplateEvidence(thin_labels(grid), (), (), (), (), (0,) * 16, 0, 0, 0)
