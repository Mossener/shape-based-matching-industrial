"""Independent complete-output decoder and fixed whole-API timing auditor.

This module imports no native library, reads no file at import and never opens
an image. Native harness comparison booleans are deliberately not accepted as
equality evidence. The caller supplies exact archive bytes from its allowlist.
"""
from dataclasses import dataclass
import hashlib
import math
import re
import statistics
import struct


FIXTURES = tuple(["LED_%d" % i for i in range(1, 9)] + ["case1"] +
                 ["tiny_s5_i%d" % i for i in (7, 70, 127, 215, 293, 353, 436, 493)] +
                 ["tiny_s2_i%d" % i for i in (3, 92, 153, 214, 295, 374, 446, 494)])
VARIANTS = ("exact_v11", "index_reserve_copy_actual_match")
CLOCKS = ("api_wall_ms", "internal_search_ms", "internal_total_ms")
SCHEDULE_FIELDS = ("call_id", "fixture", "phase", "round", "position", "variant")
ROW_FIELDS = set(SCHEDULE_FIELDS) | {
    "output_file", "output_bytes", "output_sha256", "record_count",
    "has_internal_timing", *CLOCKS}


def require(value, message):
    if not value:
        raise ValueError(message)


def uint(value, bits, name):
    require(type(value) is int and 0 <= value < (1 << bits), name + " must be uint%d" % bits)


@dataclass(frozen=True)
class Record:
    x: int
    y: int
    template_id: int
    score_bits: int
    class_id: bytes


@dataclass(frozen=True)
class Archive:
    call_id: int
    records: tuple


