"""Independent supplied-label checks, first written against a fixed-empty stub.

No test/image/native/Git execution belongs to this source-writing stage. Root
coordinates the real RED run before the reference is implemented. The finite
suite must run inside an external 60s / 512-MiB RSS / 64-MiB output guard.
"""
from collections import Counter
from dataclasses import astuple
from fractions import Fraction
from itertools import combinations
import random
from time import monotonic
import unittest

import edge_chains as core
import independent_edge_oracle as reference


def labeled_grid(width, height, pixels):
    rows = [[255] * width for _ in range(height)]
    for pixel in pixels:
        rows[pixel // width][pixel % width] = pixel % 8
    return tuple(tuple(row) for row in rows)


def chain_rows(chains):
    return tuple(astuple(chain) for chain in chains)


class IndependentEdgeOracleTests(unittest.TestCase):
    def test_thinning_literal_requires_two_synchronous_subiterations(self):
        source = ((0, 1, 2), (3, 4, 5), (6, 7, 0))
        got = reference.reference_thinning(source)
        self.assertEqual((got.width, got.height, got.eligible_labels), (3, 3, source))
        self.assertEqual(got.labels, ((255, 255, 255), (255, 4, 255), (255, 255, 255)))
        self.assertEqual(got.round_deletions, ((6, 2), (0, 0)))

    def test_thinning_literal_preserves_original_direction_labels(self):
        source = ((0, 7, 1, 6, 2, 5, 3),)
        got = reference.reference_thinning(source)
        self.assertEqual((got.labels, got.eligible_labels, got.round_deletions),
                         (source, source, ((0, 0),)))

    def test_two_by_two_block_is_erased_in_first_subiteration(self):
        got = reference.reference_thinning(((0, 1), (2, 3)))
        self.assertEqual(got.labels, ((255, 255), (255, 255)))
        self.assertEqual(got.round_deletions, ((4, 0), (0, 0)))

    def test_literal_singleton_and_diagonal_are_retained_as_open_chains(self):
        self.assertEqual(chain_rows(reference.reference_chains(labeled_grid(3, 3, (4,)))),
                         ((0, (4,), False, False),))
        self.assertEqual(chain_rows(reference.reference_chains(labeled_grid(2, 2, (0, 3)))),
                         ((0, (0, 3), False, False),))

    def test_raw_two_by_two_graph_covers_each_junction_edge_once(self):
        got = reference.reference_chains(((0, 1), (2, 3)))
        self.assertEqual(chain_rows(got), tuple(
            (i, edge, False, False) for i, edge in enumerate(
                ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)))))

    def test_literal_pure_cycle_has_dihedral_canonical_order(self):
        got = reference.reference_chains(labeled_grid(3, 3, (1, 3, 5, 7)))
        self.assertEqual(chain_rows(got), ((0, (1, 3, 7, 5), True, False),))

    def test_literal_returning_cycle_keeps_one_junction_without_repetition(self):
        got = reference.reference_chains(labeled_grid(3, 4, (1, 4, 6, 8, 10)))
        self.assertEqual(chain_rows(got), ((0, (1, 4), False, False),
                                           (1, (4, 6, 10, 8), True, True)))

    def test_sampling_literals_cover_axis_diagonal_and_closing_marker(self):
        cases = (
            (reference.Chain(3, (0, 1, 2, 3, 4, 5, 6)), 7, (3, (0, 2, 4, 6), 6000)),
            (reference.Chain(0, (0, 6, 12, 18, 24)), 5, (0, (0, 12, 18, 24), 5656)),
            (reference.Chain(0, (0, 1, 5, 7, 3), True), 3, (0, (0, 5, 3), 6242)),
            (reference.Chain(0, (0, 1, 3), True), 2, (0, (0, 3), 3414)),
            (reference.Chain(2, (4,)), 3, (2, (4,), 0)),
        )
        for chain, width, want in cases:
            with self.subTest(chain=chain):
                self.assertEqual(astuple(reference.reference_sampling(chain, width)), want)

    def test_literal_ownership_uses_lowest_chain_id_and_original_chain_index(self):
        got = reference.reference_template(labeled_grid(3, 4, (1, 4, 6, 8, 10)))
        self.assertEqual(chain_rows(got.samplings), ((0, (1, 4), 1000),
                                                   (1, (4, 10, 8), 5656)))
        self.assertEqual(chain_rows(got.ownership), ((1, 0, (0,)), (4, 0, (0, 1)),
                                                   (8, 1, (1,)), (10, 1, (1,))))
        self.assertEqual(chain_rows(got.samples), (
            (1, 0, 0, 1, 0, 1, 0, 1), (4, 0, 1, 1, 1, 4, 4, 1),
            (8, 1, 3, 2, 2, 0, 10, 1), (10, 1, 2, 1, 3, 2, 12, 1)))
        self.assertEqual((got.occupied_cells, got.lcm, got.denominator), (4, 1, 4))

    def test_literal_unequal_cell_occupancies_have_exact_integer_weights(self):
        got = reference.reference_template((tuple(0 for _ in range(20)),))
        self.assertEqual(tuple(sample.pixel_id for sample in got.samples),
                         (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 19))
        self.assertEqual(got.cell_counts, (3, 2, 3, 3) + (0,) * 12)
        self.assertEqual((got.occupied_cells, got.lcm, got.denominator), (4, 6, 24))
        self.assertEqual(tuple(sample.weight for sample in got.samples),
                         (2, 2, 2, 3, 3, 2, 2, 2, 2, 2, 2))

    def test_fractional_cell_mass_is_computed_before_integer_scaling(self):
        self.assertEqual(reference.fractional_weights((0, 0, 15)),
                         (Fraction(1, 4), Fraction(1, 4), Fraction(1, 2)))
        self.assertEqual(reference.fractional_weights((0, 0, 0, 1, 1, 2, 2, 2, 3, 3, 3)),
                         (Fraction(1, 12),) * 3 + (Fraction(1, 8),) * 2
                         + (Fraction(1, 12),) * 6)
        self.assertEqual(reference.fractional_weights(()), ())

    def test_empty_and_erased_templates_are_contract_errors(self):
        for source in (((255, 255),), ((0, 0), (0, 0))):
            with self.subTest(source=source), self.assertRaises(ValueError):
                reference.reference_template(source)

    def assert_graph_partition(self, source, chains):
        """Audit edge coverage/maximality directly from all coordinate pairs."""
        width = len(source[0])
        nodes = tuple(y * width + x for y, row in enumerate(source)
                      for x, label in enumerate(row) if label != 255)
        expected = set()
        for left, right in combinations(nodes, 2):
            if max(abs(left % width - right % width),
                   abs(left // width - right // width)) == 1:
                expected.add((left, right))
        degrees = Counter(node for edge in expected for node in edge)
        observed, represented = Counter(), set()
        for index, chain in enumerate(chains):
            self.assertEqual(chain.chain_id, index)
            ids = chain.pixel_ids
            self.assertTrue(ids)
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(set(ids) <= set(nodes))
            represented.update(ids)
            pairs = list(zip(ids, ids[1:]))
            if chain.closed:
                self.assertGreaterEqual(len(ids), 3)
                pairs.append((ids[-1], ids[0]))
                junctions = sum(degrees[pixel] != 2 for pixel in ids)
                self.assertEqual(junctions, 1 if chain.returning else 0)
                alternatives = tuple(ids[k:] + ids[:k] for k in range(len(ids)))
                reversed_ids = ids[::-1]
                alternatives += tuple(reversed_ids[k:] + reversed_ids[:k] for k in range(len(ids)))
                self.assertEqual(ids, min(alternatives))
            elif len(ids) == 1:
                self.assertEqual(degrees[ids[0]], 0)
                self.assertFalse(chain.returning)
            else:
                self.assertFalse(chain.returning)
                self.assertEqual(ids, min(ids, ids[::-1]))
                self.assertTrue(all(degrees[pixel] == 2 for pixel in ids[1:-1]))
                self.assertNotEqual(degrees[ids[0]], 2)
                self.assertNotEqual(degrees[ids[-1]], 2)
            observed.update(tuple(sorted(edge)) for edge in pairs)
        self.assertEqual(represented, set(nodes))
        self.assertEqual(observed, Counter({edge: 1 for edge in expected}))
        self.assertEqual(tuple((chain.pixel_ids, chain.closed) for chain in chains),
                         tuple(sorted((chain.pixel_ids, chain.closed) for chain in chains)))

    def assert_complete_grid(self, source):
        width, height = len(source[0]), len(source)
        expected_thin = reference.reference_thinning(source)
        # These boundary assertions reject shared fixed-empty stubs as well as
        # disagreement. Expected dimensions/eligible labels come from input.
        self.assertEqual((expected_thin.width, expected_thin.height), (width, height))
        self.assertEqual(expected_thin.eligible_labels, source)
        self.assertEqual(astuple(core.thin_labels(source)), astuple(expected_thin))
        self.assertTrue(expected_thin.round_deletions)
        self.assertEqual(expected_thin.round_deletions[-1], (0, 0))
        before = sum(label != 255 for row in source for label in row)
        after = sum(label != 255 for row in expected_thin.labels for label in row)
        self.assertEqual(sum(sum(pair) for pair in expected_thin.round_deletions), before - after)
        for y, row in enumerate(expected_thin.labels):
            for x, label in enumerate(row):
                self.assertTrue(label == 255 or label == source[y][x])
        for grid in (source, expected_thin.labels):
            expected_chains = reference.reference_chains(grid)
            self.assert_graph_partition(grid, expected_chains)
            self.assertEqual(chain_rows(core.extract_chains(grid)), chain_rows(expected_chains))
            for chain in expected_chains:
                expected_sampling = reference.reference_sampling(chain, width)
                copied = core.Chain(chain.chain_id, chain.pixel_ids, chain.closed, chain.returning)
                self.assertEqual(astuple(core.sample_chain(copied, width)), astuple(expected_sampling))
        if not after:
            with self.assertRaises(ValueError):
                reference.reference_template(source)
            with self.assertRaises(ValueError):
                core.prepare_template(source)
            return
        prepared = reference.reference_template(source)
        self.assertTrue(prepared.samples)
        self.assertEqual(astuple(prepared.thinning), astuple(expected_thin))
        self.assertEqual(astuple(core.prepare_template(source)), astuple(prepared))
        cells = tuple(sample.cell for sample in prepared.samples)
        masses = reference.fractional_weights(cells)
        self.assertEqual(len(masses), len(prepared.samples))
        self.assertEqual(sum(masses), Fraction(1))
        self.assertEqual(tuple(Fraction(sample.weight, prepared.denominator)
                               for sample in prepared.samples), masses)
        self.assertEqual(sum(sample.weight for sample in prepared.samples), prepared.denominator)
        self.assertEqual(prepared.cell_counts, tuple(cells.count(cell) for cell in range(16)))
        self.assertEqual(prepared.occupied_cells, len(set(cells)))
        for cell in set(cells):
            self.assertEqual(sum(mass for sample, mass in zip(prepared.samples, masses)
                                 if sample.cell == cell), Fraction(1, prepared.occupied_cells))

    def test_exhaustive_all_512_three_by_three_bitmaps(self):
        start, comparisons = monotonic(), 0
        for mask in range(512):
            if monotonic() - start > 45:
                self.fail("exhaustive wall budget exceeded; incomplete")
            source = tuple(tuple((mask + 3 * (3 * y + x)) % 8
                                 if mask & (1 << (3 * y + x)) else 255
                                 for x in range(3)) for y in range(3))
            with self.subTest(mask=mask):
                self.assert_complete_grid(source)
            comparisons += 1
        self.assertEqual(comparisons, 512)

    def test_fixed_seed_100_multilabel_four_and_five_by_five_cases(self):
        rng, start, comparisons = random.Random(20261023), monotonic(), 0
        for index in range(100):
            if monotonic() - start > 8:
                self.fail("seeded wall budget exceeded; incomplete")
            size = 4 + index % 2
            source = tuple(tuple(rng.randrange(8) if rng.randrange(2) else 255
                                 for _ in range(size)) for _ in range(size))
            with self.subTest(seed=20261023, index=index, size=size):
                self.assert_complete_grid(source)
            comparisons += 1
        self.assertEqual(comparisons, 100)


if __name__ == "__main__":
    unittest.main()
