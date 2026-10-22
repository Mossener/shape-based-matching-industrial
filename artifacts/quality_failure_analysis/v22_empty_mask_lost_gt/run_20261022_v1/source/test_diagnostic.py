"""Synthetic geometry/provenance fixtures; no dataset or matcher access."""
import itertools
import unittest

from diagnostic import Candidate, assign, classify, iou, maximum_capacity, nms_trace, size_upper


def candidate(box, score=90., template=0):
    return Candidate('test', template, 0, 0, score, tuple(box), (1, 0., 1.))


class DiagnosticTests(unittest.TestCase):
    def test_iou_half_boundary_and_invalid_box(self):
        self.assertEqual(iou((0, 0, 2, 2), (0, 0, 1, 2)), .5)
        self.assertEqual(iou((0, 0, 0, 2), (0, 0, 2, 2)), 0.)

    def test_nms_strict_boundary_and_first_blocker(self):
        # 6 / 20 == .3 is retained; a later candidate can touch two kept boxes.
        raw = [candidate((0, 0, 13, 1), 99., 0),
               candidate((7, 0, 13, 1), 98., 1),
               candidate((3, 0, 13, 1), 97., 2)]
        kept, blockers = nms_trace(raw)
        self.assertEqual(kept, [0, 1])
        self.assertEqual(blockers, {2: 0})

    def test_classify_absent_raw_candidate(self):
        truth = [{'gt_id': 0, 'box': (0, 0, 10, 10)}]
        raw = [candidate((30, 0, 10, 10))]
        kept, blockers = nms_trace(raw)
        labels = assign(raw, kept, truth)
        self.assertEqual(classify(0, truth, raw, kept, blockers, labels)['category'],
                         'no_raw_candidate_ge_0_5')

    def test_nms_suppression_is_directly_proven(self):
        truth = [{'gt_id': 0, 'box': (0, 0, 10, 10)}]
        raw = [candidate((4, 0, 10, 10), 95., 0),
               candidate((0, 0, 10, 10), 90., 1)]
        kept, blockers = nms_trace(raw)
        labels = assign(raw, kept, truth)
        detail = classify(0, truth, raw, kept, blockers, labels)
        self.assertEqual(detail['category'], 'all_overlapping_raw_suppressed_by_nms')
        self.assertEqual(detail['overlapping_raw_ranks'], [1])
        self.assertEqual(detail['blocker_raw_ranks'], [0])
        self.assertEqual(labels, [('FP', -1)])

    def test_gt_identity_competition_is_not_automatically_capacity_loss(self):
        truth = [{'gt_id': 0, 'box': (0, 0, 10, 10)},
                 {'gt_id': 1, 'box': (1, 0, 10, 10)}]
        raw = [candidate((1, 0, 10, 10))]
        kept, blockers = nms_trace(raw)
        labels = assign(raw, kept, truth)
        self.assertEqual(labels, [('TP', 1)])
        self.assertEqual(classify(0, truth, raw, kept, blockers, labels)['category'],
                         'surviving_candidate_assigned_elsewhere')
        self.assertEqual(maximum_capacity([[0, 1]], 2), 1)

    def test_detected_and_assignment_id_tiebreak(self):
        truth = [{'gt_id': 7, 'box': (0, 0, 10, 10)},
                 {'gt_id': 3, 'box': (0, 0, 10, 10)}]
        raw = [candidate((0, 0, 10, 10))]
        kept, blockers = nms_trace(raw)
        labels = assign(raw, kept, truth)
        self.assertEqual(labels, [('TP', 3)])
        self.assertEqual(classify(3, truth, raw, kept, blockers, labels)['category'], 'detected')

    def test_size_upper_is_best_continuous_translation(self):
        for w, h, u, v in itertools.product(range(1, 4), repeat=4):
            expected = max(iou((0, 0, w, h), (x, y, u, v))
                           for x, y in itertools.product(range(-4, 5), repeat=2))
            self.assertEqual(size_upper((w, h), (u, v)), expected)

    def test_capacity_exhaustive_three_by_three(self):
        for mask in range(512):
            graph = [[j for j in range(3) if mask & (1 << (3*i+j))] for i in range(3)]
            brute = max(sum(x >= 0 for x in pick)
                        for pick in itertools.product(range(-1, 3), repeat=3)
                        if len({x for x in pick if x >= 0}) == sum(x >= 0 for x in pick)
                        and all(x < 0 or x in graph[i] for i, x in enumerate(pick)))
            self.assertEqual(maximum_capacity(graph, 3), brute)


if __name__ == '__main__':
    unittest.main()
