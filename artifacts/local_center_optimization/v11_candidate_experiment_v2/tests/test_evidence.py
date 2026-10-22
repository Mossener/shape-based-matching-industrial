"""Small synthetic evidence checks; no compiler, matcher, dataset or image access."""
import copy
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from correctness_evidence import FIELDS, ROUTE_FIELDS, expected_routes, validate_rows
from dependency_pins import parse_depfile


class EvidenceContract(unittest.TestCase):
    names = ["development_" + str(i) for i in range(16)]
    counts = {"core": (2304, {"exact_v11": 512, "linear16": 1024, "direct16": 1024, "total": 2560}),
              "flags": (3124, {"exact_v11": 781, "linear16": 1562, "direct16": 1562, "total": 3905}),
              "lifetime": (76, {"exact_v11": 68, "linear16": 38, "direct16": 38, "total": 144})}

    def synthetic(self, stage):
        routes = expected_routes(stage, self.names)
        rows = [dict(zip(ROUTE_FIELDS, route), expected_count="3", actual_count="3",
                     full_ordered_equal="1", first_mismatch="") for route in routes]
        count, calls = self.counts[stage]
        matrix = {stage: dict(expected_csv_rows=count, expected_matcher_calls=calls,
                             expected_phases=dict(Counter(r[0] for r in routes)),
                             expected_variant_rows=dict(Counter(r[1] for r in routes)))}
        output = ("MATCHER_CALLS exact_v11={exact_v11} linear16={linear16} direct16={direct16} total={total}\n"
                  .format(**calls) + "PASS V2 direct16 and frozen linear16 ordered contract stage=" +
                  stage + " comparisons=" + str(count) + "\n")
        return rows, matrix, output

    def test_all_three_predeclared_counts_are_distinct_and_accepted(self):
        for stage in self.counts:
            rows, matrix, output = self.synthetic(stage)
            actual = validate_rows(rows, FIELDS, stage, self.names, matrix, output)
            self.assertEqual(actual["rows"], self.counts[stage][0])
        self.assertEqual(sum(v[0] for v in self.counts.values()), 5504)
        self.assertEqual(sum(v[1]["total"] for v in self.counts.values()), 6609)

    def test_wrong_variant_route_order_options_count_or_native_calls_fail(self):
        rows, matrix, output = self.synthetic("lifetime")
        for field, value in (("variant", "direct16_off"), ("input", "wrong"), ("threads", "4"),
                             ("flags", "63"), ("cache", "0"), ("actual_count", "2"),
                             ("full_ordered_equal", "0"), ("first_mismatch", "0"),
                             ("expected_count", "03")):
            changed = copy.deepcopy(rows)
            # Concurrent rows have one thread; every other changed value differs at row0.
            index = 28 if field == "threads" else 0
            changed[index][field] = value
            with self.assertRaises(ValueError, msg=field):
                validate_rows(changed, FIELDS, "lifetime", self.names, matrix, output)
        changed = copy.deepcopy(rows)
        changed[0], changed[1] = changed[1], changed[0]
        for invalid in (rows[:-1], rows + [rows[0]], changed):
            with self.assertRaises(ValueError):
                validate_rows(invalid, FIELDS, "lifetime", self.names, matrix, output)
        for invalid in (output.replace("exact_v11=68", "exact_v11=67"), output + output,
                        output.replace("MATCHER_CALLS", "missing")):
            with self.assertRaises(ValueError):
                validate_rows(rows, FIELDS, "lifetime", self.names, matrix, invalid)
        with self.assertRaises(ValueError):
            validate_rows(rows, list(reversed(FIELDS)), "lifetime", self.names, matrix, output)


class DependencyContract(unittest.TestCase):
    def test_alias_occurrences_and_make_escapes_are_preserved_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path(directory).resolve()
            data = b"direct_core.o: a.hpp dir/../a.hpp a.hpp \\\r\n escaped\\ name\\#x$$1.h\n"
            self.assertEqual(parse_depfile(data, "direct_core.o", cwd),
                             [cwd / "a.hpp"] * 3 + [cwd / "escaped name#x$1.h"])

    def test_wrong_target_multiple_rules_bad_escape_and_empty_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for data in (b"core.o: a.h\n", b"direct_core.o: a.h\nother.o: b.h\n",
                         b"direct_core.o: a#comment\n", b"direct_core.o: a$literal\n",
                         b"direct_core.o: a.h\\", b"direct_core.o:\n",
                         b"direct_core.o: \0\n", b"direct_core.o: \xff\n"):
                with self.assertRaises(ValueError):
                    parse_depfile(data, "direct_core.o", directory)


if __name__ == "__main__":
    unittest.main()
