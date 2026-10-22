import struct
import unittest

from analysis_core import compare, frame_result, legacy_selected
from test_numeric import candidate


class FrameAnalysis(unittest.TestCase):
    def test_pose_identity_and_new_lost_ids_survive_net_equal_tp(self):
        truth = [dict(gt_id=2, bbox_obj=[0, 0, 10, 10], visib_fract=1),
                 dict(gt_id=4, bbox_obj=[20, 0, 10, 10], visib_fract=.5)]
        a = candidate(0)
        b = candidate(20)
        left = frame_result([a], truth)
        right = frame_result([b], truth)
        value = compare(left, right)
        self.assertEqual(value['allGT'], dict(retained=[], new=[4], lost=[2], same_pose=[], exact_detection_retained=[]))
        # Different template IDs across training arms may refer to the same pose.
        changed_template = tuple([a[0], 17, *a[2:]])
        value = compare(left, frame_result([changed_template], truth))
        self.assertEqual(value['allGT'], dict(retained=[2], new=[], lost=[], same_pose=[2], exact_detection_retained=[]))

    def test_legacy_lossy_score_csv_bound_to_full_json_and_raw_bits(self):
        score = struct.unpack('<f', struct.pack('<I', struct.unpack('<I', struct.pack('<f', 90.))[0]+1))[0]
        kept = [candidate(0, score)]
        row = dict(rank='0', class_id='tless_object_1', score=format(score, '.6g'), template_id='0',
                   bbox_x='0', bbox_y='0', bbox_w='10', bbox_h='10', allGT_label='TP', allGT_id='2',
                   eligible_label='TP', eligibleGT_id='2')
        full = dict(rank=0, class_id='tless_object_1', score=score, template_id=0, bbox_obj=[0, 0, 10, 10],
                    allGT_label='TP', allGT_id=2, eligible_label='TP', eligibleGT_id=2)
        legacy_selected([row], [full], kept, [('TP', 2)], [('TP', 2)])
        with self.assertRaises(ValueError):
            legacy_selected([row], [dict(full, score=90.)], kept, [('TP', 2)], [('TP', 2)])


if __name__ == '__main__':
    unittest.main()
