"""Exact sparse weighted matching on supplied synthetic chain graphs.

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
* All input collections are tuples/lists; solve snapshots them into tuples.
  Validation failures raise ValueError, including bool where an int is needed.
* Positive weights are required. The empty chain is the legal zero-weight
  contribution, rather than individual zero/negative-weight scoring samples.

For a fixed case, one state per compatible edge stores its exact Python-int
score and a predecessor index. Fenwick prefix maxima query strict scene rank,
and all edges of one template row query before any of that row updates.
Original edge IDs resolve equal scores in colexicographic witness order. Cases
are visited in the declared case tie order, so later equal scores do not win.
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


@dataclass
class _Counters:
    case_count: int = 0
    edge_states: int = 0
    fenwick_queries: int = 0
    fenwick_updates: int = 0
    fenwick_query_visits: int = 0
    fenwick_update_visits: int = 0
    maximum_integer_bits: int = 0

    def snapshot(self) -> WorkCounters:
        return WorkCounters(**vars(self))


@dataclass(frozen=True, slots=True)
class _State:
    score: int
    edge: Edge | None
    predecessor: int


def _integer(value, name: str, *, positive: bool = False) -> None:
    if type(value) is not int or (value <= 0 if positive else value < 0):
        requirement = "a positive builtin int" if positive else "a nonnegative builtin int"
        raise ValueError(name + " must be " + requirement)


def _sequence(value, name: str) -> tuple:
    if not isinstance(value, (tuple, list)):
        raise ValueError(name + " must be a tuple or list")
    return tuple(value)


def _physical_ids(values, name: str) -> tuple[int, ...]:
    values = _sequence(values, name)
    for value in values:
        _integer(value, name + " entry")
    if len(set(values)) != len(values):
        raise ValueError(name + " must contain unique physical IDs")
    return values


def _validated(template, scenes) -> tuple[TemplateChain, tuple[SceneChain, ...]]:
    """Snapshot and validate every supplied chain before handling zero edges."""
    if not isinstance(template, TemplateChain):
        raise ValueError("template must be a TemplateChain")
    _integer(template.chain_id, "template chain ID")
    if type(template.closed) is not bool:
        raise ValueError("template closed flag must be bool")
    sample_ids = _physical_ids(template.sample_ids, "template sample IDs")
    weights = _sequence(template.weights, "template weights")
    if len(weights) != len(sample_ids):
        raise ValueError("weights and template sample IDs must have equal length")
    for weight in weights:
        _integer(weight, "template weight", positive=True)
    known_samples = set(sample_ids)
    validated = []
    scene_chain_ids = set()
    for scene in _sequence(scenes, "scene chains"):
        if not isinstance(scene, SceneChain):
            raise ValueError("each scene must be a SceneChain")
        _integer(scene.chain_id, "scene chain ID")
        if scene.chain_id in scene_chain_ids:
            raise ValueError("scene chain IDs must be unique")
        scene_chain_ids.add(scene.chain_id)
        if type(scene.closed) is not bool:
            raise ValueError("scene closed flag must be bool")
        pixel_ids = _physical_ids(scene.pixel_ids, "scene pixel IDs")
        known_pixels = set(pixel_ids)
        edges = []
        seen_edges = set()
        for supplied_edge in _sequence(scene.edges, "compatibility edges"):
            edge = _sequence(supplied_edge, "compatibility edge")
            if len(edge) != 2:
                raise ValueError("compatibility edge must contain exactly two IDs")
            sample_id, pixel_id = edge
            _integer(sample_id, "edge template sample ID")
            _integer(pixel_id, "edge scene pixel ID")
            if sample_id not in known_samples or pixel_id not in known_pixels:
                raise ValueError("compatibility edge refers to an unknown physical ID")
            if edge in seen_edges:
                raise ValueError("compatibility edges within a scene chain must be unique")
            seen_edges.add(edge)
            edges.append(edge)
        # Canonical edge order does not alter either chain's supplied topology.
        validated.append(SceneChain(scene.chain_id, pixel_ids,
                                    tuple(sorted(edges)), scene.closed))
    validated.sort(key=lambda scene: scene.chain_id)
    return (TemplateChain(template.chain_id, sample_ids, weights, template.closed),
            tuple(validated))


def _better(left: int, right: int, states: list[_State]) -> int:
    """Exact score first, then smallest reversed original-edge witness.

    Every nonempty state has a unique terminal edge within its case. Equal
    terminal IDs therefore identify the same already-canonical state, while
    different terminal IDs decide the colex comparison immediately. A state
    was itself created from the canonical best prefix by this same rule.
    """
    if left == right:
        return left
    if states[left].score != states[right].score:
        return left if states[left].score > states[right].score else right
    if left == 0:
        return right
    if right == 0:
        return left
    return left if states[left].edge < states[right].edge else right


def _run_case(template: TemplateChain, scene: SceneChain, case: MatchCase,
              template_positions: dict[int, int], weights: dict[int, int],
              work: _Counters) -> tuple[int, tuple[Edge, ...]]:
    """Solve one linearized compatibility DAG with batched sparse row updates."""
    n, m = len(template.sample_ids), len(scene.pixel_ids)
    scene_positions = {pixel: index for index, pixel in enumerate(scene.pixel_ids)}
    transformed = []
    for edge in scene.edges:
        sample_id, pixel_id = edge
        row, column = template_positions[sample_id], scene_positions[pixel_id]
        if template.closed:
            row = (row - case.template_cut) % n
        if scene.closed:
            column = (case.direction * (column - case.scene_cut)) % m
        elif case.direction == -1:
            column = m - 1 - column
        transformed.append((row, column, edge))
    transformed.sort()
    # Only ranks incident to compatibility edges are needed. Their strict
    # order is unchanged by dropping all nonincident scene nodes.
    columns = sorted({column for _, column, _ in transformed})
    ranks = {column: rank for rank, column in enumerate(columns)}
    tree = [0] * (len(columns) + 1)
    states = [_State(0, None, 0)]
    best = 0
    cursor = 0
    work.case_count += 1
    while cursor < len(transformed):
        end = cursor + 1
        row = transformed[cursor][0]
        while end < len(transformed) and transformed[end][0] == row:
            end += 1
        pending = []
        for _, column, edge in transformed[cursor:end]:
            rank = ranks[column]
            index = rank  # strict prefix: current column is rank+1 in the tree.
            prefix = 0
            work.fenwick_queries += 1
            while index:
                prefix = _better(prefix, tree[index], states)
                work.fenwick_query_visits += 1
                index -= index & -index
            score = states[prefix].score + weights[edge[0]]
            states.append(_State(score, edge, prefix))
            state_index = len(states) - 1
            work.edge_states += 1
            work.maximum_integer_bits = max(work.maximum_integer_bits, score.bit_length())
            pending.append((rank + 1, state_index))
            best = _better(best, state_index, states)
        # No state from the current template row was visible to its queries.
        for index, state_index in pending:
            work.fenwick_updates += 1
            while index < len(tree):
                tree[index] = _better(tree[index], state_index, states)
                work.fenwick_update_visits += 1
                index += index & -index
        cursor = end
    witness = []
    state_index = best
    while state_index:
        state = states[state_index]
        witness.append(state.edge)
        state_index = state.predecessor
    witness.reverse()
    return states[best].score, tuple(witness)


def solve(template: TemplateChain, scenes: tuple[SceneChain, ...]) -> MatchResult:
    """Return exact B optimum, A point-support bound, witness and work counts.

    Input collections may also be lists. Case ties use scene chain ID, scene
    direction (+1 first), template cut, then scene cut. Witness ties apply
    only within that first winning case. For no compatible edge, case is None
    and the original total weight is preserved. solve handles only one
    template chain; summing separate results permits the contract's cross-
    template-chain pixel reuse. No global scene assignment is introduced.
    """
    template, scenes = _validated(template, scenes)
    template_positions = {sample: index for index, sample in enumerate(template.sample_ids)}
    weights = dict(zip(template.sample_ids, template.weights))
    total_weight = sum(template.weights)
    supported = {sample_id for scene in scenes for sample_id, _ in scene.edges}
    independent = sum(weights[sample] for sample in supported)
    work = _Counters(maximum_integer_bits=total_weight.bit_length())
    best_score, best_case, best_witness = 0, None, ()
    for scene in scenes:
        if not scene.edges:
            continue
        scene_positions = {pixel: index for index, pixel in enumerate(scene.pixel_ids)}
        directions = (1,) if len(scene.pixel_ids) == 1 else (1, -1)
        template_cuts = (sorted({template_positions[sample] for sample, _ in scene.edges})
                         if template.closed and not scene.closed else (0,))
        scene_cuts = (sorted({scene_positions[pixel] for _, pixel in scene.edges})
                      if scene.closed else (0,))
        for direction in directions:
            for template_cut in template_cuts:
                for scene_cut in scene_cuts:
                    case = MatchCase(scene.chain_id, direction, template_cut, scene_cut)
                    score, witness = _run_case(template, scene, case,
                                               template_positions, weights, work)
                    # Enumeration is in case tie order; a later tie cannot win.
                    if score > best_score:
                        best_score, best_case, best_witness = score, case, witness
    return MatchResult(template.chain_id, best_score, independent, total_weight,
                       best_case, best_witness, work.snapshot())
