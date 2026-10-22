"""Independent standard-library candidate/GT arithmetic; no file or image I/O."""
from collections import Counter
import struct


def order(candidate):
    cls, template, x, y, bits, (bx, by, width, height), _ = candidate
    return (-struct.unpack('<f', bits)[0], cls, template, y, x, by, bx, width, height)


def overlap(a, b):
    x, y, width, height = a
    u, v, other_width, other_height = b
    if min(width, height, other_width, other_height) <= 0:
        return 0.
    intersection = max(0., min(x+width, u+other_width)-max(x, u))*max(
        0., min(y+height, v+other_height)-max(y, v))
    return intersection/(width*height+other_width*other_height-intersection)


def nms(raw):
    kept = []
    for candidate in sorted(raw, key=order):
        if all(candidate[0] != old[0] or overlap(candidate[5], old[5]) <= .3 for old in kept):
            kept.append(candidate)
    return kept


def evaluate(kept, gt, eligible):
    labels = [('FP', -1) for _ in kept]
    used, overlaps = set(), []
    for ignored in ([False, True] if eligible else [False]):
        for rank, candidate in enumerate(kept):
            if labels[rank][0] != 'FP':
                continue
            options = []
            for truth in gt:
                if truth['gt_id'] in used or (eligible and (truth['visib_fract'] < .5) != ignored):
                    continue
                value = overlap(candidate[5], truth['bbox_obj'])
                if value >= .5:
                    options.append((-value, truth['gt_id']))
            if options:
                negative_iou, identity = min(options)
                used.add(identity)
                labels[rank] = ('IGNORE' if ignored else 'TP', identity)
                if not ignored:
                    overlaps.append(-negative_iou)
    counts = Counter(label for label, _ in labels)
    total = sum(not eligible or truth['visib_fract'] >= .5 for truth in gt)
    return dict(tp=counts['TP'], fp=counts['FP'], fn=total-counts['TP'], gt=total,
                ignored=counts['IGNORE'], matched_iou_sum=sum(overlaps)), labels
