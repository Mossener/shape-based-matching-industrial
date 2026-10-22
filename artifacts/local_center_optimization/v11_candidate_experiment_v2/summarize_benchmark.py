"""Pure five-case row summary plus optional local evidence receipt checks."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from benchmark_contract import CASES, FIELDS, TIMINGS, validate_samples
from benchmark_statistics import describe, paired_stats

PAIRS = (("direct16_on", "direct16_off"), ("linear16_on", "linear16_off"),
         ("direct16_on", "linear16_on"), ("direct16_off", "linear16_off"),
         ("linear16_off", "exact_v11"), ("direct16_off", "exact_v11"))
RATIO_METRICS = ("preprocess_ms", "search_ms", "total_ms", "adapter_wall_ms")


def summarize_rows(rows, image_names):
    validation = validate_samples(rows, image_names)
    measured = {(row["image"], int(row["round"]), row["case"]): row
                for row in rows if row["phase"] == "measured"}
    if len(measured) != 1875:
        raise ValueError("Measured pairing keys must be unique and complete")
    groups = {"LED": image_names[:8], "case1": image_names[8:9], "tiny": image_names[9:]}
    ratios, absolute = {}, {}
    for metric in RATIO_METRICS:
        ratios[metric] = {}
        for numerator, denominator in PAIRS:
            per_image = {}
            for name in image_names:
                a = [float(measured[name, round_index, numerator][metric]) for round_index in range(15)]
                b = [float(measured[name, round_index, denominator][metric]) for round_index in range(15)]
                per_image[name] = paired_stats(a, b)
            medians = [per_image[name]["median"] for name in image_names]
            pooled = [value for name in image_names for value in per_image[name]["ratios"]]
            key = numerator + "__over__" + denominator
            ratios[metric][key] = dict(numerator=numerator, denominator=denominator, per_image=per_image,
                equal_weight_image_medians=describe(medians), pooled_round_ratios=describe(pooled),
                groups={group: describe([per_image[name]["median"] for name in names])
                        for group, names in groups.items()},
                regressions=[dict(image=name, median_ratio=per_image[name]["median"])
                             for name in image_names if per_image[name]["median"] > 1],
                all_images_by_descending_ratio=sorted(
                    [dict(image=name, median_ratio=per_image[name]["median"]) for name in image_names],
                    key=lambda item: (-item["median_ratio"], item["image"])))
    for metric in TIMINGS:
        absolute[metric] = {}
        for identity, _, _ in CASES:
            per_image = {name: describe([float(measured[name, index, identity][metric]) for index in range(15)])
                         for name in image_names}
            absolute[metric][identity] = dict(per_image=per_image,
                equal_weight_image_medians=describe([per_image[name]["median"] for name in image_names]),
                pooled_round_observations=describe([float(measured[name, index, identity][metric])
                                                   for name in image_names for index in range(15)]))
    return dict(validation=validation, image_names=image_names, measured_rounds=15,
                ratio_definition="median of fifteen same-image/same-round numerator/denominator ratios; "
                    "equal-weight aggregation uses one paired median per image; never ratio of absolute medians",
                quantiles="descriptive linear interpolation at p*(n-1); no confidence/significance claim",
                zero_policy="A zero numerator gives ratio0 and a zero geometric mean; denominator0 rejects the summary. "
                    "Timer-resolution zeros cannot establish zero computation cost.",
                ratios=ratios, absolute_ms=absolute,
                limitation="Single local run; scheduler/thermal/code-layout effects remain. V11 and linear adapters copy "
                    "Result vectors within adapter wall time; direct uses its native result vector. Internal search is "
                    "the primary algorithm comparison. No accuracy-improvement or universal speed claim.")


def pin(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return dict(path=str(path), size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def check(item):
    if pin(item["path"]) != item:
        raise ValueError("Evidence/source byte changed: " + item["path"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Fresh summary output required")
    evidence_pin = pin(args.run_evidence)
    evidence = json.loads(args.run_evidence.read_text(encoding="utf-8-sig"))
    if evidence.get("passed") is not True:
        raise ValueError("Successful benchmark run evidence required")
    pins = evidence["verified_pins_before"] + [evidence["csv"], evidence_pin]
    sources = [Path(__file__), Path(__file__).with_name("benchmark_statistics.py"),
               Path(__file__).with_name("benchmark_contract.py")]
    pins += [pin(source) for source in sources]
    for item in pins:
        check(item)
    with Path(evidence["csv"]["path"]).open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != list(FIELDS):
            raise ValueError("Fixed benchmark CSV columns required")
        rows = list(reader)
    result = summarize_rows(rows, evidence["image_names"])
    for item in pins:
        check(item)
    result.update(passed=True, created_at=datetime.now(timezone.utc).isoformat(),
                  run_evidence=evidence_pin, csv=evidence["csv"], verified_pins_before_after=pins)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write("\n")
    print("Summary: " + str(args.output.resolve()))


if __name__ == "__main__":
    main()
