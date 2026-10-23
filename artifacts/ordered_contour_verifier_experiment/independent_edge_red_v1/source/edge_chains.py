"""Deterministic mathematical chains and weights on supplied tiny label grids.

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

This mathematical component cannot establish pixel provenance, detector
quality, native performance or industrial generalization. Validating the
operators on supplied labels does not regenerate those labels from images.
"""
from dataclasses import dataclass
from math import gcd

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


_OFFSETS = ((0, -1), (1, -1), (1, 0), (1, 1),
            (0, 1), (-1, 1), (-1, 0), (-1, -1))


def _grid(value) -> tuple[LabelGrid, int, int]:
    """Copy rectangular legal labels; bool is deliberately not a label int."""
    if not isinstance(value, (tuple, list)) or not value:
        raise ValueError("label grid must be a nonempty list or tuple")
    rows = []
    width = None
    for row in value:
        if not isinstance(row, (tuple, list)) or not row:
            raise ValueError("label grid rows must be nonempty lists or tuples")
        if width is None:
            width = len(row)
        if len(row) != width:
            raise ValueError("label grid must be rectangular")
        for label in row:
            if type(label) is not int or not (0 <= label <= 7 or label == 255):
                raise ValueError("label must be a builtin int in 0..7 or 255")
        rows.append(tuple(row))
    return tuple(rows), width, len(rows)


def _delete_batch(active: set[int], width: int, height: int,
                  second: bool) -> set[int]:
    """Read one unchanged bitmap and return, without applying, its deletions."""
    deletions = set()
    for pixel in sorted(active):
        y, x = divmod(pixel, width)
        neighbors = tuple(0 <= x + dx < width and 0 <= y + dy < height and
                          (y + dy) * width + x + dx in active
                          for dx, dy in _OFFSETS)
        count = sum(neighbors)
        if not 2 <= count <= 6:
            continue
        transitions = sum(not neighbors[index] and neighbors[(index + 1) % 8]
                          for index in range(8))
        if transitions != 1:
            continue
        north, east, south, west = (neighbors[index] for index in (0, 2, 4, 6))
        if second:
            removable = not (north and east and west) and not (north and south and west)
        else:
            removable = not (north and east and south) and not (east and south and west)
        if removable:
            deletions.add(pixel)
    return deletions


def thin_labels(grid) -> ThinningResult:
    """Run the fixed two-subiteration Zhang--Suen rule with outside value zero."""
    eligible, width, height = _grid(grid)
    active = {y * width + x for y, row in enumerate(eligible)
              for x, label in enumerate(row) if label != 255}
    rounds = []
    while True:
        first = _delete_batch(active, width, height, False)
        active.difference_update(first)
        second = _delete_batch(active, width, height, True)
        active.difference_update(second)
        rounds.append((len(first), len(second)))
        if not first and not second:
            break
    labels = tuple(tuple(label if y * width + x in active else 255
                         for x, label in enumerate(row))
                   for y, row in enumerate(eligible))
    return ThinningResult(width, height, eligible, labels, tuple(rounds))


