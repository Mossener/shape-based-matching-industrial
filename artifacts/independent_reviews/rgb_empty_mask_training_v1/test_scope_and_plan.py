"""Scope, frozen-byte and fixed-canvas corruption fixtures; synthetic only."""
import copy
from pathlib import Path
import tempfile
import unittest

from audit import Reader, check_pin, pin, validate_fixed_union


def row(level=0):
    return dict(level=level,width=100,height=100,min_x=0,min_y=0,
                max_x=100,max_y=100,actual_features=37)


class ScopeAndPlan(unittest.TestCase):
    def test_feature_targets_are_not_actual_caps(self):
        self.assertEqual(validate_fixed_union([row(),row(1)])['width'],848)

    def test_fine_and_coarse_extents_are_separately_checked(self):
        for change in [dict(level=2),dict(width=785,max_x=785),
                       dict(height=769,max_y=769),dict(actual_features=0),
                       dict(min_x=-1),dict(max_x=101)]:
            bad=row();bad.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_fixed_union([bad])
        for change in [dict(width=425,max_x=424),dict(height=417,max_y=416),
                       dict(width=424,max_x=424),dict(height=416,max_y=416)]:
            bad=row(1);bad.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_fixed_union([bad])
        with self.assertRaises(ValueError):
            validate_fixed_union([])

    def test_pin_rejects_byte_and_size_changes(self):
        value=b'fixed numeric evidence';expected=pin(value)
        check_pin(value,expected)
        for changed in [value+b'!',b'FIXED numeric evidence']:
            with self.assertRaises(ValueError):
                check_pin(changed,expected)
        wrong=copy.deepcopy(expected);wrong['bytes']+=1
        with self.assertRaises(ValueError):
            check_pin(value,wrong)

    def test_reader_rejects_images_and_unlisted_private_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'image.png').write_bytes(b'synthetic')
            frozen=root/'frozen_inputs';frozen.mkdir();p=frozen/'numeric.json';p.write_bytes(b'{}')
            reader=Reader(root)
            with self.assertRaises(ValueError):reader.read(root/'image.png')
            with self.assertRaises(ValueError):reader.read(p)
            reader.private={'frozen_inputs/numeric.json':pin(b'{}')}
            self.assertEqual(reader.read(p),b'{}')
            p.write_bytes(b'{ }')
            with self.assertRaises(ValueError):reader.read(p)
            self.assertEqual(set(reader.pins),{str(p.resolve())})

    def test_reader_rejects_outside_root_and_changes_after_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);root=base/'experiment';root.mkdir()
            outside=base/'outside.json';outside.write_bytes(b'{}')
            inside=root/'numeric.json';inside.write_bytes(b'{}')
            reader=Reader(root)
            with self.assertRaises(ValueError):reader.read(outside)
            reader.read(inside);reader.final_check();inside.write_bytes(b'[]')
            with self.assertRaises(ValueError):reader.final_check()


if __name__=='__main__':
    unittest.main()
