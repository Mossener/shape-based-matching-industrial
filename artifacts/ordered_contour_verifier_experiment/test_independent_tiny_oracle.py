"""Independent mathematical checks only; no pixels, native build, or detector.

The oracle tests were written before its implementation. Execution is deferred
to the root coordinator; this file does not claim a completed red/green run.
"""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import independent_tiny_oracle as oracle
import weighted_ordered_match as core


def fixture(ids, weights, pixels, edges, *, template_closed=False,
            scene_closed=False, template_id=3, scene_id=7):
    return (core.TemplateChain(template_id, tuple(ids), tuple(weights), template_closed),
            (core.SceneChain(scene_id, tuple(pixels), tuple(edges), scene_closed),))


@contextmanager
def mutated_core(name, replacements):
    """Load an actual temporary source copy; never modify the supplied core."""
    source = Path(core.__file__).read_text(encoding="utf-8")
    for before, after in replacements:
        if source.count(before) != 1:
            raise AssertionError("mutation anchor changed: " + name)
        source = source.replace(before, after, 1)
    module_name = "_ordered_core_mutant_" + name
    with tempfile.TemporaryDirectory(prefix="ordered_core_mutant_") as temporary:
        path = Path(temporary) / (module_name + ".py")
        path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            yield module
        finally:
            sys.modules.pop(module_name, None)


def solve_with(module, template, scenes):
    """Rebuild public dataclasses for independently imported source copies."""
    converted = module.TemplateChain(template.chain_id, template.sample_ids,
                                     template.weights, template.closed)
    converted_scenes = tuple(module.SceneChain(s.chain_id, s.pixel_ids,
                                              s.edges, s.closed) for s in scenes)
    return module.solve(converted, converted_scenes)