def _edge(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left < right else (right, left)


def _canonical(pixels: tuple[int, ...], closed: bool) -> tuple[int, ...]:
    if not closed:
        return min(pixels, tuple(reversed(pixels)))
    # IDs are unique. Every lexicographically minimal rotation must start at
    # the unique smallest ID, so only its two directions need consideration.
    start = pixels.index(min(pixels))
    forward = pixels[start:] + pixels[:start]
    backward = forward[:1] + tuple(reversed(forward[1:]))
    return min(forward, backward)


def _walk(start: int, neighbor: int, adjacency: dict[int, tuple[int, ...]],
          used: set[tuple[int, int]]) -> tuple[tuple[int, ...], bool]:
    """Follow one unused edge through degree-two nodes up to a trail endpoint."""
    pixels = [start]
    previous, current = start, neighbor
    used.add(_edge(previous, current))
    while current != start:
        pixels.append(current)
        following = adjacency[current]
        if len(following) != 2:
            return tuple(pixels), False
        next_pixel = following[0] if following[1] == previous else following[1]
        next_edge = _edge(current, next_pixel)
        if next_edge in used:
            raise RuntimeError("degree-two walk encountered an already decomposed edge")
        used.add(next_edge)
        previous, current = current, next_pixel
    # The closing edge is used, but the repeated starting physical ID is not
    # appended. It remains available via Chain.closed rather than a duplicate.
    return tuple(pixels), True


def extract_chains(thinned_grid) -> tuple[Chain, ...]:
    """Decompose exactly the supplied eight-neighbor graph, without re-thinning."""
    labels, width, height = _grid(thinned_grid)
    active = {y * width + x for y, row in enumerate(labels)
              for x, label in enumerate(row) if label != 255}
    adjacency = {}
    for pixel in sorted(active):
        y, x = divmod(pixel, width)
        adjacency[pixel] = tuple(sorted((y + dy) * width + x + dx
                                       for dx, dy in _OFFSETS
                                       if 0 <= x + dx < width and 0 <= y + dy < height
                                       and (y + dy) * width + x + dx in active))
    used = set()
    raw = []
    # First extract all trails incident to non-degree-two nodes. Each shared
    # junction remains a physical endpoint of each incident trail.
    for start in sorted(active):
        degree = len(adjacency[start])
        if degree == 0:
            raw.append(((start,), False, False))
            continue
        if degree == 2:
            continue
        for neighbor in adjacency[start]:
            if _edge(start, neighbor) in used:
                continue
            pixels, closed = _walk(start, neighbor, adjacency, used)
            raw.append((_canonical(pixels, closed), closed, closed))
    # Any edge left now belongs to an all-degree-two cyclic component.
    for start in sorted(active):
        for neighbor in adjacency[start]:
            if _edge(start, neighbor) in used:
                continue
            if len(adjacency[start]) != 2:
                raise RuntimeError("unused edge remained incident to a junction")
            pixels, closed = _walk(start, neighbor, adjacency, used)
            if not closed:
                raise RuntimeError("remaining degree-two component was not cyclic")
            raw.append((_canonical(pixels, True), True, False))
    all_edges = {_edge(pixel, neighbor) for pixel in active
                 for neighbor in adjacency[pixel]}
    if used != all_edges:
        raise RuntimeError("chain decomposition did not cover the complete edge inventory")
    raw.sort(key=lambda row: (row[0], row[1]))
    return tuple(Chain(index, pixels, closed, returning)
                 for index, (pixels, closed, returning) in enumerate(raw))


def _validated_chain(chain: Chain, width: int) -> Chain:
    if type(width) is not int or width <= 0:
        raise ValueError("width must be a positive builtin int")
    if not isinstance(chain, Chain):
        raise ValueError("chain must be a Chain")
    if type(chain.chain_id) is not int or chain.chain_id < 0:
        raise ValueError("chain ID must be a nonnegative builtin int")
    if type(chain.closed) is not bool or type(chain.returning) is not bool:
        raise ValueError("chain flags must be bool")
    if chain.returning and not chain.closed:
        raise ValueError("a returning trail must be closed")
    if not isinstance(chain.pixel_ids, (tuple, list)) or not chain.pixel_ids:
        raise ValueError("chain must contain at least one physical pixel")
    pixels = tuple(chain.pixel_ids)
    for pixel in pixels:
        if type(pixel) is not int or pixel < 0:
            raise ValueError("chain pixels must be nonnegative builtin ints")
    if len(set(pixels)) != len(pixels):
        raise ValueError("chain physical pixel IDs must be unique")
    if chain.closed and len(pixels) < 3:
        raise ValueError("a closed graph cycle must have at least three physical pixels")
    return Chain(chain.chain_id, pixels, chain.closed, chain.returning)


def _step(left: int, right: int, width: int) -> int:
    left_y, left_x = divmod(left, width)
    right_y, right_x = divmod(right, width)
    dx, dy = abs(left_x - right_x), abs(left_y - right_y)
    if dx > 1 or dy > 1 or (dx == 0 and dy == 0):
        raise ValueError("consecutive chain pixels must be distinct eight-neighbors")
    return 1414 if dx == 1 and dy == 1 else 1000


def sample_chain(chain: Chain, width: int) -> ChainSampling:
    """Sample fixed arc markers at the first reached real node, preserving order."""
    chain = _validated_chain(chain, width)
    cumulative = [0]
    for left, right in zip(chain.pixel_ids, chain.pixel_ids[1:]):
        cumulative.append(cumulative[-1] + _step(left, right, width))
    total = cumulative[-1]
    if chain.closed:
        total += _step(chain.pixel_ids[-1], chain.pixel_ids[0], width)
    selected = {0}
    if not chain.closed:
        selected.add(len(chain.pixel_ids) - 1)
    position = 1
    for marker in range(2000, total, 2000):
        while position < len(cumulative) and cumulative[position] < marker:
            position += 1
        # A marker in the closing edge reaches the next first point. It is
        # deliberately the same physical ID and is counted only once.
        selected.add(position if position < len(cumulative) else 0)
    samples = tuple(pixel for index, pixel in enumerate(chain.pixel_ids)
                    if index in selected)
    return ChainSampling(chain.chain_id, samples, total)


def prepare_template(grid) -> TemplateEvidence:
    """Thin, extract, sample, own shared pixels once, and form exact cell weights."""
    thinning = thin_labels(grid)
    chains = extract_chains(thinning.labels)
    samplings = tuple(sample_chain(chain, thinning.width) for chain in chains)
    memberships = {}
    for sampling in samplings:
        for pixel in sampling.pixel_ids:
            memberships.setdefault(pixel, []).append(sampling.chain_id)
    if not memberships:
        raise ValueError("template has no owned samples after thinning")
    ownership = tuple(SampleOwnership(pixel, min(memberships[pixel]),
                                      tuple(sorted(memberships[pixel])))
                      for pixel in sorted(memberships))
    positions = {(chain.chain_id, pixel): index for chain in chains
                 for index, pixel in enumerate(chain.pixel_ids)}
    xs = [row.pixel_id % thinning.width for row in ownership]
    ys = [row.pixel_id // thinning.width for row in ownership]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    span_x, span_y = xmax - xmin + 1, ymax - ymin + 1
    cell_counts = [0] * 16
    cells = {}
    for row in ownership:
        y, x = divmod(row.pixel_id, thinning.width)
        cell = (4 * (y - ymin) // span_y) * 4 + 4 * (x - xmin) // span_x
        cells[row.pixel_id] = cell
        cell_counts[cell] += 1
    common = 1
    occupied = 0
    for count in cell_counts:
        if count:
            occupied += 1
            common = common // gcd(common, count) * count
    samples = []
    for row in ownership:
        y, x = divmod(row.pixel_id, thinning.width)
        cell = cells[row.pixel_id]
        samples.append(WeightedSample(row.pixel_id, row.owner_chain_id,
                                      positions[(row.owner_chain_id, row.pixel_id)],
                                      x, y, thinning.labels[y][x], cell,
                                      common // cell_counts[cell]))
    denominator = occupied * common
    if sum(sample.weight for sample in samples) != denominator:
        raise RuntimeError("exact cell weights do not sum to their full denominator")
    return TemplateEvidence(thinning, chains, samplings, ownership, tuple(samples),
                            tuple(cell_counts), occupied, common, denominator)
