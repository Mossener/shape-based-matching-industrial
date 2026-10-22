"""Literal tests for the V31 all-bank geometry planner.

The fixtures are synthetic and intentionally tiny.  They exercise the exact
integer rules inherited from frozen_helpers/padding_plan.hpp without reading a
bank, an image, or invoking native code.
"""
from __future__ import annotations

import unittest

from planner import (
    ARMS,
    OBJECTS,
    Bank,
    BankLayer,
    BankTemplate,
    GeometryError,
    ResourceError,
    bank_from_records,
    plan_all,
)


def layer(level: int, *, width: int = 32, height: int = 24,
          tl_x: int = 0, tl_y: int = 0, points=((2, 3, 0), (8, 9, 1))) -> BankLayer:
    return BankLayer(level=level, width=width, height=height,
                     tl_x=tl_x, tl_y=tl_y, features=tuple(points))


def template(template_id: int = 0, *, l0=None, l1=None) -> BankTemplate:
    return BankTemplate(template_id=template_id,
                        layers=(l0 or layer(0), l1 or layer(1)))


def banks(count: int = 1, *, special=None):
    result = []
    for arm in ARMS:
        for object_id in OBJECTS:
            key = (arm, object_id)
            ts = tuple(template(i, **(special(key, i) if special else {})) for i in range(count))
            result.append(Bank(arm=arm, object_id=object_id,
                               class_id=f"tless_object_{object_id}", templates=ts))
    return tuple(result)


def counts(value=1):
    return {(arm, object_id): value for arm in ARMS for object_id in OBJECTS}