class IndependentTinyOracleTests(unittest.TestCase):
    def checked(self, template, scenes, numerator):
        expected = oracle.brute_force(template, scenes)
        self.assertEqual(expected.numerator, numerator)
        result = core.solve(template, scenes)
        oracle.audit_result(template, scenes, result, reference=expected)
        return expected, result

    def test_cyclic_predicate_rejects_two_turns_and_reverse_order(self):
        self.assertTrue(oracle.circular_order((2, 4, 0), 5))
        self.assertTrue(oracle.circular_order((4, 0, 2), 5))
        self.assertFalse(oracle.circular_order((0, 2, 1, 3), 5))
        self.assertFalse(oracle.circular_order((0, 3, 2, 1), 5))
        self.assertFalse(oracle.circular_order((0, 1, 0), 5))

    def test_true_cell_weights_use_lcm_of_occupancies(self):
        self.assertEqual(oracle.cell_weights((0, 0, 15)), ((1, 1, 2), 4))
        self.assertEqual(oracle.cell_weights((0, 0, 0, 15, 15, 6)),
                         ((2, 2, 2, 3, 3, 6), 18))
        self.assertEqual(oracle.cell_weights(()), ((), 0))

    def test_realizable_partitions_are_bound_to_actual_bbox_cells(self):
        realized = 0
        for size in range(4):
            for partition in oracle.cell_partitions(size):
                coordinates = oracle.partition_coordinates(partition)
                if coordinates is None:
                    self.assertGreater(size, 1)
                    self.assertEqual(len(set(partition)), 1)
                    continue
                actual = oracle.bbox_cells(coordinates)
                self.assertEqual(oracle.cell_weights(actual),
                                 oracle.cell_weights(partition))
                self.assertEqual(len(set(coordinates)), size)
                realized += 1
        self.assertEqual(realized, 7)

    def test_row_and_scene_point_reuse_have_distinct_regressions(self):
        self.checked(*fixture((11,), (7,), (101, 151),
                              ((11, 101), (11, 151))), 7)
        self.checked(*fixture((11, 23), (3, 7), (101,),
                              ((11, 101), (23, 101))), 7)

    def test_closed_seams_and_fixed_template_cut_are_independent(self):
        for template_closed, scene_closed, expected_case in (
                (False, True, (7, 1, 0, 2)),
                (True, False, (7, 1, 1, 0)),
                (True, True, (7, 1, 0, 2))):
            with self.subTest(types=(template_closed, scene_closed)):
                expected, _ = self.checked(*fixture(
                    (11, 23, 47), (1, 2, 3), (101, 151, 181),
                    ((11, 181), (23, 101), (47, 151)),
                    template_closed=template_closed, scene_closed=scene_closed), 6)
                self.assertEqual(expected.case, expected_case)

    def test_reverse_and_nonmonotonic_ids_preserve_supplied_topology(self):
        expected, _ = self.checked(*fixture(
            (11, 47, 23), (2, 3, 5), (101, 181, 151),
            ((11, 151), (47, 181), (23, 101))), 10)
        self.assertEqual(expected.case, (7, -1, 0, 0))
        self.assertEqual(expected.witness, ((11, 151), (47, 181), (23, 101)))

    def test_single_lap_rejects_duplicate_physical_nodes(self):
        self.checked(*fixture((11, 23, 47, 59), (1, 1, 1, 1), (101, 151),
                              ((11, 101), (23, 151), (47, 101), (59, 151)),
                              scene_closed=True), 2)

    def test_actual_cell_weight_optimum_can_have_fewer_matches(self):
        # The first four points occupy cell 0; the fifth occupies cell 15.
        # A three-point chain has weight 3. A two-point chain has weight 5.
        weights, denominator = oracle.cell_weights((0, 0, 0, 0, 15))
        self.assertEqual((weights, denominator), ((1, 1, 1, 1, 4), 8))
        expected, _ = self.checked(*fixture(
            (11, 23, 47, 59, 71), weights, (101, 151, 181),
            ((11, 101), (23, 151), (47, 181), (71, 151))), 5)
        self.assertEqual(len(expected.witness), 2)

    def test_huge_exact_integer_optimum_distinguishes_adjacent_values(self):
        large = 2 ** 220
        expected, _ = self.checked(*fixture((11, 23), (large, large + 1),
                                            (101,), ((11, 101), (23, 101))), large + 1)
        self.assertEqual(expected.witness, ((23, 101),))

    def test_scene_choice_does_not_concatenate_chains(self):
        template = core.TemplateChain(3, (11, 23, 47), (2, 3, 5))
        scenes = (core.SceneChain(2, (101,), ((11, 101),)),
                  core.SceneChain(9, (151, 181), ((23, 151), (47, 181))))
        expected, _ = self.checked(template, scenes, 8)
        self.assertEqual(expected.case, (9, 1, 0, 0))

    def test_distinct_template_chains_can_reuse_one_scene_pixel(self):
        total = 0
        for chain_id, sample, weight in ((3, 11, 4), (4, 23, 9)):
            expected, _ = self.checked(*fixture((sample,), (weight,), (101,),
                                                ((sample, 101),), template_id=chain_id), weight)
            total += expected.numerator
        self.assertEqual(total, 13)

    def test_case_tie_precedes_colexicographic_witness_tie(self):
        template = core.TemplateChain(3, (11,), (7,))
        scenes = (core.SceneChain(9, (101,), ((11, 101),)),
                  core.SceneChain(2, (181,), ((11, 181),)))
        expected, _ = self.checked(template, scenes, 7)
        self.assertEqual((expected.case, expected.witness),
                         ((2, 1, 0, 0), ((11, 181),)))

    def test_colex_tie_uses_original_ids_and_recursive_predecessors(self):
        expected, _ = self.checked(*fixture(
            (31, 23, 11), (1, 1, 1), (181, 101),
            ((31, 181), (23, 181), (11, 101))), 2)
        self.assertEqual(expected.witness, ((23, 181), (11, 101)))

    def test_exhaustive_n_m_up_to_three_all_graphs_types_cells_and_ids(self):
        summary = oracle.run_exhaustive(core.solve, seconds=45.0)
        self.assertEqual(summary["comparisons"], 24912)
        self.assertEqual(summary["bbox_realizable_comparisons"], 19552)
        self.assertEqual(summary["abstract_membership_comparisons"], 5360)
        self.assertEqual(summary["id_profiles"], 2)
        self.assertEqual(summary["maximum_n"], 3)
        self.assertEqual(summary["maximum_m"], 3)

    def test_fixed_seed_sparse_four_to_eight_point_cases(self):
        summary = oracle.run_seeded(core.solve, seed=20261023, seconds=8.0)
        self.assertEqual(summary["comparisons"], 100)


