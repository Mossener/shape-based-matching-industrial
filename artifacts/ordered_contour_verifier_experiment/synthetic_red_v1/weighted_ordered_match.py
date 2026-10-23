"""Synthetic weighted-chain API -- deliberately zero-result RED stub.

No image/gradient/detector work belongs in this module. This file is a Python
mathematical prototype, not a native implementation or a latency claim.

API (all matching inputs are supplied, not generated here):

* TemplateChain: canonical sample order, unique nonnegative integer physical
  sample IDs, strictly positive builtin-int weights, and a boolean closed flag.
* SceneChain: canonical unique physical pixel order, unique nonnegative integer
  chain ID, supplied (template_sample_id, scene_pixel_id) edges, closed flag.
  Physical pixels may occur in different scene chains. Edges within a chain
  must be unique. Input order defines topology; IDs are never numerically
  sorted to change that topology.
* solve(template, scenes): one template chain chooses at most one scene chain;
  returns the exact integer optimum and independent-support upper bound.
  Empty template chains/zero edges are legal zero contributions. All supplied
  IDs/weights/flags, including unused/empty chains, are validated by solve.
* MatchCase cuts are zero-based indices in the supplied canonical order.
  Direction is +1/-1 on the scene. An unmatched result has case=None.
* witness is a tuple of original edge IDs in matched, transformed template
  order. Case ties precede the colexicographic original-edge witness tie.
* WorkCounters count all enumerated nonempty cases, not only the winner.

Do not claim a RED observation merely because this stub exists. The root must
run the handwritten tests and retain the actual expected assertion failures
before the matching implementation replaces this stub.
"""
from dataclasses import dataclass

Edge = tuple[int, int]


@dataclass(frozen=True)
class TemplateChain:
    chain_id: int
    sample_ids: tuple[int, ...]
    weights: tuple[int, ...]
    closed: bool = False


@dataclass(frozen=True)
class SceneChain:
    chain_id: int
    pixel_ids: tuple[int, ...]
    edges: tuple[Edge, ...]
    closed: bool = False


@dataclass(frozen=True)
class MatchCase:
    scene_chain_id: int
    direction: int
    template_cut: int
    scene_cut: int


@dataclass(frozen=True)
class WorkCounters:
    case_count: int = 0
    edge_states: int = 0
    fenwick_queries: int = 0
    fenwick_updates: int = 0
    fenwick_query_visits: int = 0
    fenwick_update_visits: int = 0
    maximum_integer_bits: int = 0


@dataclass(frozen=True)
class MatchResult:
    template_chain_id: int
    numerator: int
    independent_numerator: int
    total_weight: int
    case: MatchCase | None
    witness: tuple[Edge, ...]
    work: WorkCounters


def solve(template: TemplateChain, scenes: tuple[SceneChain, ...]) -> MatchResult:
    """Return deliberately zero output until the root observes the RED run."""
    return MatchResult(template.chain_id, 0, 0, 0, None, (), WorkCounters())
