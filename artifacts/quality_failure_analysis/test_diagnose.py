"""Diagnostic contracts: catch greedy matching and boundary/category mistakes."""
import itertools
import unittest
from diagnose import iou, maximum_pairs, analyze_frame


class DiagnosticContracts(unittest.TestCase):
    def test_augmenting_path_recovers_target_that_greedy_consumes(self):
        self.assertEqual(len(maximum_pairs([[0, 1], [0]], 2)), 2)

    def test_all_three_by_three_graphs_against_exhaustive_injections(self):
        # Independent enumeration of every partial injective assignment.
        for bits in range(512):
            graph = [[g for g in range(3) if bits & (1 << (p*3+g))]
                     for p in range(3)]
            best = 0
            for assignment in itertools.product((-1, 0, 1, 2), repeat=3):
                used = [g for g in assignment if g >= 0]
                if len(used) == len(set(used)) and all(
                    g < 0 or g in graph[p] for p, g in enumerate(assignment)):
                    best = max(best, len(used))
            pairs = maximum_pairs(graph, 3)
            self.assertEqual(len(pairs), best, (bits, graph))
            self.assertEqual(len({p for p, _ in pairs}), len(pairs))
            self.assertEqual(len({g for _, g in pairs}), len(pairs))
            self.assertTrue(all(g in graph[p] for p, g in pairs))

    def test_iou_half_is_inclusive_and_touching_is_zero(self):
        self.assertEqual(iou((0, 0, 10, 10), (0, 0, 20, 10)), .5)
        self.assertEqual(iou((0, 0, 10, 10), (10, 0, 10, 10)), 0)
        self.assertEqual(iou((0, 0, 0, 10), (0, 0, 10, 10)), 0)

    def test_three_capacity_terms_partition_false_negatives(self):
        # GT0 only raw, GT1 absent entirely, GT2 retained. No pixel claim.
        targets = [(0, 0, 10, 10), (50, 0, 10, 10), (100, 0, 10, 10)]
        raw = [targets[0], targets[2]]
        kept = [dict(box=targets[2], label='TP')]
        got = analyze_frame(raw, kept, targets, [])
        self.assertEqual((got['raw_capacity'], got['selected_capacity'],
                          got['actual_tp']), (2, 1, 1))
        self.assertEqual((got['raw_capacity_deficit'],
                          got['selected_capacity_loss'],
                          got['assignment_capacity_loss']), (1, 1, 0))
        self.assertEqual(got['gt_without_raw_overlap'], 1)

    def test_fp_associations_are_exclusive_with_target_priority(self):
        target = (0, 0, 10, 10)
        other = (40, 0, 10, 10)
        boxes = [target, other, (8, 0, 10, 10),
                 (48, 0, 10, 10), (100, 0, 10, 10)]
        got = analyze_frame(boxes, [dict(box=b, label='FP') for b in boxes],
                            [target], [target, other])
        self.assertEqual(got['fp_associations'], dict(
            target_ge_0_5=1, other_ge_0_5=1, target_ge_0_1=1,
            other_ge_0_1=1, no_overlap_ge_0_1=1))

    def test_impossible_tp_count_and_non_subset_are_rejected(self):
        box = (0, 0, 10, 10)
        with self.assertRaises(ValueError):
            analyze_frame([], [dict(box=box, label='FP')], [], [])
        with self.assertRaises(ValueError):
            analyze_frame([box], [dict(box=box, label='TP')], [], [])

    def test_fp_cannot_lend_geometric_capacity_to_invalid_tp_labels(self):
        a, b = (0, 0, 10, 10), (50, 0, 10, 10)
        # Total pool has capacity2, but the two labelled TPs share only GT0.
        with self.assertRaises(ValueError):
            analyze_frame([a, a, b], [dict(box=a, label='TP'),
                dict(box=a, label='TP'), dict(box=b, label='FP')], [a, b], [])


if __name__ == '__main__':
    unittest.main()
