import csv
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = list(csv.DictReader((root / "raw.csv").open(newline="")))
assert len(rows) == 153
names = ["case1"] + [f"LED{i}" for i in range(1, 9)]
summary = {}
for name in names:
    all_rows = [r for r in rows if r["workload"] == name]
    selected = [r for r in all_rows if r["phase"] == "measured"]
    assert len(all_rows) == 17 and len(selected) == 15
    assert sorted(int(r["round"]) for r in selected) == list(range(15))
    assert all(int(r["matches"]) > 0 for r in all_rows)
    stats = {}
    for metric in ("preprocess_ms", "search_ms", "total_ms"):
        values = sorted(float(r[metric]) for r in selected)
        stats[metric] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
    summary[name] = stats
led = {}
for metric in ("preprocess_ms", "search_ms", "total_ms"):
    medians = [summary[f"LED{i}"][metric]["median"] for i in range(1, 9)]
    led[metric] = {"mean_image_median": statistics.mean(medians), "min_image_median": min(medians), "max_image_median": max(medians)}
result = {"calls": len(rows), "measured_calls": 135, "opencv_threads": 1, "openmp_threads": 4,
          "workloads": summary, "LED_rollup": led,
          "method": "15 measured calls per image; 2 warmups excluded; LED rollup is equal-weight mean and range of eight image medians"}
(root / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
with (root / "summary.csv").open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["workload", "preprocess_median_ms", "search_median_ms", "total_median_ms"])
    for name in names:
        writer.writerow([name] + [summary[name][m]["median"] for m in ("preprocess_ms", "search_ms", "total_ms")])
print(json.dumps({"case1": summary["case1"], "LED_rollup": led}, indent=2))
