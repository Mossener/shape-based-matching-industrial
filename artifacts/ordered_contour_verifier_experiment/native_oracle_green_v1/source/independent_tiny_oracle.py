"""Tiny independent oracle for supplied ordered compatibility graphs.

The objective is computed by enumerating partial injective correspondences and
testing their original open/circular order. It does not import or call the
optimized solver's Fenwick, validation, cut, or witness helpers. The score
predicate has no cut variables, so it also checks the one-sided cut reduction.

Canonical case/witness ties are checked separately: every optimum injection is
tested against explicit walks of the declared case domain, including all cut
positions before incidence filtering. This tie check necessarily uses the
contract's case definition, but never supplies the objective's order predicate.

Public API:
  brute_force(template, scenes) -> OracleResult
  audit_result(template, scenes, result, reference=None) -> None or AssertionError
  run_exhaustive(solver, seconds=45.0) -> compact counts
  run_seeded(solver, seed=20261023, seconds=8.0) -> compact counts

Inputs expose only the public TemplateChain/SceneChain fields. Oracle inputs
are limited to eight points per chain. Exhaustion includes n,m=0..3, all edge
graphs, four open/closed types, two positive-ID profiles, and every membership
partition of template points among at most 16 cells, modulo cell renaming.
Each weight is genuinely LCM(occupancies)/own occupancy; it is not an arbitrary
small weight assignment. Realizable partitions are additionally bound to
distinct synthetic coordinates and the actual 4x4 bbox rule. A nontrivial
all-in-one-cell partition is only an abstract membership case: distinct points
cannot all land in one cell of their own bbox. Its weights coincide with the
all-singleton partition, but that does not make its geometry realizable.

No images, chains from pixels, native implementation, quality, or timing claim
belongs here. Drivers have a wall guard; the coordinator must impose the
60-second / 512-MiB RSS / 64-MiB output process limits around the complete run.
"""
from dataclasses import dataclass
from math import lcm
import random
from time import monotonic


@dataclass(frozen=True)
class OracleResult:
    numerator: int
    independent_numerator: int
    total_weight: int
    case: tuple[int, int, int, int] | None
    witness: tuple[tuple[int, int], ...]
    partial_injections_checked: int


@dataclass(frozen=True)
class _Template:
    chain_id: int
    sample_ids: tuple[int, ...]
    weights: tuple[int, ...]
    closed: bool


@dataclass(frozen=True)
class _Scene:
    chain_id: int
    pixel_ids: tuple[int, ...]
    edges: tuple[tuple[int, int], ...]
    closed: bool


def _ids(values, name):
    if not isinstance(values, (tuple, list)):
        raise ValueError(name + " must be a sequence")
    result = tuple(values)
    if any(type(value) is not int or value < 0 for value in result):
        raise ValueError(name + " must have nonnegative integer IDs")
    if len(set(result)) != len(result):
        raise ValueError(name + " repeats a physical ID")
    if len(result) > 8:
        raise ValueError("tiny oracle supports at most eight points per chain")
    return result


