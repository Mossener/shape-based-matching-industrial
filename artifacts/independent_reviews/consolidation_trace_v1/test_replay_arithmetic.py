import copy
import unittest

from audit_replay_statistics import compare, distribution, paired


class ReplayArithmetic(unittest.TestCase):
    def test_paired_median_differs_from_ratio_of_medians(self):
        a, b = [2, 50, 200], [1, 100, 100]
        ratios, median = paired(a, b)
        self.assertEqual(ratios, [2, .5, 2])
        self.assertEqual(median, 2)
        self.assertEqual(distribution(a)['median']/distribution(b)['median'], .5)

    def test_zero_copy_quantiles_and_bad_timing(self):
        self.assertEqual(distribution([0]*31), dict(median=0, p10=0, p90=0))
        self.assertEqual(distribution(list(range(31))), dict(median=15, p10=3, p90=27))
        for values in [[float('nan')], [-1]]:
            with self.assertRaises(ValueError):
                distribution(values)
        with self.assertRaises(ValueError):
            paired([1], [0])

    def test_changed_summary_numeric_or_identity_is_rejected(self):
        expected = dict(case='a', methods=dict(hash=dict(ratio=2., regressions=['a'])))
        compare(expected, copy.deepcopy(expected))
        for changed in [dict(case='b', methods=expected['methods']),
                        dict(case='a', methods=dict(hash=dict(ratio=.5, regressions=['a']))),
                        dict(case='a', methods=dict(hash=dict(ratio=2., regressions=[])))]:
            with self.assertRaises(ValueError):
                compare(expected, changed)


if __name__ == '__main__':
    unittest.main()
