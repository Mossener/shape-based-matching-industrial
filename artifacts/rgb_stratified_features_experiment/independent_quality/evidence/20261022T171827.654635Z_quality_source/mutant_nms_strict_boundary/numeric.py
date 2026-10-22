"""Independent numeric primitives for the RGB empty-mask audit.

This module deliberately has no filesystem, OpenCV, or project evaluator
dependency.  Candidate records are tuples of class, template, coordinates,
float32 score bits, official box and training pose.
"""
from collections import Counter
import struct


def score(bits):
    return struct.unpack('<f', struct.pack('<I', int(bits)))[0]


def float_bits(value):
    return struct.unpack('<I', struct.pack('<f', float(value)))[0]


def candidate_order(candidate):
    cls, template, x, y, score_bits, box, _pose = candidate
    bx, by, width, height = box
    return (-score(score_bits), cls, template, y, x, by, bx, width, height)


def overlap(a, b):
    x, y, width, height = a
    u, v, other_width, other_height = b
    if min(width, height, other_width, other_height) <= 0:
        return 0.0
    area = max(0.0, min(x + width, u + other_width) - max(x, u)) * max(
        0.0, min(y + height, v + other_height) - max(y, v))
    return area / (width * height + other_width * other_height - area)


def nms(raw, threshold=0.3):
    kept = []
    for candidate in sorted(raw, key=candidate_order):
        if all(candidate[0] != old[0] or overlap(candidate[5], old[5]) < threshold
               for old in kept):
            kept.append(candidate)
    return kept


def evaluate(kept, gt, eligible=False, threshold=0.5):
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
                if value >= threshold:
                    options.append((-value, truth['gt_id']))
            if options:
                negative_iou, identity = min(options)
                used.add(identity)
                labels[rank] = ('IGNORE' if ignored else 'TP', identity)
                if not ignored:
                    overlaps.append(-negative_iou)
    counts = Counter(label for label, _ in labels)
    total = sum(not eligible or truth['visib_fract'] >= .5 for truth in gt)
    return dict(tp=counts['TP'], fp=counts['FP'], fn=total - counts['TP'], gt=total,
                ignored=counts['IGNORE'], matched_iou_sum=sum(overlaps)), labels


def finish(counts):
    result = dict(counts)
    tp, fp, fn, total = (result.get(name, 0) for name in ('tp', 'fp', 'fn', 'gt'))
    result.update(precision=tp / (tp + fp) if tp + fp else 0.0,
                  recall=tp / total if total else 0.0,
                  f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
                  mean_tp_iou=result.get('matched_iou_sum', 0.0) / tp if tp else 0.0)
    return result
