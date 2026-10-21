"""V4 search-ablation summaries; reuse the previous audited numerical routines."""
import argparse
import csv
import importlib.util
import itertools
import json
import sys
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parents[1] / "response_optimization" / "summarize.py"
SPEC = importlib.util.spec_from_file_location("response_summary", BASE_PATH)
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)


def normalized(rows):
    return [dict(row, mode=row["dataset"]) for row in rows]


def renamed(records):
    return [{("dataset" if key == "mode" else key): value for key, value in row.items()}
            for row in records]


def paired(rows):
    # The existing audited routine calls its immutable reference 'original'.
    translated = [dict(row, case="original" if row["case"] == "v4" else row["case"])
                  for row in rows]
    result = BASE.paired_speedups(translated)
    for row in result:
        for field in ("case", "baseline"):
            if row[field] == "original":
                row[field] = "v4"
    return renamed(result)


def csv_smoke():
    rows = list(csv.DictReader(sys.stdin))
    assert len(rows) == 1 and len(rows[0]) == 33 and None not in rows[0]
    row = rows[0]
    assert row["total_ms"] == "9" and row["api_total_ms"] == "8"
    assert row["preprocess_ms"] == "6" and row["search_ms"] == "7"
    assert row["matches"] == "11" and row["best_score"] == "98"
    assert row["width"] == "896" and row["templates"] == "900"
    assert row["levels"] == "3" and row["threshold"] == "75"
    print("PASS V4/current CSV serializer: 33 fields aligned")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check-csv-layout", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        BASE.self_test()
        trial = normalized([dict(dataset="LED", case="v4")])[0]
        assert trial["mode"] == "LED" and renamed([trial])[0]["dataset"] == "LED"
        print("PASS search summary normalization")
        return
    if args.check_csv_layout:
        csv_smoke()
        return
    if args.directory is None:
        parser.error("directory required")
    path = args.directory
    config = json.loads((path / "config.json").read_text())
    with (path / "raw.csv").open(newline="") as stream:
        source = list(csv.DictReader(stream))
    if not source or any(None in row or any(v is None for v in row.values()) for row in source):
        raise ValueError("Empty or malformed raw.csv")
    rows = normalized(source)
    summary = BASE.grouped_summary(rows)
    BASE.write_csv(path / "summary_by_image.csv", renamed(summary))
    BASE.write_csv(path / "summary_rollup.csv", renamed(BASE.rollup(summary)))
    BASE.write_csv(path / "paired_speedups.csv", paired(rows))
    expected = set()
    for dataset, images in config["images"].items():
        expected.update(itertools.product([dataset], images, config["cases"], ["cold", "warmup", "measured"]))
    actual = {(r["mode"], r["image"], r["case"], r["phase"]) for r in summary}
    samples = {"cold": 1, "warmup": config["warmups"], "measured": config["repeats"]}
    validation = {
        "rows": len(rows), "phase_groups": len(summary), "expected_phase_groups": len(expected),
        "missing_groups": len(expected - actual), "unexpected_groups": len(actual - expected),
        "incorrect_sample_counts": sum(r["samples"] != samples[r["phase"]] for r in summary),
        "semantic_failures": sum(r["semantic_equal"] != "1" for r in rows),
        "strict_set_differences": sum(r["strict_equal"] != "1" for r in rows),
        "raw_count_differences": sum(r["count_equal"] != "1" for r in rows),
        "positive_match_failures": sum(int(r["matches"]) == 0 for r in rows),
        "p95_method": "linear interpolation at (n-1)*0.95; descriptive sample quantile",
        "rollup": "arithmetic mean of per-image medians within each dataset; do not combine LED and case1",
        "primary_search_measure": "internal search_ms excludes V4 adapter conversion and input I/O",
        "wall_limit": "V4 external total includes Match-to-Result allocation/copy conversion",
    }
    (path / "summary_validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    print(json.dumps(validation, indent=2))
    if any(validation[field] for field in ("missing_groups", "unexpected_groups", "incorrect_sample_counts",
                                          "semantic_failures", "raw_count_differences", "positive_match_failures")):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
