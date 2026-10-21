"""Catch treating scale/aspect-incompatible boxes as searchable placements."""
import unittest
from size_coverage import ideal_iou


class IdealBoxContracts(unittest.TestCase):
    def test_hand_derived_area_and_aspect_limits(self):
        for a, b, value in [((10, 10), (20, 20), .25),
                            ((2, 8), (8, 2), 1/7),
                            ((1, 1), (2, 1), .5),
                            ((0, 1), (1, 1), 0)]:
            self.assertAlmostEqual(ideal_iou(a, b), value)

    def test_all_small_rectangles_against_translated_pixel_sets(self):
        for aw in range(1, 4):
            for ah in range(1, 4):
                a = {(x, y) for x in range(aw) for y in range(ah)}
                for bw in range(1, 4):
                    for bh in range(1, 4):
                        best = 0
                        for dx in range(-3, 4):
                            for dy in range(-3, 4):
                                b = {(x+dx, y+dy) for x in range(bw) for y in range(bh)}
                                best = max(best, len(a & b)/len(a | b))
                        self.assertAlmostEqual(ideal_iou((aw, ah), (bw, bh)), best)


if __name__ == '__main__':
    unittest.main()
