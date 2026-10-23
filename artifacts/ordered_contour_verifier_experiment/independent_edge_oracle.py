"""Independent mathematical reference for tiny supplied eligible-label grids.

Root captured real RED against the fixed-empty predecessor before authorizing
this implementation. No edge_chains helper is imported or called; only its
public field schema forms the comparison boundary.

Thinning evaluates Boolean deletion predicates on synchronous active-point
sets. Graph construction tests all coordinate pairs. Chain decomposition uses
connected components of the degree-two induced subgraph, rather than the
contract implementation's junction/unused-edge traversal. Each such component
is a pure cycle or a path with two boundary attachments. Boundary-boundary
edges and isolated points complete the decomposition. Return loops have the
same boundary attachment at both ends and store that junction only once.

Sampling finds marker positions by cumulative integer length and binary search.
Ownership precedes cell assignment. Cell mass is computed independently as a
Fraction first; the common rational denominator then gives integer weights.

All work is mathematical on tiny supplied labels. It establishes no RGB pixel
provenance, image experiment, detector accuracy, native timing, or production
authorization. The coordinator owns wall/RSS/output process limits. This source
contains no test runner and performs no filesystem or image I/O.
"""
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from itertools import accumulate, combinations
from math import gcd

ORACLE_PHASE = "INDEPENDENT_REFERENCE_IMPLEMENTATION_V1"


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


def _eligible_grid(grid):
    """Snapshot the supplied labels without borrowing core validation."""
    if not isinstance(grid, (list, tuple)) or not grid:
        raise ValueError("eligible grid must be nonempty")
    if any(not isinstance(row, (list, tuple)) or not row for row in grid):
        raise ValueError("eligible rows must be nonempty sequences")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("eligible grid must be rectangular")
    result = tuple(tuple(row) for row in grid)
    if any(type(label) is not int or label not in (0, 1, 2, 3, 4, 5, 6, 7, 255)
           for row in result for label in row):
        raise ValueError("labels must be builtin ints in 0..7 or 255")
    return result


def _deletable(active, point, second):
    x, y = point
    ring = tuple((x + dx, y + dy) in active for dx, dy in (
        (0, -1), (1, -1), (1, 0), (1, 1),
        (0, 1), (-1, 1), (-1, 0), (-1, -1)))
    if not 2 <= sum(ring) <= 6:
        return False
    starts = sum(ring[index] and not ring[index - 1] for index in range(8))
    if starts != 1:
        return False
    north, east, south, west = ring[0], ring[2], ring[4], ring[6]
    if second:
        return not (north and east and west) and not (north and south and west)
    return not (north and east and south) and not (east and south and west)


def reference_thinning(grid) -> ThinningResult:
    """Zhang--Suen predicates on sets, deleting an entire subiteration at once."""
    eligible = _eligible_grid(grid)
    height, width = len(eligible), len(eligible[0])
    active = {(x, y) for y, row in enumerate(eligible)
              for x, label in enumerate(row) if label != 255}
    rounds = []
    while True:
        first = {point for point in active if _deletable(active, point, False)}
        active.difference_update(first)
        second = {point for point in active if _deletable(active, point, True)}
        active.difference_update(second)
        rounds.append((len(first), len(second)))
        if not first and not second:
            break
    labels = tuple(tuple(label if (x, y) in active else 255
                         for x, label in enumerate(row))
                   for y, row in enumerate(eligible))
    return ThinningResult(width, height, eligible, labels, tuple(rounds))


def _canonical(sequence, closed):
    sequence = tuple(sequence)
    if not closed:
        return min(sequence, sequence[::-1])
    alternatives = [direction[cut:] + direction[:cut]
                    for direction in (sequence, sequence[::-1])
                    for cut in range(len(sequence))]
    return min(alternatives)


def _component_path(component, adjacency, start):
    """Traverse the unique internal path, without reserving global graph edges."""
    path, previous, current = [], None, start
    while True:
        path.append(current)
        next_nodes = (adjacency[current] & component) - {previous}
        if not next_nodes:
            break
        if len(next_nodes) != 1:
            raise AssertionError("degree-two induced component is not a path")
        previous, current = current, next(iter(next_nodes))
        if current in path:
            raise AssertionError("unexpected cycle in attached degree-two component")
    if set(path) != component:
        raise AssertionError("incomplete degree-two component path")
    return tuple(path)


def _component_cycle(component, adjacency):
    start = min(component)
    path, previous, current = [start], start, min(adjacency[start])
    while current != start:
        if current in path or current not in component:
            raise AssertionError("malformed pure degree-two cycle")
        path.append(current)
        following = adjacency[current] - {previous}
        if len(following) != 1:
            raise AssertionError("pure cycle vertex has wrong degree")
        previous, current = current, next(iter(following))
    if set(path) != component:
        raise AssertionError("incomplete pure cycle")
    return tuple(path)


