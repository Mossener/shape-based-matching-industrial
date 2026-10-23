"""Handwritten label-grid/chain regressions, written before implementation.

These tests use tiny in-memory labels only. They do not decode images, call a
detector, implement the independent oracle, or authorize a quality experiment.
"""
from dataclasses import FrozenInstanceError
import unittest

from edge_chains import (Chain, extract_chains, prepare_template, sample_chain,
                         thin_labels)


def grid(width, height, pixels):
    """Place explicit physical IDs with distinct legal direction labels."""
    rows = [[255] * width for _ in range(height)]
    for pixel_id in pixels:
        rows[pixel_id // width][pixel_id % width] = pixel_id % 8
    return tuple(tuple(row) for row in rows)


class EdgeChainsTests(unittest.TestCase):
    def test_horizontal_line_keeps_original_direction_labels(self):
        source = ((0, 1, 2, 3, 4, 5, 6),)
        result = thin_labels(source)
        self.assertEqual((result.width, result.height), (7, 1))
        self.assertEqual(result.eligible_labels, source)
        self.assertEqual(result.labels, source)
        self.assertEqual(result.round_deletions, ((0, 0),))

    def test_two_subiterations_use_synchronous_deletion_and_retain_center_label(self):
        source = ((0, 1, 2), (3, 4, 5), (6, 7, 0))
        result = thin_labels(source)
        self.assertEqual(result.labels, ((255, 255, 255),
                                         (255, 4, 255),
                                         (255, 255, 255)))
        self.assertEqual(result.round_deletions, ((6, 2), (0, 0)))
        self.assertEqual(result.eligible_labels, source)

    def test_all_invalid_grid_is_valid_scene_evidence(self):
        source = ((255, 255), (255, 255))
        result = thin_labels(source)
        self.assertEqual(result.labels, source)
        self.assertEqual(result.round_deletions, ((0, 0),))
        self.assertEqual(extract_chains(source), ())

    def test_isolated_pixel_remains_a_singleton_open_chain(self):
        source = grid(3, 3, (4,))
        result = thin_labels(source)
        self.assertEqual(result.labels, source)
        self.assertEqual(extract_chains(result.labels),
                         (Chain(0, (4,), False, False),))

    def test_diagonal_touch_is_an_eight_neighbor_edge(self):
        source = grid(2, 2, (0, 3))
        self.assertEqual(extract_chains(source),
                         (Chain(0, (0, 3), False, False),))
        sampling = sample_chain(Chain(0, (0, 3)), 2)
        self.assertEqual((sampling.pixel_ids, sampling.arclength), ((0, 3), 1414))

    def test_open_chain_uses_canonical_forward_or_reverse_pixel_sequence(self):
        self.assertEqual(extract_chains(grid(1, 5, (0, 1, 2, 3, 4))),
                         (Chain(0, (0, 1, 2, 3, 4), False, False),))

    def test_pure_diamond_cycle_is_canonical_and_does_not_repeat_first_pixel(self):
        chains = extract_chains(grid(3, 3, (1, 3, 5, 7)))
        self.assertEqual(chains, (Chain(0, (1, 3, 7, 5), True, False),))
        self.assertEqual(len(chains[0].pixel_ids), len(set(chains[0].pixel_ids)))

    def test_right_triangle_is_a_three_node_eight_neighbor_cycle(self):
        chains = extract_chains(grid(2, 2, (0, 1, 3)))
        self.assertEqual(chains, (Chain(0, (0, 1, 3), True, False),))
        sampling = sample_chain(chains[0], 2)
        self.assertEqual((sampling.pixel_ids, sampling.arclength), ((0, 3), 3414))

    def test_return_to_same_junction_is_a_closed_returning_trail(self):
        source = grid(3, 4, (1, 4, 6, 8, 10))
        self.assertEqual(thin_labels(source).labels, source)
        chains = extract_chains(source)
        self.assertEqual(chains, (Chain(0, (1, 4), False, False),
                                  Chain(1, (4, 6, 10, 8), True, True)))
        self.assertEqual(len(chains[1].pixel_ids), len(set(chains[1].pixel_ids)))

    def test_every_junction_edge_is_covered_once_without_joining_branches(self):
        chains = extract_chains(((0, 1), (2, 3)))
        self.assertEqual(chains, tuple(Chain(index, edge, False, False)
                                      for index, edge in enumerate(
                                          ((0, 1), (0, 2), (0, 3),
                                           (1, 2), (1, 3), (2, 3)))))

    def test_disconnected_chains_get_ids_after_global_canonical_sort(self):
        self.assertEqual(extract_chains(grid(5, 1, (0, 4))),
                         (Chain(0, (0,), False, False),
                          Chain(1, (4,), False, False)))

    def test_axial_sampling_uses_exact_1000_steps_and_open_endpoints(self):
        sampling = sample_chain(Chain(3, (0, 1, 2, 3, 4, 5, 6)), 7)
        self.assertEqual((sampling.chain_id, sampling.pixel_ids, sampling.arclength),
                         (3, (0, 2, 4, 6), 6000))

    def test_diagonal_sampling_uses_exact_1414_steps_and_first_reached_vertex(self):
        sampling = sample_chain(Chain(0, (0, 6, 12, 18, 24)), 5)
        self.assertEqual((sampling.pixel_ids, sampling.arclength),
                         ((0, 12, 18, 24), 5656))

    def test_closed_sampling_includes_closing_edge_and_deduplicates_next_first(self):
        sampling = sample_chain(Chain(0, (0, 1, 5, 7, 3), True), 3)
        self.assertEqual((sampling.pixel_ids, sampling.arclength),
                         ((0, 5, 3), 6242))

    def test_short_open_chain_and_singleton_are_never_silently_dropped(self):
        self.assertEqual(sample_chain(Chain(0, (4,)), 3).pixel_ids, (4,))
        self.assertEqual(sample_chain(Chain(0, (0, 1)), 3).pixel_ids, (0, 1))

    def test_shared_sample_is_owned_only_by_the_smallest_chain_id(self):
        prepared = prepare_template(grid(3, 4, (1, 4, 6, 8, 10)))
        ownership = {row.pixel_id: row for row in prepared.ownership}
        self.assertIn(4, ownership)
        self.assertEqual(ownership[4].owner_chain_id, 0)
        self.assertEqual(ownership[4].member_chain_ids, (0, 1))
        self.assertEqual(tuple(row.pixel_id for row in prepared.samples), (1, 4, 8, 10))
        sample = next(row for row in prepared.samples if row.pixel_id == 4)
        self.assertEqual((sample.owner_chain_id, sample.chain_index, sample.label), (0, 1, 4))
        self.assertEqual(tuple(row.pixel_ids for row in prepared.samplings),
                         ((1, 4), (4, 10, 8)))

    def test_zero_owned_chain_is_kept_as_a_zero_contribution(self):
        # Two branch junctions 14/15 are already sampled by smaller chain IDs.
        source = grid(6, 5, (0, 5, 7, 10, 14, 15, 19, 22, 24, 29))
        prepared = prepare_template(source)
        self.assertEqual(prepared.thinning.labels, source)
        self.assertEqual(prepared.chains[2], Chain(2, (14, 15), False, False))
        self.assertEqual(tuple(sample for sample in prepared.samples
                               if sample.owner_chain_id == 2), ())
        self.assertEqual(prepared.samplings[2].pixel_ids, (14, 15))
        self.assertGreater(prepared.denominator, 0)

    def test_four_by_four_cell_weights_use_exact_lcm_of_occupied_cell_counts(self):
        prepared = prepare_template((tuple(0 for _ in range(20)),))
        self.assertEqual(tuple(sample.pixel_id for sample in prepared.samples),
                         (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 19))
        self.assertEqual(prepared.cell_counts, (3, 2, 3, 3) + (0,) * 12)
        self.assertEqual((prepared.occupied_cells, prepared.lcm, prepared.denominator),
                         (4, 6, 24))
        self.assertEqual(tuple(sample.weight for sample in prepared.samples),
                         (2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2))
        self.assertEqual(sum(sample.weight for sample in prepared.samples), 24)
        self.assertEqual(tuple((sample.x, sample.y, sample.cell)
                               for sample in prepared.samples[:5]),
                         ((0, 0, 0), (2, 0, 0), (4, 0, 0), (6, 0, 1), (8, 0, 1)))

    def test_one_sample_has_one_occupied_cell_and_unit_weight(self):
        prepared = prepare_template(grid(3, 3, (4,)))
        self.assertEqual(len(prepared.samples), 1)
        sample, = prepared.samples
        self.assertEqual((sample.pixel_id, sample.x, sample.y, sample.cell, sample.weight),
                         (4, 1, 1, 0, 1))
        self.assertEqual((prepared.occupied_cells, prepared.lcm, prepared.denominator), (1, 1, 1))

    def test_whole_empty_template_is_a_contract_error(self):
        with self.assertRaisesRegex(ValueError, "no owned samples"):
            prepare_template(((255, 255),))

    def test_component_erased_by_thinning_is_not_passed_through_as_a_template(self):
        with self.assertRaisesRegex(ValueError, "no owned samples"):
            prepare_template(((0, 0), (0, 0)))

    def test_source_lists_are_snapshotted_and_results_are_frozen_tuples(self):
        source = [[0, 1, 2]]
        result = thin_labels(source)
        source[0][0] = 7
        self.assertEqual(result.eligible_labels, ((0, 1, 2),))
        self.assertEqual(result.labels, ((0, 1, 2),))
        self.assertIsInstance(result.labels, tuple)
        self.assertIsInstance(result.labels[0], tuple)
        with self.assertRaises(FrozenInstanceError):
            result.width = 9

    def test_label_grid_requires_nonempty_rectangular_list_or_tuple(self):
        for invalid in ((), [], ((),), ((0,), (0, 1)), "012", None):
            with self.subTest(grid=invalid), self.assertRaises(ValueError):
                thin_labels(invalid)
            with self.subTest(extract_grid=invalid), self.assertRaises(ValueError):
                extract_chains(invalid)

    def test_labels_require_builtin_int_zero_to_seven_or_255(self):
        for invalid in (True, False, -1, 8, 254, 256, 1.0, "1"):
            with self.subTest(label=invalid), self.assertRaises(ValueError):
                thin_labels(((invalid,),))
            with self.subTest(extract_label=invalid), self.assertRaises(ValueError):
                extract_chains(((invalid,),))

    def test_sampling_rejects_invalid_width_or_chain_metadata(self):
        for width in (True, 0, -1, 2.0, "2"):
            with self.subTest(width=width), self.assertRaises(ValueError):
                sample_chain(Chain(0, (0,)), width)
        for invalid in (Chain(True, (0,)), Chain(-1, (0,)), Chain(0, (), False),
                        Chain(0, (True,)), Chain(0, (-1,)), Chain(0, (0, 0)),
                        Chain(0, (0, 2)), Chain(0, (0, 1), 1),
                        Chain(0, (0, 1), False, True), Chain(0, (0, 1), True),
                        Chain(0, (0, 1, 4, 0), True)):
            with self.subTest(chain=invalid), self.assertRaises(ValueError):
                sample_chain(invalid, 3)


if __name__ == "__main__":
    unittest.main()