def decode_output(data, expected_call_id):
    """Decode every byte; class identifiers remain arbitrary length-delimited bytes."""
    uint(expected_call_id, 64, "expected call id")
    require(type(data) is bytes and len(data) >= 24, "Truncated output header or non-bytes input")
    require(data[:8] == b"HMOUT001", "Unexpected output magic")
    call_id, count = struct.unpack_from("<QQ", data, 8)
    require(call_id == expected_call_id, "Output call id differs")
    require(count <= (len(data) - 24) // 24, "Output count exceeds remaining minimum record bytes")
    records = []
    offset = 24
    for _ in range(count):
        require(len(data) - offset >= 24, "Truncated fixed record fields")
        x, y, template_id, score_bits, length = struct.unpack_from("<iiiIQ", data, offset)
        offset += 24
        require(length <= len(data) - offset, "Truncated class bytes")
        name = data[offset:offset + length]
        offset += length
        records.append(Record(x, y, template_id, score_bits, name))
    require(offset == len(data), "Trailing output bytes")
    return Archive(call_id, tuple(records))


def expected_schedule():
    rows = []
    for fixture_index, fixture in enumerate(FIXTURES):
        for phase, rounds, phase_offset in (("cold", 1, 0), ("warm", 2, 1), ("formal", 16, 3)):
            for round_index in range(rounds):
                k = fixture_index + round_index + phase_offset
                order = list(VARIANTS)
                order = order[k % 2:] + order[:k % 2]
                if (k // 2) % 2:
                    order.reverse()
                for position, variant in enumerate(order):
                    rows.append(dict(call_id=len(rows), fixture=fixture, phase=phase,
                                     round=round_index, position=position, variant=variant))
    return rows


def validate_schedule(rows):
    require(type(rows) is list, "Ordered timing rows must be a list")
    expected = expected_schedule()
    require(len(rows) == len(expected) == 950, "Timing call budget differs")
    for row, wanted in zip(rows, expected):
        require(type(row) is dict, "Timing row must be a dictionary")
        for field in SCHEDULE_FIELDS:
            require(field in row and type(row[field]) is type(wanted[field]) and
                    row[field] == wanted[field], "Ordered timing schedule differs: " + field)
    return expected


def quantiles(values):
    ordered = sorted(values)
    require(len(ordered) == 16, "Exactly sixteen formal latency values required")
    return {name: ordered[math.ceil(q * len(ordered)) - 1]
            for name, q in (("p10", .1), ("p50", .5), ("p90", .9))}


def audit_timing(rows, read_output):
    """Repeat every ordered equality and statistic from raw complete archives.

    read_output receives only canonical names outputs/call_NNNNNN.bin. It must
    enforce its own filesystem containment/regular-file rules, if it uses disk.
    Full timing clocks must be positive to support ratios; zero is not accepted
    as a speedup or silently removed. Correctness-only clocks use another stage.
    """
    validate_schedule(rows)
    decoded = {}
    by_route = {}
    for row in rows:
        require(set(row) == ROW_FIELDS, "Unexpected/missing timing row fields")
        call_id = row["call_id"]
        expected_name = "outputs/call_%06d.bin" % call_id
        require(row["output_file"] == expected_name, "Noncanonical output archive path")
        uint(row["output_bytes"], 64, "output bytes")
        uint(row["record_count"], 64, "record count")
        require(type(row["output_sha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", row["output_sha256"]) is not None,
                "Canonical SHA256 required")
        require(row["has_internal_timing"] is True, "Timed flagged call must retain internal clocks")
        for clock in CLOCKS:
            value = row[clock]
            require(type(value) in (int, float) and math.isfinite(value) and value > 0,
                    "Invalid full timing clock: " + clock)
        try:
            data = read_output(expected_name)
        except (OSError, KeyError) as error:
            raise ValueError("Missing/unreadable output archive: " + expected_name) from error
        require(type(data) is bytes and len(data) == row["output_bytes"], "Output byte length differs")
        require(hashlib.sha256(data).hexdigest() == row["output_sha256"], "Output SHA256 differs")
        archive = decode_output(data, call_id)
        require(len(archive.records) == row["record_count"], "Decoded output count differs")
        decoded[call_id] = archive.records
        by_route[(row["fixture"], row["phase"], row["round"], row["variant"])] = row
    equalities = 0
    for row in rows:
        cold = by_route[(row["fixture"], "cold", 0, VARIANTS[0])]
        pair = by_route[(row["fixture"], row["phase"], row["round"], VARIANTS[0])]
        require(decoded[row["call_id"]] == decoded[cold["call_id"]],
                "Full output differs from baseline cold oracle at call %d" % row["call_id"])
        equalities += 1
        require(decoded[row["call_id"]] == decoded[pair["call_id"]],
                "Full output differs from same-round baseline at call %d" % row["call_id"])
        equalities += 1
    fixtures = []
    positions = {}
    for fixture in FIXTURES:
        summary = {"fixture": fixture}
        positions[fixture] = {}
        for variant in VARIANTS:
            formal = [by_route[(fixture, "formal", index, variant)] for index in range(16)]
            counts = [sum(row["position"] == position for row in formal) for position in (0, 1)]
            require(counts == [8, 8], "Formal variant positions unbalanced")
            positions[fixture][variant] = counts
        for clock in CLOCKS:
            baseline = [by_route[(fixture, "formal", i, VARIANTS[0])][clock] for i in range(16)]
            candidate = [by_route[(fixture, "formal", i, VARIANTS[1])][clock] for i in range(16)]
            ratios = [candidate[i] / baseline[i] for i in range(16)]
            require(all(math.isfinite(value) and value > 0 for value in ratios), "Invalid paired ratio")
            summary[clock] = {
                VARIANTS[0]: quantiles(baseline), VARIANTS[1]: quantiles(candidate),
                "paired_ratios": ratios, "paired_ratio_median": statistics.median(ratios),
                "regression_rounds": [i for i, value in enumerate(ratios) if value > 1]}
        fixtures.append(summary)
    groups = {}
    for name, selected in (("LED", fixtures[:8]), ("case1", fixtures[8:9]),
                           ("tiny", fixtures[9:]), ("all25", fixtures)):
        groups[name] = {}
        for clock in CLOCKS:
            values = [item[clock]["paired_ratio_median"] for item in selected]
            groups[name][clock] = {
                "fixtures": len(values), "median": statistics.median(values),
                "geometric_mean": math.exp(math.fsum(math.log(value) for value in values) / len(values)),
                "regression_fixtures": [item["fixture"] for item in selected
                                        if item[clock]["paired_ratio_median"] > 1]}
    return dict(calls=len(rows), formal_rows=800, ordered_equalities=equalities,
                formal_position_counts=positions, fixtures=fixtures, groups=groups,
                definitions={"paired_median": "arithmetic mean of middle two sorted ratios",
                             "latency_quantiles": "nearest rank ceil(q*N), 1-based",
                             "ratio": "candidate/baseline; less than one is faster",
                             "aggregate": "equal-fixture summary of per-fixture paired medians"})