def _inputs(template, scenes):
    """Independent public-boundary snapshot, not the solver's validator."""
    samples = _ids(template.sample_ids, "template")
    if not isinstance(template.weights, (tuple, list)):
        raise ValueError("weights must be a sequence")
    weights = tuple(template.weights)
    if len(weights) != len(samples) or any(type(w) is not int or w <= 0 for w in weights):
        raise ValueError("weights must be positive integers, one per sample")
    if type(template.chain_id) is not int or template.chain_id < 0:
        raise ValueError("invalid template chain ID")
    if type(template.closed) is not bool or not isinstance(scenes, (tuple, list)):
        raise ValueError("invalid closed flag or scene collection")
    checked_scenes, chain_ids = [], set()
    for scene in scenes:
        pixels = _ids(scene.pixel_ids, "scene")
        if type(scene.chain_id) is not int or scene.chain_id < 0 or scene.chain_id in chain_ids:
            raise ValueError("invalid or repeated scene chain ID")
        chain_ids.add(scene.chain_id)
        if type(scene.closed) is not bool or not isinstance(scene.edges, (tuple, list)):
            raise ValueError("invalid scene flag or edge collection")
        edges = []
        for edge in scene.edges:
            if not isinstance(edge, (tuple, list)) or len(edge) != 2:
                raise ValueError("an edge needs two original physical IDs")
            a, b = edge
            if type(a) is not int or type(b) is not int or a not in samples or b not in pixels:
                raise ValueError("edge references an unknown physical ID")
            if (a, b) in edges:
                raise ValueError("duplicate compatibility edge")
            edges.append((a, b))
        checked_scenes.append(_Scene(scene.chain_id, pixels, tuple(edges), scene.closed))
    return (_Template(template.chain_id, samples, weights, template.closed),
            tuple(checked_scenes))


def circular_order(indices, period):
    """A distinct sequence travels forward around its original cycle once.

    For two or more entries a circular traversal has exactly one descent when
    its closing step is included. Counting just internal descents would admit
    a second turn across the start/end seam. No cut or doubled list is used.
    """
    indices = tuple(indices)
    if type(period) is not int or period < 0:
        raise ValueError("period must be a nonnegative integer")
    if any(type(index) is not int or not 0 <= index < period for index in indices):
        return False
    if len(indices) != len(set(indices)):
        return False
    if len(indices) < 2:
        return True
    return sum(left > right for left, right in
               zip(indices, indices[1:] + indices[:1])) == 1


def _original_order(template, scene, matching, direction):
    """Order predicate on original indices, independent of all linearizations."""
    if len(matching) < 2:
        return True
    if scene.closed:
        ordered = sorted(matching)  # original template orientation, seam 0
        columns = tuple(j if direction == 1 else len(scene.pixel_ids) - 1 - j
                        for _, j in ordered)
        return circular_order(columns, len(scene.pixel_ids))
    if template.closed:
        # An open scene fixes the start/end; the template is tested as a cycle.
        ordered = sorted(matching, key=lambda edge: direction * edge[1])
        return circular_order(tuple(i for i, _ in ordered), len(template.sample_ids))
    columns = tuple(direction * j for _, j in sorted(matching))
    return all(a < b for a, b in zip(columns, columns[1:]))


def _walk(length, cut, direction, closed):
    """Explicit physical-order walk, used only for case/witness tie checking."""
    order = list(range(length))
    if not closed:
        return order if direction == 1 else order[::-1]
    forward = order[cut:] + order[:cut]
    return forward if direction == 1 else forward[:1] + forward[1:][::-1]


def _declared_cases(template, scene):
    """Visit full physical cuts, then enforce the declared admissible domain."""
    n, m = len(template.sample_ids), len(scene.pixel_ids)
    incident_samples = {sample for sample, _ in scene.edges}
    incident_pixels = {pixel for _, pixel in scene.edges}
    directions = (1,) if m == 1 else (1, -1)
    for direction in directions:
        for template_cut in (range(n) if template.closed else (0,)):
            if template.closed and scene.closed and template_cut != 0:
                continue
            if template.closed and not scene.closed and template.sample_ids[template_cut] not in incident_samples:
                continue
            for scene_cut in (range(m) if scene.closed else (0,)):
                if scene.closed and scene.pixel_ids[scene_cut] not in incident_pixels:
                    continue
                yield (scene.chain_id, direction, template_cut, scene_cut)