class TargetedMutationTests(unittest.TestCase):
    def rejected(self, name, replacements, data):
        template, scenes = data
        expected = oracle.brute_force(template, scenes)
        with mutated_core(name, replacements) as mutant:
            result = solve_with(mutant, template, scenes)
            with self.assertRaises(AssertionError, msg="surviving mutant: " + name):
                oracle.audit_result(template, scenes, result, reference=expected)

    def test_immediate_template_row_updates_are_rejected(self):
        old = """        # No state from the current template row was visible to its queries.
        for index, state_index in pending:
            work.fenwick_updates += 1
            while index < len(tree):
                tree[index] = _better(tree[index], state_index, states)
                work.fenwick_update_visits += 1
                index += index & -index
"""
        immediate = """            index = rank + 1
            work.fenwick_updates += 1
            while index < len(tree):
                tree[index] = _better(tree[index], state_index, states)
                work.fenwick_update_visits += 1
                index += index & -index
"""
        self.rejected("immediate_row", ((old, ""),
                      ("            pending.append((rank + 1, state_index))\n",
                       "            pending.append((rank + 1, state_index))\n" + immediate)),
                      fixture((11,), (7,), (101, 151), ((11, 101), (11, 151))))

    def test_nonstrict_scene_prefix_is_rejected(self):
        self.rejected("nonstrict_prefix", (("            index = rank  # strict prefix:",
                                            "            index = rank + 1  # strict prefix:"),),
                      fixture((11, 23), (3, 7), (101,), ((11, 101), (23, 101))))

    def test_omitting_scene_cuts_is_rejected(self):
        self.rejected("omitted_scene_cuts", ((
            "        scene_cuts = (sorted({scene_positions[pixel] for _, pixel in scene.edges})\n"
            "                      if scene.closed else (0,))",
            "        scene_cuts = (0,)"),),
            fixture((11, 23, 47), (1, 2, 3), (101, 151, 181),
                    ((11, 181), (23, 101), (47, 151)), scene_closed=True))

    def test_omitting_template_cuts_is_rejected(self):
        self.rejected("omitted_template_cuts", ((
            "        template_cuts = (sorted({template_positions[sample] for sample, _ in scene.edges})\n"
            "                         if template.closed and not scene.closed else (0,))",
            "        template_cuts = (0,)"),),
            fixture((11, 23, 47), (1, 2, 3), (101, 151, 181),
                    ((11, 181), (23, 101), (47, 151)), template_closed=True))

    def test_float_weight_accumulation_is_rejected(self):
        self.rejected("float_weights", ((
            "            score = states[prefix].score + weights[edge[0]]",
            "            score = int(float(states[prefix].score) + float(weights[edge[0]]))"),),
            fixture((11, 23), (2 ** 220, 2 ** 220 + 1), (101,),
                    ((11, 101), (23, 101))))

    def test_sorting_witness_by_ids_instead_of_path_order_is_rejected(self):
        self.rejected("wrong_witness_order", (("    witness.reverse()",
                                               "    witness.sort()"),),
                      fixture((11, 47, 23), (1, 1, 1), (101, 181, 151),
                              ((11, 101), (47, 181), (23, 151))))


if __name__ == "__main__":
    unittest.main()
