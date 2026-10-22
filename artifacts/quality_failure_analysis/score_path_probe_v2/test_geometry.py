"""Synthetic geometry/LM semantics only; never imports native/image libraries."""
import unittest

import geometry as g


class GeometryTests(unittest.TestCase):
    def test_physical_anchor_does_not_reuse_arm_local_match_coordinates(self):
        self.assertEqual(g.physical_anchor((100, 200, 20, 30), (17, 19, 20, 30), (31, 37)),
                         (178, 282))

    def test_native_grid_neighbors_are_fixed_floor_and_ceiling(self):
        self.assertEqual(g.neighbors(1, 1), [(1, 1)])
        self.assertEqual(g.neighbors(2, 4), [(1, 1), (5, 1), (1, 5), (5, 5)])
        self.assertEqual(g.neighbors(-2, 1), [(-3, 1), (1, 1)])

    def test_all_clamped_parents_including_duplicate_window_bases(self):
        parents = g.parents((1, 1), (160, 160), (16, 16))
        self.assertEqual([(p['row'], p['col']) for p in parents], [(0, 0), (0, 1), (1, 0), (1, 1)])
        self.assertEqual({p['base'] for p in parents}, {(0, 0)})
        parents = g.parents((81, 81), (160, 160), (16, 16))
        self.assertEqual(len(parents), 49)
        self.assertEqual(len({p['base'] for p in parents}), 25)

    def test_coarse_flat_domain_preserves_wrap_and_zero_tail(self):
        # W=4,H=3,wf=hf=2 => computed flat j=0..6, regardless of right-edge wrap.
        lm = [[[4] * 12 for _ in range(64)]]
        raw = g.coarse_values(lm, [(0, 0, 0)], (32, 24), (16, 16), 8)
        self.assertEqual(raw, [4]*7+[0]*5)
        self.assertEqual(raw[3], 4)  # Row 0/col 3 wraps the nominal template.

    def test_window_base_skip_is_not_pointwise_feature_clipping(self):
        lm = [[[4] * 1600 for _ in range(16)]]
        # A base-x=-4 feature is skipped for the entire native local window.
        values, skipped = g.local_values(lm, [(0, 0, 0)], (160, 160), (-4, 0), 4)
        self.assertEqual(skipped, [0])
        self.assertEqual(values, [0]*256)
        # The standalone physical point at cell col=1 is in bounds and scores 4.
        self.assertEqual(g.physical_raw(lm, [(0, 0, 0)], (160, 160), (1, 1), 4), 4)
        self.assertIsNone(g.physical_raw(lm, [(0, 0, 0)], (160, 160), (-3, 1), 4))

    def test_off_grid_parent_query_and_unsafe_native_memory_are_not_negatives(self):
        with self.assertRaises(ValueError):
            g.parents((2, 1), (160, 160), (16, 16))
        lm = [[[4] * 12 for _ in range(64)]]
        with self.assertRaises(ValueError):
            g.coarse_values(lm, [(31, 23, 0)], (32, 24), (1, 1), 8)

    def test_native_clamp_order_and_truncation_survive_undersized_geometry(self):
        # Actual source applies max(border) THEN min(max_x), even if max_x<border.
        # center=-1 => C++ -1/4=0, not Python -1//4=-1.
        result = g.parents((-31, -31), (64, 64), (33, 33))
        self.assertEqual(len(result), 16)
        self.assertEqual({p['start'] for p in result}, {(-1, -1)})
        self.assertEqual({p['base'] for p in result}, {(-32, -32)})

    def test_native_tie_rule_and_zero_sentinel(self):
        self.assertEqual(g.winner([0]*256), dict(raw=0, row=-1, col=-1, ties=256))
        vector = [1]*256
        vector[7] = vector[65] = 4
        self.assertEqual(g.winner(vector), dict(raw=4, row=0, col=7, ties=2))


if __name__ == '__main__':
    unittest.main()
