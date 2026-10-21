"""Summarize every predeclared paired timing; never discard a regression."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def quantile(values, p):
    values = sorted(values)
    position = (len(values) - 1) * p
    low = math.floor(position)
    high = math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def distribution(values):
    return {
        "p10": quantile(values, .1),
        "median": median(values),
        "p90": quantile(values, .9),
        "geometric_mean": math.exp(sum(math.log(v) for v in values) / len(values)),
        "minimum": min(values), "maximum": max(values),
    }


def verify_closure(evidence, result):
    """Verify actual pinned bytes, then return every pin for a read-after check."""
    pins = {}

    def pin(path, expected):
        expected = expected.upper()
        path = str(Path(path).resolve())
        require(path not in pins or pins[path] == expected, "Conflicting hash pin: " + path)
        require(sha256(path) == expected, "Pinned bytes changed: " + path)
        pins[path] = expected

    pin(evidence, sha256(evidence))
    for key in ("source_sha256", "protected_source_sha256"):
        require(bool(result[key]), "Missing source/protected hash closure")
        for path, expected in result[key].items():
            pin(path, expected)
    manifest_path = Path(result["build_manifest_path"])
    pin(manifest_path, result["build_manifest_expected_sha256"])
    pin(manifest_path.with_suffix(".sha256"), result["build_manifest_receipt_sha256_before"])
    receipt = manifest_path.with_suffix(".sha256").read_text(encoding="ascii").strip()
    require(receipt.upper() == result["build_manifest_expected_sha256"].upper(), "Manifest receipt digest differs")
    require(result["build_manifest_sha256_before"] == result["build_manifest_expected_sha256"], "Manifest before pin differs")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    require(manifest["passed"] and not manifest["source_changes_during_build"], "Unsuccessful benchmark build")
    require(manifest["source_sha256"] == result["source_sha256"], "Build/run source closure differs")
    require(manifest["protected_source_sha256"] == result["protected_source_sha256"], "Build/run protected closure differs")
    require(manifest["correctness_gates"] == result["correctness_gates"], "Original build gates differ")
    require(manifest["executable"] == result["executable"], "Executable path differs from build")
    require(manifest["executable_sha256"] == result["executable_sha256_before"], "Executable build/run pin differs")
    pin(result["executable"], result["executable_sha256_before"])
    pin(manifest["compiler"], manifest["compiler_sha256"])
    pin(result["csv"], result["csv_sha256"])
    require(sorted(gate["stage"] for gate in result["correctness_gates"]) ==
            ["core", "flags", "lifetime"], "All original correctness gates required")
    for gate in result["correctness_gates"]:
        pin(gate["path"], gate["sha256"])
        checked = json.loads(Path(gate["path"]).read_text(encoding="utf-8-sig"))
        require(checked["passed"] and checked["exit_code"] == 0 and checked["mismatches"] == 0,
                "Correctness gate failed")
        require(checked["stage"] == gate["stage"] and checked["csv_sha256"] == gate["csv_sha256"],
                "Correctness gate identity differs")
        pin(checked["csv"], gate["csv_sha256"])
    protocol_paths = [path for path in result["source_sha256"]
                      if Path(path).name == "BENCHMARK_PROTOCOL.json"]
    require(len(protocol_paths) == 1, "Exactly one pinned protocol required")
    pin(protocol_paths[0], result["protocol_sha256"])
    protocol = json.loads(Path(protocol_paths[0]).read_text(encoding="utf-8-sig"))
    require(protocol["fixture_count"] == 25 and protocol["flags"] == 127 and
            protocol["cold_calls_per_case_image"] == 1 and protocol["warm_calls_per_case_image"] == 2
            and protocol["measured_rounds"] == 15, "Benchmark protocol shape differs")
    index_paths = [path for path in result["source_sha256"]
                   if str(path).replace("\\", "/").endswith("datasets/tless_tiny/index.json")]
    require(len(index_paths) == 1, "Pinned tiny index required")
    index = json.loads(Path(index_paths[0]).read_text(encoding="utf-8-sig"))
    development = [frame for frame in index["test"] if frame["split"] == "development"]
    require(len(development) == 16, "Sixteen development metadata entries required")
    names = ["LED_" + str(i) for i in range(1, 9)] + ["case1"] + [
        "tiny_s" + str(frame["scene_id"]) + "_i" + str(frame["image_id"]) for frame in development]
    return pins, names


def summarize(evidence, destination):
    require(not destination.exists(), "Refusing to overwrite a summary")
    evidence_hash_before = sha256(evidence)
    result = json.loads(evidence.read_text(encoding="utf-8-sig"))
    require(result["passed"] and result["exit_code"] == 0, "Successful benchmark required")
    require(result["rows"] == result["expected_rows"] == 1350, "Unexpected benchmark row count")
    require(not result["source_changes_during_run"], "Sources changed during run")
    for key in ("build_manifest", "build_manifest_receipt", "executable"):
        require(not result[key + "_changed"], key + " changed during run")
        require(result[key + "_sha256_before"] == result[key + "_sha256_after"], key + " hashes differ")
    pins, expected_names = verify_closure(evidence, result)
    require(pins[str(evidence.resolve())] == evidence_hash_before, "Evidence changed while opening")
    with open(result["csv"], encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 1350, "Raw row count differs")
    images = {}
    cases = ("exact_v11", "candidate_off", "candidate_on")
    metrics = ("search_ms", "total_ms", "adapter_wall_ms")
    for row in rows:
        require(row["full_ordered_equal"] == "1", "Non-equivalent matcher output")
        require(row["case"] in cases, "Unknown benchmark case")
        require(row["phase"] in ("cold", "warm", "measured"), "Unknown phase")
        image_index, round_ = int(row["image_index"]), int(row["round"])
        require(0 <= image_index < 25 and row["image"] == expected_names[image_index], "Unexpected image identity")
        expected_threshold = 75 if image_index < 8 else 90 if image_index == 8 else 85
        expected_templates = 900 if image_index < 8 else 361 if image_index == 8 else 2212
        require(float(row["threshold"]) == expected_threshold and int(row["templates"]) == expected_templates,
                "Template bank/threshold differs from protocol")
        require(int(row["width"]) > 0 and int(row["height"]) > 0, "Positive image dimensions required")
        call_round = round_ + {"cold": 0, "warm": 1, "measured": 3}[row["phase"]]
        route = list(cases)
        rotation = (image_index + call_round) % 3
        route = route[rotation:] + route[:rotation]
        if (image_index + call_round) % 2:
            route.reverse()
        position = int(row["order_position"])
        require(0 <= position < 3 and route[position] == row["case"], "Case order differs from protocol")
        for metric in metrics:
            value = float(row[metric])
            require(math.isfinite(value) and value > 0, "Positive finite measured time required")
        key = (row["phase"], int(row["round"]), row["case"])
        invariant = tuple(row[name] for name in ("width", "height", "templates", "threshold"))
        group = images.setdefault(image_index, {"name": row["image"], "invariant": invariant, "rows": {}})
        require(group["name"] == row["image"], "Image index/name mismatch")
        require(group["invariant"] == invariant, "Image dimensions/bank/threshold changed between calls")
        require(key not in group["rows"], "Duplicate paired sample")
        group["rows"][key] = row
    require(sorted(images) == list(range(25)), "All 25 images required")
    per_image = []
    for index, group in sorted(images.items()):
        expected_keys = {(phase, round_, case)
                         for phase, count in (("cold", 1), ("warm", 2), ("measured", 15))
                         for round_ in range(count) for case in cases}
        require(set(group["rows"]) == expected_keys, "Incomplete phase/case/round pairing")
        item = {"image_index": index, "image": group["name"], "metrics": {}}
        for metric in metrics:
            values = {case: [float(group["rows"][("measured", round_, case)][metric])
                             for round_ in range(15)] for case in cases}
            paired = {}
            for label, numerator, denominator in (
                ("on_over_off", "candidate_on", "candidate_off"),
                ("off_over_v11", "candidate_off", "exact_v11"),
                ("on_over_v11", "candidate_on", "exact_v11"),
            ):
                ratios = [a / b for a, b in zip(values[numerator], values[denominator])]
                paired[label] = {"all_ratios": ratios, **distribution(ratios)}
            item["metrics"][metric] = {
                "case_median_ms": {case: median(v) for case, v in values.items()},
                "paired_ratios": paired,
            }
        per_image.append(item)
    rollups = {}
    for metric in metrics:
        rollups[metric] = {}
        for label in ("on_over_off", "off_over_v11", "on_over_v11"):
            image_medians = [item["metrics"][metric]["paired_ratios"][label]["median"]
                             for item in per_image]
            rollups[metric][label] = {
                "equal_weight_image_median_ratios": distribution(image_medians),
                "regression_images": [item["image"] for item, value in zip(per_image, image_medians) if value > 1],
                "no_gain_images": [item["image"] for item, value in zip(per_image, image_medians) if value >= 1],
            }
    summary = {
        "benchmark_evidence": str(evidence.resolve()), "benchmark_evidence_sha256": evidence_hash_before,
        "csv": result["csv"], "csv_sha256": result["csv_sha256"],
        "protocol_sha256": result["protocol_sha256"], "image_count": 25,
        "measured_rounds_per_case_image": 15, "all_rows": 1350,
        "ratio_direction": "Lower is faster; 1 is no measured change",
        "equal_weight_rollups": rollups, "per_image": per_image,
        "limits": ["Quantiles are descriptive; no confidence-interval claim.",
                   "Exact V11 adapter wall includes an extra output copy; prefer internal search/total for V11 comparisons.",
                   "Candidate off/on use symmetric adapters; all images and regressions retained.",
                   "Exact equality cannot show an accuracy improvement; no production adoption is implied."],
        "verified_file_count": len(pins),
        "verification": "Actual evidence/build/receipt/executable/compiler/runtime/source/protected/protocol/gate/CSV pins checked before reads and again before writing; case order and per-image bank/threshold/dimension invariants checked.",
    }
    for path, expected in pins.items():
        require(sha256(path) == expected, "Pinned bytes changed while summarizing: " + path)
    destination.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(destination.resolve()), "sha256": sha256(destination),
                      "rollups": rollups}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summarize(args.evidence, args.output)
