"""Synthetic complete-summary arithmetic tests; no dataset/native access."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from summarize_benchmark import summarize_rows
from benchmark_contract_test import synthetic


def paired_fixture():
    rows, names = synthetic()
    for row in rows:
        if row["phase"] != "measured":
            continue
        round_index = int(row["round"]) % 3
        if row["case"] == "direct16_on":
            search = (1, 2, 9)[round_index]
        elif row["case"] == "direct16_off":
            search = (1, 8, 3)[round_index]
        else:
            search = 2
        row["search_ms"] = str(search)
        row["total_ms"] = str(7 + search)
        row["adapter_wall_ms"] = str(8 + search)
        # Fused response has no separate linearize phase. A valid zero
        # component must retain absolute summaries without a 0/0 ratio.
        row["linearize_ms"] = "0"
    return rows, names


class CompleteSummary(unittest.TestCase):
    def test_paired_summary_preserves_all_rounds_and_distinguishes_absolute_medians(self):
        rows, names = paired_fixture()
        result = summarize_rows(rows, names)
        ratio = result["ratios"]["search_ms"]["direct16_on__over__direct16_off"]
        self.assertEqual(ratio["per_image"][names[0]]["ratios"], [1, .25, 3] * 5)
        self.assertEqual(ratio["equal_weight_image_medians"]["median"], 1)
        self.assertEqual(ratio["equal_weight_image_medians"]["geomean"], 1)
        self.assertEqual(ratio["regressions"], [])
        self.assertEqual(result["absolute_ms"]["search_ms"]["direct16_on"]["per_image"][names[0]]["median"], 2)
        self.assertEqual(result["absolute_ms"]["search_ms"]["direct16_off"]["per_image"][names[0]]["median"], 3)
        self.assertNotIn("linearize_ms", result["ratios"])
        self.assertEqual(result["absolute_ms"]["linearize_ms"]["direct16_on"]["per_image"][names[0]]["median"], 0)

    def test_equal_image_weights_and_regressions_include_the_worse_image(self):
        rows, names = paired_fixture()
        for row in rows:
            if row["phase"] == "measured" and row["image"] == names[0] and row["case"] == "direct16_on":
                search = 2 * float(row["search_ms"])
                row.update(search_ms=str(search), total_ms=str(7 + search), adapter_wall_ms=str(8 + search))
        result = summarize_rows(rows, names)
        ratio = result["ratios"]["search_ms"]["direct16_on__over__direct16_off"]
        self.assertEqual(ratio["equal_weight_image_medians"]["median"], 1)
        self.assertAlmostEqual(ratio["equal_weight_image_medians"]["geomean"], 2 ** (1 / 25))
        self.assertEqual(ratio["regressions"], [dict(image=names[0], median_ratio=2)])
        self.assertEqual(ratio["all_images_by_descending_ratio"][0], ratio["regressions"][0])
        self.assertAlmostEqual(ratio["groups"]["LED"]["geomean"], 2 ** (1 / 8))
        self.assertEqual(ratio["groups"]["tiny"]["median"], 1)

    def test_invalid_or_incomplete_samples_do_not_get_a_summary(self):
        rows, names = paired_fixture()
        for changed in (rows[:-1], rows + [rows[0]]):
            with self.assertRaises(ValueError):
                summarize_rows(changed, names)
        changed = copy.deepcopy(rows)
        changed[0]["cache"] = "1"
        with self.assertRaises(ValueError):
            summarize_rows(changed, names)


if __name__ == "__main__":
    unittest.main()
