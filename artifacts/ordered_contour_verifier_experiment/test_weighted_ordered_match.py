"""Handwritten mathematical regressions; no images or detector execution.

Written before the implementation. The first coordinated run is expected to
observe assertion failures against the separately supplied zero-result stub.
This module does not implement the independent exhaustive oracle.
"""
import unittest

from weighted_ordered_match import MatchCase, SceneChain, TemplateChain, solve


class WeightedOrderedMatchTests(unittest.TestCase):
    def template(self, ids, weights, closed=False, chain_id=0):
        return TemplateChain(chain_id, tuple(ids), tuple(weights), closed)

    def scene(self, ids, edges=(), closed=False, chain_id=0):
        return SceneChain(chain_id, tuple(ids), tuple(edges), closed)

    def test_empty_template_is_a_zero_contribution_chain(self):
        result = solve(self.template((), ()), (self.scene((), closed=True),))
        self.assertEqual((result.numerator, result.independent_numerator,
                          result.total_weight, result.case, result.witness),
                         (0, 0, 0, None, ()))

    def test_no_edges_keeps_the_complete_weight_denominator(self):
        result = solve(self.template((10, 20), (3, 5)),
                       (self.scene((100, 200, 300)),))
        self.assertEqual((result.numerator, result.independent_numerator,
                          result.total_weight, result.case, result.witness),
                         (0, 0, 8, None, ()))
        self.assertEqual((result.work.case_count, result.work.edge_states), (0, 0))

    def test_one_edge_has_its_integer_weight_and_own_chain_identity(self):
        result = solve(self.template((50,), (7,), chain_id=9),
                       (self.scene((90,), ((50, 90),), chain_id=3),))
        self.assertEqual(result.template_chain_id, 9)
        self.assertEqual((result.numerator, result.independent_numerator,
                          result.total_weight), (7, 7, 7))
        self.assertEqual(result.case, MatchCase(3, 1, 0, 0))
        self.assertEqual(result.witness, ((50, 90),))

    def test_same_template_row_cannot_chain_two_edges(self):
        result = solve(self.template((10,), (7,)),
                       (self.scene((100, 200), ((10, 100), (10, 200))),))
        self.assertEqual((result.numerator, result.independent_numerator), (7, 7))
        self.assertEqual(result.witness, ((10, 100),))
        self.assertEqual(result.case, MatchCase(0, 1, 0, 0))
        self.assertEqual((result.work.case_count, result.work.edge_states), (2, 4))

    def test_scene_pixel_cannot_be_reused_in_one_correspondence(self):
        result = solve(self.template((10, 20), (3, 7)),
                       (self.scene((100,), ((10, 100), (20, 100))),))
        self.assertEqual((result.numerator, result.independent_numerator), (7, 10))
        self.assertEqual(result.witness, ((20, 100),))

    def test_weighted_optimum_can_use_fewer_points_than_maximum_count(self):
        result = solve(self.template((10, 20, 30, 40), (3, 3, 3, 11)),
                       (self.scene((100, 200, 300),
                                   ((10, 100), (20, 200), (30, 300), (40, 200))),))
        self.assertEqual((result.numerator, result.independent_numerator), (14, 20))
        self.assertEqual(result.witness, ((10, 100), (40, 200)))
        self.assertEqual(result.case.direction, 1)

    def test_witness_tie_compares_reversed_original_edge_ids(self):
        result = solve(self.template((30, 20, 10), (1, 1, 1)),
                       (self.scene((300, 200),
                                   ((30, 300), (20, 300), (10, 200))),))
        self.assertEqual(result.numerator, 2)
        self.assertEqual(result.witness, ((20, 300), (10, 200)))

    def test_witness_final_edge_tie_uses_ids_not_input_indices(self):
        result = solve(self.template((90, 10), (1, 1)),
                       (self.scene((100,), ((90, 100), (10, 100))),))
        self.assertEqual(result.numerator, 1)
        self.assertEqual(result.witness, ((10, 100),))

    def test_open_open_can_require_reverse_scene_direction(self):
        result = solve(self.template((1, 2, 3), (2, 3, 5)),
                       (self.scene((10, 20, 30),
                                   ((1, 30), (2, 20), (3, 10))),))
        self.assertEqual(result.numerator, 10)
        self.assertEqual(result.case, MatchCase(0, -1, 0, 0))
        self.assertEqual(result.witness, ((1, 30), (2, 20), (3, 10)))

    def test_open_closed_can_cross_the_canonical_scene_seam_once(self):
        result = solve(self.template((1, 2, 3), (1, 2, 3)),
                       (self.scene((10, 20, 30),
                                   ((1, 30), (2, 10), (3, 20)), closed=True),))
        self.assertEqual(result.numerator, 6)
        self.assertEqual(result.case, MatchCase(0, 1, 0, 2))
        self.assertEqual(result.witness, ((1, 30), (2, 10), (3, 20)))

    def test_closed_open_can_rotate_template_samples(self):
        result = solve(self.template((1, 2, 3), (1, 2, 3), closed=True),
                       (self.scene((10, 20, 30),
                                   ((3, 10), (1, 20), (2, 30))),))
        self.assertEqual(result.numerator, 6)
        self.assertEqual(result.case, MatchCase(0, 1, 2, 0))
        self.assertEqual(result.witness, ((3, 10), (1, 20), (2, 30)))

    def test_closed_closed_fixes_template_cut_zero(self):
        result = solve(self.template((1, 2, 3), (1, 2, 3), closed=True),
                       (self.scene((10, 20, 30),
                                   ((3, 10), (1, 20), (2, 30)), closed=True),))
        self.assertEqual(result.numerator, 6)
        self.assertEqual(result.case, MatchCase(0, 1, 0, 1))
        self.assertEqual(result.witness, ((1, 20), (2, 30), (3, 10)))

    def test_a_scene_cycle_cannot_be_used_for_two_laps(self):
        result = solve(self.template((1, 2, 3, 4), (1, 1, 1, 1)),
                       (self.scene((10, 20),
                                   ((1, 10), (2, 20), (3, 10), (4, 20)),
                                   closed=True),))
        self.assertEqual((result.numerator, result.independent_numerator), (2, 4))
        self.assertEqual(result.witness, ((1, 10), (2, 20)))
        self.assertEqual(len({edge[1] for edge in result.witness}), 2)

    def test_one_template_chain_cannot_combine_different_scene_chains(self):
        result = solve(self.template((1, 2, 3), (3, 4, 5)),
                       (self.scene((10,), ((1, 10),), chain_id=1),
                        self.scene((20, 30), ((2, 20), (3, 30)), chain_id=2)))
        self.assertEqual((result.numerator, result.independent_numerator), (9, 12))
        self.assertEqual(result.case.scene_chain_id, 2)
        self.assertEqual(result.witness, ((2, 20), (3, 30)))

    def test_scene_chain_id_tie_precedes_witness_edge_order(self):
        result = solve(self.template((1,), (7,)),
                       (self.scene((1,), ((1, 1),), chain_id=9),
                        self.scene((99,), ((1, 99),), chain_id=2)))
        self.assertEqual(result.numerator, 7)
        self.assertEqual(result.case, MatchCase(2, 1, 0, 0))
        self.assertEqual(result.witness, ((1, 99),))

    def test_case_direction_tie_precedes_witness_edge_order(self):
        result = solve(self.template((100, 5), (1, 1)),
                       (self.scene((90, 10),
                                   ((100, 90), (100, 10), (5, 90), (5, 10))),))
        self.assertEqual(result.numerator, 2)
        self.assertEqual(result.case, MatchCase(0, 1, 0, 0))
        self.assertEqual(result.witness, ((100, 90), (5, 10)))

    def test_arbitrary_precision_weights_distinguish_adjacent_huge_integers(self):
        large = 2 ** 200
        result = solve(self.template((1, 2), (large, large + 1)),
                       (self.scene((10,), ((1, 10), (2, 10))),))
        self.assertEqual((result.numerator, result.independent_numerator),
                         (large + 1, 2 * large + 1))
        self.assertEqual(result.witness, ((2, 10),))

    def test_edges_and_scene_input_order_do_not_change_canonical_result(self):
        template = self.template((1, 2), (2, 5))
        left = self.scene((30, 10), ((2, 10), (1, 30)), chain_id=8)
        right = self.scene((40,), ((1, 40),), chain_id=1)
        reordered_left = self.scene((30, 10), ((1, 30), (2, 10)), chain_id=8)
        self.assertEqual(solve(template, (left, right)),
                         solve(template, (right, reordered_left)))

    def test_scene_pixel_may_belong_to_multiple_distinct_chains(self):
        result = solve(self.template((1,), (9,)),
                       (self.scene((77,), ((1, 77),), chain_id=6),
                        self.scene((77,), ((1, 77),), chain_id=7)))
        self.assertEqual((result.numerator, result.independent_numerator), (9, 9))
        self.assertEqual(result.case.scene_chain_id, 6)

    def test_no_scene_chains_is_zero_support_with_unchanged_total_weight(self):
        result = solve(self.template((1, 2), (4, 9)), ())
        self.assertEqual((result.numerator, result.independent_numerator,
                          result.total_weight, result.case), (0, 0, 13, None))

    def test_template_ids_must_be_unique_physical_ids(self):
        with self.assertRaises(ValueError):
            solve(self.template((1, 1), (2, 3)), ())

    def test_scene_ids_must_be_unique_even_for_a_closed_chain(self):
        with self.assertRaises(ValueError):
            solve(self.template((1,), (1,)),
                  (self.scene((10, 20, 10), ((1, 10),), closed=True),))

    def test_repeated_compatibility_edges_are_rejected(self):
        with self.assertRaises(ValueError):
            solve(self.template((1,), (1,)),
                  (self.scene((10,), ((1, 10), (1, 10))),))

    def test_compatibility_edges_require_known_template_and_scene_ids(self):
        for edges in (((2, 10),), ((1, 20),)):
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                solve(self.template((1,), (1,)), (self.scene((10,), edges),))

    def test_weights_are_strictly_positive_builtin_integers(self):
        for bad in (True, 1.0, 0, -1, "1"):
            with self.subTest(weight=bad), self.assertRaises(ValueError):
                solve(self.template((1,), (bad,)), ())

    def test_weights_and_template_ids_have_equal_length(self):
        with self.assertRaises(ValueError):
            solve(self.template((1, 2), (3,)), ())

    def test_physical_ids_are_nonnegative_builtin_integers(self):
        for bad in (True, 1.0, -1, "1"):
            with self.subTest(identifier=bad), self.assertRaises(ValueError):
                solve(self.template((bad,), (1,)), ())
            with self.subTest(scene_identifier=bad), self.assertRaises(ValueError):
                solve(self.template((1,), (1,)), (self.scene((bad,)),))

    def test_scene_chain_ids_are_unique_nonnegative_builtin_integers(self):
        for bad in (True, 1.0, -1, "1"):
            with self.subTest(chain_id=bad), self.assertRaises(ValueError):
                solve(self.template((1,), (1,)), (self.scene((), chain_id=bad),))
        with self.assertRaises(ValueError):
            solve(self.template((1,), (1,)),
                  (self.scene((), chain_id=3), self.scene((), chain_id=3)))

    def test_template_chain_id_is_a_nonnegative_builtin_integer(self):
        for bad in (True, 1.0, -1, "1"):
            with self.subTest(chain_id=bad), self.assertRaises(ValueError):
                solve(self.template((), (), chain_id=bad), ())

    def test_closed_flags_require_actual_booleans(self):
        with self.assertRaises(ValueError):
            solve(self.template((1,), (1,), closed=1), ())
        with self.assertRaises(ValueError):
            solve(self.template((1,), (1,)), (self.scene((), closed=0),))


if __name__ == "__main__":
    unittest.main()
