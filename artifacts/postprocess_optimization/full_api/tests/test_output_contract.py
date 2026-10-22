"""Literal and adversarial tests, written before output_contract.py.

Pure Python only: no compiler, detector, image or source-template inputs.
"""
import copy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from output_contract import (FIXTURES, VARIANTS, audit_timing, decode_output,
                             expected_schedule, validate_schedule)


LITERAL = bytes([
    72, 77, 79, 85, 84, 48, 48, 49,
    8, 7, 6, 5, 4, 3, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0,
    255, 255, 255, 255, 2, 0, 0, 0, 253, 255, 255, 255,
    0, 0, 0, 128, 3, 0, 0, 0, 0, 0, 0, 0, 65, 0, 66])
EMPTY = b"HMOUT001" + bytes(16)


def empty_wire(call_id):
    # Test fixture writer only. The production decoder never calls this.
    return b"HMOUT001" + call_id.to_bytes(8, "little") + bytes(8)


def evidence():
    outputs = {}
    rows = []
    for item in expected_schedule():
        raw = empty_wire(item["call_id"])
        name = "outputs/call_%06d.bin" % item["call_id"]
        outputs[name] = raw
        latency = 8.0 if item["variant"] == VARIANTS[0] else 4.0
        rows.append(dict(item, output_file=name, output_bytes=len(raw),
                         output_sha256=hashlib.sha256(raw).hexdigest(), record_count=0,
                         api_wall_ms=latency, internal_search_ms=latency / 2,
                         internal_total_ms=latency * .75, has_internal_timing=True))
    return rows, outputs