def _case_witness(template, scene, matching, case):
    _, direction, template_cut, scene_cut = case
    template_rank = {value: rank for rank, value in enumerate(
        _walk(len(template.sample_ids), template_cut, 1, template.closed))}
    scene_rank = {value: rank for rank, value in enumerate(
        _walk(len(scene.pixel_ids), scene_cut, direction, scene.closed))}
    ordered = sorted(matching, key=lambda edge: template_rank[edge[0]])
    columns = tuple(scene_rank[j] for _, j in ordered)
    if not all(a < b for a, b in zip(columns, columns[1:])):
        return None
    return tuple((template.sample_ids[i], scene.pixel_ids[j]) for i, j in ordered)


def brute_force(template, scenes):
    """Enumerate partial injections; return exact optimum and full canonical tie."""
    template, scenes = _inputs(template, scenes)
    sample_index = {sample: i for i, sample in enumerate(template.sample_ids)}
    total = sum(template.weights)
    supported = {sample for scene in scenes for sample, _ in scene.edges}
    independent = sum(weight for sample, weight in zip(template.sample_ids, template.weights)
                      if sample in supported)
    best_score, optimum_injections, checked = 0, [], 0
    for scene in scenes:
        pixel_index = {pixel: j for j, pixel in enumerate(scene.pixel_ids)}
        neighbors = [[] for _ in template.sample_ids]
        for sample, pixel in scene.edges:
            neighbors[sample_index[sample]].append(pixel_index[pixel])
        directions = (1,) if len(scene.pixel_ids) == 1 else (1, -1)

        def visit(i, used_scene, matching, score):
            nonlocal best_score, optimum_injections, checked
            if i == len(template.sample_ids):
                checked += 1
                if not matching or score < best_score:
                    return
                if not any(_original_order(template, scene, matching, d) for d in directions):
                    return
                if score > best_score:
                    best_score, optimum_injections = score, []
                optimum_injections.append((scene, tuple(matching)))
                return
            visit(i + 1, used_scene, matching, score)  # unmatched template point
            for j in neighbors[i]:
                bit = 1 << j
                if used_scene & bit:
                    continue
                matching.append((i, j))
                visit(i + 1, used_scene | bit, matching, score + template.weights[i])
                matching.pop()

        visit(0, 0, [], 0)
    if best_score == 0:
        return OracleResult(0, independent, total, None, (), checked)
    winner = None
    for scene, matching in optimum_injections:
        for case in _declared_cases(template, scene):
            witness = _case_witness(template, scene, matching, case)
            if witness is None:
                continue
            key = (case[0], 0 if case[1] == 1 else 1, case[2], case[3],
                   tuple(reversed(witness)))
            if winner is None or key < winner[0]:
                winner = (key, case, witness)
    if winner is None:
        raise AssertionError("original cyclic optimum has no declared-case representation")
    return OracleResult(best_score, independent, total, winner[1], winner[2], checked)


def audit_result(template, scenes, result, *, reference=None):
    """Reject illegal, suboptimal, inexact, or noncanonical solver evidence."""
    if reference is None:
        reference = brute_force(template, scenes)
    template, scenes = _inputs(template, scenes)
    assert type(result.numerator) is int, "numerator must remain an exact builtin integer"
    assert type(result.independent_numerator) is int, "independent support must remain integer"
    assert type(result.total_weight) is int, "total weight must remain integer"
    assert result.template_chain_id == template.chain_id, "wrong template chain identity"
    assert result.total_weight == reference.total_weight, "changed complete denominator weight"
    assert result.independent_numerator == reference.independent_numerator, "wrong A support union"
    assert 0 <= result.numerator <= result.independent_numerator <= result.total_weight, "B <= A <= total violated"
    assert result.numerator == reference.numerator, "suboptimal or excessive exact numerator"
    if result.numerator == 0:
        assert result.case is None and tuple(result.witness) == (), "zero result has a witness/case"
        return
    assert result.case is not None, "positive result lacks case"
    case = (result.case.scene_chain_id, result.case.direction,
            result.case.template_cut, result.case.scene_cut)
    selected = [scene for scene in scenes if scene.chain_id == case[0]]
    assert len(selected) == 1, "case selects no unique scene chain"
    scene = selected[0]
    assert case in tuple(_declared_cases(template, scene)), "case outside declared cut/direction domain"
    witness = tuple(tuple(edge) for edge in result.witness)
    assert witness, "positive result has empty witness"
    assert all(edge in scene.edges for edge in witness), "witness edge absent from selected compatibility graph"
    assert len({a for a, _ in witness}) == len(witness), "witness reuses a template sample"
    assert len({b for _, b in witness}) == len(witness), "witness reuses a scene physical pixel"
    sample_index = {sample: i for i, sample in enumerate(template.sample_ids)}
    pixel_index = {pixel: j for j, pixel in enumerate(scene.pixel_ids)}
    matching = tuple((sample_index[a], pixel_index[b]) for a, b in witness)
    assert _original_order(template, scene, matching, case[1]), "witness violates original cyclic order"
    assert _case_witness(template, scene, matching, case) == witness, "witness order violates selected physical walks"
    assert sum(template.weights[i] for i, _ in matching) == result.numerator, "witness does not justify numerator"
    assert case == reference.case, "case tie order violated"
    assert witness == reference.witness, "reversed-original-edge witness tie order violated"


