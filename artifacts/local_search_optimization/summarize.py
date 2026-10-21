"""Independent validation and descriptive paired summaries for the local kernel."""
import argparse
import csv
import itertools
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

METRICS = ("search_ms", "api_total_ms", "preprocess_ms", "wall_ms")


def quantile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No output records for {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError(f"Empty or malformed CSV: {path}")
    return rows


def self_test():
    assert quantile([3, 1, 2], 0.5) == 2
    assert quantile([0, 10], 0.95) == 9.5
    assert quantile([7], 0.05) == 7
    print("PASS local benchmark summary quantiles")


def csv_smoke():
    rows = list(csv.DictReader(sys.stdin))
    assert len(rows) == 1 and len(rows[0]) == 33 and None not in rows[0]
    row = rows[0]
    assert row["wall_ms"] == "9" and row["api_total_ms"] == "8"
    assert row["preprocess_ms"] == "6" and row["search_ms"] == "7"
    assert row["matches"] == "11" and row["semantic_count"] == "12"
    assert row["semantic_hash"] == row["expected_semantic_hash"] == "aaa"
    assert row["strict_hash"] == row["expected_strict_hash"] == "bbb"
    assert row["width"] == "896" and row["threshold"] == "75"
    print("PASS local benchmark CSV: 33 fields aligned")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check-csv-layout", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.check_csv_layout:
        csv_smoke()
        return
    if args.directory is None:
        parser.error("directory required")
    folder = args.directory
    config = json.loads((folder / "config.json").read_text(encoding="utf-8-sig"))
    rows = read_csv(folder / "raw.csv")
    sanity = read_csv(folder / "float_sanity.csv")
    groups = defaultdict(list)
    for row in rows:
        groups[(row["dataset"], row["image"], row["case"], row["phase"])].append(row)
        for metric in METRICS:
            if not math.isfinite(float(row[metric])) or float(row[metric]) < 0:
                raise ValueError(f"Invalid {metric}: {row}")
    expected = set()
    for dataset, images in config["images"].items():
        expected.update(itertools.product([dataset], images, config["cases"], ["cold", "warmup", "measured"]))
    phase_counts = {"cold": config["cold"], "warmup": config["warmups"], "measured": config["repeats"]}
    summary = []
    for (dataset, image, case, phase), group in sorted(groups.items()):
        for metric in METRICS:
            values = [float(row[metric]) for row in group]
            summary.append(dict(dataset=dataset, image=image, case=case, phase=phase, metric=metric,
                                samples=len(values), median=statistics.median(values),
                                p05=quantile(values, .05), p95=quantile(values, .95)))
    write_csv(folder / "summary_by_image.csv", summary)
    rollup = defaultdict(list)
    for row in summary:
        if row["phase"] == "measured":
            rollup[(row["dataset"], row["case"], row["metric"])].append(row["median"])
    write_csv(folder / "summary_rollup.csv", [dict(dataset=d, case=c, metric=m, images=len(v),
        mean_image_median=statistics.mean(v)) for (d, c, m), v in sorted(rollup.items())])
    measured = {(r["dataset"], r["image"], r["case"], int(r["round"])): r
                for r in rows if r["phase"] == "measured"}
    if len(measured) != sum(r["phase"] == "measured" for r in rows):
        raise ValueError("Duplicate measured case/round records")
    pairs = []
    for dataset, images in config["images"].items():
        for image in images:
            for baseline, case in (("fallback", "fused"), ("v4", "fallback"), ("v4", "fused")):
                for metric in METRICS:
                    ratios, differences = [], []
                    for round_ in range(config["repeats"]):
                        before = float(measured[(dataset, image, baseline, round_)][metric])
                        after = float(measured[(dataset, image, case, round_)][metric])
                        if after <= 0:
                            raise ValueError("Cannot compute a paired speed ratio with zero duration")
                        ratios.append(before / after)
                        differences.append(after - before)
                    pairs.append(dict(dataset=dataset, image=image, baseline=baseline, case=case, metric=metric,
                        samples=len(ratios), median_ratio=statistics.median(ratios),
                        p05_ratio=quantile(ratios, .05), p95_ratio=quantile(ratios, .95),
                        median_difference_ms=statistics.median(differences)))
    write_csv(folder / "paired_speedups.csv", pairs)
    actual = set(groups)
    sanity_expected = {(dataset, image) for dataset, images in config["images"].items() for image in images}
    sanity_actual = {(r["dataset"], r["image"]) for r in sanity}
    comparisons = rows + sanity
    validation = dict(rows=len(rows), phase_groups=len(groups), expected_phase_groups=len(expected),
        missing_groups=len(expected - actual), unexpected_groups=len(actual - expected),
        incorrect_sample_counts=sum(len(group) != phase_counts[key[3]] for key, group in groups.items()),
        sanity_rows=len(sanity), missing_sanity=len(sanity_expected - sanity_actual),
        unexpected_sanity=len(sanity_actual - sanity_expected),
        duplicate_sanity=len(sanity) - len(sanity_actual),
        semantic_failures=sum(r["semantic_equal"] != "1" for r in comparisons),
        strict_set_differences=sum(r["strict_equal"] != "1" for r in comparisons),
        raw_count_differences=sum(r["count_equal"] != "1" for r in comparisons),
        hash_disagreements=sum(r["semantic_hash"] != r["expected_semantic_hash"] or
                               r["strict_hash"] != r["expected_strict_hash"] for r in rows),
        positive_match_failures=sum(int(r["matches"]) <= 0 for r in comparisons),
        quantiles="linear interpolation at (n-1)*p; descriptive quantiles, not confidence intervals",
        rollup="arithmetic mean of per-image measured medians within each dataset",
        pairing="same image and measured round; baseline/case ratio >1 means case is faster",
        wall_limit="V4 wall_ms includes adapter conversion; primary comparisons use internal api_total_ms/search_ms")
    (folder / "summary_validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))
    check_fields = ("missing_groups", "unexpected_groups", "incorrect_sample_counts", "missing_sanity",
                    "unexpected_sanity", "duplicate_sanity", "semantic_failures", "strict_set_differences",
                    "raw_count_differences", "hash_disagreements", "positive_match_failures")
    if any(validation[field] for field in check_fields):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
