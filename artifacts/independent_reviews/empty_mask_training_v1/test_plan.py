import unittest

from audit_plan import dimensions


def row(level=0, width=10, height=20, x=10, y=20):
    return dict(level=level, width=width, height=height, min_x=0, min_y=0, max_x=x, max_y=y)


class PaddingArithmetic(unittest.TestCase):
    def test_minimum_size(self):
        p = dimensions([row()])
        self.assertEqual((p['width'], p['height'], p['padding_ltrb']), (848, 672, [64, 64, 64, 68]))

    def test_refinement_margin_and_coarse_endpoint(self):
        p = dimensions([row(width=800, x=799), row(1, height=400, y=400)])
        self.assertEqual((p['width'], p['height'], p['padding_ltrb']), (864, 816, [64, 64, 80, 212]))

    def test_invalid_or_over_budget(self):
        for rows in [[], [row(level=2)], [row(x=11)], [row(width=3000)]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                dimensions(rows)


if __name__ == '__main__':
    unittest.main()
