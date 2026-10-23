"""Seven semantic candidate faults in actual temporary source copies.

Reference values come only from independent_candidate_oracle. The existing
test module contributes observable normalization only, never expected scores.
Baseline, independent reference, mutation anchors, import, and mutant scoring
all run outside assertRaises. Only a full observable-value mismatch can count
as a detected semantic fault; an import/runtime error fails the test instead.

Original source/tests and old evidence remain unchanged. Run only under the
coordinator's external wall/RSS/output guard. These hand-supplied tiny labels
give no image provenance, real-image quality, or native-speed evidence. This
file is first delivered without execution.
"""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import candidate_compatibility as candidate
import independent_candidate_oracle as reference
from test_independent_candidate_oracle import observable


def labels(width, height, pixels):
    """Build literal supplied labels; pixel IDs and labels are hand fixtures."""
    values = dict(pixels)
    return tuple(tuple(values.get(y * width + x, 255) for x in range(width))
                 for y in range(height))


def score(module, template_grid, scene_grid, tl=(0, 0), match=(0, 0),
          padding=(0, 0, 0, 0)):
    """Invoke the real candidate factories and scorer from the selected module."""
    return module.score_candidate(module.edge.prepare_template(template_grid),
                                  module.prepare_scene(scene_grid), tl, match,
                                  padding)


@contextmanager
def temporary_fault(name, before, after):
    """Import one changed source copy, without mutating the live module."""
    source = Path(candidate.__file__).read_text(encoding="utf-8")
    if source.count(before) != 1:
        raise AssertionError("fault anchor must occur exactly once: " + name)
    source = source.replace(before, after, 1)
    module_name = "_candidate_fault_v1_" + name
    with tempfile.TemporaryDirectory(prefix="candidate_fault_v1_") as directory:
        path = Path(directory) / (module_name + ".py")
        path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            yield module
        finally:
            sys.modules.pop(module_name, None)


