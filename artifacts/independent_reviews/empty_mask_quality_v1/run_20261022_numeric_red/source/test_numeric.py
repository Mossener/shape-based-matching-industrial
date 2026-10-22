"""Literal semantic tests only; never import target evaluator or read images."""
import struct
import unittest

from numeric import evaluate, nms


def candidate(x, score=90, template=0, cls='tless_object_1', width=10):
    return (cls, template, x+64, 64, struct.pack('<f', score), (x, 0., width, 10.), (7, 0., 1.))


class NumericQuality(unittest.TestCase):
    def test_nms_uses_score_then_stable_full_identity_and_class(self):
        first, lower = candidate(0), candidate(0, 89, 1)
        other_class = candidate(0, 88, 2, 'tless_object_2')
        distant = candidate(20, 87, 3)
        self.assertEqual(nms([distant, lower, other_class, first]), [first, other_class, distant])

    def test_nms_does_not_suppress_exact_point_three(self):
        # intersection=6*10, union=20*10: IoU exactly .3.
        a, b = candidate(0, width=13), candidate(7, 89, 1, width=13)
        self.assertEqual(nms([a, b]), [a, b])

    def test_allgt_and_eligible_ignores_are_one_to_one(self):
        kept = [candidate(0), candidate(20, 89, 1), candidate(20, 88, 2), candidate(40, 87, 3)]
        gt = [dict(gt_id=3, bbox_obj=[0, 0, 10, 10], visib_fract=1),
              dict(gt_id=4, bbox_obj=[20, 0, 10, 10], visib_fract=.4)]
        all_counts, all_labels = evaluate(kept, gt, False)
        eligible, labels = evaluate(kept, gt, True)
        self.assertEqual(all_counts, dict(tp=2, fp=2, fn=0, gt=2, ignored=0, matched_iou_sum=2.))
        self.assertEqual(all_labels, [('TP', 3), ('TP', 4), ('FP', -1), ('FP', -1)])
        self.assertEqual(eligible, dict(tp=1, fp=2, fn=0, gt=1, ignored=1, matched_iou_sum=1.))
        self.assertEqual(labels, [('TP', 3), ('IGNORE', 4), ('FP', -1), ('FP', -1)])

    def test_eligible_tp_pass_precedes_ignore_and_gt_tie_uses_smallest_id(self):
        kept = [candidate(0)]
        gt = [dict(gt_id=1, bbox_obj=[0, 0, 10, 10], visib_fract=.4),
              dict(gt_id=7, bbox_obj=[0, 0, 10, 10], visib_fract=.5),
              dict(gt_id=3, bbox_obj=[0, 0, 10, 10], visib_fract=1)]
        counts, labels = evaluate(kept, gt, True)
        self.assertEqual(labels, [('TP', 3)])
        self.assertEqual((counts['tp'], counts['fn'], counts['ignored']), (1, 1, 0))

    def test_half_iou_is_accepted_and_negative_frame_keeps_fp(self):
        kept = [candidate(0, width=20)]
        counts, labels = evaluate(kept, [dict(gt_id=2, bbox_obj=[0, 0, 10, 10], visib_fract=1)], False)
        self.assertEqual(labels, [('TP', 2)])
        self.assertEqual(counts['matched_iou_sum'], .5)
        counts, labels = evaluate(kept, [], True)
        self.assertEqual(counts, dict(tp=0, fp=1, fn=0, gt=0, ignored=0, matched_iou_sum=0.))
        self.assertEqual(labels, [('FP', -1)])


if __name__ == '__main__':
    unittest.main()
