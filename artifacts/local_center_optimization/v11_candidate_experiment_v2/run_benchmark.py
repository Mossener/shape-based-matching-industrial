"""Gated uninstrumented five-case build/run; native CPU assignment is external.

Reuses only the three correctness-proven uninstrumented matcher objects. The
correctness harness object and all diagnostic sources are excluded from link.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re

import run_correctness as base
from auxiliary_dependencies import parse_depfile
from benchmark_contract import FIELDS, validate_samples
from correctness_evidence import validate_csv

HERE, ROOT = base.HERE, base.ROOT
LIMITATION = ("Single local uninstrumented benchmark. Original three matcher objects and complete local "
              "source/dependency/compiler/runtime/receipt gates are reused; atomic correctness test object "
              "and diagnostic sources are excluded. Not an attestation of all OS/linker/loader reads. "
              "V11 and linear Result copies are inside adapter wall time; direct uses native results. "
              "No universal speed or accuracy-improvement claim.")


def correct_gates(paths, root_review_path):
    base.require(len(paths) == 3, "Exactly three distinct successful correctness result paths required")
    results = [(path.resolve(strict=True), base.read_json(path)) for path in paths]
    base.require(Counter(item["stage"] for _, item in results) == Counter(("core", "flags", "lifetime")),
                 "Core/flags/lifetime exactly once are required")
    build_path = Path(results[0][1]["build_directory"]).resolve(strict=True)
    built, inherited_pins = base.verify_build(build_path)
    base.require(all(Path(item["build_directory"]).resolve() == build_path for _, item in results),
                 "All correctness stages must share one exact successful executable/build")
    matrix = base.read_json(HERE / "REGRESSION_MATRIX.json")
    validations, gates, extra_pins = {}, {}, []
    for path, item in results:
        base.require(base.inside(path, HERE) and item["passed"] is True and
                     item["pins_unchanged_after"] is True and item["matcher_command"]["exit_code"] == 0,
                     "Successful local correctness gate with unchanged pins required")
        base.require(item["executable_before"] == item["executable_after"] == built["executable"],
                     "Correctness executable identities differ")
        base.checks(item["verified_pins_before"])
        pins = [base.pin(path), item["csv"], item["matcher_command"]["stdout"], item["matcher_command"]["stderr"]]
        base.checks(pins)
        output = Path(item["matcher_command"]["stdout"]["path"]).read_text(encoding="utf-8", errors="replace")
        output += "\n" + Path(item["matcher_command"]["stderr"]["path"]).read_text(encoding="utf-8", errors="replace")
        validation = validate_csv(Path(item["csv"]["path"]), item["stage"], built["development_names"], matrix, output)
        base.require(validation == item["csv_validation"], "Saved/revalidated correctness row gates differ")
        validations[item["stage"]] = validation
        gates[item["stage"]] = base.pin(path)
        extra_pins += pins
    review_pin = base.pin(root_review_path)
    review = base.read_json(root_review_path)
    base.require(review["passed"] is True and review["build_manifest_sha256"] ==
                 base.pin(build_path / "build_manifest.json")["sha256"], "Fresh parent build review required")
    base.require(Counter(item["stage"] for item in review["stages"]) == Counter(("core", "flags", "lifetime")),
                 "Fresh parent review must contain all three stages exactly once")
    for item in review["stages"]:
        stage = item["stage"]
        base.require(item["result_sha256"] == gates[stage]["sha256"] and item["validation"] == validations[stage],
                     "Parent review must bind each exact correctness result and validation")
    base.require(review["native_calls_in_review"] == review["image_decodes_in_review"] == 0,
                 "Parent receipt must be saved-artifact review without matcher/decode reruns")
    base.require(sum(value["rows"] for value in validations.values()) == 5504 and
                 sum(value["actual_matcher_calls"]["total"] for value in validations.values()) == 6609,
                 "Complete correctness matrix count differs")
    return built, inherited_pins + extra_pins + [review_pin], dict(
        correctness=gates, root_review=review_pin, validations=validations)


def validator_gate(path):
    pin = base.pin(path)
    item = base.read_json(path)
    base.require(item["phase"] == "green" and item["accepted"] is True and item["source_unchanged"] is True and
                 item["exit_code"] == 0 and item["expected_tests"] == 11 and item["synthetic_only"] is True and
                 item["matcher_calls"] == item["image_decodes"] == 0, "Current eleven-test synthetic GREEN required")
    expected_sources = {str((HERE / name).resolve()) for name in (
        "benchmark_contract.py", "benchmark_statistics.py", "summarize_benchmark.py",
        "tests/benchmark_contract_test.py", "tests/benchmark_statistics_test.py", "tests/benchmark_summary_test.py",
        "run_summary_validator.py")}
    base.require(set(item["source_sha256"]) == expected_sources, "All seven current synthetic validator source pins required")
    pins = [pin, item["red_evidence"]]
    for source, expected in item["source_sha256"].items():
        actual = base.pin(source)
        base.require(actual["sha256"] == expected, "Synthetic validator source changed since GREEN: " + source)
        pins.append(actual)
    base.checks(pins)
    return pins


def recipe(build_path, tool, objects):
    prefix = base.unit_specs(build_path, tool)[3]["prefix"]
    source = HERE / "benchmark.cpp"
    target = "benchmark.o"
    obj, scan, depfile = (build_path / name for name in (target, "benchmark_scan.d", "benchmark.d"))
    exe = build_path / "benchmark.exe"
    return dict(source=str(source), target=target, object=str(obj), scan=str(scan), depfile=str(depfile),
        executable=str(exe),
        discovery=prefix + ["-M", "-MF", str(scan), "-MT", target, str(source)],
        compile=prefix + ["-c", "-MD", "-MF", str(depfile), "-MT", target, str(source), "-o", str(obj)],
        link=[tool["compiler"]["path"], "-fopenmp"] + [item["path"] for item in objects] +
             [str(obj), tool["import_library"]["path"], "-o", str(exe)])


def build(args):
    destination = (args.build_directory or HERE / "build" / ("benchmark_" + base.stamp())).resolve()
    base.require(base.inside(destination, HERE / "build") and destination != HERE / "build", "Contained benchmark build required")
    destination.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, started_at=base.now(), working_directory=str(destination),
                  commands=[], limitation=LIMITATION)
    manifest_path = destination / "build_manifest.json"
    try:
        base.require(args.root_review is not None and args.validator_evidence is not None,
                     "Root correctness review and current synthetic GREEN required")
        built, pins, gates = correct_gates(args.correctness_evidence, args.root_review)
        pins += validator_gate(args.validator_evidence)
        source_items = built["source_pins"] + [base.pin(HERE / name) for name in (
            "benchmark.cpp", "run_benchmark.py", "auxiliary_dependencies.py", "benchmark_contract.py",
            "benchmark_statistics.py", "summarize_benchmark.py", "run_summary_validator.py",
            "tests/benchmark_contract_test.py", "tests/benchmark_statistics_test.py", "tests/benchmark_summary_test.py")]
        pins += source_items
        base.checks(pins)
        units = built["dependency_units"][:3]
        base.require([item["target"] for item in units] == ["v11_reference.o", "v18_reference.o", "direct_core.o"],
                     "Only the three uninstrumented matcher objects may be reused")
        objects = [base.pin(item["object"]) for item in units]
        base.require(objects == [item["artifacts"][0] for item in units], "Reused object pins differ from correctness build")
        spec = recipe(destination, built["toolchain"], objects)
        result.update(inherited_build_manifest=base.pin(Path(built["working_directory"]) / "build_manifest.json"),
                      gates=gates, verified_pins_before=pins, source_pins=source_items, reused_objects=objects,
                      toolchain=built["toolchain"], environment=base.ENVIRONMENT,
                      image_names=["LED_" + str(index) for index in range(1, 9)] + ["case1"] + built["development_names"],
                      recipe=spec)
        env = base.environment(built["toolchain"])
        ran = base.command(spec["discovery"], destination, env, destination, "benchmark_scan")
        result["commands"].append(ran)
        base.require(ran["exit_code"] == 0, "Benchmark dependency discovery failed")
        dependencies = parse_depfile(Path(spec["scan"]).read_bytes(), spec["target"], destination)
        base.require(Path(spec["source"]).resolve() in dependencies, "Benchmark discovery omitted its source")
        dependency_pins = base.scoped_dependencies(dependencies, source_items, built["toolchain"])
        discovery_pin = base.pin(spec["scan"])
        result.update(dependencies=dependency_pins, discovery_depfile_pin=discovery_pin)
        base.checks(pins + objects + dependency_pins + [discovery_pin])
        ran = base.command(spec["compile"], destination, env, destination, "benchmark_compile")
        result["commands"].append(ran)
        base.require(ran["exit_code"] == 0, "Benchmark compile failed")
        base.require(parse_depfile(Path(spec["depfile"]).read_bytes(), spec["target"], destination) == dependencies,
                     "Benchmark pre-M/actual-MD ordered occurrences differ")
        base.checks(pins + objects + dependency_pins + [discovery_pin])
        artifacts = [base.pin(spec[key]) for key in ("object", "scan", "depfile")]
        ran = base.command(spec["link"], destination, env, destination, "link")
        result["commands"].append(ran)
        base.require(ran["exit_code"] == 0, "Benchmark link failed")
        base.checks(pins + objects + dependency_pins + artifacts + [discovery_pin])
        for item in result["commands"]:
            base.checks([item["stdout"], item["stderr"]])
        result.update(passed=True, artifacts=artifacts, executable=base.pin(spec["executable"]), pins_unchanged_after=True)
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    result["finished_at"] = base.now()
    base.write_json(manifest_path, result)
    (destination / "build_manifest.sha256").write_text(base.sha(manifest_path.read_bytes()) + "\n", encoding="ascii")
    print("Benchmark build evidence: " + str(manifest_path), flush=True)
    base.require(result["passed"], result.get("error", "Benchmark build failed"))


def verify_build(destination):
    manifest_path, receipt_path = destination / "build_manifest.json", destination / "build_manifest.sha256"
    base.require(base.sha(manifest_path.read_bytes()) == receipt_path.read_text(encoding="ascii").strip(),
                 "Benchmark manifest SHA receipt differs")
    built = base.read_json(manifest_path)
    base.require(built["passed"] is True and Path(built["working_directory"]).resolve() == destination and
                 built["pins_unchanged_after"] is True and built["environment"] == base.ENVIRONMENT,
                 "Successful exact benchmark build required")
    inherited = base.read_json(Path(built["inherited_build_manifest"]["path"]))
    original, original_pins = base.verify_build(Path(inherited["working_directory"]).resolve())
    base.require(built["toolchain"] == original["toolchain"], "Benchmark must reuse the exact correctness toolchain")
    objects = [base.pin(item["object"]) for item in original["dependency_units"][:3]]
    base.require(objects == built["reused_objects"] and built["recipe"] == recipe(destination, built["toolchain"], objects),
                 "Benchmark recipe/object identities differ; correctness/diagnostic harness may not be linked")
    spec = built["recipe"]
    base.require([item["argv"] for item in built["commands"]] == [spec["discovery"], spec["compile"], spec["link"]] and
                 all(type(item["exit_code"]) is int and item["exit_code"] == 0 for item in built["commands"]),
                 "Benchmark exact scan/compile/link commands differ")
    before = parse_depfile(Path(spec["scan"]).read_bytes(), spec["target"], destination)
    actual = parse_depfile(Path(spec["depfile"]).read_bytes(), spec["target"], destination)
    base.require(before == actual == [Path(item["path"]) for item in built["dependencies"]],
                 "Benchmark ordered dependency occurrence receipts differ")
    base.scoped_dependencies(actual, built["source_pins"], built["toolchain"])
    pins = original_pins + built["verified_pins_before"] + built["reused_objects"] + built["dependencies"] + built["artifacts"]
    pins += [built["executable"], built["discovery_depfile_pin"], base.pin(manifest_path), base.pin(receipt_path)]
    for item in built["commands"]:
        pins += [item["stdout"], item["stderr"]]
    base.checks(pins)
    return built, pins


def run(args):
    base.require(args.build_directory is not None, "Run requires successful benchmark --build-directory")
    destination = args.build_directory.resolve(strict=True)
    base.require(base.inside(destination, HERE / "build"), "Contained benchmark build required")
    evidence = HERE / ("benchmark_" + base.stamp())
    evidence.mkdir(exist_ok=False)
    result = dict(passed=False, started_at=base.now(), environment=base.ENVIRONMENT,
                  cv_threads=1, omp_threads=4, limitation=LIMITATION)
    try:
        built, pins = verify_build(destination)
        result.update(build_manifest=base.pin(destination / "build_manifest.json"),
                      executable_before=built["executable"], verified_pins_before=pins,
                      image_names=built["image_names"])
        csv_path = evidence / "samples.csv"
        argv = [built["executable"]["path"], "--output", str(csv_path)]
        ran = base.command(argv, ROOT, base.environment(built["toolchain"]), evidence, "matcher")
        result["matcher_command"] = ran
        base.checks(pins)
        result.update(pins_unchanged_after=True, executable_after=base.pin(built["executable"]["path"]))
        if csv_path.exists():
            result["csv"] = base.pin(csv_path)
        base.require(ran["exit_code"] == 0, "Five-case native benchmark failed")
        with csv_path.open(newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            base.require(reader.fieldnames == list(FIELDS), "Benchmark CSV columns differ")
            result["csv_validation"] = validate_samples(list(reader), built["image_names"])
        output = Path(ran["stdout"]["path"]).read_text(encoding="utf-8", errors="replace")
        output += "\n" + Path(ran["stderr"]["path"]).read_text(encoding="utf-8", errors="replace")
        calls = re.findall(r"^MATCHER_CALLS exact_v11=(\d+) linear16=(\d+) direct16=(\d+) total=(\d+)$", output, re.MULTILINE)
        base.require(calls == [("450", "900", "900", "2250")] and
                     output.count("PASS V2 five-case ordered benchmark calls=2250") == 1,
                     "Exactly2250 native API calls and unique PASS marker required")
        result["actual_matcher_calls"] = dict(exact_v11=450, linear16=900, direct16=900, total=2250)
        base.checks(pins)
        base.checks([result["csv"], ran["stdout"], ran["stderr"]])
        result["passed"] = True
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    result["finished_at"] = base.now()
    path = evidence / "result.json"
    base.write_json(path, result)
    print("Benchmark evidence: " + str(path), flush=True)
    base.require(result["passed"], result.get("error", "Benchmark failed"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("build", "run"))
    parser.add_argument("--build-directory", type=Path)
    parser.add_argument("--correctness-evidence", type=Path, nargs="+", default=[])
    parser.add_argument("--root-review", type=Path)
    parser.add_argument("--validator-evidence", type=Path)
    args = parser.parse_args()
    (build if args.mode == "build" else run)(args)


if __name__ == "__main__":
    main()
