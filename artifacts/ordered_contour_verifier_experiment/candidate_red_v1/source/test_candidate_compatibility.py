"""Frozen supplied-grid behavior examples; no image, native build or timing."""
from dataclasses import FrozenInstanceError
import unittest
from unittest.mock import patch

import candidate_compatibility as compat
import edge_chains as edge
import weighted_ordered_match as core


MIN64 = -(2 ** 63)
MAX64 = 2 ** 63 - 1


def grid(width, height, foreground, label=0):
    """A constant direction label unless a test explicitly overrides it."""
    foreground = set(foreground)
    return tuple(tuple(label if y * width + x in foreground else 255
                       for x in range(width)) for y in range(height))


class CandidateCompatibilityTests(unittest.TestCase):
    def singleton(self, scene_grid=((0,),), *, tl=(0, 0), match=(0, 0),
                  padding=(0, 0, 0, 0), template_grid=((0,),)):
        return compat.score_candidate(edge.prepare_template(template_grid),
                                      compat.prepare_scene(scene_grid), tl,
                                      match, padding)

    def support(self, result, sample_id):
        by_id = {row.sample_id: row for row in result.samples}
        self.assertIn(sample_id, by_id)
        return by_id[sample_id]

    def assertTotals(self, result, a, b, denominator):
        self.assertEqual((result.independent_numerator,
                          result.ordered_numerator, result.denominator),
                         (a, b, denominator))
        self.assertLessEqual(0, result.ordered_numerator)
        self.assertLessEqual(result.ordered_numerator,
                             result.independent_numerator)
        self.assertLessEqual(result.independent_numerator, result.denominator)
        self.assertEqual(result.independent_accepted, 20 * a >= 13 * denominator)
        self.assertEqual(result.ordered_accepted, 20 * b >= 13 * denominator)

    def test_scene_factory_thins_then_extracts_instead_of_using_eligible_pixels(self):
        # Zhang--Suen erases this whole tiny component; eligible pixels remain
        # available diagnostically but cannot provide compatibility support.
        prepared = compat.prepare_scene(((0, 0), (0, 0)))
        self.assertEqual(prepared.thinning.eligible_labels, ((0, 0), (0, 0)))
        self.assertEqual(prepared.thinning.labels, ((255, 255), (255, 255)))
        self.assertEqual(prepared.chains, ())
        self.assertEqual(prepared.memberships, ())
        self.assertTotals(self.singleton(((0, 0), (0, 0))), 0, 0, 1)

    def test_scene_memberships_include_every_vertex_not_only_template_samples(self):
        prepared = compat.prepare_scene((tuple(0 for _ in range(5)),))
        self.assertEqual(prepared.chains, (edge.Chain(0, (0, 1, 2, 3, 4)),))
        self.assertEqual(prepared.memberships, tuple(
            compat.ScenePixelMembership(pixel, (compat.SceneChainMember(0, pixel),))
            for pixel in range(5)))

    def test_scene_shared_junction_has_both_chain_indices(self):
        prepared = compat.prepare_scene(grid(3, 4, (1, 4, 6, 8, 10)))
        self.assertEqual(prepared.chains,
                         (edge.Chain(0, (1, 4)),
                          edge.Chain(1, (4, 6, 10, 8), True, True)))
        self.assertEqual(prepared.memberships, (
            compat.ScenePixelMembership(1, (compat.SceneChainMember(0, 0),)),
            compat.ScenePixelMembership(4, (compat.SceneChainMember(0, 1),
                                           compat.SceneChainMember(1, 0))),
            compat.ScenePixelMembership(6, (compat.SceneChainMember(1, 1),)),
            compat.ScenePixelMembership(8, (compat.SceneChainMember(1, 3),)),
            compat.ScenePixelMembership(10, (compat.SceneChainMember(1, 2),))))

    def test_scene_factory_snapshots_lists_and_freezes_membership_tuples(self):
        source = [[0, 0, 0]]
        prepared = compat.prepare_scene(source)
        source[0][0] = 7
        self.assertEqual(prepared.thinning.labels, ((0, 0, 0),))
        self.assertIsInstance(prepared.memberships, tuple)
        self.assertEqual(len(prepared.memberships), 3)
        self.assertIsInstance(prepared.memberships[0].members, tuple)
        with self.assertRaises(FrozenInstanceError):
            prepared.memberships = ()
        with self.assertRaises(FrozenInstanceError):
            prepared.memberships[0].pixel_id = 9
        with self.assertRaises(FrozenInstanceError):
            prepared.memberships[0].members[0].chain_index = 9

    def test_scene_empty_is_legal_and_retains_dimensions(self):
        prepared = compat.prepare_scene(((255, 255, 255), (255, 255, 255)))
        self.assertEqual((prepared.thinning.width, prepared.thinning.height), (3, 2))
        self.assertEqual(prepared.chains, ())
        self.assertEqual(prepared.memberships, ())
        result = self.singleton(((255, 255, 255), (255, 255, 255)))
        self.assertTotals(result, 0, 0, 1)
        self.assertEqual(len(result.chains), 1)
        self.assertEqual(result.chains[0].case, None)
        self.assertEqual(result.chains[0].witness, ())
        self.assertEqual(result.chains[0].total_weight, 1)

    def test_scene_factory_rejects_malformed_supplied_grids(self):
        invalids = ((), [], ((),), ((0,), (0, 0)), "0", None,
                    ((True,),), ((1.0,),), ((-1,),), ((8,),), ((254,),))
        for invalid in invalids:
            with self.subTest(grid=invalid), self.assertRaises(ValueError):
                compat.prepare_scene(invalid)

    def test_same_singleton_returns_full_exact_evidence(self):
        result = self.singleton()
        self.assertTotals(result, 1, 1, 1)
        self.assertEqual(result.samples, (compat.SampleSupport(
            0, (0, 0), (0, 0), (0, 0), (0, 0), True, True, (0,), 0),))
        self.assertEqual(result.independent_witness, ((0, 0),))
        self.assertEqual(result.outside_padded_sample_ids, ())
        self.assertEqual(result.outside_original_sample_ids, ())
        self.assertEqual(result.cross_chain_reused_pixel_ids, ())
        self.assertEqual(len(result.chains), 1)
        chain = result.chains[0]
        self.assertEqual((chain.template_chain_id, chain.numerator,
                          chain.independent_numerator, chain.total_weight),
                         (0, 1, 1, 1))
        self.assertEqual(chain.case, core.MatchCase(0, 1, 0, 0))
        self.assertEqual(chain.witness, ((0, 0),))
        self.assertGreater(chain.work.edge_states, 0)

    def test_chebyshev_radius_two_includes_diagonal_boundary(self):
        result = self.singleton(grid(6, 6, (14,)))  # scene (2,2)
        self.assertTotals(result, 1, 1, 1)
        self.assertEqual(self.support(result, 0).compatible_pixel_ids, (14,))

    def test_chebyshev_distance_three_is_not_supported(self):
        for pixel in (3, 18, 21):  # (3,0), (0,3), (3,3) in width6
            with self.subTest(pixel=pixel):
                result = self.singleton(grid(6, 6, (pixel,)))
                self.assertTotals(result, 0, 0, 1)
                self.assertEqual(self.support(result, 0).compatible_pixel_ids, ())
                self.assertEqual(result.independent_witness, ())

    def test_outside_center_cannot_be_rescued_by_nearby_foreground(self):
        for match in ((-1, 0), (3, 0), (0, -1), (0, 3)):
            with self.subTest(match=match):
                result = self.singleton(grid(3, 3, (0, 2, 6, 8)), match=match)
                self.assertTotals(result, 0, 0, 1)
                row = self.support(result, 0)
                self.assertFalse(row.padded_in_bounds)
                self.assertFalse(row.original_in_bounds)
                self.assertEqual(row.compatible_pixel_ids, ())
                self.assertIsNone(row.independent_witness)
                self.assertEqual(result.outside_padded_sample_ids, (0,))
                self.assertEqual(result.outside_original_sample_ids, (0,))

    def test_unsigned_circular_direction_difference_wraps_at_seven(self):
        for template_label, scene_label, expected in ((0, 7, 1), (7, 0, 1),
                                                       (0, 1, 1), (7, 6, 1),
                                                       (0, 2, 0), (7, 5, 0),
                                                       (0, 4, 0), (0, 255, 0)):
            with self.subTest(template=template_label, scene=scene_label):
                result = self.singleton(((scene_label,),),
                                        template_grid=((template_label,),))
                self.assertTotals(result, expected, expected, 1)

    def test_independent_witness_chooses_smallest_physical_pixel(self):
        result = self.singleton(grid(5, 1, (0, 4)), match=(2, 0))
        self.assertTotals(result, 1, 1, 1)
        self.assertEqual(self.support(result, 0).compatible_pixel_ids, (0, 4))
        self.assertEqual(self.support(result, 0).independent_witness, 0)
        self.assertEqual(result.independent_witness, ((0, 0),))
        self.assertEqual(len(result.chains), 1)
        self.assertEqual(result.chains[0].case, core.MatchCase(0, 1, 0, 0))

    def test_independent_support_cannot_join_disconnected_scene_chains(self):
        template = edge.prepare_template((tuple(0 for _ in range(9)),))
        self.assertEqual(tuple((row.pixel_id, row.weight) for row in template.samples),
                         ((0, 1), (2, 1), (4, 2), (6, 2), (8, 2)))
        result = compat.score_candidate(template,
                                        compat.prepare_scene(grid(9, 1, (0, 8))),
                                        (0, 0), (0, 0))
        self.assertTotals(result, 6, 2, 8)
        self.assertTrue(result.independent_accepted)
        self.assertFalse(result.ordered_accepted)
        self.assertEqual(result.independent_witness, ((0, 0), (2, 0), (6, 8), (8, 8)))
        self.assertEqual(len(result.chains), 1)
        self.assertEqual(result.chains[0].case, core.MatchCase(1, 1, 0, 0))
        self.assertEqual(result.chains[0].witness, ((6, 8),))

    def test_one_scene_pixel_is_not_reused_inside_one_template_chain(self):
        template = edge.prepare_template((tuple(0 for _ in range(5)),))
        result = compat.score_candidate(template,
                                        compat.prepare_scene(grid(5, 1, (2,))),
                                        (0, 0), (0, 0))
        self.assertTotals(result, 3, 1, 3)
        self.assertEqual(result.independent_witness, ((0, 2), (2, 2), (4, 2)))
        self.assertEqual(len(result.chains), 1)
        self.assertEqual(result.chains[0].witness, ((0, 2),))
        self.assertEqual(result.cross_chain_reused_pixel_ids, ())

    def test_u_shape_and_long_false_line_have_support_but_incompatible_order(self):
        foreground = tuple(range(9)) + (20, 32, 42, 52) + tuple(range(44, 52))
        template = edge.prepare_template(grid(11, 5, foreground))
        self.assertEqual(len(template.chains), 1)
        self.assertEqual(tuple(row.pixel_id for row in
                               sorted(template.samples, key=lambda row: row.chain_index)),
                         (0, 2, 4, 6, 8, 32, 42, 51, 49, 47, 45, 44))
        self.assertEqual(template.denominator, 16)
        scene = compat.prepare_scene(grid(15, 5, range(30, 45)))
        result = compat.score_candidate(template, scene, (0, 0), (0, 0))
        self.assertEqual(result.independent_numerator, template.denominator)
        self.assertLess(result.ordered_numerator, result.independent_numerator)
        self.assertGreater(result.ordered_numerator, 0)
        self.assertEqual(result.denominator, 16)
        self.assertTrue(result.independent_accepted)

    def test_junction_memberships_cannot_duplicate_support_inside_one_chain(self):
        scene_grid = [list(row) for row in grid(3, 4, (1, 4, 6, 8, 10), label=4)]
        scene_grid[1][1] = 0  # only shared physical junction4 is compatible
        template = edge.prepare_template(((0, 0, 0),))
        result = compat.score_candidate(template, compat.prepare_scene(scene_grid),
                                        (0, 0), (0, 1))
        self.assertTotals(result, 2, 1, 2)
        self.assertEqual(result.independent_witness, ((0, 4), (2, 4)))
        self.assertEqual(len(result.chains), 1)
        self.assertEqual(result.chains[0].case, core.MatchCase(0, 1, 0, 0))
        self.assertEqual(result.chains[0].witness, ((0, 4),))
        self.assertEqual(result.cross_chain_reused_pixel_ids, ())

    def test_different_template_chains_may_reuse_same_scene_pixel(self):
        template = edge.prepare_template(grid(3, 1, (0, 2)))
        result = compat.score_candidate(template,
                                        compat.prepare_scene(grid(3, 1, (1,))),
                                        (0, 0), (0, 0))
        self.assertTotals(result, 2, 2, 2)
        self.assertEqual(result.independent_witness, ((0, 1), (2, 1)))
        self.assertEqual(result.cross_chain_reused_pixel_ids, (1,))
        self.assertEqual(tuple(chain.template_chain_id for chain in result.chains), (0, 1))
        self.assertEqual(tuple(chain.witness for chain in result.chains),
                         (((0, 1),), ((2, 1),)))

    def test_chain_with_no_owned_samples_keeps_full_zero_result(self):
        source = grid(6, 5, (0, 5, 7, 10, 14, 15, 19, 22, 24, 29))
        template = edge.prepare_template(source)
        result = compat.score_candidate(template, compat.prepare_scene(source),
                                        (0, 0), (0, 0))
        self.assertTotals(result, template.denominator, template.denominator,
                          template.denominator)
        self.assertEqual(len(result.chains), len(template.chains))
        by_id = {chain.template_chain_id: chain for chain in result.chains}
        self.assertIn(2, by_id)
        zero = by_id[2]
        self.assertEqual((zero.numerator, zero.independent_numerator,
                          zero.total_weight, zero.case, zero.witness),
                         (0, 0, 0, None, ()))
        self.assertEqual(zero.work, core.WorkCounters())

    def test_core_receives_owned_chain_order_and_only_scene_chains_with_edges(self):
        template = edge.prepare_template(grid(3, 3, (1, 3, 5, 7)))
        # A closed diamond has physical-ID-sorted owned samples1,5,7 but
        # canonical chain sampling order1,7,5. The extra scene singleton15
        # lies outside every radius-two neighborhood and must be omitted.
        scene = compat.prepare_scene(grid(8, 3, (1, 8, 10, 17, 15)))
        with patch.object(compat.core, "solve", wraps=core.solve) as solve_spy:
            result = compat.score_candidate(template, scene, (0, 0), (0, 0))
        self.assertEqual(solve_spy.call_count, 1)
        args = solve_spy.call_args.args
        self.assertEqual(args[0].sample_ids, (1, 7, 5))
        self.assertEqual(args[0].closed, True)
        self.assertTrue(args[1])
        self.assertTrue(all(chain.edges for chain in args[1]))
        self.assertTrue(all(15 not in chain.pixel_ids for chain in args[1]))
        self.assertTrue(any(chain.closed for chain in args[1]))
        self.assertEqual(len(result.chains), 1)

    def test_nonzero_tl_negative_relative_and_asymmetric_padding_keep_frames(self):
        result = self.singleton(grid(7, 6, (16,)), tl=(4, 5), match=(6, 7),
                                padding=(1, 2, 3, 1))
        self.assertTotals(result, 1, 1, 1)
        self.assertEqual(self.support(result, 0), compat.SampleSupport(
            0, (0, 0), (-4, -5), (2, 2), (1, 0), True, True, (16,), 16))

    def test_template_canvas_pixel_is_used_directly_without_second_origin_adjustment(self):
        template_grid = grid(5, 3, (7,))  # p_canvas=(2,1)
        result = self.singleton(grid(7, 6, (25,)), template_grid=template_grid,
                                tl=(1, 2), match=(3, 4))
        self.assertTotals(result, 1, 1, 1)
        self.assertEqual(self.support(result, 7), compat.SampleSupport(
            7, (2, 1), (1, -1), (4, 3), (4, 3), True, True, (25,), 25))

    def test_padding_only_support_is_legal_but_marked_outside_original(self):
        result = self.singleton(grid(7, 6, (7,)), match=(0, 1),
                                padding=(1, 2, 3, 1))
        self.assertTotals(result, 1, 1, 1)
        row = self.support(result, 0)
        self.assertEqual(row.q_original, (-1, -1))
        self.assertTrue(row.padded_in_bounds)
        self.assertFalse(row.original_in_bounds)
        self.assertEqual(result.outside_padded_sample_ids, ())
        self.assertEqual(result.outside_original_sample_ids, (0,))

    def test_outside_diagnostics_are_sample_sorted_and_do_not_shrink_denominator(self):
        template = edge.prepare_template(((0, 0, 0, 0, 0),))
        result = compat.score_candidate(template, compat.prepare_scene(((0, 0, 0),)),
                                        (0, 0), (-1, 0))
        self.assertTotals(result, 1, 1, 3)
        self.assertEqual(tuple(row.sample_id for row in result.samples), (0, 2, 4))
        self.assertEqual(result.outside_padded_sample_ids, (0, 4))
        self.assertEqual(result.outside_original_sample_ids, (0, 4))
        self.assertEqual(result.independent_witness, ((2, 0),))

    def test_coordinate_inputs_allow_builtin_int64_boundary_without_overflow(self):
        for tl, match, expected in (((MAX64, 0), (MAX64, 0), (0, 0)),
                                     ((0, 0), (MIN64, 0), (MIN64, 0)),
                                     ((0, MAX64), (0, MAX64), (0, 0))):
            with self.subTest(tl=tl, match=match):
                result = self.singleton(tl=tl, match=match)
                self.assertEqual(self.support(result, 0).q_padded, expected)
                self.assertEqual(self.support(result, 0).q_original, expected)

    def test_relative_subtraction_checks_overflow_before_later_cancellation(self):
        # 0-MIN64 overflows although MIN64+(0-MIN64) would equal0.
        for tl, match in (((MIN64, 0), (MIN64, 0)),
                           ((0, MIN64), (0, MIN64))):
            with self.subTest(tl=tl), self.assertRaises(ValueError):
                self.singleton(tl=tl, match=match)

    def test_padded_addition_checks_each_axis_for_overflow(self):
        for tl, match in (((-1, 0), (MAX64, 0)), ((1, 0), (MIN64, 0)),
                           ((0, -1), (0, MAX64)), ((0, 1), (0, MIN64))):
            with self.subTest(tl=tl, match=match), self.assertRaises(ValueError):
                self.singleton(tl=tl, match=match)

    def test_original_subtraction_is_checked_even_for_outside_padded_centers(self):
        for match, padding in (((MIN64, 0), (1, 0, 0, 0)),
                                ((0, MIN64), (0, 1, 0, 0))):
            with self.subTest(match=match), self.assertRaises(ValueError):
                self.singleton(grid(3, 3, (0,)), match=match, padding=padding)

    def test_coordinate_pairs_reject_bool_float_bad_lengths_and_out_of_int64(self):
        invalids = ((True, 0), (0, False), (1.0, 0), (0, 1.0), (), (0,),
                    (0, 0, 0), "00", None, (MIN64 - 1, 0), (0, MAX64 + 1))
        for value in invalids:
            with self.subTest(tl=value), self.assertRaises(ValueError):
                self.singleton(tl=value)
            with self.subTest(match=value), self.assertRaises(ValueError):
                self.singleton(match=value)

    def test_padding_rejects_bad_types_negative_values_and_nonpositive_original_size(self):
        invalids = ((True, 0, 0, 0), (0, False, 0, 0), (0, 0, 1.0, 0),
                    (-1, 0, 0, 0), (0, 0, 0, -1), (), (0, 0),
                    (0, 0, 0, 0, 0), "0000", None,
                    (3, 0, 0, 0), (1, 0, 2, 0), (0, 3, 0, 0), (0, 1, 0, 2),
                    (MAX64, 0, 1, 0), (0, MAX64, 0, 1), (MAX64 + 1, 0, 0, 0))
        for value in invalids:
            with self.subTest(padding=value), self.assertRaises(ValueError):
                self.singleton(grid(3, 3, (0,)), padding=value)

    def test_candidate_results_are_frozen_and_keep_immutable_tuples(self):
        result = self.singleton()
        self.assertEqual(len(result.samples), 1)
        self.assertIsInstance(result.samples, tuple)
        self.assertIsInstance(result.samples[0].compatible_pixel_ids, tuple)
        self.assertIsInstance(result.chains, tuple)
        self.assertIsInstance(result.independent_witness, tuple)
        with self.assertRaises(FrozenInstanceError):
            result.denominator = 9
        with self.assertRaises(FrozenInstanceError):
            result.samples[0].sample_id = 9

    def test_fixed_threshold_is_inclusive_and_exact(self):
        for numerator, denominator, expected in ((13, 20, True), (12, 20, False),
                                                   (0, 20, False), (20, 20, True),
                                                   (65, 100, True), (64, 100, False)):
            with self.subTest(n=numerator, d=denominator):
                self.assertIs(compat.passes_threshold(numerator, denominator), expected)

    def test_threshold_uses_arbitrary_precision_without_float(self):
        factor = 2 ** 220
        self.assertTrue(compat.passes_threshold(13 * factor, 20 * factor))
        self.assertFalse(compat.passes_threshold(13 * factor - 1, 20 * factor))
        self.assertTrue(compat.passes_threshold(20 * factor, 20 * factor))

    def test_threshold_rejects_noninteger_and_invalid_score_domains(self):
        for numerator, denominator in ((True, 1), (0, True), (1.0, 2), (1, 2.0),
                                         (0, 0), (1, -1), (-1, 20), (21, 20),
                                         ("1", 2), (1, None)):
            with self.subTest(n=numerator, d=denominator), self.assertRaises(ValueError):
                compat.passes_threshold(numerator, denominator)


if __name__ == "__main__":
    unittest.main()
