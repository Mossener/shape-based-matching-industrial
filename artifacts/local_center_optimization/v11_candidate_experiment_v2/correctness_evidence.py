"""Independent expected row routes and call-count checks; no matcher/image reads."""
from collections import Counter
import csv
import re

from dependency_pins import require

FIELDS = ["phase", "variant", "input", "threads", "flags", "cache", "expected_count",
          "actual_count", "full_ordered_equal", "first_mismatch"]
ROUTE_FIELDS = FIELDS[:6]


def expected_routes(stage, development_names):
    require(len(development_names) == 16 and len(set(development_names)) == 16,
            "Exactly sixteen distinct development names required")
    names = ["LED_" + str(i) for i in range(1, 9)] + ["case1"] + development_names + [
        "LED_two_classes", "synthetic_zero_maxima", "LED_zero_mask", "LED_full_mask",
        "LED_partial_mask", "LED_empty_candidates", "LED_larger_same_detector"]
    rows = []

    def add(phase, index, threads, flags, cache, variant):
        rows.append((phase, variant, names[index], str(threads), str(flags), str(cache)))

    def pair(phase, index, threads, flags, cache):
        for variant in ("direct16", "linear16"):
            add(phase, index, threads, flags, cache, variant)

    if stage == "core":
        for threads in (1, 4, 2, 4):
            for flags in (63, 127):
                for index in range(32):
                    add("baseline_repeat", index, threads, flags, -1, "exact_v11")
                    for _ in range(2):
                        for cache in (0, 1):
                            pair("core", index, threads, flags, cache)
    elif stage == "flags":
        for flags in range(128):
            for index in (0, 27, 8, 1, 26, 31):
                for cache in (0, 1):
                    pair("flags", index, 4, flags, cache)
        for index in (28, 29, 30, 0):
            for flags in (0, 55, 127):
                for cache in (0, 1):
                    pair("mask_restore", index, 4, flags, cache)
        for cache in (0, 1):
            pair("log_flag", 0, 4, 127, cache)
    elif stage == "lifetime":
        for phase, index in (("pre_move", 0), ("move_constructed", 8),
                             ("moved_from_reused", 1), ("assignment_destination_populated", 8),
                             ("move_assigned", 0), ("assignment_source_reused", 31)):
            pair(phase, index, 4, 127, 1)
        for index in (0, 8, 1, 0):
            pair("legacy_default", index, 4, 127, 0)
            pair("explicit_default", index, 4, 127, 0)
        route = (0, 8, 1, 27, 31, 0)
        for indices in (route, tuple(reversed(route))):
            for index in indices:
                for flags in (127, 55):
                    pair("concurrent", index, 1, flags, 1)
    else:
        raise ValueError("Only core/flags/lifetime stages are accepted")
    return rows


def validate_rows(rows, fieldnames, stage, development_names, matrix, output):
    require(fieldnames == FIELDS, "Correctness CSV columns differ")
    expected = expected_routes(stage, development_names)
    spec = matrix[stage]
    require(len(expected) == spec["expected_csv_rows"] == len(rows), "CSV row count differs")
    for index, (row, route) in enumerate(zip(rows, expected)):
        require(tuple(row.get(key) for key in ROUTE_FIELDS) == route,
                "CSV ordered route differs at row " + str(index))
        require(row["full_ordered_equal"] == "1" and row["first_mismatch"] == "",
                "Matcher output mismatch declared in CSV")
        a, b = row["expected_count"], row["actual_count"]
        require(a.isdigit() and b.isdigit() and a == str(int(a)) and b == str(int(b))
                and a == b, "Output vector counts differ or are not canonical nonnegative integers")
        require(None not in row, "Unexpected CSV fields")
    phases = dict(Counter(row["phase"] for row in rows))
    variants = dict(Counter(row["variant"] for row in rows))
    require(phases == spec["expected_phases"] and variants == spec["expected_variant_rows"],
            "Phase/variant histogram differs")
    found = re.findall(r"^MATCHER_CALLS exact_v11=(\d+) linear16=(\d+) direct16=(\d+) total=(\d+)$",
                       output, re.MULTILINE)
    require(len(found) == 1, "Exactly one actual native API call-count line required")
    calls = dict(zip(("exact_v11", "linear16", "direct16", "total"), map(int, found[0])))
    require(calls == spec["expected_matcher_calls"], "Actual native matcher-call counts differ")
    require(output.count("PASS V2 direct16 and frozen linear16 ordered contract stage=" + stage +
                         " comparisons=" + str(len(rows))) == 1, "Missing unique stage PASS marker")
    return dict(rows=len(rows), phases=phases, variants=variants, actual_matcher_calls=calls,
                complete_ordered_route_equal=True, mismatches=0)


def validate_csv(path, stage, development_names, matrix, output):
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        return validate_rows(rows, reader.fieldnames, stage, development_names, matrix, output)
