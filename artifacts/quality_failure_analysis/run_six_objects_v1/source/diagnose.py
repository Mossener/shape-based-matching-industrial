"""Development-only numeric failure decomposition. No image I/O."""
from collections import Counter


def iou(a, b):
    if a[2] <= 0 or a[3] <= 0 or b[2] <= 0 or b[3] <= 0:
        return 0.0
    w = max(0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0]))
    h = max(0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    intersection = w*h
    return intersection/(a[2]*a[3]+b[2]*b[3]-intersection)


def maximum_pairs(graph, target_count):
    owners = [-1]*target_count

    def augment(p, seen):
        for g in graph[p]:
            if not 0 <= g < target_count:
                raise ValueError('Target index outside graph')
            if g in seen:
                continue
            seen.add(g)
            if owners[g] < 0 or augment(owners[g], seen):
                owners[g] = p
                return True
        return False

    for p in range(len(graph)):
        augment(p, set())
    return [(p, g) for g, p in enumerate(owners) if p >= 0]


def analyze_frame(raw_boxes, selected, targets, other_gt):
    if Counter(tuple(d['box']) for d in selected) - Counter(map(tuple, raw_boxes)):
        raise ValueError('Selected boxes are not a multiset subset of raw boxes')
    if any(d['label'] not in ('TP', 'FP') for d in selected):
        raise ValueError('Unknown allGT label')
    raw_graph = [[g for g, gt in enumerate(targets) if iou(box, gt) >= .5]
                 for box in raw_boxes]
    selected_graph = [[g for g, gt in enumerate(targets)
                       if iou(d['box'], gt) >= .5] for d in selected]
    raw_capacity = len(maximum_pairs(raw_graph, len(targets)))
    selected_capacity = len(maximum_pairs(selected_graph, len(targets)))
    tp = sum(d['label'] == 'TP' for d in selected)
    if not tp <= selected_capacity <= raw_capacity <= len(targets):
        raise ValueError('Impossible baseline/capacity counts')
    tp_graph = [row for row, d in zip(selected_graph, selected) if d['label'] == 'TP']
    if len(maximum_pairs(tp_graph, len(targets))) != tp:
        raise ValueError('TP labels have no valid one-to-one geometric assignment')
    associations = dict.fromkeys(('target_ge_0_5', 'other_ge_0_5',
                                  'target_ge_0_1', 'other_ge_0_1',
                                  'no_overlap_ge_0_1'), 0)
    for d in selected:
        if d['label'] == 'TP':
            continue
        target = max((iou(d['box'], b) for b in targets), default=0)
        other = max((iou(d['box'], b) for b in other_gt), default=0)
        category = ('target_ge_0_5' if target >= .5 else
                    'other_ge_0_5' if other >= .5 else
                    'target_ge_0_1' if target >= .1 else
                    'other_ge_0_1' if other >= .1 else 'no_overlap_ge_0_1')
        associations[category] += 1
    reachable = {g for row in raw_graph for g in row}
    return dict(raw_capacity=raw_capacity, selected_capacity=selected_capacity,
                actual_tp=tp, raw_capacity_deficit=len(targets)-raw_capacity,
                selected_capacity_loss=raw_capacity-selected_capacity,
                assignment_capacity_loss=selected_capacity-tp,
                gt_without_raw_overlap=len(targets)-len(reachable),
                fp_associations=associations)