def cell_weights(cells):
    """Exact contract weights for actual 4x4 cell labels, with complete D."""
    cells = tuple(cells)
    if any(type(cell) is not int or not 0 <= cell < 16 for cell in cells):
        raise ValueError("4x4 cell labels must be integers in 0..15")
    if not cells:
        return (), 0
    counts = {cell: cells.count(cell) for cell in set(cells)}
    common = lcm(*counts.values())
    return tuple(common // counts[cell] for cell in cells), len(counts) * common


def cell_partitions(size):
    """All cell membership partitions once, using restricted-growth labels."""
    if type(size) is not int or not 0 <= size <= 16:
        raise ValueError("partition size must be an integer in 0..16")
    if size == 0:
        yield ()
        return

    def extend(word, maximum):
        if len(word) == size:
            yield tuple(word)
            return
        for cell in range(maximum + 2):
            word.append(cell)
            yield from extend(word, max(maximum, cell))
            word.pop()

    yield from extend([0], 0)


def partition_coordinates(partition):
    """Realize each n<=3 feasible partition by distinct integer coordinates.

    None explicitly marks the impossible all-in-one-cell geometry for n>1.
    Cell names may differ after bbox normalization; memberships/weights agree.
    """
    partition = tuple(partition)
    if len(partition) > 3:
        raise ValueError("coordinate realization is limited to n<=3")
    cell_weights(partition)  # validate the declared cell labels
    if len(partition) > 1 and len(set(partition)) == 1:
        return None
    block_ids, occurrences, coordinates = {}, {}, []
    for cell in partition:
        block_ids.setdefault(cell, len(block_ids))
        offset = occurrences.get(cell, 0)
        coordinates.append((64 * block_ids[cell] + offset, 0))
        occurrences[cell] = offset + 1
    return tuple(coordinates)


def bbox_cells(coordinates):
    """Independent integer implementation of the specified 4x4 bbox rule."""
    coordinates = tuple(coordinates)
    if not coordinates:
        return ()
    xmin, xmax = min(x for x, _ in coordinates), max(x for x, _ in coordinates)
    ymin, ymax = min(y for _, y in coordinates), max(y for _, y in coordinates)
    return tuple(4 * (4 * (y - ymin) // (ymax - ymin + 1))
                 + 4 * (x - xmin) // (xmax - xmin + 1) for x, y in coordinates)


class _WallGuard:
    def __init__(self, seconds):
        if not 0 < seconds <= 60:
            raise ValueError("tiny run must reserve at most 60 seconds")
        self.deadline = monotonic() + seconds

    def check(self):
        if monotonic() > self.deadline:
            raise TimeoutError("tiny oracle wall budget exhausted; incomplete")


def _positive_ids(size, scene, variant, closed):
    base = 11 + 1000 * scene + 100 * variant
    values = [base + 12 * i for i in range(size)]
    # For three closed nodes the canonical dihedral representative is sorted.
    # Open triples and cycles with >=4 nodes can have nonmonotonic IDs while
    # preserving canonical endpoint/dihedral orientation.
    if size >= 3 and (not closed or size >= 4):
        values[1], values[2] = values[2], values[1]
    if variant == 0:
        values.sort()
    return tuple(values)


def run_exhaustive(solver, *, seconds=45.0):
    """Exactly 24,912 small comparisons, with no numeric result sampling."""
    # Public data carriers only; no optimized implementation helper is used.
    from weighted_ordered_match import SceneChain, TemplateChain

    guard = _WallGuard(seconds)
    comparisons = realized = abstract = 0
    for n in range(4):
        for cells in cell_partitions(n):
            coordinates = partition_coordinates(cells)
            weights, denominator = cell_weights(cells)
            if coordinates is not None:
                assert cell_weights(bbox_cells(coordinates)) == (weights, denominator)
            for m in range(4):
                for template_closed in (False, True):
                    for scene_closed in (False, True):
                        for variant in range(2):
                            samples = _positive_ids(n, False, variant, template_closed)
                            pixels = _positive_ids(m, True, variant, scene_closed)
                            template = TemplateChain(3, samples, weights, template_closed)
                            possible = tuple((a, b) for a in samples for b in pixels)
                            for mask in range(1 << (n * m)):
                                if comparisons % 128 == 0:
                                    guard.check()
                                edges = tuple(edge for bit, edge in enumerate(possible) if mask & (1 << bit))
                                scenes = (SceneChain(7, pixels, edges, scene_closed),)
                                expected = brute_force(template, scenes)
                                try:
                                    audit_result(template, scenes, solver(template, scenes), reference=expected)
                                except AssertionError as failure:
                                    raise AssertionError((n, m, cells, template_closed, scene_closed,
                                                          variant, mask, str(failure))) from failure
                                comparisons += 1
                                realized += coordinates is not None
                                abstract += coordinates is None
    guard.check()
    return {"comparisons": comparisons, "bbox_realizable_comparisons": realized,
            "abstract_membership_comparisons": abstract, "id_profiles": 2,
            "maximum_n": 3, "maximum_m": 3,
            "tie_scope": "full declared case and reversed-original-edge witness"}


def run_seeded(solver, *, seed=20261023, seconds=8.0):
    """100 sparse finite cases for every n,m=4..8 and four topology types."""
    from weighted_ordered_match import SceneChain, TemplateChain

    guard, rng, comparisons = _WallGuard(seconds), random.Random(seed), 0
    for n in range(4, 9):
        for m in range(4, 9):
            for template_closed in (False, True):
                for scene_closed in (False, True):
                    guard.check()
                    samples = _positive_ids(n, False, 1, template_closed)
                    pixels = _positive_ids(m, True, 1, scene_closed)
                    coordinates = rng.sample(tuple((x, y) for x in range(12) for y in range(12)), n)
                    weights, _ = cell_weights(bbox_cells(coordinates))
                    edges = tuple((sample, pixel) for sample in samples
                                  for pixel in rng.sample(pixels, 2))
                    template = TemplateChain(3, samples, weights, template_closed)
                    scenes = (SceneChain(7, pixels, edges, scene_closed),)
                    expected = brute_force(template, scenes)
                    audit_result(template, scenes, solver(template, scenes), reference=expected)
                    comparisons += 1
    guard.check()
    return {"comparisons": comparisons, "seed": seed, "maximum_n": 8, "maximum_m": 8}


if __name__ == "__main__":
    import json
    from weighted_ordered_match import solve

    print(json.dumps({"exhaustive": run_exhaustive(solve),
                      "seeded": run_seeded(solve)}, sort_keys=True))
