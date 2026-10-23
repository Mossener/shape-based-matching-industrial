"""Independent supplied-label checks; frozen before reference implementation.

No real image, matcher, native build, or timing measurement is exercised.
The exhaustive test has 512 occupancies, two fixed direction-label profiles,
three <=3-owned-sample templates, and two coordinate transforms: 6,144 exact
candidate comparisons. No occupancy or scene chain is silently skipped.
The coordinator supplies the complete-process 60s/512MiB/64MiB hard limits.
"""
from dataclasses import FrozenInstanceError, fields, is_dataclass
import json
import unittest

import candidate_compatibility as candidate
import edge_chains as edge
import independent_candidate_oracle as reference
import independent_edge_oracle as edge_reference
import independent_tiny_oracle as tiny


MIN64, MAX64 = -(2 ** 63), 2 ** 63 - 1


def grid(width, height, foreground, label=0):
    """Literal physical IDs are supplied; labels do not come from an image."""
    foreground = dict(foreground) if isinstance(foreground, dict) else {
        pixel: label for pixel in foreground}
    return tuple(tuple(foreground.get(y * width + x, 255)
                       for x in range(width)) for y in range(height))


def observable(value):
    """Compare every public dataclass field, omitting only solver work."""
    if is_dataclass(value):
        return tuple((field.name, observable(getattr(value, field.name)))
                     for field in fields(value) if field.name != "work")
    if isinstance(value, (tuple, list)):
        return tuple(observable(item) for item in value)
    return value


def case_tuple(case):
    return None if case is None else (case.scene_chain_id, case.direction,
                                      case.template_cut, case.scene_cut)