class OutputContract(unittest.TestCase):
    def test_literal_signed_fields_score_bits_and_nul(self):
        item = decode_output(LITERAL, 0x0102030405060708)
        self.assertEqual(item.call_id, 0x0102030405060708)
        self.assertEqual([(x.x, x.y, x.template_id, x.score_bits, x.class_id)
                          for x in item.records], [(-1, 2, -3, 0x80000000, b"A\0B")])
        self.assertEqual(decode_output(EMPTY, 0).records, ())

    def test_rejects_every_truncated_prefix_extra_and_wrong_identity(self):
        for size in range(len(LITERAL)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                decode_output(LITERAL[:size], 0x0102030405060708)
        for bad in (LITERAL + b"\0", b"badMAGIC" + LITERAL[8:],
                    LITERAL[:16] + bytes([255]) * 8 + LITERAL[24:],
                    LITERAL[:40] + bytes([255]) * 8 + LITERAL[48:]):
            with self.assertRaises(ValueError):
                decode_output(bad, 0x0102030405060708)
        for bad_id in (False, -1, 1 << 64, 7):
            with self.assertRaises(ValueError):
                decode_output(LITERAL, bad_id)

    def test_schedule_budget_order_and_balance(self):
        rows = expected_schedule()
        self.assertEqual(len(FIXTURES), 25)
        self.assertEqual(len(rows), 950)
        self.assertEqual([x["call_id"] for x in rows], list(range(950)))
        self.assertEqual(sum(x["phase"] == "formal" for x in rows), 800)
        validate_schedule(rows)
        for fixture in FIXTURES:
            for variant in VARIANTS:
                formal = [x for x in rows if x["fixture"] == fixture and
                          x["variant"] == variant and x["phase"] == "formal"]
                self.assertEqual([sum(x["position"] == p for x in formal) for p in (0, 1)], [8, 8])
        self.assertEqual([(x["phase"], x["round"], x["variant"]) for x in rows[:8]],
                         [("cold", 0, VARIANTS[0]), ("cold", 0, VARIANTS[1]),
                          ("warm", 0, VARIANTS[1]), ("warm", 0, VARIANTS[0]),
                          ("warm", 1, VARIANTS[1]), ("warm", 1, VARIANTS[0]),
                          ("formal", 0, VARIANTS[0]), ("formal", 0, VARIANTS[1])])

    def test_schedule_rejects_missing_duplicate_reorder_or_mutated_metadata(self):
        rows = expected_schedule()
        mutations = [rows[:-1], rows + [rows[-1]], [rows[1], rows[0]] + rows[2:]]
        for field, value in (("call_id", True), ("fixture", "heldout"),
                             ("phase", "warm"), ("round", 1), ("position", 1),
                             ("variant", VARIANTS[1])):
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            mutations.append(changed)
        for changed in mutations:
            with self.assertRaises(ValueError):
                validate_schedule(changed)

    def test_audit_recomputes_every_row_and_statistics(self):
        rows, outputs = evidence()
        result = audit_timing(rows, outputs.__getitem__)
        self.assertEqual(result["calls"], 950)
        self.assertEqual(result["formal_rows"], 800)
        self.assertEqual(result["ordered_equalities"], 1900)
        self.assertEqual(result["formal_position_counts"][FIXTURES[0]][VARIANTS[0]], [8, 8])
        first = result["fixtures"][0]
        self.assertEqual(first["api_wall_ms"]["paired_ratios"], [.5] * 16)
        self.assertEqual(first["api_wall_ms"]["paired_ratio_median"], .5)
        self.assertEqual(first["api_wall_ms"][VARIANTS[0]], {"p10": 8., "p50": 8., "p90": 8.})
        self.assertEqual(result["groups"]["all25"]["api_wall_ms"],
                         {"fixtures": 25, "median": .5, "geometric_mean": .5,
                          "regression_fixtures": []})

    def test_audit_rejects_timing_types_nonfinite_and_nonpositive(self):
        rows, outputs = evidence()
        for field in ("api_wall_ms", "internal_search_ms", "internal_total_ms"):
            for bad in (float("nan"), float("inf"), -1., 0., True, "1"):
                changed = copy.deepcopy(rows)
                changed[100][field] = bad
                with self.subTest(field=field, value=bad), self.assertRaises(ValueError):
                    audit_timing(changed, outputs.__getitem__)

    def test_pairing_arithmetic_median_nearest_rank_and_regressions(self):
        rows, outputs = evidence()
        for row in rows:
            if row["fixture"] == FIXTURES[0] and row["phase"] == "formal":
                index = row["round"]
                latency = float(index + 1)
                if row["variant"] == VARIANTS[1]:
                    latency *= (16 - index) / 10
                row.update(api_wall_ms=latency, internal_search_ms=latency,
                           internal_total_ms=latency)
            if row["fixture"] == "case1" and row["variant"] == VARIANTS[1]:
                row.update(api_wall_ms=12., internal_search_ms=6., internal_total_ms=9.)
        result = audit_timing(rows, outputs.__getitem__)
        first = result["fixtures"][0]["api_wall_ms"]
        self.assertAlmostEqual(first["paired_ratio_median"], .85)
        self.assertEqual(first[VARIANTS[0]], {"p10": 2., "p50": 8., "p90": 15.})
        self.assertEqual(first["regression_rounds"], list(range(6)))
        self.assertEqual(result["groups"]["case1"]["api_wall_ms"],
                         {"fixtures": 1, "median": 1.5, "geometric_mean": 1.5,
                          "regression_fixtures": ["case1"]})

    def test_audit_rejects_record_fields_bits_order_and_multiplicity(self):
        rows, outputs = evidence()
        # All outputs share the same two records; mutate a candidate formal row.
        record = LITERAL[24:]
        second = bytearray(record)
        second[0] = 5
        changed_outputs = {}
        for row in rows:
            raw = (b"HMOUT001" + row["call_id"].to_bytes(8, "little") +
                   (2).to_bytes(8, "little") + record + second)
            changed_outputs[row["output_file"]] = raw
            row.update(output_bytes=len(raw), output_sha256=hashlib.sha256(raw).hexdigest(), record_count=2)
        audit_timing(rows, changed_outputs.__getitem__)
        target = next(row for row in rows if row["variant"] == VARIANTS[1] and row["phase"] == "formal")
        original = changed_outputs[target["output_file"]]
        for offset in (24, 28, 32, 36, 48, 49, 50):
            raw = bytearray(original)
            raw[offset] ^= 1
            self._reject_changed_archive(rows, changed_outputs, target, bytes(raw))
        swapped = original[:24] + bytes(second) + record
        self._reject_changed_archive(rows, changed_outputs, target, swapped)
        duplicate = original[:16] + (3).to_bytes(8, "little") + original[24:] + record
        self._reject_changed_archive(rows, changed_outputs, target, duplicate, 3)

    def _reject_changed_archive(self, rows, outputs, target, raw, count=2):
        changed = copy.deepcopy(rows)
        changed[target["call_id"]].update(output_bytes=len(raw),
            output_sha256=hashlib.sha256(raw).hexdigest(), record_count=count)
        archives = dict(outputs)
        archives[target["output_file"]] = raw
        with self.assertRaises(ValueError):
            audit_timing(changed, archives.__getitem__)

    def test_audit_rejects_manifest_hash_size_count_and_unsafe_paths(self):
        rows, outputs = evidence()
        for field, value in (("output_sha256", "0" * 64), ("output_bytes", 23),
                             ("record_count", 1), ("record_count", False),
                             ("has_internal_timing", False), ("output_file", "../private.bmp"),
                             ("output_file", "D:/private.bmp"), ("output_file", "outputs/../x.bin"),
                             ("output_file", "outputs/call_000001.bin")):
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit_timing(changed, outputs.__getitem__)
        changed = copy.deepcopy(rows)
        changed[0]["unexpected"] = 1
        with self.assertRaises(ValueError):
            audit_timing(changed, outputs.__getitem__)
        del outputs[rows[-1]["output_file"]]
        with self.assertRaises(ValueError):
            audit_timing(rows, outputs.__getitem__)


if __name__ == "__main__":
    unittest.main()
