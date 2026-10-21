"""Synthetic provenance/parser checks only; no matcher or real image decoding."""
import csv
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import time

EXPERIMENT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("center_benchmark_summary", EXPERIMENT / "summarize.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def fixture(root):
    source, protected, exe, compiler = [root / name for name in ("source.txt", "protected.txt", "benchmark.exe", "compiler.exe")]
    for path in (source, protected, exe, compiler):
        path.write_text("synthetic " + path.name, encoding="utf-8")
    protocol = root / "BENCHMARK_PROTOCOL.json"
    protocol.write_bytes((EXPERIMENT / "BENCHMARK_PROTOCOL.json").read_bytes())
    index = root / "datasets/tless_tiny/index.json"
    frames = [{"scene_id": 1 + i // 8, "image_id": i % 8, "split": "development"} for i in range(16)]
    write_json(index, {"test": frames})
    gates = []
    sources = {str(path): module.sha256(path) for path in (source, compiler, protocol, index)}
    for stage in ("core", "flags", "lifetime"):
        path, csv_path = root / (stage + ".json"), root / (stage + ".csv")
        csv_path.write_text("synthetic correctness\n", encoding="utf-8")
        gate = {"passed": True, "exit_code": 0, "mismatches": 0, "stage": stage,
                "csv": str(csv_path), "csv_sha256": module.sha256(csv_path)}
        write_json(path, gate)
        gates.append({"stage": stage, "path": str(path), "sha256": module.sha256(path),
                      "csv_sha256": module.sha256(csv_path)})
        sources[str(path)] = module.sha256(path)
        sources[str(csv_path)] = module.sha256(csv_path)
    protected_pins = {str(protected): module.sha256(protected)}
    manifest = root / "build_manifest.json"
    write_json(manifest, {"passed": True, "source_changes_during_build": [], "source_sha256": sources,
                         "protected_source_sha256": protected_pins, "correctness_gates": gates,
                         "executable": str(exe), "executable_sha256": module.sha256(exe),
                         "compiler": str(compiler), "compiler_sha256": module.sha256(compiler)})
    receipt = manifest.with_suffix(".sha256")
    receipt.write_text(module.sha256(manifest) + "\n", encoding="ascii")
    csv_path = root / "benchmark.csv"
    fields = ["image", "image_index", "width", "height", "templates", "threshold", "phase", "round",
              "order_position", "case", "search_ms", "total_ms", "adapter_wall_ms", "full_ordered_equal"]
    names = ["LED_" + str(i) for i in range(1, 9)] + ["case1"] + [
        "tiny_s" + str(frame["scene_id"]) + "_i" + str(frame["image_id"]) for frame in frames]
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for i, name in enumerate(names):
            for phase, count, offset in (("cold", 1, 0), ("warm", 2, 1), ("measured", 15, 3)):
                for round_ in range(count):
                    route = ["exact_v11", "candidate_off", "candidate_on"]
                    rotation = (i + round_ + offset) % 3
                    route = route[rotation:] + route[:rotation]
                    if (i + round_ + offset) % 2:
                        route.reverse()
                    for position, case in enumerate(route):
                        on = case == "candidate_on"
                        writer.writerow({"image": name, "image_index": i, "width": 640, "height": 480,
                                         "templates": 900 if i < 8 else 361 if i == 8 else 2212,
                                         "threshold": 75 if i < 8 else 90 if i == 8 else 85,
                                         "phase": phase, "round": round_, "order_position": position, "case": case,
                                         "search_ms": 8 if on else 10, "total_ms": 13 if on else 15,
                                         "adapter_wall_ms": 14 if on else 16, "full_ordered_equal": 1})
    evidence = root / "evidence.json"
    result = {"passed": True, "exit_code": 0, "rows": 1350, "expected_rows": 1350,
              "source_changes_during_run": [], "source_sha256": sources,
              "protected_source_sha256": protected_pins, "correctness_gates": gates,
              "build_manifest_path": str(manifest), "build_manifest_expected_sha256": module.sha256(manifest),
              "executable": str(exe), "csv": str(csv_path), "csv_sha256": module.sha256(csv_path),
              "protocol_sha256": module.sha256(protocol)}
    for key, path in (("build_manifest", manifest), ("build_manifest_receipt", receipt), ("executable", exe)):
        result[key + "_changed"] = False
        result[key + "_sha256_before"] = result[key + "_sha256_after"] = module.sha256(path)
    write_json(evidence, result)
    return evidence, (source, protected, protocol, manifest, receipt, exe, root / "core.csv")


def main():
    root = EXPERIMENT / "build" / ("summary_contract_" + time.strftime("%Y%m%d_%H%M%S") + "_" + str(time.time_ns() % 1000000))
    root.mkdir(parents=True, exist_ok=False)
    evidence, mutable_pins = fixture(root)
    outcomes = []
    with contextlib.redirect_stdout(io.StringIO()):
        module.summarize(evidence, root / "accepted.json")
    accepted = json.loads((root / "accepted.json").read_text())
    ratio = accepted["equal_weight_rollups"]["search_ms"]["on_over_off"]["equal_weight_image_median_ratios"]["median"]
    assert abs(ratio - .8) < 1e-12
    outcomes.append({"case": "valid_synthetic_pairing", "accepted": True, "search_ratio": ratio})

    def reject(label, mutate, restore):
        mutate()
        try:
            module.summarize(evidence, root / (label + ".json"))
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            outcomes.append({"case": label, "rejected": True, "reason": str(error)})
        else:
            raise AssertionError("Unexpected acceptance: " + label)
        finally:
            restore()

    for path in mutable_pins:
        old = path.read_bytes()
        reject("changed_" + path.name.replace(".", "_"),
               lambda path=path: path.write_bytes(old + b"changed"),
               lambda path=path: path.write_bytes(old))

    original_evidence = evidence.read_bytes()
    result = json.loads(original_evidence)
    csv_path = Path(result["csv"])
    original_csv = csv_path.read_bytes()
    rows = list(csv.DictReader(io.StringIO(original_csv.decode())))
    fields = list(rows[0])

    def alter_csv(field, value, row_index=0):
        changed = [dict(row) for row in rows]
        changed[row_index][field] = value
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(changed)
        csv_path.write_text(stream.getvalue(), encoding="utf-8", newline="")
        changed_result = dict(result)
        changed_result["csv_sha256"] = module.sha256(csv_path)
        write_json(evidence, changed_result)

    def restore_csv():
        csv_path.write_bytes(original_csv)
        evidence.write_bytes(original_evidence)

    for label, field, value, row_index in (("wrong_case_position", "order_position", "2", 0),
                                           ("wrong_threshold", "threshold", "74", 0),
                                           ("wrong_bank", "templates", "899", 0),
                                           ("changing_dimensions", "width", "641", 1),
                                           ("wrong_image_identity", "image", "LED_8", 0)):
        reject(label, lambda field=field, value=value, row_index=row_index: alter_csv(field, value, row_index), restore_csv)
    original_reader = module.csv.DictReader
    source = mutable_pins[0]
    original_source = source.read_bytes()

    def reader_with_mid_read_mutation(stream):
        for row in original_reader(stream):
            yield row
        source.write_bytes(original_source + b"changed during CSV read")

    def restore_reader():
        module.csv.DictReader = original_reader
        source.write_bytes(original_source)

    reject("mid_read_source_change", lambda: setattr(module.csv, "DictReader", reader_with_mid_read_mutation), restore_reader)
    report = {"passed": True, "synthetic_only": True, "matcher_calls": 0, "image_decodes": 0,
              "summary_source_sha256": module.sha256(EXPERIMENT / "summarize.py"),
              "test_source_sha256": module.sha256(__file__), "outcomes": outcomes,
              "limitation": "Synthetic validator checks are not matcher correctness, speed or accuracy evidence."}
    write_json(root / "contract_result.json", report)
    print(json.dumps({"passed": True, "cases": len(outcomes), "evidence": str(root / "contract_result.json")}, indent=2))


if __name__ == "__main__":
    main()
