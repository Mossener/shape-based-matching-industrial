"""Small synthetic training-table checks; no images, native tools or matcher."""
import copy
import unittest

from audit_training import inspect_object


def fixture():
    row = dict(class_id='tless_object_1', training_image='7', angle='0', scale='1',
               success='1', template_id='0', source_crop_x='2', source_crop_y='3',
               source_crop_w='4', source_crop_h='5', canvas='64', mask_x='10',
               mask_y='11', mask_w='4', mask_h='5', templ_tl_x='8', templ_tl_y='9',
               features_l0='32', features_l1='16', error='')
    meta = dict(class_id='tless_object_1', template_id=0, training_image_id=7,
                angle=0, scale=1, tl_x=8, tl_y=9, warped_mask_bbox=[10, 11, 4, 5])
    return [row], [copy.deepcopy(row)], [meta], {(7, 0, 1.0)}


class NumericTraining(unittest.TestCase):
    def test_success(self):
        self.assertEqual(inspect_object(1, *fixture()),
                         dict(object_id=1, attempts=1, successful_templates=1,
                              insufficient_features=0, opencv_exception_attempts=0))

    def test_failed_attempt_is_retained_without_inventing_partial_features(self):
        rows, old, _, expected = fixture()
        rows[0].update(success='0', template_id='-1', features_l0='0', features_l1='0',
                       templ_tl_x='0', templ_tl_y='0', error='insufficient_features')
        self.assertEqual(inspect_object(1, rows, old, [], expected)['insufficient_features'], 1)

    def test_corruptions(self):
        for field, changed in [('class_id', 'tless_object_25'), ('angle', '30'),
                               ('mask_x', '12'), ('success', '2'), ('template_id', '1'),
                               ('features_l1', '17'), ('error', 'insufficient_features')]:
            with self.subTest(field=field):
                rows, old, meta, expected = fixture()
                rows[0][field] = changed
                with self.assertRaises(ValueError):
                    inspect_object(1, rows, old, meta, expected)

    def test_missing_or_duplicate_pose(self):
        rows, old, meta, expected = fixture()
        for bad in [[], rows + rows]:
            with self.assertRaises(ValueError):
                inspect_object(1, bad, old, meta, expected)

    def test_wrong_metadata_origin(self):
        rows, old, meta, expected = fixture()
        meta[0]['tl_x'] = 10
        with self.assertRaises(ValueError):
            inspect_object(1, rows, old, meta, expected)

    def test_exception_and_failure_serialization(self):
        rows, old, _, expected = fixture()
        rows[0].update(success='0', template_id='-1', features_l0='0', features_l1='0',
                       templ_tl_x='0', templ_tl_y='0', error='opencv_exception')
        result = inspect_object(1, rows, old, [], expected)
        self.assertEqual(result['opencv_exception_attempts'], 1)
        rows[0]['error'] = ''
        with self.assertRaises(ValueError):
            inspect_object(1, rows, old, [], expected)


if __name__ == '__main__':
    unittest.main()
