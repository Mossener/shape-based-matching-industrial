"""Synthetic identity/order/timing checks; no compiler, matcher or dataset access."""
from collections import Counter
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark_contract import CASES, PHASES, TIMINGS, order, validate_samples


def synthetic():
    names = ["LED_" + str(i) for i in range(1, 9)] + ["case1"] + ["tiny_" + str(i) for i in range(16)]
    rows = []
    for image, name in enumerate(names):
        for phase, count, offset, parity in PHASES:
            for round_index in range(count):
                # Independent literal protocol expression, not order().
                rotation = (image + offset + round_index) % 5
                values = list(range(rotation, 5)) + list(range(rotation))
                if (image + round_index // 5 + parity) % 2:
                    values = list(reversed(values))
                for position, case in enumerate(values):
                    identity, variant, cache = CASES[case]
                    row = dict(image=name, image_index=str(image), width="1024", height="1024",
                               templates=str(900 if image < 8 else 361 if image == 8 else 2212),
                               threshold=str(75 if image < 8 else 90 if image == 8 else 85),
                               phase=phase, round=str(round_index), order_position=str(position),
                               case=identity, variant=variant, cache=str(cache),
                               result_count=str(image + 1), full_ordered_equal="1")
                    row.update({timing: "1" for timing in TIMINGS})
                    row.update(preprocess_ms="6", search_ms="2", total_ms="9", adapter_wall_ms="10")
                    rows.append(row)
    return rows, names


class BenchmarkContract(unittest.TestCase):
    def test_a_complete_fixed_five_case_route_is_accepted(self):
        rows, names = synthetic()
        actual = validate_samples(rows, names)
        self.assertEqual(actual["rows"], 2250)
        self.assertEqual(actual["measured_rows"], 1875)

    def test_b_changed_variant_or_cache_cannot_hide_behind_case_name(self):
        rows, names = synthetic()
        for field, value in (("variant", "direct16"), ("cache", "1")):
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            with self.assertRaises(ValueError):
                validate_samples(changed, names)

    def test_c_missing_duplicate_reordered_or_wrong_sample_identity_fails(self):
        rows, names = synthetic()
        changed = copy.deepcopy(rows)
        changed[0], changed[1] = changed[1], changed[0]
        for invalid in (rows[:-1], rows + [rows[0]], changed):
            with self.assertRaises(ValueError):
                validate_samples(invalid, names)
        for field, value in (("case", "linear16_on"), ("phase", "measured"), ("round", "14"),
                             ("order_position", "4"), ("image_index", "1"), ("image", "unknown"),
                             ("templates", "360"), ("threshold", "74"), ("full_ordered_equal", "0"),
                             ("result_count", "2"), ("width", "1000"), ("height", "0")):
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            with self.assertRaises(ValueError, msg=field):
                validate_samples(changed, names)

    def test_d_nonfinite_negative_or_inconsistent_timing_fails(self):
        rows, names = synthetic()
        for field, value in (("search_ms", "nan"), ("total_ms", "inf"), ("gradient_ms", "-1"),
                             ("total_ms", "1"), ("preprocess_ms", "1")):
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            with self.assertRaises(ValueError):
                validate_samples(changed, names)

    def test_e_each_case_occupies_each_measured_position_three_times(self):
        for image in range(25):
            observed = Counter()
            for round_index in range(15):
                route = order(image, "measured", round_index)
                self.assertEqual(sorted(route), list(range(5)))
                observed.update((case, position) for position, case in enumerate(route))
            self.assertEqual(observed, Counter({(case, position): 3
                                               for case in range(5) for position in range(5)}))


if __name__ == "__main__":
    unittest.main()
