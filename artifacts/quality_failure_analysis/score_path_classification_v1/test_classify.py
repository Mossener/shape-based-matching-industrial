import unittest
from classify import neighbor_path, propagation_path


def link(admitted=0, emitted=0, point_pass=0, winner=0):
    return dict(admitted=admitted, predicts_emission=emitted,
                point_fine_pass=point_pass, point_is_winner=winner)


class ClassificationTests(unittest.TestCase):
    def test_native_neighbor_first_failed_step_and_displacement(self):
        cases = [([], 'no_reachable_parent'),
                 ([link(point_pass=1, winner=1)], 'all_reachable_coarse_rejected'),
                 ([link(admitted=1)], 'admitted_window_maximum_below85'),
                 ([link(1, 1)], 'neighbor_below85_while_window_winner_passes'),
                 ([link(1, 1, 1)], 'neighbor_passes_but_local_winner_displaced'),
                 ([link(1, 1, 1, 1)], 'native_neighbor_emitted')]
        for rows, expected in cases:
            self.assertEqual(neighbor_path(rows), expected)

    def test_any_admitted_path_wins_over_rejected_counterfactual(self):
        self.assertEqual(neighbor_path([link(point_pass=1, winner=1), link(1, 1, 1, 1)]),
                         'native_neighbor_emitted')

    def test_pre_support_and_representative_support_are_distinct(self):
        row = dict(pre_iou_gt=.5, rep_iou_gt=.49, nms_selected_rank=-1, allGT_label='SUPPRESSED', allGT_id=-1)
        self.assertEqual(propagation_path([row], 3)['path'], 'traced_pre_support_lost_at_representative')
        row['rep_iou_gt'] = .5
        self.assertEqual(propagation_path([row], 3)['path'], 'traced_post_support_suppressed_by_nms')

    def test_selected_support_requires_target_assignment_and_complete_class_identity(self):
        row = dict(pre_iou_gt=.4, rep_iou_gt=.6, nms_selected_rank=0, allGT_label='TP', allGT_id=4)
        value = propagation_path([row], 3)
        self.assertFalse(value['pre_support']);self.assertTrue(value['post_support'])
        self.assertEqual(value['path'], 'selected_traced_support_not_assigned_target')
        row['allGT_id'] = 3
        self.assertEqual(propagation_path([row], 3)['path'], 'assigned_target_by_traced_representative')


if __name__ == '__main__':
    unittest.main()
