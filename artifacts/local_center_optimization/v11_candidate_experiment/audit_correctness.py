"""Fresh provenance/CSV audit; never execute the matcher or decode an image."""
import argparse
import base64
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMMIT = "b25df46f6ddf9c24fb43f5836f1414dc38c8caed"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest().upper()


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def audit(acceptance, output):
    require(not output.exists(), "Refusing to overwrite a fresh audit")
    pins = {}

    def pin(path, expected):
        path = str(Path(path).resolve())
        expected = expected.upper()
        require(path not in pins or pins[path] == expected, "Conflicting file pin")
        require(digest(path) == expected, "Changed pinned bytes: " + path)
        pins[path] = expected

    acceptance_before = digest(acceptance)
    accepted = read(acceptance)
    pin(acceptance, acceptance_before)
    require(accepted["passed"] and accepted["baseline_commit"] == COMMIT, "Invalid acceptance report")
    pin(accepted["baseline_manifest"], accepted["baseline_manifest_sha256"])
    pin(accepted["build_manifest"], accepted["build_manifest_sha256"])
    pin(accepted["candidate_change_manifest"], accepted["candidate_change_manifest_sha256"])
    pin(HERE / "candidate.patch", accepted["patch_sha256"])
    build = read(accepted["build_manifest"])
    require(build["passed"] and not build["source_changes_during_build"], "Build failed or sources changed")
    require(len(build["compilation"]) == 4 and all(step["exit_code"] == 0 for step in build["compilation"]),
            "All three translation units and link must compile successfully")
    require(build["baseline_commit"] == COMMIT, "Build baseline commit differs")
    pin(build["compiler"], build["compiler_sha256"])
    pin(build["executable"], build["executable_sha256"])
    receipt = Path(accepted["build_receipt"])
    pin(receipt, digest(receipt))
    require(receipt.read_text(encoding="ascii").strip().upper() == accepted["build_manifest_sha256"].upper(),
            "Build receipt does not match accepted manifest")
    for group in ("source_sha256", "protected_source_sha256"):
        require(bool(build[group]), "Missing build closure")
        for path, expected in build[group].items():
            pin(path, expected)
    matrix = read(HERE / "REGRESSION_MATRIX.json")
    expected_rows = {"core": 1280, "flags": 1562, "lifetime": 38}
    expected_calls = {"core": 1536, "flags": 2343, "lifetime": 106}
    require(sorted(item["stage"] for item in accepted["stages"]) == sorted(expected_rows), "Three distinct stages required")
    audited = []
    for entry in accepted["stages"]:
        stage = entry["stage"]
        pin(entry["evidence"], entry["evidence_sha256"])
        result = read(entry["evidence"])
        require(result["passed"] and result["stage"] == stage and result["exit_code"] == 0 and
                result["mismatches"] == 0 and not result["source_changes_during_run"], "Stage failed")
        require(result["build_manifest"] == build, "Stage embedded build manifest differs")
        require(result["source_sha256"] == build["source_sha256"] and
                result["protected_source_sha256"] == build["protected_source_sha256"], "Stage source closure differs")
        require(result["build_manifest_expected_sha256"] == accepted["build_manifest_sha256"], "Stage manifest identity differs")
        for label, path, expected in (
            ("build_manifest", accepted["build_manifest"], accepted["build_manifest_sha256"]),
            ("build_manifest_receipt", receipt, digest(receipt)),
            ("executable", build["executable"], build["executable_sha256"]),
        ):
            require(not result[label + "_changed"] and result[label + "_sha256_before"] == expected and
                    result[label + "_sha256_after"] == expected, "Stage before/after identity differs: " + label)
            pin(path, expected)
        pin(result["csv"], result["csv_sha256"])
        require(entry["csv"] == result["csv"] and entry["csv_sha256"] == result["csv_sha256"], "Accepted CSV identity differs")
        with open(result["csv"], encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        require(len(rows) == result["rows"] == result["expected_rows"] == matrix[stage]["expected_csv_rows"] == expected_rows[stage],
                "Audited row count differs")
        require(matrix[stage]["expected_matcher_calls"] == expected_calls[stage], "Declared matcher-call matrix differs")
        require(all(row["full_ordered_equal"] == "1" and row["first_mismatch"] == "" and
                    row["expected_count"] == row["actual_count"] for row in rows),
                "Ordered comparison, first-mismatch or vector-length failure in CSV")
        phases = Counter(row["phase"] for row in rows)
        if stage == "core":
            require(phases == {"baseline_repeat": 256, "core": 1024}, "Core phase distribution differs")
            require(Counter(row["threads"] for row in rows) == {"1": 320, "2": 320, "4": 640}, "Core thread passes differ")
        elif stage == "flags":
            require(phases == {"flags": 1536, "mask_restore": 24, "log_flag": 2}, "Flag phase distribution differs")
            require(Counter(int(row["flags"]) for row in rows if row["phase"] == "flags") == {i: 12 for i in range(128)},
                    "All 128 flag combinations must each have twelve candidate comparisons")
        else:
            require(phases == {"pre_move": 1, "move_constructed": 1, "moved_from_reused": 1,
                               "assignment_destination_populated": 1, "move_assigned": 1, "assignment_source_reused": 1,
                               "legacy_default": 4, "explicit_default": 4, "concurrent": 24}, "Lifetime phase distribution differs")
        audited.append({"stage": stage, "rows": len(rows), "expected_matcher_calls": expected_calls[stage], "phases": dict(phases)})
    green_path = HERE / "cache_contract_green_20261021_225524_029.json"
    green = read(green_path)
    require(green["accepted"] and green["phase"] == "Green" and green["compile_exit"] == green["test_exit"] == 0,
            "Cache GREEN evidence failed")
    require((HERE / "candidate/line2Dup_local_cache.hpp").read_bytes() == base64.b64decode(green["cache_header_base64"]),
            "Cache header differs from literal GREEN bytes")
    require(digest(HERE / "tests/cache_contract_test.cpp") == green["test_source_sha256"], "Cache contract test source changed")
    red_path = ROOT / green["red_evidence"]
    pin(red_path, digest(red_path))
    red = read(red_path)
    require(red["accepted"] and red["phase"] == "Red" and red["compile_exit"] == 0 and red["test_exit"] == 1 and
            any("stored result was not retrieved" in line for line in red["test_output"]), "Literal RED semantics failed")
    snapshot = subprocess.run([sys.executable, str(HERE / "snapshot_v11.py"), "--mode", "verify"],
                              cwd=ROOT, capture_output=True, text=True, check=True)
    frozen = json.loads(snapshot.stdout)
    require(frozen["passed"] and frozen["commit"] == COMMIT and frozen["files"] == 23 and
            frozen["baseline_manifest_sha256"].upper() == accepted["baseline_manifest_sha256"], "Fresh frozen-Git verification failed")
    require(sum(item["rows"] for item in audited) == 2880 and sum(item["expected_matcher_calls"] for item in audited) == 3985,
            "Aggregate coverage differs")
    for path, expected in pins.items():
        require(digest(path) == expected, "Pinned bytes changed during fresh audit: " + path)
    report = {"passed": True, "matcher_executions": 0, "image_decodes": 0, "audit_source_sha256": digest(__file__),
              "acceptance_manifest": str(acceptance.resolve()), "acceptance_manifest_sha256": acceptance_before,
              "verified_file_count": len(pins), "stages": audited, "frozen_git_verification": frozen,
              "ordered_audit_rows": 2880, "declared_original_matcher_calls": 3985,
              "limitations": ["Fresh byte/CSV provenance audit only; it does not rerun the matcher.",
                              "Per-vector full_ordered_equal and first_mismatch are emitted by the pinned direct tuple comparator; passed CSVs do not serialize each raw match record.",
                              "This is fixed-matrix output equivalence, not universal equivalence, accuracy improvement or speed evidence."]}
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "output": str(output.resolve()), "sha256": digest(output),
                      "verified_files": len(pins), "rows": 2880, "new_matcher_calls": 0}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--acceptance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    audit(args.acceptance, args.output)
