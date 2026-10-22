"""Literal report math; importing the CLI never performs file or native I/O."""
import unittest

from analysis_core import frame_result
from audit_quality import add, finished, first_difference, frame_counts
from test_numeric import candidate


class Reporting(unittest.TestCase):
    def test_frame_and_pooled_counts_include_negative_false_positives(self):
        positive = frame_result([candidate(0)], [dict(gt_id=1, bbox_obj=[0, 0, 10, 10], visib_fract=1)])
        negative = frame_result([candidate(20)], [])
        self.assertEqual(frame_counts(positive), dict(raw=1, selected=1, tp=1, fp=0, fn=0, gt=1,
            eligible_tp=1, eligible_fp=0, eligible_fn=0, eligible_gt=1, ignored=0,
            all_iou_sum=1., eligible_iou_sum=1., negative_fp=0))
        totals = {}
        add(totals, positive); add(totals, negative)
        result = finished(totals)
        self.assertEqual(result['allGT'], dict(tp=1, fp=1, fn=0, gt=1, ignored=0, matched_iou_sum=1.,
            precision=.5, recall=1., f1=2/3, mean_tp_iou=1.))
        self.assertEqual({key: result[key] for key in ('raw_candidates', 'negative_frames', 'negative_frames_with_fp', 'negative_fp')},
                         dict(raw_candidates=2, negative_frames=1, negative_frames_with_fp=1, negative_fp=1))

    def test_first_difference_preserves_score_bits_and_missing_row(self):
        one = candidate(0)
        value = first_difference([one], [])
        self.assertEqual(value['rank'], 0)
        self.assertIsNone(value['after'])
        self.assertEqual(value['before'][4]['float32_bits'], 1119092736)
        self.assertIsNone(first_difference([one], [one]))


if __name__ == '__main__':
    unittest.main()
