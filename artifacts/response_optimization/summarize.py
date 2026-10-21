"""Summarize same-process ablations without third-party Python packages."""
import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from itertools import product
from pathlib import Path

TIMES = (
    "total_ms", "api_total_ms", "pyramid_ms", "gradient_ms", "spread_ms",
    "response_ms", "linearize_ms", "preprocess_ms", "search_ms",
)


def percentile(values, probability):
    """Linear interpolation between adjacent sorted samples (inclusive endpoints)."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def grouped_summary(rows):
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row[k] for k in ("image", "cv_threads", "mode", "case", "phase"))
        groups[key].append(row)
    result = []
    for key, samples in sorted(groups.items()):
        record = dict(zip(("image", "cv_threads", "mode", "case", "phase"), key))
        record["samples"] = len(samples)
        for field in TIMES:
            values = [float(r[field]) for r in samples if r[field] != ""]
            record[field + "_median"] = statistics.median(values) if values else ""
            record[field + "_p95"] = percentile(values, 0.95) if values else ""
        record["semantic_failures"] = sum(r["semantic_equal"] != "1" for r in samples)
        record["strict_set_differences"] = sum(r["strict_equal"] != "1" for r in samples)
        record["raw_count_differences"] = sum(r["count_equal"] != "1" for r in samples)
        result.append(record)
    return result


def rollup(summaries):
    """Give each image equal weight; do not pool unrelated image latencies."""
    groups = defaultdict(list)
    for row in summaries:
        groups[tuple(row[k] for k in ("cv_threads", "mode", "case", "phase"))].append(row)
    records = []
    for key, images in sorted(groups.items()):
        record = dict(zip(("cv_threads", "mode", "case", "phase"), key))
        record["images"] = len(images)
        for field in TIMES:
            medians = [row[field + "_median"] for row in images if row[field + "_median"] != ""]
            record[field + "_mean_image_median"] = statistics.mean(medians) if medians else ""
        records.append(record)
    return records


def paired_speedups(rows):
    groups = defaultdict(dict)
    for row in rows:
        if row["phase"] == "measured":
            key = tuple(row[k] for k in ("image", "cv_threads", "mode", "round"))
            if row["case"] in groups[key]:
                raise ValueError("Duplicate case in paired measured round")
            groups[key][row["case"]] = row
    ratios = defaultdict(list)
    for (_, threads, mode, _), cases in groups.items():
        for baseline in ("original", "all_false"):
            if baseline not in cases:
                raise ValueError("Missing paired baseline: " + baseline)
            for name, row in cases.items():
                if name == baseline:
                    continue
                for field in TIMES:
                    old, new = cases[baseline][field], row[field]
                    if old != "" and new != "" and float(old) > 0 and float(new) > 0:
                        ratios[(threads, mode, baseline, name, field)].append(float(old) / float(new))
    records = []
    for key, values in sorted(ratios.items()):
        record = dict(zip(("cv_threads", "mode", "baseline", "case", "timing"), key))
        record.update(pairs=len(values), speedup_median=statistics.median(values),
                      speedup_p05=percentile(values, 0.05), speedup_p95=percentile(values, 0.95))
        records.append(record)
    return records


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def self_test():
    assert math.isclose(percentile([1, 2, 3, 4, 5, 6, 7], 0.95), 6.7)
    assert statistics.median([7, 1, 3]) == 3
    rows = []
    for round_id in range(7):
        for case, total in (("original", 20), ("all_false", 20), ("all", 10)):
            row = {field: "" for field in TIMES}
            row.update(image="1.bmp", cv_threads="1", mode="full", case=case,
                       phase="measured", round=str(round_id), total_ms=str(total),
                       semantic_equal="1", strict_equal="1", count_equal="1")
            rows.append(row)
    summary = grouped_summary(rows)
    assert len(summary) == 3 and all(r["samples"] == 7 for r in summary)
    assert all(r["images"] == 1 for r in rollup(summary))
    paired = paired_speedups(rows)
    assert next(r for r in paired if r["baseline"] == "original" and r["case"] == "all")["speedup_median"] == 2
    print("PASS summarize self-test: grouping, p95 interpolation, equal-image rollup, paired ratios")


def check_csv_layout():
    rows = list(csv.DictReader(sys.stdin))
    assert len(rows) == 2
    for row in rows:
        assert None not in row and all(value is not None for value in row.values())
        assert row["preprocess_ms"] == "6" and row["search_ms"] == "7"
        assert row["match_count"] == "11" and row["semantic_count"] == "12"
        assert row["strict_hash"] == "def" and row["padded_width"] == "896"
        if row["case"] == "original":
            assert all(row[field] == "" for field in TIMES[1:7])
        else:
            assert [row[field] for field in TIMES[1:7]] == ["9", "1", "2", "3", "4", "5"]
    print("PASS original/current shared CSV serializer: 27 fields correctly aligned")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check-csv-layout", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.check_csv_layout:
        check_csv_layout()
        return
    if args.run_directory is None:
        parser.error("run_directory is required")
    with (args.run_directory / "raw.csv").open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Empty raw.csv")
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("Malformed CSV row length")
    summaries = grouped_summary(rows)
    write_csv(args.run_directory / "summary_by_image.csv", summaries)
    write_csv(args.run_directory / "summary_rollup.csv", rollup(summaries))
    write_csv(args.run_directory / "paired_speedups.csv", paired_speedups(rows))
    measured = [r for r in summaries if r["phase"] == "measured"]
    configuration = json.loads((args.run_directory / "config.json").read_text(encoding="utf-8-sig"))
    expected_groups = set(product(
        (str(i) + ".bmp" for i in configuration["images"]),
        (str(t) for t in configuration["opencv_threads"]),
        configuration["modes"], configuration["cases"],
    ))
    actual_groups = {tuple(r[k] for k in ("image", "cv_threads", "mode", "case")) for r in measured}
    sample_failures = 0
    for r in summaries:
        expected_samples = {"cold": 1,
                            "warmup": configuration["warmups_per_image_case_threads_mode"],
                            "measured": configuration["repeats"]}.get(r["phase"])
        sample_failures += expected_samples != r["samples"]
    validation = {
        "rows": len(rows), "measured_groups": len(measured),
        "expected_measured_groups": len(expected_groups),
        "missing_measured_groups": len(expected_groups - actual_groups),
        "unexpected_measured_groups": len(actual_groups - expected_groups),
        "incorrect_phase_sample_counts": sample_failures,
        "minimum_measured_samples": min((r["samples"] for r in measured), default=0),
        "semantic_failures": sum(r["semantic_equal"] != "1" for r in rows),
        "strict_set_differences": sum(r["strict_equal"] != "1" for r in rows),
        "raw_count_differences": sum(r["count_equal"] != "1" for r in rows),
        "p95_method": "linear interpolation at (n-1)*0.95; descriptive sample quantile",
        "rollup_method": "arithmetic mean of per-image medians; each image equal weight",
        "paired_speedup_method": "baseline/variant for the same image/thread/mode/round; median over pairs",
        "original_total_limit": "includes immutable adapter log-capture and Match-to-Result vector allocation/copy conversion overhead; see all_false contrast",
    }
    (args.run_directory / "summary_validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))
    if (validation["semantic_failures"] or validation["minimum_measured_samples"] < 7
            or validation["missing_measured_groups"] or validation["unexpected_measured_groups"]
            or validation["incorrect_phase_sample_counts"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
