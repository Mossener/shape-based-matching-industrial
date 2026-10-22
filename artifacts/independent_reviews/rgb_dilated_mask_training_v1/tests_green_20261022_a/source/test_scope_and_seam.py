"""Synthetic corruption fixtures: no real bank, source execution, or images."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import audit


def rows():
    return [dict(arm=arm, object_id=obj, class_id=f"tless_object_{obj}",
                 template_id=0, level=level, width=100, height=100,
                 min_x=0, min_y=0, max_x=100, max_y=100, actual_features=59)
            for obj in [1, 2, 5, 8, 12, 17]
            for arm in ["rgb_control", "rgb_dilated_mask"] for level in [0, 1]]


class ScopeAndSeam(unittest.TestCase):
    def test_full_union_does_not_allow_duplicate_layers(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit.validate_fixed_union(rows() + [rows()[0]])

    def test_full_union_does_not_allow_incomplete_pose(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            audit.validate_fixed_union(rows()[:-1])

    def test_full_union_requires_all_six_objects_and_both_arms(self):
        for changed in [rows()[4:], [r for r in rows() if r["arm"] == "rgb_control"]]:
            with self.assertRaises(ValueError):
                audit.validate_fixed_union(changed)

    def test_fixed_resources_and_feature_targets_are_not_caps(self):
        plan = audit.validate_fixed_union(rows())
        self.assertEqual((plan["width"], plan["height"], plan["alignment"]), (848, 832, 16))
        self.assertEqual(plan["padding_ltrb"], [64, 64, 64, 228])
        self.assertEqual(plan["estimated_dynamic_bytes"], 361234432)
        self.assertEqual(plan["loaded_layers"], 24)

    def test_fine_margin_and_coarse_coordinate_edge_are_strict(self):
        for level, changes in [(0, dict(width=785, max_x=785)),
                               (0, dict(height=769, max_y=769)),
                               (1, dict(width=425, max_x=424)),
                               (1, dict(width=424, max_x=424)),
                               (1, dict(height=416, max_y=416))]:
            changed = rows()
            changed[level].update(changes)
            with self.subTest(level=level, changes=changes), self.assertRaises(ValueError):
                audit.validate_fixed_union(changed)

    def test_seam_rejects_extra_delta_and_ambiguous_occurrence(self):
        self.assertTrue(callable(getattr(audit, "check_core_pair", None)), "Independent seam checker missing")
        old = b"prefix\n" + audit.OLD + b"\nsuffix\n"
        new = old.replace(audit.OLD, audit.NEW)
        audit.check_core_pair(old, new, pin_original=False)
        for bad in [new+b"extra", old, new.replace(b"prefix", b"other"),
                    new+audit.NEW]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                audit.check_core_pair(old, bad, pin_original=False)
        with self.assertRaises(ValueError):
            audit.check_core_pair(old+audit.OLD, new+audit.NEW, pin_original=False)

    def test_numeric_reader_requires_pinned_inherited_path_and_forbids_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            exp, parent = base/"experiment", base/"inherited"
            exp.mkdir();parent.mkdir()
            numeric = parent/"frozen_inputs"/"obj1"/"rgb_training"/"template_attempts.csv"
            numeric.parent.mkdir(parents=True);numeric.write_bytes(b"literal")
            reader = audit.Reader(exp)
            self.assertTrue(callable(getattr(reader, "allow_inherited", None)), "Pinned inherited reader missing")
            with self.assertRaises(ValueError):
                reader.read(numeric)
            reader.allow_inherited(parent, {numeric.relative_to(parent).as_posix(): audit.pin(b"literal")})
            self.assertEqual(reader.read(numeric), b"literal")
            numeric.write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                reader.read(numeric)
            image = exp/"fixture.png";image.write_bytes(b"synthetic")
            with self.assertRaises(ValueError):
                reader.read(image)

    def test_geometry_plan_rejects_wrong_padding_or_protocol_factor(self):
        self.assertTrue(callable(getattr(audit, "validate_protocol", None)), "Independent protocol validator missing")
        protocol = dict(
            objects=[1, 2, 5, 8, 12, 17],
            experiment="RGB_grayscale_source_official_mask_per_layer_dilation",
            change_surface=dict(core_changes=1, core_old=audit.OLD.decode(),
                                core_new=audit.NEW.decode(), third_addTemplate_argument="warped_official_mask"),
            training=dict(attempts_total=20736, views_per_object=72, attempts_per_object=3456,
                          scales=[.75, 1., 1.5, 2.], angles_degrees=list(range(0, 360, 30)),
                          pyramid_T=[4, 8], weak_threshold=20, strong_threshold=40,
                          requested_features=[32, 16], border=16),
            geometry_gate=dict(required_width=848, required_height=832, source_width=720,
                               source_height=540, padding_ltrb=[64, 64, 64, 228], alignment=16,
                               exact_size_required=True,
                               limits=dict(axis=2048, pixels=2097152, bytes_per_pixel=512,
                                           estimated_dynamic_bytes=1073741824, peak_rss_bytes=1610612736)))
        audit.validate_protocol(protocol)
        for section, key, value in [("geometry_gate", "padding_ltrb", [64]*4),
                                    ("training", "requested_features", [31, 15]),
                                    ("change_surface", "third_addTemplate_argument", "empty")]:
            changed = copy.deepcopy(protocol);changed[section][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit.validate_protocol(changed)


if __name__ == "__main__":
    unittest.main()