def reference_chains(grid) -> tuple[Chain, ...]:
    """Decompose degree-two induced components and direct boundary edges."""
    labels = _eligible_grid(grid)
    width = len(labels[0])
    nodes = tuple(y * width + x for y, row in enumerate(labels)
                  for x, label in enumerate(row) if label != 255)
    adjacency = {pixel: set() for pixel in nodes}
    for left, right in combinations(nodes, 2):
        dx = abs(left % width - right % width)
        dy = abs(left // width - right // width)
        if max(dx, dy) == 1:
            adjacency[left].add(right)
            adjacency[right].add(left)
    boundary = {pixel for pixel in nodes if len(adjacency[pixel]) != 2}
    pending = set(nodes) - boundary
    trails = []
    for pixel in sorted(boundary):
        if not adjacency[pixel]:
            trails.append(((pixel,), False, False))
        for other in sorted(adjacency[pixel] & boundary):
            if pixel < other:
                trails.append(((pixel, other), False, False))
    while pending:
        seed, component, queue = min(pending), set(), []
        queue.append(seed)
        while queue:
            pixel = queue.pop()
            if pixel in component:
                continue
            component.add(pixel)
            queue.extend((adjacency[pixel] - boundary) - component)
        pending.difference_update(component)
        attachments = sorted((outside, inside) for inside in component
                             for outside in adjacency[inside] & boundary)
        if not attachments:
            sequence = _component_cycle(component, adjacency)
            trails.append((_canonical(sequence, True), True, False))
            continue
        if len(attachments) != 2:
            raise AssertionError("degree-two path needs exactly two boundary attachments")
        (left, start), (right, end) = attachments
        internal = _component_path(component, adjacency, start)
        if internal[-1] != end:
            raise AssertionError("degree-two component attachments disagree")
        returning = left == right
        sequence = (left,) + internal + (() if returning else (right,))
        trails.append((_canonical(sequence, returning), returning, returning))
    trails.sort(key=lambda row: (row[0], row[1]))
    return tuple(Chain(index, sequence, closed, returning)
                 for index, (sequence, closed, returning) in enumerate(trails))


def reference_sampling(chain: Chain, width: int) -> ChainSampling:
    """Find first reached vertices directly in cumulative exact arclength."""
    if type(width) is not int or width <= 0:
        raise ValueError("width must be a positive builtin integer")
    if type(chain.chain_id) is not int or chain.chain_id < 0:
        raise ValueError("chain ID must be a nonnegative builtin integer")
    if type(chain.closed) is not bool or type(chain.returning) is not bool:
        raise ValueError("chain flags must be bool")
    if chain.returning and not chain.closed:
        raise ValueError("a returning chain must be closed")
    if not isinstance(chain.pixel_ids, (list, tuple)) or not chain.pixel_ids:
        raise ValueError("a chain needs physical pixels")
    ids = tuple(chain.pixel_ids)
    if any(type(pixel) is not int or pixel < 0 for pixel in ids) or len(ids) != len(set(ids)):
        raise ValueError("physical IDs must be unique nonnegative builtin integers")
    if chain.closed and len(ids) < 3:
        raise ValueError("a closed chain needs at least three unique pixels")
    edges = tuple(zip(ids, ids[1:])) + (((ids[-1], ids[0]),) if chain.closed else ())
    lengths = []
    for left, right in edges:
        dx = abs(left % width - right % width)
        dy = abs(left // width - right // width)
        if max(dx, dy) != 1:
            raise ValueError("chain step is not an eight-neighbor edge")
        lengths.append(1414 if dx and dy else 1000)
    cumulative = (0,) + tuple(accumulate(lengths))
    total = cumulative[-1]
    selected = {0} if chain.closed else {0, len(ids) - 1}
    for marker in range(2000, total, 2000):
        reached = bisect_left(cumulative, marker)
        selected.add(reached % len(ids))
    pixels = tuple(pixel for index, pixel in enumerate(ids) if index in selected)
    return ChainSampling(chain.chain_id, pixels, total)


def fractional_weights(cells) -> tuple[Fraction, ...]:
    """Equal occupied-cell mass, expressed independently as exact fractions."""
    cells = tuple(cells)
    if any(type(cell) is not int or not 0 <= cell < 16 for cell in cells):
        raise ValueError("cell IDs must be builtin integers in 0..15")
    if not cells:
        return ()
    occupancy = Counter(cells)
    return tuple(Fraction(1, len(occupancy) * occupancy[cell]) for cell in cells)


def reference_template(grid) -> TemplateEvidence:
    """Assemble all evidence; derive integer weights from rational cell mass."""
    thinning = reference_thinning(grid)
    chains = reference_chains(thinning.labels)
    samplings = tuple(reference_sampling(chain, thinning.width) for chain in chains)
    memberships = {}
    for sampling in samplings:
        for pixel in sampling.pixel_ids:
            memberships.setdefault(pixel, []).append(sampling.chain_id)
    if not memberships:
        raise ValueError("no owned samples")
    physical_ids = tuple(sorted(memberships))
    ownership = tuple(SampleOwnership(pixel, min(memberships[pixel]),
                                      tuple(sorted(memberships[pixel])))
                      for pixel in physical_ids)
    xs = tuple(pixel % thinning.width for pixel in physical_ids)
    ys = tuple(pixel // thinning.width for pixel in physical_ids)
    xmin, ymin = min(xs), min(ys)
    xspan, yspan = max(xs) - xmin + 1, max(ys) - ymin + 1
    cells = tuple(4 * (4 * (y - ymin) // yspan) + 4 * (x - xmin) // xspan
                  for x, y in zip(xs, ys))
    masses = fractional_weights(cells)
    denominator = 1
    for mass in masses:
        denominator = denominator * mass.denominator // gcd(denominator, mass.denominator)
    cell_counts = tuple(cells.count(cell) for cell in range(16))
    occupied = sum(count != 0 for count in cell_counts)
    common = denominator // occupied
    samples = []
    for row, x, y, cell, mass in zip(ownership, xs, ys, cells, masses):
        scaled = mass * denominator
        if scaled.denominator != 1:
            raise AssertionError("fractional sample mass did not become an integer")
        index = chains[row.owner_chain_id].pixel_ids.index(row.pixel_id)
        samples.append(WeightedSample(row.pixel_id, row.owner_chain_id, index, x, y,
                                      thinning.labels[y][x], cell, scaled.numerator))
    return TemplateEvidence(thinning, chains, samplings, ownership, tuple(samples),
                            cell_counts, occupied, common, denominator)