class CandidateFaultTests(unittest.TestCase):
    def rejected(self, name, before, after, operation, expected):
        # These operations must finish normally before mismatch detection.
        baseline = operation(candidate)
        self.assertEqual(observable(baseline), observable(expected),
                         "baseline differs from independent reference")
        with temporary_fault(name, before, after) as faulty:
            actual = operation(faulty)
            with self.assertRaises(AssertionError,
                                   msg="undetected semantic fault: " + name):
                self.assertEqual(observable(actual), observable(expected))

    def test_outside_center_cannot_borrow_an_in_bounds_neighbor(self):
        # Center x=-1 has a valid radius-two neighbor at x=0, but is unsupported.
        template_grid = ((0,),)
        scene_grid = ((0, 255, 255),)
        expected = reference.reference_candidate(template_grid, scene_grid,
                                                  (0, 0), (-1, 0))
        self.assertEqual((expected.independent_numerator,
                          expected.ordered_numerator, expected.denominator),
                         (0, 0, 1))
        self.assertEqual(expected.outside_padded_sample_ids, (0,))
        self.rejected("rescue_outside_center",
                      "    if padded_in_bounds:\n",
                      "    if True:\n",
                      lambda module: score(module, template_grid, scene_grid,
                                           match=(-1, 0)), expected)

    def test_unsigned_labels_seven_and_zero_remain_adjacent(self):
        template_grid, scene_grid = ((0,),), ((7,),)
        expected = reference.reference_candidate(template_grid, scene_grid,
                                                  (0, 0), (0, 0))
        self.assertEqual((expected.independent_numerator,
                          expected.ordered_numerator, expected.denominator),
                         (1, 1, 1))
        self.rejected("drop_unsigned_wraparound",
                      "                if min(difference, 8 - difference) <= 1:\n",
                      "                if difference <= 1:\n",
                      lambda module: score(module, template_grid, scene_grid),
                      expected)

    def test_radius_two_corner_is_not_reduced_to_radius_one(self):
        template_grid, scene_grid = ((0,),), labels(3, 3, ((8, 0),))
        expected = reference.reference_candidate(template_grid, scene_grid,
                                                  (0, 0), (0, 0))
        self.assertEqual(expected.samples[0].compatible_pixel_ids, (8,))
        self.assertEqual(expected.ordered_numerator, 1)
        self.rejected("shrink_radius_to_one",
                      "        for neighbor_y in range(max(0, y - 2), min(height, y + 3)):\n"
                      "            for neighbor_x in range(max(0, x - 2), min(width, x + 3)):\n",
                      "        for neighbor_y in range(max(0, y - 1), min(height, y + 2)):\n"
                      "            for neighbor_x in range(max(0, x - 1), min(width, x + 2)):\n",
                      lambda module: score(module, template_grid, scene_grid),
                      expected)

    def test_owned_samples_keep_chain_order_instead_of_pixel_id_order(self):
        # One induced open V: canonical full path (0,6,12,8,4). Arc sampling
        # owns (0,12,8,4), not sorted (0,4,8,12). Labels/radius make each owned
        # point compatible only with its identical scene pixel. The unsampled
        # pixel6 has label6, but is distance3 from the other label6 sample4.
        source = labels(5, 3, ((0, 0), (6, 6), (12, 2), (8, 4), (4, 6)))
        expected = reference.reference_candidate(source, source, (0, 0), (0, 0))
        self.assertEqual((expected.independent_numerator,
                          expected.ordered_numerator, expected.denominator),
                         (4, 4, 4))
        self.assertEqual(expected.chains[0].witness,
                         ((0, 0), (12, 12), (8, 8), (4, 4)))
        self.rejected("sort_owned_by_physical_id",
                      "                             key=lambda sample: sample.chain_index))\n",
                      "                             key=lambda sample: sample.pixel_id))\n",
                      lambda module: score(module, source, source), expected)

    def test_canvas_origin_is_subtracted_once_instead_of_added(self):
        template_grid, scene_grid = ((0,),), ((0, 255, 255, 255, 255),)
        expected = reference.reference_candidate(template_grid, scene_grid,
                                                  (2, 0), (2, 0))
        self.assertEqual(expected.samples[0].relative, (-2, 0))
        self.assertEqual(expected.samples[0].q_padded, (0, 0))
        self.assertEqual(expected.ordered_numerator, 1)
        self.rejected("add_canvas_origin",
                      "    relative = tuple(_int64(position - origin, \"p_canvas-tl\")\n",
                      "    relative = tuple(_int64(position + origin, \"p_canvas-tl\")\n",
                      lambda module: score(module, template_grid, scene_grid,
                                           tl=(2, 0), match=(2, 0)), expected)

    def test_independent_witness_uses_smallest_compatible_physical_id(self):
        # Disconnected x=0/x=4 points are both within radius2 of center x=2.
        # A's witness must be0 even though both choices give the same score.
        template_grid, scene_grid = ((0,),), ((0, 255, 255, 255, 0),)
        expected = reference.reference_candidate(template_grid, scene_grid,
                                                  (0, 0), (2, 0))
        self.assertEqual(expected.samples[0].compatible_pixel_ids, (0, 4))
        self.assertEqual(expected.independent_witness, ((0, 0),))
        self.rejected("largest_independent_witness",
                      "                         compatible, compatible[0] if compatible else None)\n",
                      "                         compatible, compatible[-1] if compatible else None)\n",
                      lambda module: score(module, template_grid, scene_grid,
                                           match=(2, 0)), expected)

    def test_float_cross_products_cannot_accept_one_integer_below_threshold(self):
        # All points are real factory input, isolated on a spacing-three grid.
        # The bbox is exactly (0,0)..(159,159), so its 4x4 cells have side40.
        # Ten pairwise-coprime occupancies make L=24,292,717,665,935,660;
        # six additional singleton cells are fully supported. The hand-listed
        # scene subset has A=B=13*D/20-1. No evidence/weights are forged.
        counts = (20, 31, 37, 41, 43, 47, 53, 59, 61, 67, 1, 1, 1, 1, 1, 1)
        supported = (1, 6, 14, 27, 13, 8, 51, 24, 47, 34, 1, 1, 1, 1, 1, 1)
        template_pixels, scene_pixels = [], []
        for cell, (count, keep) in enumerate(zip(counts, supported)):
            row, column = divmod(cell, 4)
            positions = tuple((x, y) for y in range(0, 160, 3)
                              for x in range(0, 160, 3)
                              if x // 40 == column and y // 40 == row)
            # Preserve the maximum bbox coordinate even in a singleton cell.
            selected = ((159, 159),) if cell == 15 else positions[:count]
            self.assertEqual(len(selected), count)
            template_pixels.extend((y * 160 + x, 0) for x, y in selected)
            scene_pixels.extend((y * 160 + x, 0) for x, y in selected[:keep])
        self.assertEqual((len(template_pixels), len(scene_pixels)), (465, 231))
        template_grid = labels(160, 160, template_pixels)
        scene_grid = labels(160, 160, scene_pixels)
        expected = reference.reference_candidate(template_grid, scene_grid,
                                                  (0, 0), (0, 0))
        self.assertEqual((expected.independent_numerator,
                          expected.ordered_numerator, expected.denominator),
                         (252644263725730863, 252644263725730863,
                          388683482654970560))
        self.assertEqual(20 * expected.ordered_numerator -
                         13 * expected.denominator, -20)
        self.assertEqual((expected.independent_accepted, expected.ordered_accepted),
                         (False, False))
        # Both float products round to the same finite binary64 value, so the
        # mutant returns normally but incorrectly accepts this exact deficit.
        self.rejected("float_threshold_cross_products",
                      "    return 20 * numerator >= 13 * denominator\n",
                      "    return 20.0 * numerator >= 13.0 * denominator\n",
                      lambda module: score(module, template_grid, scene_grid),
                      expected)


if __name__ == "__main__":
    unittest.main()
