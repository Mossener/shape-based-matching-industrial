"""Synthetic valid and mutation checks for the independent timing audit."""
from __future__ import annotations

import copy
import csv
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

import timing_audit as audit


def valid_rows():
    frames = [(1, 10), (4, 20)]
    objects = (1, 2)
    references = {(obj, scene, image, arm): (10 + obj, 2 + obj)
                  for obj in objects for scene, image in frames for arm in audit.ARMS}
    rows = []
    for obj in objects:
        for scene, image in frames:
            for round_id in range(8):
                for order in range(4):
                    arm, path = audit.VARIANTS[(order + round_id) % 4]
                    # Warmup is intentionally huge so accidental warmup
                    # inclusion visibly changes quantiles.
                    base = 10000 if round_id == 0 else obj * 10 + round_id
                    factor = .5 if arm == "rgb_dilated_mask" else 1
                    value = base * factor + (.1 if path == "fused" else 0)
                    raw, selected = references[(obj, scene, image, arm)]
                    rows.append(dict(zip(audit.TIMING_HEADER, map(str, (
                        obj, scene, image, round_id, int(round_id == 0), order,
                        arm, path, value, value + 2, raw, selected, 1)))))
    return frames, objects, references, rows


def encoded(rows, header):
    result = io.StringIO(newline="")
    writer = csv.DictWriter(result, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return result.getvalue().encode()


class TimingAuditTests(unittest.TestCase):
    def setUp(self):
        self.frames, self.objects, self.references, self.rows = valid_rows()

    def validate(self, rows=None):
        return audit.validate_timing_rows(self.rows if rows is None else rows, self.frames,
                                          self.references, expected_calls=128, objects=self.objects)

    def test_minimal_valid_rotating_schedule_and_warmup_exclusion(self):
        result = self.validate()
        variants, paired = audit.recompute_statistics(result["formal"])
        self.assertEqual([item["samples"] for item in variants], [28] * 4)
        self.assertEqual([item["samples"] for item in paired], [28] * 2)
        self.assertTrue(all(item["match_p95_ms"] < 100 for item in variants))
        self.assertEqual(paired[0]["match_ratio_median"], .5)
        self.assertEqual(variants[0]["match_median_ms"], 17)

    def test_nearest_rank_even_median_is_lower_middle(self):
        self.assertEqual(audit.nearest_rank([100, 1, 10, 20], .5), 10)
        self.assertEqual(audit.nearest_rank(range(1, 21), .95), 19)

    def test_missing_duplicate_reordered_and_extra_rows_rejected(self):
        mutations = [self.rows[:-1], self.rows + self.rows[:1]]
        duplicate = copy.deepcopy(self.rows)
        duplicate[1] = duplicate[0]
        mutations.append(duplicate)
        reordered = copy.deepcopy(self.rows)
        reordered[3], reordered[4] = reordered[4], reordered[3]
        mutations.append(reordered)
        for rows in mutations:
            with self.subTest(length=len(rows)), self.assertRaises(audit.AuditError):
                self.validate(rows)

    def test_route_flags_counts_and_clock_mutations_rejected(self):
        mutations = {"object_id": "25", "scene": "2", "image": "99", "round": "7",
                     "order": "1", "arm": "rgb_dilated_mask", "path": "fused",
                     "warmup": "0", "exact_own_reference": "0", "raw": "999",
                     "selected": "999", "match_ms": "nan", "external_call_ms": "inf"}
        for field, value in mutations.items():
            rows = copy.deepcopy(self.rows)
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(audit.AuditError):
                self.validate(rows)
        for field in ("match_ms", "external_call_ms"):
            for value in ("0", "-1", "-inf"):
                rows = copy.deepcopy(self.rows)
                rows[0][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(audit.AuditError):
                    self.validate(rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["external_call_ms"] = "1"
        with self.assertRaisesRegex(audit.AuditError, "below match"):
            self.validate(rows)

    def test_csv_header_width_and_noncanonical_integer_rejected(self):
        with self.assertRaisesRegex(audit.AuditError, "header"):
            audit.csv_rows(encoded(self.rows, audit.TIMING_HEADER[::-1]), audit.TIMING_HEADER)
        with self.assertRaisesRegex(audit.AuditError, "width"):
            audit.csv_rows(b"a,b\n1,2,3\n", ["a", "b"])
        for value in ("+1", "01", "1.0", " 1", "-0"):
            with self.subTest(value=value), self.assertRaises(audit.AuditError):
                audit.integer(value)

    def test_native_summary_quantiles_ratios_counts_and_flags(self):
        grouped = self.validate()
        variants, paired = audit.recompute_statistics(grouped["formal"])
        summary = dict(passed=1, stage="timing", objects=list(audit.OBJECTS), unique_frames=64,
                       object_frame_combinations=384, matcher_calls=12288, warmup_rounds=1,
                       measured_rounds=7, exact_own_reference_every_call=1,
                       decode_total_ms=100, peak_rss_bytes=1024,
                       decode_and_bank_load_excluded_from_external_call=1, paired_performance_benchmark=1,
                       variants=variants, paired_empty_mask_over_rgb=paired)
        audit.validate_stage_summary(summary, variants, paired)
        for field in ("match_median_ms", "match_p95_ms", "external_median_ms", "external_p95_ms"):
            modified = copy.deepcopy(summary)
            modified["variants"][0][field] += 1
            with self.subTest(field=field), self.assertRaises(audit.AuditError):
                audit.validate_stage_summary(modified, variants, paired)
        for field in ("match_ratio_median", "match_ratio_p95", "external_ratio_median", "external_ratio_p95"):
            modified = copy.deepcopy(summary)
            modified["paired_empty_mask_over_rgb"][0][field] += .1
            with self.subTest(field=field), self.assertRaises(audit.AuditError):
                audit.validate_stage_summary(modified, variants, paired)
        for field in ("passed", "matcher_calls", "measured_rounds", "exact_own_reference_every_call"):
            modified = copy.deepcopy(summary)
            modified[field] = 0
            with self.subTest(field=field), self.assertRaises(audit.AuditError):
                audit.validate_stage_summary(modified, variants, paired)
        for field, value in (("decode_total_ms", float("nan")), ("decode_total_ms", -1),
                             ("peak_rss_bytes", 1_610_612_737), ("peak_rss_bytes", 1.5),
                             ("peak_rss_bytes", float("inf"))):
            modified = copy.deepcopy(summary)
            modified[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(audit.AuditError):
                audit.validate_stage_summary(modified, variants, paired)

    def test_frame_pair_median_then_equal_object_mean(self):
        grouped = self.validate()
        additional = audit.additional_equal_frame_summary(grouped["by_frame"], self.objects, 2)
        self.assertEqual(len(additional["per_object"]), 2)
        per_object = additional["per_object"]
        self.assertEqual(per_object[0]["variants"]["rgb_control/fallback"]["mean_frame_match_median_ms"], 14)
        self.assertEqual(per_object[1]["variants"]["rgb_control/fallback"]["mean_frame_match_median_ms"], 24)
        self.assertEqual(additional["equal_object_overall"]["variants"]["rgb_control/fallback"]["mean_frame_match_median_ms"], 19)
        self.assertEqual(additional["equal_object_overall"]["paired_dilation_over_control"]["fallback"]["mean_frame_match_ratio_median"], .5)

    def test_paired_ratio_uses_same_round_not_ratio_of_medians(self):
        groups = {}
        for arm, path in audit.VARIANTS:
            values = [1, 10, 100] if arm == "rgb_control" else [2, 100, 300]
            groups[(arm, path)] = [dict(object_id=1, scene=1, image=1, round=i + 1,
                                        match_ms=value, external_call_ms=value + 1)
                                   for i, value in enumerate(values)]
        _, paired = audit.recompute_statistics(groups)
        self.assertEqual(paired[0]["match_ratio_median"], 3)
        self.assertNotEqual(paired[0]["match_ratio_median"], 100 / 10)

    def test_numeric_reader_refuses_images_and_changed_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reader = audit.Reader(root)
            image = root / "forbidden.png"
            image.write_bytes(b"pixels")
            with self.assertRaisesRegex(audit.AuditError, "access refused"):
                reader.read(image)
            numeric = root / "numeric.json"
            numeric.write_text("{}")
            reader.read(numeric)
            numeric.write_text("[]")
            with self.assertRaisesRegex(audit.AuditError, "changed"):
                reader.read(numeric)

    def test_bank_order_counts_and_clocks(self):
        templates = {(obj, arm): 100 + obj if arm == "rgb_control" else 3456 for obj in self.objects for arm in audit.ARMS}
        rows = [dict(object_id=str(obj), arm=arm, templates=str(templates[(obj, arm)]),
                     metadata_load_ms="1", bank_load_ms="2") for obj in self.objects for arm in audit.ARMS]
        self.assertEqual(len(audit.validate_bank_rows(encoded(rows, audit.BANK_HEADER), templates, self.objects)), 4)
        changed = copy.deepcopy(rows)
        changed[1]["templates"] = "3455"
        with self.assertRaisesRegex(audit.AuditError, "template"):
            audit.validate_bank_rows(encoded(changed, audit.BANK_HEADER), templates, self.objects)
        changed[1]["templates"] = "3456"
        changed[1]["bank_load_ms"] = "nan"
        with self.assertRaises(audit.AuditError):
            audit.validate_bank_rows(encoded(changed, audit.BANK_HEADER), templates, self.objects)


if __name__ == "__main__":
    unittest.main()

