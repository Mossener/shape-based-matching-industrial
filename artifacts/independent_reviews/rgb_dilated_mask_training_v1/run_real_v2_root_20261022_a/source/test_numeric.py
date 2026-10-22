"""Small synthetic training-table checks; no images, native tools or matcher."""
import copy
import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest

from training_numeric import inspect_object, audit_bank, validate_private_numeric
from test_bank import literal


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
    def test_changed_old_geometry_is_rejected_against_frozen_input_pin(self):
        original = b'class_id,mask_x\ntless_object_1,10\n'
        pins = {'frozen_inputs/old_attempts.csv':
                dict(sha256=hashlib.sha256(original).hexdigest(), bytes=len(original))}
        validate_private_numeric('frozen_inputs/old_attempts.csv', original, pins)
        with self.assertRaises(ValueError):
            validate_private_numeric('frozen_inputs/old_attempts.csv', original.replace(b',10', b',11'), pins)
        with self.assertRaises(ValueError):
            validate_private_numeric('frozen_inputs/unlisted.csv', original, pins)

    def test_success(self):
        self.assertEqual(inspect_object(1, *fixture()),
                         dict(object_id=1, attempts=1, successful_templates=1,
                              insufficient_features=0, opencv_exception_attempts=0))

    def test_actual_counts_above_requests(self):
        rows, old, meta, expected = fixture()
        rows[0].update(features_l0='59', features_l1='18')
        self.assertEqual(inspect_object(1, rows, old, meta, expected)['successful_templates'], 1)

    def test_failed_attempt_is_retained_without_inventing_partial_features(self):
        rows, old, _, expected = fixture()
        rows[0].update(success='0', template_id='-1', features_l0='0', features_l1='0',
                       templ_tl_x='0', templ_tl_y='0', error='insufficient_features')
        self.assertEqual(inspect_object(1, rows, old, [], expected)['insufficient_features'], 1)

    def test_corruptions(self):
        for field, changed in [('class_id', 'tless_object_25'), ('angle', '30'),
                               ('mask_x', '12'), ('success', '2'), ('template_id', '1'),
                               ('features_l1', '0'), ('error', 'insufficient_features')]:
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


class SerializedDiagnostics(unittest.TestCase):
    def records(self):
        row = fixture()[0][0]
        row.update(templ_tl_x='2', templ_tl_y='3', features_l0='2', features_l1='2')
        diagnostics = []
        for level, side in [(0, 64), (1, 32)]:
            values = dict(class_id='tless_object_1', training_image=7, angle=0, scale=1,
                          template_id=0, level=level, canvas_width=side, canvas_height=side,
                          tl_x=2, tl_y=3, width=8, height=9, actual_features=2,
                          min_x=0, min_y=1, max_x=8, max_y=9, min_absolute_x=2,
                          min_absolute_y=4, max_absolute_x=10, max_absolute_y=12,
                          min_canvas_edge_distance=2)
            diagnostics.append({key: str(value) for key, value in values.items()})
        return [row], diagnostics

    def test_literal_bank_agrees_and_every_field_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory/'templates_tless_object_1.yml.gz').write_bytes(gzip.compress(literal().encode()))
            attempts, diagnostics = self.records()
            result = audit_bank(directory, 1, attempts, diagnostics, Path.read_bytes)
            self.assertEqual(result['serialized_layers_checked'], 2)
            self.assertEqual(result['minimum_canvas_edge_distance'], 2)
            for field in diagnostics[0]:
                changed = copy.deepcopy(diagnostics)
                changed[0][field] = ('wrong_class' if field == 'class_id' else
                                     str(float(changed[0][field])+1) if field == 'scale' else
                                     str(int(changed[0][field])+1))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    audit_bank(directory, 1, attempts, changed, Path.read_bytes)
            for bad in [[], diagnostics+diagnostics]:
                with self.assertRaises(ValueError):
                    audit_bank(directory, 1, attempts, bad, Path.read_bytes)

    def test_failed_bank_is_absent_and_failed_layers_are_not_invented(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            rows, diagnostics = self.records()
            rows[0]['success'] = '0'
            self.assertEqual(audit_bank(directory, 1, rows, [], Path.read_bytes)['serialized_layers_checked'], 0)
            with self.assertRaises(ValueError):
                audit_bank(directory, 1, rows, diagnostics, Path.read_bytes)
            (directory/'templates_tless_object_1.yml.gz').write_bytes(gzip.compress(literal().encode()))
            with self.assertRaises(ValueError):
                audit_bank(directory, 1, rows, [], Path.read_bytes)


if __name__ == '__main__':
    unittest.main()
