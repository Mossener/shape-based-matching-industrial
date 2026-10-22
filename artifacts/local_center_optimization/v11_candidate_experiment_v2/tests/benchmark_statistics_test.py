"""Arithmetic-only tests; this suite never opens images or runs a matcher."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark_statistics import describe, paired_stats


class BenchmarkStatistics(unittest.TestCase):
    def test_paired_round_median_is_not_ratio_of_absolute_medians(self):
        numerator, denominator = [1, 2, 9] * 5, [1, 8, 3] * 5
        result = paired_stats(numerator, denominator)
        self.assertEqual(result["ratios"], [1, .25, 3] * 5)
        self.assertEqual(result["median"], 1)
        self.assertNotEqual(result["median"], 2 / 3)
        self.assertAlmostEqual(result["geomean"], .75 ** (1 / 3))

    def test_equal_image_weights_geomean_and_descriptive_quantiles(self):
        result = describe([1, 4])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["median"], 2.5)
        self.assertEqual(result["geomean"], 2)
        self.assertAlmostEqual(result["p10"], 1.3)
        self.assertAlmostEqual(result["p90"], 3.7)
        self.assertEqual((result["min"], result["max"]), (1, 4))

    def test_zero_observations_are_descriptive_and_bad_denominators_fail(self):
        self.assertEqual(describe([0, 1])["geomean"], 0)
        self.assertEqual(paired_stats([0, 1], [1, 1])["median"], .5)
        for a, b in (([1], [0]), ([1], [-1]), ([1], [math.inf]),
                     ([math.nan], [1]), ([1, 2], [1]), ([], [])):
            with self.assertRaises(ValueError):
                paired_stats(a, b)
        for values in ([], [-1, 1], [math.nan], [math.inf]):
            with self.assertRaises(ValueError):
                describe(values)


if __name__ == "__main__":
    unittest.main()
