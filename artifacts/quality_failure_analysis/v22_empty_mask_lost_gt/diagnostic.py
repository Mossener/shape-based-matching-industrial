"""Pure numeric V22 failure provenance; no file I/O or evaluator imports."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    cls: str
    template: int
    x: int
    y: int
    score: float
    box: tuple
    pose: tuple


def iou(a, b):
    if min(a[2], a[3], b[2], b[3]) <= 0:
        return 0.
    width = max(0., min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0]))
    height = max(0., min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    intersection = width*height
    return intersection/(a[2]*a[3]+b[2]*b[3]-intersection)


def size_upper(a, b):
    if min(*a, *b) <= 0:
        return 0.
    intersection = min(a[0], b[0])*min(a[1], b[1])
    return intersection/(a[0]*a[1]+b[0]*b[1]-intersection)


def order(candidate):
    bx, by, width, height = candidate.box
    return (-candidate.score, candidate.cls, candidate.template, candidate.y,
            candidate.x, by, bx, width, height)


def nms_trace(raw):
    kept, blockers = [], {}
    for rank in sorted(range(len(raw)), key=lambda i: order(raw[i])):
        for old in kept:
            if raw[rank].cls == raw[old].cls and iou(raw[rank].box, raw[old].box) > .3:
                blockers[rank] = old
                break
        else:
            kept.append(rank)
    return kept, blockers


def assign(raw, kept, truth):
    used, labels = set(), []
    for rank in kept:
        choices = [(-iou(raw[rank].box, gt['box']), gt['gt_id']) for gt in truth
                   if gt['gt_id'] not in used and iou(raw[rank].box, gt['box']) >= .5]
        if choices:
            _, identity = min(choices)
            used.add(identity)
            labels.append(('TP', identity))
        else:
            labels.append(('FP', -1))
    return labels


def classify(identity, truth, raw, kept, blockers, labels):
    gt, = [item for item in truth if item['gt_id'] == identity]
    hits = [rank for rank, candidate in enumerate(raw) if iou(candidate.box, gt['box']) >= .5]
    survivors = [rank for rank in kept if rank in hits]
    if ('TP', identity) in labels:
        category = 'detected'
    elif not hits:
        category = 'no_raw_candidate_ge_0_5'
    elif not survivors:
        if any(rank not in blockers for rank in hits):
            raise ValueError('Missing suppression provenance')
        category = 'all_overlapping_raw_suppressed_by_nms'
    else:
        if any(labels[kept.index(rank)][0] != 'TP' for rank in survivors):
            raise ValueError('Unmatched GT has an unassigned overlapping selected box')
        category = 'surviving_candidate_assigned_elsewhere'
    return dict(category=category, overlapping_raw_ranks=hits, overlapping_kept_raw_ranks=survivors,
                blocker_raw_ranks=sorted({blockers[rank] for rank in hits if rank in blockers}))


def maximum_capacity(graph, count):
    owners = [-1]*count

    def augment(candidate, visited):
        for target in graph[candidate]:
            if not 0 <= target < count:
                raise ValueError('Invalid GT graph index')
            if target in visited:
                continue
            visited.add(target)
            if owners[target] < 0 or augment(owners[target], visited):
                owners[target] = candidate
                return True
        return False

    for candidate in range(len(graph)):
        augment(candidate, set())
    return sum(owner >= 0 for owner in owners)