class GeometryPlannerTests(unittest.TestCase):
    def test_fixed_minimum_plan_and_eighteen_banks(self):
        result = plan_all(banks(), counts())
        self.assertEqual((result.width, result.height), (848, 832))
        self.assertEqual(result.alignment, 16)
        self.assertEqual(result.padding, (64, 64, 64, 228))
        self.assertEqual(result.pixels, 848 * 832)
        self.assertEqual(result.banks, 18)
        self.assertEqual(result.loaded_layers, 36)
        nested = {arm: {object_id: 1 for object_id in OBJECTS} for arm in ARMS}
        self.assertEqual(plan_all(banks(), nested).padding, result.padding)

    def test_all_actual_templates_are_counted_without_filtering(self):
        result = plan_all(banks(3), counts(3))
        self.assertEqual((result.banks, result.loaded_layers), (18, 108))

    def test_l1_max_plus_one_is_projected_by_two(self):
        def special(key, index):
            if key == ("B", 17) and index == 0:
                return {"l1": layer(1, width=500, height=300, tl_x=-150,
                                     points=((499, 2, 0), (500, 3, 1)))}
            return {}
        result = plan_all(banks(special=special), counts())
        # max_x + 1 = 501, then level-1 projection doubles it to 1002,
        # followed by the inherited 16-pixel alignment.
        self.assertEqual(result.width, 1008)
        self.assertEqual(result.height, 832)
        self.assertEqual(result.padding[2], 224)

    def test_l0_nonlast_margin_is_projected(self):
        def special(key, index):
            if key == ("P", 12) and index == 0:
                return {"l0": layer(0, width=800, height=500)}
            return {}
        result = plan_all(banks(special=special), counts())
        # 800 + 16*T0 = 864, already aligned.
        self.assertEqual(result.width, 864)

    def test_layer_origins_are_used_for_canvas_validation(self):
        def special(key, index):
            if key == ("C0", 1) and index == 0:
                return {"l1": layer(1, tl_x=355, points=((4, 2, 0), (6, 3, 1)))}
            return {}
        with self.assertRaises(GeometryError):
            plan_all(banks(special=special), counts())

    def test_negative_origin_can_still_be_valid_when_features_are_inside(self):
        def special(key, index):
            if key == ("C0", 1) and index == 0:
                return {"l0": layer(0, tl_x=-2, points=((3, 2, 0), (6, 3, 1)))}
            return {}
        result = plan_all(banks(special=special), counts())
        self.assertEqual((result.width, result.height), (848, 832))

    def test_class_identity_is_arm_qualified(self):
        duplicate = list(banks())
        duplicate.append(duplicate[0])
        with self.assertRaises(GeometryError):
            plan_all(tuple(duplicate), counts())

    def test_missing_bank_is_rejected(self):
        with self.assertRaises(GeometryError):
            plan_all(banks()[:-1], counts())

    def test_unexpected_bank_is_rejected(self):
        bad = list(banks())
        bad[-1] = Bank("X", OBJECTS[-1], "tless_object_17", bad[-1].templates)
        with self.assertRaises(GeometryError):
            plan_all(tuple(bad), counts())

    def test_count_evidence_is_required_and_must_match(self):
        incomplete = counts()
        del incomplete[("B", 1)]
        with self.assertRaises(GeometryError):
            plan_all(banks(), incomplete)
        wrong = counts()
        wrong[("B", 1)] = 2
        with self.assertRaises(GeometryError):
            plan_all(banks(), wrong)

    def test_template_ids_must_be_dense(self):
        def special(key, index):
            if key == ("P", 1) and index == 0:
                return {}
            return {}
        bad = list(banks(2, special=special))
        item = bad[6]
        bad[6] = Bank(item.arm, item.object_id, item.class_id,
                       (BankTemplate(1, item.templates[0].layers), item.templates[1]))
        with self.assertRaises(GeometryError):
            plan_all(tuple(bad), counts(2))

    def test_incomplete_pose_is_rejected(self):
        bad = list(banks())
        item = bad[0]
        bad[0] = Bank(item.arm, item.object_id, item.class_id,
                      (BankTemplate(0, (layer(0),)),))
        with self.assertRaises(GeometryError):
            plan_all(tuple(bad), counts())

    def test_duplicate_level_is_rejected(self):
        bad = list(banks())
        item = bad[0]
        bad[0] = Bank(item.arm, item.object_id, item.class_id,
                      (BankTemplate(0, (layer(0), layer(0))),))
        with self.assertRaises(GeometryError):
            plan_all(tuple(bad), counts())

    def test_zero_extent_is_rejected_like_cpp_helper(self):
        def special(key, index):
            if key == ("C0", 1):
                return {"l0": layer(0, width=0)}
            return {}
        with self.assertRaises(GeometryError):
            plan_all(banks(special=special), counts())

    def test_feature_bounds_are_checked_against_layer_extent(self):
        def special(key, index):
            if key == ("C0", 1):
                return {"l0": layer(0, width=10, points=((11, 2, 0), (1, 3, 1)))}
            return {}
        with self.assertRaises(GeometryError):
            plan_all(banks(special=special), counts())

    def test_feature_can_equal_width_boundary_for_inherited_helper(self):
        def special(key, index):
            if key == ("C0", 1):
                return {"l0": layer(0, width=10, points=((10, 2, 0), (1, 3, 1)))}
            return {}
        result = plan_all(banks(special=special), counts())
        self.assertEqual((result.width, result.height), (848, 832))

    def test_invalid_labels_and_empty_features_are_rejected(self):
        def empty(key, index):
            if key == ("C0", 1):
                return {"l0": layer(0, points=())}
            return {}
        with self.assertRaises(GeometryError):
            plan_all(banks(special=empty), counts())
        def label(key, index):
            if key == ("C0", 1):
                return {"l0": layer(0, points=((2, 3, 8), (3, 4, 0)))}
            return {}
        with self.assertRaises(GeometryError):
            plan_all(banks(special=label), counts())

    def test_resource_axis_pixel_and_dynamic_memory_limits(self):
        def huge(key, index):
            if key == ("B", 17):
                return {"l0": layer(0, width=2000, height=2000)}
            return {}
        with self.assertRaises(ResourceError):
            plan_all(banks(special=huge), counts())

    def test_checked_uint64_overflow_is_rejected(self):
        def huge(key, index):
            if key == ("B", 17):
                return {"l0": layer(0, width=(1 << 63) - 1, height=(1 << 63) - 1)}
            return {}
        with self.assertRaises((GeometryError, OverflowError)):
            plan_all(banks(special=huge), counts())

    def test_plan_is_json_ready_and_reports_geometry_trace(self):
        result = plan_all(banks(), counts())
        data = result.to_dict()
        self.assertEqual(data["source_size"], [720, 540])
        self.assertEqual(data["padding_ltrb"], [64, 64, 64, 228])
        self.assertEqual(data["banks"], 18)
        self.assertEqual(data["loaded_layers"], 36)
        self.assertEqual(data["geometry_feasible"], 1)
        self.assertEqual(len(data["layer_requirements"]), 36)

    def test_strict_reader_template_lists_adapt_without_file_access(self):
        raw = [[
            {"width": 32, "height": 24, "tl_x": 0, "tl_y": 0,
             "pyramid_level": 0, "features": [(2, 3, 0), (8, 9, 1)]},
            {"width": 32, "height": 24, "tl_x": 0, "tl_y": 0,
             "pyramid_level": 1, "features": [(2, 3, 0), (8, 9, 1)]},
        ]]
        bank = bank_from_records("C0", 1, "tless_object_1", raw)
        self.assertEqual(bank.templates[0].layers[1].level, 1)
        self.assertEqual(bank.templates[0].layers[0].features[1], (8, 9, 1))


if __name__ == "__main__":
    unittest.main()
