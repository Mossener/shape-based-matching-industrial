"""Pure standard-library stage provenance, adapted from V23 (see ORIGIN)."""
from dataclasses import dataclass
import struct


def need(value, reason):
    if not value:
        raise ValueError(reason)


def bits(value):
    return struct.unpack('<I', struct.pack('<f', float(value)))[0]


def f32(value):
    return struct.unpack('<f', struct.pack('<I', bits(value)))[0]


@dataclass(frozen=True)
class Candidate:
    cls: str
    template: int
    x: int
    y: int
    score_bits: int
    box: tuple
    pose: tuple

    @property
    def score(self):
        return struct.unpack('<f', struct.pack('<I', self.score_bits))[0]


def iou(a, b):
    if min(a[2], a[3], b[2], b[3]) <= 0:
        return 0.
    area = max(0., min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])) * max(
        0., min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    return area/(a[2]*a[3]+b[2]*b[3]-area)


def order(c):
    bx, by, w, h = c.box
    return (-c.score, c.cls, c.template, c.y, c.x, by, bx, w, h)


def nms_trace(raw):
    kept, blockers = [], {}
    for rank in sorted(range(len(raw)), key=lambda r: order(raw[r])):
        for first in kept:
            if raw[rank].cls == raw[first].cls and iou(raw[rank].box, raw[first].box) > .3:
                blockers[rank] = first
                break
        else:
            kept.append(rank)
    return kept, blockers


def assign(raw, kept, truths, eligible=False):
    labels = [('FP', -1) for _ in kept]
    used = set()
    for ignored in ([False, True] if eligible else [False]):
        for index, rank in enumerate(kept):
            if labels[index][0] != 'FP':
                continue
            choices = [(-iou(raw[rank].box, t['box']), t['gt_id']) for t in truths
                       if t['gt_id'] not in used and (not eligible or (t['visibility'] < .5) == ignored)
                       and iou(raw[rank].box, t['box']) >= .5]
            if choices:
                _, identity = min(choices)
                labels[index] = ('IGNORE' if ignored else 'TP', identity)
                used.add(identity)
    return labels


def check_selected(raw, kept, actual, labels, eligible_labels):
    need(len(kept) == len(actual), 'Selected complete row count differs')
    for index, rank in enumerate(kept):
        candidate, label, eligible = actual[index]
        need(candidate == raw[rank], 'Selected full identity/score bits differ')
        need(label == labels[index] and eligible == eligible_labels[index], 'Selected GT assignment differs')


def check_complete_scope(per_keys, expected):
    need(len(per_keys) == len(set(per_keys)) and set(per_keys) == expected, 'Full frame schedule differs')


def check_raw_paths(left, right):
    need(left == right, 'Raw paths differ in ordered identity, bits, or multiplicity')


def diagnose(identity, truths, raw, kept, blockers, labels):
    truth, = [t for t in truths if t['gt_id'] == identity]
    overlaps = [iou(c.box, truth['box']) for c in raw]
    hits = [r for r, value in enumerate(overlaps) if value >= .5]
    hit_set = set(hits)
    selected_hits = [r for r in kept if r in hit_set]
    assigned = {r: label for r, label in zip(kept, labels)}
    matched_rank = next((r for r, label in assigned.items() if label == ('TP', identity)), None)
    if matched_rank is not None:
        category = 'matched'
    elif not hits:
        category = 'raw_gap'
    elif not selected_hits:
        category = 'nms_loss'
    else:
        need(all(assigned[r][0] == 'TP' and assigned[r][1] != identity for r in selected_hits),
             'Unmatched GT has an unassigned overlapping selected candidate')
        category = 'assignment_competition'
    suppression = []
    for rank in hits:
        if rank in kept:
            need(rank not in blockers, 'Selected candidate has blocker')
            continue
        need(rank in blockers, 'Suppressed hit has no blocker')
        first = blockers[rank]
        expected = next((r for r in kept if order(raw[r]) <= order(raw[rank]) and
                         raw[r].cls == raw[rank].cls and iou(raw[r].box, raw[rank].box) > .3), None)
        need(first == expected and first in assigned, 'First NMS blocker differs')
        suppression.append(dict(raw_rank=rank, blocker_raw_rank=first,
                                blocker_label=assigned[first][0], blocker_gt_id=assigned[first][1],
                                blocker_is_fp=assigned[first][0] == 'FP'))
    best = max(range(len(raw)), key=lambda r: (overlaps[r], -r)) if raw else None
    return dict(category=category, raw_has_hit=bool(hits), raw_hit_count=len(hits),
                best_raw_iou=overlaps[best] if best is not None else 0., best_raw_rank=best,
                selected_has_hit=bool(selected_hits), selected_hit_count=len(selected_hits),
                matched=matched_rank is not None, matched_raw_rank=matched_rank,
                hit_ranks=hits, selected_hit_ranks=selected_hits, suppression=suppression,
                competition=[dict(raw_rank=r, selected_gt_id=assigned[r][1]) for r in selected_hits
                             if matched_rank is None and assigned[r][0] == 'TP'])
