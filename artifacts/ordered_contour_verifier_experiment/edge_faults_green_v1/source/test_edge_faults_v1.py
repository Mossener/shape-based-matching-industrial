"""Six semantic edge faults in real temporary copies of the supplied core.

Each fault must import and compute a result normally. Only the subsequent
independent-reference full-field comparison is inside assertRaises. Import,
mutation-anchor, and runtime errors therefore fail the test, rather than count
as detected faults. Existing source/tests and historical receipts stay intact.

Run only through the coordinator's external wall/RSS/output guard. These tiny
label fixtures give no real-image quality, pixel-provenance, or native-speed
evidence. This file is first delivered without executing it.
"""
from contextlib import contextmanager
from dataclasses import astuple, is_dataclass
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import edge_chains as core
import independent_edge_oracle as reference


def labels(width, height, pixels):
    rows = [[255] * width for _ in range(height)]
    for pixel in pixels:
        rows[pixel // width][pixel % width] = pixel % 8
    return tuple(tuple(row) for row in rows)


def full_fields(value):
    """Compare independent dataclass types by every public field recursively."""
    if is_dataclass(value):
        return astuple(value)
    if isinstance(value, (tuple, list)):
        return tuple(full_fields(item) for item in value)
    return value


@contextmanager
def temporary_fault(name, before, after):
    """Import an actual mutated source file, never patch the live core module."""
    source = Path(core.__file__).read_text(encoding="utf-8")
    if source.count(before) != 1:
        raise AssertionError("fault anchor must occur exactly once: " + name)
    source = source.replace(before, after, 1)
    module_name = "_edge_fault_v1_" + name
    with tempfile.TemporaryDirectory(prefix="edge_fault_v1_") as directory:
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


class EdgeFaultTests(unittest.TestCase):
    def rejected(self, name, before, after, operation, expected):
        # Positive control and reference are evaluated before any rejection.
        self.assertEqual(full_fields(operation(core)), full_fields(expected),
                         "baseline differs from independent reference")
        with temporary_fault(name, before, after) as faulty:
            actual = operation(faulty)  # Import/runtime failure is a test error.
            with self.assertRaises(AssertionError, msg="undetected semantic fault: " + name):
                self.assertEqual(full_fields(actual), full_fields(expected))

    def test_in_batch_deletion_changes_synchronous_rounds(self):
        # Full 3x3 has synchronous deletion rounds (6,2), then (0,0),
        # and retains only its original center label 4.
        source = ((0, 1, 2), (3, 4, 5), (6, 7, 0))
        expected = reference.reference_thinning(source)
        self.assertEqual((expected.labels, expected.round_deletions),
                         (((255, 255, 255), (255, 4, 255), (255, 255, 255)),
                          ((6, 2), (0, 0))))
        self.rejected("asynchronous_delete",
                      "            deletions.add(pixel)\n",
                      "            deletions.add(pixel)\n            active.discard(pixel)\n",
                      lambda module: module.thin_labels(source), expected)

    def test_extract_axial_only_drops_diagonal_graph_edge(self):
        # Physical 0 and 3 form one diagonal edge, not two isolated points.
        source = labels(2, 2, (0, 3))
        expected = reference.reference_chains(source)
        self.assertEqual(full_fields(expected), ((0, (0, 3), False, False),))
        self.rejected("drop_diagonal_edges",
                      "                                       if 0 <= x + dx < width and 0 <= y + dy < height\n",
                      "                                       if (dx == 0 or dy == 0)\n"
                      "                                       and 0 <= x + dx < width and 0 <= y + dy < height\n",
                      lambda module: module.extract_chains(source), expected)

    def test_cycle_walk_repeats_physical_start_pixel(self):
        # A diamond is one four-node cycle with no duplicate endpoint.
        source = labels(3, 3, (1, 3, 5, 7))
        expected = reference.reference_chains(source)
        self.assertEqual(full_fields(expected), ((0, (1, 3, 7, 5), True, False),))
        self.rejected("repeat_closed_start",
                      "    return tuple(pixels), True\n",
                      "    return tuple(pixels + [start]), True\n",
                      lambda module: module.extract_chains(source), expected)

    def test_first_reached_skips_node_exactly_on_marker(self):
        # Exact markers 2000 and 4000 must select nodes 2 and 4 themselves.
        ids = (0, 1, 2, 3, 4, 5, 6)
        expected = reference.reference_sampling(reference.Chain(3, ids), 7)
        self.assertEqual(full_fields(expected), (3, (0, 2, 4, 6), 6000))
        self.rejected("skip_exact_marker",
                      "        while position < len(cumulative) and cumulative[position] < marker:\n",
                      "        while position < len(cumulative) and cumulative[position] <= marker:\n",
                      lambda module: module.sample_chain(module.Chain(3, ids), 7), expected)

    def test_shared_sample_is_owned_by_largest_chain(self):
        # Junction 4 is sampled by chains 0 and 1, and must be owned by 0.
        source = labels(3, 4, (1, 4, 6, 8, 10))
        expected = reference.reference_template(source)
        self.assertEqual(next(row.owner_chain_id for row in expected.ownership
                              if row.pixel_id == 4), 0)
        self.rejected("largest_chain_owner",
                      "    ownership = tuple(SampleOwnership(pixel, min(memberships[pixel]),\n",
                      "    ownership = tuple(SampleOwnership(pixel, max(memberships[pixel]),\n",
                      lambda module: module.prepare_template(source), expected)

    def test_closed_sampling_omits_closing_edge_arclength(self):
        # Two axial edges plus one diagonal closing edge total 3414.
        ids = (0, 1, 3)
        expected = reference.reference_sampling(reference.Chain(0, ids, True), 2)
        self.assertEqual(full_fields(expected), (0, (0, 3), 3414))
        self.rejected("omit_closing_arclength",
                      "        total += _step(chain.pixel_ids[-1], chain.pixel_ids[0], width)\n",
                      "        total += 0\n",
                      lambda module: module.sample_chain(module.Chain(0, ids, True), 2), expected)


if __name__ == "__main__":
    unittest.main()
