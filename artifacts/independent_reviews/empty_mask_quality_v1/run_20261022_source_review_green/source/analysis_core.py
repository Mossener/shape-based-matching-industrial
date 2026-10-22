"""Independent frame arithmetic and cross-arm GT identity comparisons."""
from checked import bits, integer, need, number
from numeric import evaluate, nms


def frame_result(raw, gt):
    kept = nms(raw)
    all_counts, all_labels = evaluate(kept, gt, False)
    eligible_counts, eligible_labels = evaluate(kept, gt, True)
    return dict(raw=raw, kept=kept, allGT=all_counts, visibility_ge_0_5=eligible_counts,
                all_labels=all_labels, eligible_labels=eligible_labels,
                raw_candidates=len(raw), negative_frames=int(not gt),
                negative_frames_with_fp=int(not gt and all_counts['fp'] > 0),
                negative_fp=all_counts['fp'] if not gt else 0)


def compare(left, right):
    result = dict(raw_equal=int(left['raw'] == right['raw']), selected_equal=int(left['kept'] == right['kept']))
    for metric, labels in [('allGT', 'all_labels'), ('visibility_ge_0_5', 'eligible_labels')]:
        before = {gt: detection for detection, (label, gt) in zip(left['kept'], left[labels]) if label == 'TP'}
        after = {gt: detection for detection, (label, gt) in zip(right['kept'], right[labels]) if label == 'TP'}
        common = before.keys() & after.keys()
        result[metric] = dict(retained=sorted(common), new=sorted(after.keys()-before.keys()), lost=sorted(before.keys()-after.keys()),
                              same_pose=sorted(gt for gt in common if before[gt][6] == after[gt][6]),
                              exact_detection_retained=sorted(gt for gt in common if before[gt] == after[gt]))
    return result


def legacy_selected(rows, full, kept, labels, eligible_labels):
    need(len(rows) == len(full) == len(kept) == len(labels) == len(eligible_labels), 'Legacy selected complete coverage differs')
    for rank, (row, record, candidate) in enumerate(zip(rows, full, kept)):
        box = tuple(number(row['bbox_'+axis]) for axis in ('x', 'y', 'w', 'h'))
        need(row['score'] == format(number(record['score']), '.6g'), 'Legacy lossy CSV/full JSON score projection differs')
        projected = (integer(row['rank']), row['class_id'], integer(row['template_id']), box)
        need(projected == (record['rank'], record['class_id'], record['template_id'], tuple(record['bbox_obj'])) ==
             (rank, candidate[0], candidate[1], candidate[5]) and bits(record['score']) == candidate[4],
             'Legacy selected full-precision identity differs from independent NMS')
        for label_field, id_field, expected in [('allGT_label', 'allGT_id', labels[rank]),
                                                ('eligible_label', 'eligibleGT_id', eligible_labels[rank])]:
            need((row[label_field], integer(row[id_field])) == (record[label_field], record[id_field]) == expected,
                 'Legacy selected GT identity differs')