class IndependentCandidateOracleTests(unittest.TestCase):
    def supplied(self, scene_grid=((0,),), *, template_grid=((0,),),
                 tl=(0, 0), match=(0, 0), padding=(0, 0, 0, 0)):
        return reference.reference_candidate(template_grid, scene_grid, tl,
                                             match, padding)

    def assertTotals(self, result, a, b, denominator):
        self.assertEqual((result.independent_numerator, result.ordered_numerator,
                          result.denominator), (a, b, denominator))
        self.assertEqual((result.independent_accepted, result.ordered_accepted),
                         (20 * a >= 13 * denominator, 20 * b >= 13 * denominator))
        self.assertTrue(0 <= b <= a <= denominator)
        for value in (result.denominator, result.independent_numerator,
                      result.ordered_numerator):
            self.assertIs(type(value), int)

    def assertEquivalent(self, template_grid, scene_grid, tl=(0, 0),
                         match=(0, 0), padding=(0, 0, 0, 0)):
        expected = reference.reference_candidate(template_grid, scene_grid, tl,
                                                  match, padding)
        actual = candidate.score_candidate(edge.prepare_template(template_grid),
                                            candidate.prepare_scene(scene_grid),
                                            tl, match, padding)
        self.assertEqual(observable(actual), observable(expected))
        # Independently re-enumerate each supplied chain problem. This checks
        # canonical case/witness ties separately from candidate aggregation.
        problems = reference.reference_problems(template_grid, scene_grid, tl,
                                                 match, padding)
        self.assertEqual(len(problems), len(actual.chains))
        for problem, result in zip(problems, actual.chains):
            optimum = tiny.brute_force(problem.template, problem.scenes)
            self.assertEqual(result.template_chain_id, problem.template.chain_id)
            self.assertEqual((result.numerator, result.independent_numerator,
                              result.total_weight, case_tuple(result.case),
                              result.witness),
                             (optimum.numerator, optimum.independent_numerator,
                              optimum.total_weight, optimum.case, optimum.witness))
            self.assertEqual(len({a for a, _ in result.witness}), len(result.witness))
            self.assertEqual(len({b for _, b in result.witness}), len(result.witness))
        owners = {}
        for result in actual.chains:
            for _, pixel in result.witness:
                owners.setdefault(pixel, set()).add(result.template_chain_id)
        self.assertEqual(actual.cross_chain_reused_pixel_ids,
                         tuple(sorted(pixel for pixel, chains in owners.items()
                                      if len(chains) > 1)))
        self.assertTrue(0 <= actual.ordered_numerator <= actual.independent_numerator
                        <= actual.denominator)
        return actual, expected, problems

    def test_singleton_has_hand_literal_complete_evidence(self):
        result = self.supplied()
        expected = reference.CandidateScore(
            1, 1, 1, True, True,
            (reference.SampleSupport(0, (0, 0), (0, 0), (0, 0), (0, 0),
                                     True, True, (0,), 0),),
            (reference.ChainResult(0, 1, 1, 1, reference.MatchCase(0, 1, 0, 0),
                                   ((0, 0),)),), (), (), ((0, 0),), ())
        self.assertEqual(result, expected)
        self.assertEquivalent(((0,),), ((0,),))

    def test_scene_erased_pixels_do_not_remain_compatible_members(self):
        scene = reference.reference_scene(((0, 0), (0, 0)))
        self.assertEqual(scene.thinning.eligible_labels, ((0, 0), (0, 0)))
        self.assertEqual(scene.thinning.labels, ((255, 255), (255, 255)))
        self.assertEqual((scene.chains, scene.memberships), ((), ()))
        self.assertTotals(self.supplied(((0, 0), (0, 0))), 0, 0, 1)

    def test_empty_scene_retains_dimensions_and_full_unmatched_chain(self):
        scene_grid = ((255, 255, 255), (255, 255, 255))
        scene = reference.reference_scene(scene_grid)
        self.assertEqual((scene.thinning.width, scene.thinning.height), (3, 2))
        self.assertEqual((scene.chains, scene.memberships), ((), ()))
        result = self.supplied(scene_grid)
        self.assertTotals(result, 0, 0, 1)
        self.assertEqual(result.chains, (reference.ChainResult(0, 0, 0, 1, None, ()),))
        self.assertEquivalent(((0,),), scene_grid)

    def test_scene_memberships_retain_every_unsampled_physical_vertex(self):
        scene = reference.reference_scene(((0, 0, 0, 0, 0),))
        self.assertEqual(scene.memberships, tuple(
            reference.ScenePixelMembership(pixel, (reference.SceneChainMember(0, pixel),))
            for pixel in range(5)))
        self.assertEqual(tuple(chain.pixel_ids for chain in scene.chains),
                         ((0, 1, 2, 3, 4),))

    def test_returning_scene_junction_keeps_all_hand_literal_memberships(self):
        scene = reference.reference_scene(grid(3, 4, (1, 4, 6, 8, 10)))
        self.assertEqual(tuple((chain.chain_id, chain.pixel_ids, chain.closed,
                               chain.returning) for chain in scene.chains),
                         ((0, (1, 4), False, False), (1, (4, 6, 10, 8), True, True)))
        self.assertEqual(scene.memberships, (
            reference.ScenePixelMembership(1, (reference.SceneChainMember(0, 0),)),
            reference.ScenePixelMembership(4, (reference.SceneChainMember(0, 1),
                                               reference.SceneChainMember(1, 0))),
            reference.ScenePixelMembership(6, (reference.SceneChainMember(1, 1),)),
            reference.ScenePixelMembership(8, (reference.SceneChainMember(1, 3),)),
            reference.ScenePixelMembership(10, (reference.SceneChainMember(1, 2),))))

    def test_canvas_origin_and_asymmetric_padding_have_literal_coordinate_stages(self):
        result = self.supplied(grid(7, 6, (25,)), template_grid=grid(5, 3, (7,)),
                               tl=(1, 2), match=(3, 4), padding=(1, 2, 3, 1))
        self.assertTotals(result, 1, 1, 1)
        self.assertEqual(result.samples, (reference.SampleSupport(
            7, (2, 1), (1, -1), (4, 3), (3, 1), True, False, (25,), 25),))
        self.assertEqual(result.outside_original_sample_ids, (7,))
        self.assertEquivalent(grid(5, 3, (7,)), grid(7, 6, (25,)),
                              (1, 2), (3, 4), (1, 2, 3, 1))

    def test_negative_relative_coordinates_are_not_rotated_or_shifted_again(self):
        result = self.supplied(grid(7, 6, (16,)), tl=(4, 5), match=(6, 7),
                               padding=(1, 2, 3, 1))
        self.assertTotals(result, 1, 1, 1)
        self.assertEqual(result.samples, (reference.SampleSupport(
            0, (0, 0), (-4, -5), (2, 2), (1, 0), True, True, (16,), 16),))

    def test_padding_area_support_is_legal_and_original_bounds_are_diagnostic(self):
        result = self.supplied(grid(7, 6, (7,)), match=(0, 1),
                               padding=(1, 2, 3, 1))
        self.assertTotals(result, 1, 1, 1)
        self.assertEqual(result.samples, (reference.SampleSupport(
            0, (0, 0), (0, 0), (0, 1), (-1, -1), True, False, (7,), 7),))
        self.assertEqual(result.outside_padded_sample_ids, ())
        self.assertEqual(result.outside_original_sample_ids, (0,))

    def test_outside_centers_are_not_rescued_on_any_border(self):
        scene = grid(3, 3, (0, 2, 6, 8))
        for center in ((-1, 0), (3, 0), (0, -1), (0, 3)):
            with self.subTest(center=center):
                result = self.supplied(scene, match=center)
                self.assertTotals(result, 0, 0, 1)
                self.assertEqual(result.samples[0].compatible_pixel_ids, ())
                self.assertIsNone(result.samples[0].independent_witness)
                self.assertEqual(result.outside_padded_sample_ids, (0,))
                self.assertEquivalent(((0,),), scene, match=center)

    def test_chebyshev_radius_two_includes_corner_but_not_distance_three(self):
        for pixel, expected in ((14, 1), (3, 0), (18, 0), (21, 0)):
            with self.subTest(pixel=pixel):
                scene = grid(6, 6, (pixel,))
                result = self.supplied(scene)
                self.assertTotals(result, expected, expected, 1)
                self.assertEqual(result.samples[0].compatible_pixel_ids,
                                 (pixel,) if expected else ())
                self.assertEquivalent(((0,),), scene)

    def test_all_64_direction_pairs_use_unsigned_circular_difference(self):
        # Hand-literal allowed scene-label sets for template labels 0..7.
        accepted = ((0, 1, 7), (0, 1, 2), (1, 2, 3), (2, 3, 4),
                    (3, 4, 5), (4, 5, 6), (5, 6, 7), (0, 6, 7))
        for template_label in range(8):
            for scene_label in range(8):
                with self.subTest(template=template_label, scene=scene_label):
                    supported = int(scene_label in accepted[template_label])
                    result = self.supplied(((scene_label,),),
                                           template_grid=((template_label,),))
                    self.assertTotals(result, supported, supported, 1)
                    self.assertEquivalent(((template_label,),), ((scene_label,),))

    def test_invalid_255_never_supplies_direction_support(self):
        result = self.supplied(((255,),))
        self.assertTotals(result, 0, 0, 1)
        self.assertEqual(result.samples[0].compatible_pixel_ids, ())

    def test_independent_witness_is_smallest_physical_id_across_components(self):
        result = self.supplied(grid(5, 1, (0, 4)), match=(2, 0))
        self.assertTotals(result, 1, 1, 1)
        self.assertEqual(result.samples[0].compatible_pixel_ids, (0, 4))
        self.assertEqual(result.independent_witness, ((0, 0),))
        self.assertEqual(result.chains[0].case, reference.MatchCase(0, 1, 0, 0))

    def test_one_scene_point_is_not_reused_within_one_template_chain(self):
        template_grid = ((0, 0, 0, 0, 0),)
        scene_grid = grid(5, 1, (2,))
        result = self.supplied(scene_grid, template_grid=template_grid)
        self.assertTotals(result, 3, 1, 3)
        self.assertEqual(result.independent_witness, ((0, 2), (2, 2), (4, 2)))
        self.assertEqual(result.chains[0].witness, ((0, 2),))
        self.assertEquivalent(template_grid, scene_grid)

    def test_disconnected_scene_chains_cannot_be_joined_for_ordered_mass(self):
        template_grid = (tuple(0 for _ in range(9)),)
        scene_grid = grid(9, 1, (0, 8))
        result = self.supplied(scene_grid, template_grid=template_grid)
        self.assertTotals(result, 6, 2, 8)
        self.assertEqual(result.independent_witness, ((0, 0), (2, 0), (6, 8), (8, 8)))
        self.assertEqual(result.chains[0].case, reference.MatchCase(1, 1, 0, 0))
        self.assertEqual(result.chains[0].witness, ((6, 8),))
        self.assertEquivalent(template_grid, scene_grid)

    def test_shared_junction_memberships_do_not_duplicate_a_physical_match(self):
        scene_grid = grid(3, 4, {1: 4, 4: 0, 6: 4, 8: 4, 10: 4})
        result = self.supplied(scene_grid, template_grid=((0, 0, 0),), match=(0, 1))
        self.assertTotals(result, 2, 1, 2)
        self.assertEqual(result.independent_witness, ((0, 4), (2, 4)))
        self.assertEqual(result.chains[0].witness, ((0, 4),))
        self.assertEquivalent(((0, 0, 0),), scene_grid, match=(0, 1))

    def test_distinct_template_chains_can_reuse_one_scene_pixel(self):
        template_grid, scene_grid = grid(3, 1, (0, 2)), grid(3, 1, (1,))
        result = self.supplied(scene_grid, template_grid=template_grid)
        self.assertTotals(result, 2, 2, 2)
        self.assertEqual(tuple(chain.witness for chain in result.chains),
                         (((0, 1),), ((2, 1),)))
        self.assertEqual(result.cross_chain_reused_pixel_ids, (1,))
        self.assertEquivalent(template_grid, scene_grid)

    def test_closed_template_problem_preserves_original_chain_index_order(self):
        template_grid = grid(3, 3, (1, 3, 5, 7))
        scene_grid = grid(8, 3, (1, 8, 10, 17, 15))
        problems = reference.reference_problems(template_grid, scene_grid, (0, 0), (0, 0))
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].template, reference.TemplateInput(
            0, (1, 7, 5), (1, 1, 1), True))
        self.assertEqual(len(problems[0].scenes), 1)
        self.assertEqual(problems[0].scenes[0].pixel_ids, (1, 8, 17, 10))
        self.assertTrue(problems[0].scenes[0].closed)
        self.assertEquivalent(template_grid, scene_grid)

    def test_problem_keeps_unsampled_scene_nodes_and_omits_nonincident_chains(self):
        problems = reference.reference_problems(((0,),), grid(9, 1, (0, 1, 2, 3, 4, 8)),
                                                 (0, 0), (0, 0))
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].scenes, (reference.SceneInput(
            0, (0, 1, 2, 3, 4), ((0, 0), (0, 1), (0, 2)), False),))
        self.assertEquivalent(((0,),), grid(9, 1, (0, 1, 2, 3, 4, 8)))

    def test_zero_owned_chain_is_retained_as_a_complete_zero_result(self):
        source = grid(6, 5, (0, 5, 7, 10, 14, 15, 19, 22, 24, 29))
        result = self.supplied(source, template_grid=source)
        self.assertGreaterEqual(len(result.chains), 3)
        self.assertEqual(result.chains[2], reference.ChainResult(2, 0, 0, 0, None, ()))
        self.assertEquivalent(source, source)

    def test_outside_sample_ids_remain_sorted_without_denominator_shrinkage(self):
        result = self.supplied(((0, 0, 0),), template_grid=((0, 0, 0, 0, 0),),
                               match=(-1, 0))
        self.assertTotals(result, 1, 1, 3)
        self.assertEqual(tuple(row.sample_id for row in result.samples), (0, 2, 4))
        self.assertEqual(result.outside_padded_sample_ids, (0, 4))
        self.assertEqual(result.outside_original_sample_ids, (0, 4))
        self.assertEqual(result.independent_witness, ((2, 0),))
        self.assertEquivalent(((0, 0, 0, 0, 0),), ((0, 0, 0),), match=(-1, 0))

    def test_signed_int64_boundary_values_are_legal_when_all_stages_fit(self):
        for tl, match, q in (((MAX64, 0), (MAX64, 0), (0, 0)),
                              ((0, MAX64), (0, MAX64), (0, 0)),
                              ((0, 0), (MIN64, 0), (MIN64, 0))):
            with self.subTest(tl=tl, match=match):
                result = self.supplied(tl=tl, match=match)
                self.assertEqual(len(result.samples), 1)
                self.assertEqual(result.samples[0].q_padded, q)
                self.assertEqual(result.samples[0].q_original, q)
                self.assertEquivalent(((0,),), ((0,),), tl, match)

    def test_relative_subtraction_overflow_is_rejected_before_cancellation(self):
        for tl, match in (((MIN64, 0), (MIN64, 0)), ((0, MIN64), (0, MIN64))):
            with self.subTest(tl=tl), self.assertRaises(ValueError):
                self.supplied(tl=tl, match=match)

    def test_predicted_center_addition_overflow_is_rejected_on_each_axis(self):
        for tl, match in (((-1, 0), (MAX64, 0)), ((1, 0), (MIN64, 0)),
                           ((0, -1), (0, MAX64)), ((0, 1), (0, MIN64))):
            with self.subTest(tl=tl, match=match), self.assertRaises(ValueError):
                self.supplied(tl=tl, match=match)

    def test_original_frame_subtraction_is_checked_even_for_outside_centers(self):
        for match, padding in (((MIN64, 0), (1, 0, 0, 0)),
                                ((0, MIN64), (0, 1, 0, 0))):
            with self.subTest(match=match), self.assertRaises(ValueError):
                self.supplied(grid(3, 3, (0,)), match=match, padding=padding)

    def test_pose_validation_rejects_bool_float_bad_pairs_and_out_of_range_ints(self):
        invalids = ((True, 0), (0, False), (1.0, 0), (0, 1.0), (), (0,),
                    (0, 0, 0), "00", None, (MIN64 - 1, 0), (0, MAX64 + 1))
        for value in invalids:
            with self.subTest(tl=value), self.assertRaises(ValueError):
                self.supplied(tl=value)
            with self.subTest(match=value), self.assertRaises(ValueError):
                self.supplied(match=value)

    def test_padding_validation_checks_types_sign_sums_and_positive_original_size(self):
        invalids = ((True, 0, 0, 0), (0, False, 0, 0), (0, 0, 1.0, 0),
                    (-1, 0, 0, 0), (0, 0, 0, -1), (), (0, 0),
                    (0, 0, 0, 0, 0), "0000", None, (3, 0, 0, 0),
                    (1, 0, 2, 0), (0, 3, 0, 0), (0, 1, 0, 2),
                    (MAX64, 0, 1, 0), (0, MAX64, 0, 1), (MAX64 + 1, 0, 0, 0))
        for value in invalids:
            with self.subTest(padding=value), self.assertRaises(ValueError):
                self.supplied(grid(3, 3, (0,)), padding=value)

    def test_exact_threshold_is_inclusive_at_thirteen_twentieths(self):
        for numerator, denominator, accepted in ((13, 20, True), (12, 20, False),
                                                   (65, 100, True), (64, 100, False),
                                                   (0, 20, False), (20, 20, True)):
            with self.subTest(n=numerator, d=denominator):
                self.assertIs(reference.reference_threshold(numerator, denominator), accepted)
                self.assertIs(candidate.passes_threshold(numerator, denominator), accepted)

    def test_threshold_does_not_round_arbitrary_precision_integers_to_float(self):
        scale = 2 ** 220
        self.assertTrue(reference.reference_threshold(13 * scale, 20 * scale))
        self.assertFalse(reference.reference_threshold(13 * scale - 1, 20 * scale))
        self.assertTrue(reference.reference_threshold(20 * scale, 20 * scale))

    def test_threshold_rejects_noninteger_and_invalid_score_domains(self):
        for numerator, denominator in ((True, 1), (0, True), (1.0, 2), (1, 2.0),
                                         (0, 0), (1, -1), (-1, 20), (21, 20),
                                         ("1", 2), (1, None)):
            with self.subTest(n=numerator, d=denominator), self.assertRaises(ValueError):
                reference.reference_threshold(numerator, denominator)

    def test_supplied_grid_validation_and_empty_template_are_contract_errors(self):
        for invalid in ((), [], ((),), ((0,), (0, 0)), "0", None,
                        ((True,),), ((1.0,),), ((-1,),), ((8,),), ((254,),)):
            with self.subTest(scene=invalid), self.assertRaises(ValueError):
                reference.reference_scene(invalid)
            with self.subTest(template=invalid), self.assertRaises(ValueError):
                self.supplied(template_grid=invalid)
        for empty in (((255,),), ((0, 0), (0, 0))):
            with self.subTest(empty=empty), self.assertRaises(ValueError):
                self.supplied(template_grid=empty)

    def test_independent_evidence_is_frozen_and_snapshots_supplied_lists(self):
        source = [[0, 0, 0]]
        scene = reference.reference_scene(source)
        source[0][0] = 7
        self.assertEqual(scene.thinning.labels, ((0, 0, 0),))
        with self.assertRaises(FrozenInstanceError):
            scene.memberships = ()
        result = self.supplied()
        self.assertEqual(len(result.samples), 1)
        self.assertIsInstance(result.samples, tuple)
        self.assertIsInstance(result.samples[0].compatible_pixel_ids, tuple)
        self.assertIsInstance(result.chains, tuple)
        with self.assertRaises(FrozenInstanceError):
            result.samples[0].q_padded = (1, 1)

    def test_tiny_reference_limits_reject_over_eight_points_without_truncation(self):
        # A 17-node open chain has nine owned samples; a 9-node scene chain
        # exceeds the brute-force scene limit. Both errors must be explicit.
        for template_grid, scene_grid in (((tuple(0 for _ in range(17)),), ((0,),)),
                                           (((0,),), (tuple(0 for _ in range(9)),))):
            with self.subTest(template=template_grid, scene=scene_grid):
                with self.assertRaises(ValueError):
                    reference.reference_candidate(template_grid, scene_grid, (0, 0), (0, 0))
                with self.assertRaises(ValueError):
                    reference.reference_problems(template_grid, scene_grid, (0, 0), (0, 0))

    def test_exhaustive_all_512_three_by_three_scene_occupancies(self):
        templates = (grid(3, 3, (4,)), ((0, 0, 0, 0, 0),),
                     grid(3, 3, (1, 3, 5, 7)))
        transforms = (((0, 0), (0, 0), (0, 0, 0, 0)),
                      ((2, 1), (1, 2), (1, 0, 0, 1)))
        label_profiles = ((0,) * 9, (0, 7, 2, 6, 4, 1, 5, 3, 0))
        max_owned = max(len(edge_reference.reference_template(template).samples)
                        for template in templates)
        self.assertEqual(max_owned, 3)
        comparisons = chain_comparisons = maximum_scene_chain = 0
        for mask in range(512):
            # One subtest per occupancy keeps deliberate empty-stub RED output
            # finite while GREEN executes every profile/template/transform.
            with self.subTest(occupancy=mask):
                for labels in label_profiles:
                    scene_grid = grid(3, 3, {pixel: labels[pixel]
                                            for pixel in range(9) if mask & (1 << pixel)})
                    prepared = reference.reference_scene(scene_grid)
                    scene_maximum = max((len(chain.pixel_ids) for chain in prepared.chains),
                                        default=0)
                    self.assertLessEqual(scene_maximum, 8,
                                         "3x3 scene exceeded declared tiny limit; no skip allowed")
                    maximum_scene_chain = max(maximum_scene_chain, scene_maximum)
                    for template_grid in templates:
                        for tl, match, padding in transforms:
                            actual, _, problems = self.assertEquivalent(
                                template_grid, scene_grid, tl, match, padding)
                            self.assertGreater(actual.denominator, 0)
                            comparisons += 1
                            chain_comparisons += len(problems)
        self.assertEqual(comparisons, 6144)
        self.assertGreater(maximum_scene_chain, 0)
        print("INDEPENDENT_CANDIDATE_EXHAUSTIVE " + json.dumps({
            "scene_occupancies": 512, "direction_profiles": 2, "templates": 3,
            "transforms": 2, "candidate_comparisons": comparisons,
            "chain_brute_force_comparisons": chain_comparisons,
            "maximum_owned_template_samples": max_owned,
            "maximum_scene_chain_points": maximum_scene_chain,
            "skipped_cases": 0}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
