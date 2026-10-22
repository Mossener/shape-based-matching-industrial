"""Synthetic-only tests of the independent arithmetic auditor."""
import copy
import math
import unittest

from audit_benchmark import CASES, METRICS, compare, reconstruct, stats


def synthetic():
    names = ['LED_'+str(i) for i in range(1, 9)]+['case1']+['synthetic_'+str(i) for i in range(16)]
    rows = []
    for image, name in enumerate(names):
        for phase, rounds, offset, parity in [('cold', 1, 0, 0), ('warm', 2, 1, 1), ('measured', 15, 3, 0)]:
            for iteration in range(rounds):
                order = list(range(5))
                at = (image+offset+iteration) % 5
                order = order[at:]+order[:at]
                if (image+iteration//5+parity) % 2:
                    order = order[::-1]
                for position, which in enumerate(order):
                    identity, variant, cache = CASES[which]
                    row = dict(image=name, image_index=image, width=1024, height=1024,
                               templates=900 if image < 8 else 361 if image == 8 else 2212,
                               threshold=75 if image < 8 else 90 if image == 8 else 85,
                               phase=phase, round=iteration, order_position=position,
                               case=identity, variant=variant, cache=cache,
                               result_count=2, full_ordered_equal=1)
                    row.update({m: 1 for m in METRICS})
                    # Five repeats of these three paired patterns. Independent
                    # medians give 2/10=.2, while median([2,.2,2]) is 2.
                    off, on = [(1, 2), (10, 2), (100, 200)][iteration % 3]
                    search = on if identity == 'direct16_on' else off
                    row.update(preprocess_ms=7, search_ms=search, total_ms=7+search+3,
                               adapter_wall_ms=7+search+4)
                    rows.append({k: str(v) for k, v in row.items()})
    return names, rows


class ArithmeticTests(unittest.TestCase):
    def test_inclusive_total_and_paired_median(self):
        names, rows = synthetic()
        result, descriptive = reconstruct(rows, names)
        pair = result['ratios']['search_ms']['direct16_on__over__direct16_off']
        self.assertEqual(pair['per_image']['LED_1']['median'], 2)
        self.assertEqual(pair['equal_weight_image_medians']['median'], 2)
        self.assertEqual(len(pair['regressions']), 25)
        self.assertEqual(descriptive['LED']['search_ms']['direct16_on'], 2)
        self.assertEqual(descriptive['LED']['search_ms']['direct16_off'], 10)

    def test_wrong_route_and_inclusive_clocks_rejected(self):
        names, original = synthetic()
        for field, value in [('order_position', '9'), ('variant', 'unknown'),
                             ('result_count', '-1'), ('total_ms', '1'),
                             ('preprocess_ms', '1'), ('width', '1023'),
                             ('search_ms', 'nan')]:
            rows = copy.deepcopy(original)
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                reconstruct(rows, names)

    def test_summary_and_nonfinite_rejections(self):
        result = stats([0., 2., 4.])
        self.assertEqual(result['median'], 2)
        self.assertEqual(result['geomean'], 0)
        self.assertTrue(math.isclose(result['p10'], .4))
        compare(result, dict(result))
        bad = dict(result, median=3)
        with self.assertRaises(ValueError):
            compare(result, bad)
        for observations in [[], [-1], [math.inf], [math.nan]]:
            with self.assertRaises(ValueError):
                stats(observations)


if __name__ == '__main__':
    unittest.main()
