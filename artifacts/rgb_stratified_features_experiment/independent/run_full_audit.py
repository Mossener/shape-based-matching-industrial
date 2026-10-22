"""One-shot guarded runner for the real full-training numeric audit.

The native training runner already records a complete absolute-path output pin
list in ``run_training_v1_PROVENANCE.json``.  This wrapper converts that list
to the strict run-relative map consumed by ``training_audit.py`` and checks
every item against the current file before starting the one heavy audit.

``--reserve-only`` creates the persistent, exclusive stage reservation without
opening the training output directory.  ``--execute`` is intentionally a
single-use operation: it requires that reservation, creates a fresh map,
execution directory and receipts, and never retries after a failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
AUDITOR = HERE / "training_audit.py"
GUARD = EXPERIMENT / "execution_guard.py"
BOUNDED = HERE / "bounded_classifier_v2.py"
RESERVATION_SCHEMA = "independent_full_training_audit_reservation_v2"
RUNNER_SCHEMA = "independent_full_training_audit_runner_v2"
OBJECTS = [1, 2, 5, 8, 12, 17]
EXPECTED = {
    "shared_poses": 20736,
    "shared_pools": 41472,
    "arm_layer_rows": 82944,
    "arm_attempts": 41472,
    "matcher_calls": 0,
    "rgb_decodes": 432,
    "mask_decodes": 432,
}
BUDGET = {
    "wall_seconds": 5400,
    "rss_bytes": 1536 * 1024 * 1024,
    "audit_output_bytes": 256 * 1024 * 1024,
    "execution_log_bytes": 64 * 1024 * 1024,
}


def require(value: object, message: str) -> None:
    if not value:
        raise ValueError(message)


def file_pin(path: Path) -> dict:
    path = Path(path).resolve(strict=True)
    require(not path.is_symlink(), "symlink is not an auditable file: " + str(path))
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def check_pin(pin: dict) -> None:
    require(file_pin(pin["path"]) == pin,
            "source or manifest pin changed: " + str(pin.get("path")))


def _json(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(data, dict), "JSON root must be an object: " + str(path))
    return data


def source_pins() -> list[dict]:
    paths = [Path(__file__), GUARD, AUDITOR,
             HERE / "numeric_oracle.py", HERE / "pool_stream.py",
             HERE / "strict_bank_reader.py", BOUNDED,
             EXPERIMENT / "TRAINING_INPUT_FREEZE.json",
             EXPERIMENT / "TRAINING_SOURCE_FREEZE.json"]
    return [file_pin(path) for path in paths]


def _relative(run: Path, path: Path) -> str:
    run = run.resolve()
    path = path.resolve(strict=True)
    require(path.is_relative_to(run), "runner pin escaped run directory: " + str(path))
    rel = path.relative_to(run).as_posix()
    require(rel and Path(rel).as_posix() == rel and ".." not in Path(rel).parts,
            "invalid run-relative output path: " + rel)
    return rel


def derive_output_pins(run: Path, provenance: Path) -> dict:
    """Build a complete map from the runner's original absolute pins.

    No directory walk is used to discover files.  Every expected file must be
    named by the runner provenance, and each source pin is checked byte-for-byte
    before it is converted to a relative key.
    """
    run = Path(run).resolve(strict=True)
    provenance = Path(provenance).resolve(strict=True)
    data = _json(provenance)
    require(data.get("mode") == "train" and data.get("passed") is True,
            "runner provenance is not a completed train run")
    require(data.get("expected_shared_poses") == EXPECTED["shared_poses"],
            "runner provenance pose budget differs")
    require(data.get("expected_matcher_calls") == 0,
            "runner provenance matcher budget differs")
    original = data.get("files")
    require(isinstance(original, list) and original, "runner provenance has no output pins")
    result: dict[str, dict] = {}
    for pin in original:
        require(isinstance(pin, dict) and set(pin) == {"path", "bytes", "sha256"},
                "runner output pin schema differs")
        path = Path(pin["path"]).resolve(strict=True)
        rel = _relative(run, path)
        require(rel not in result, "duplicate runner output pin: " + rel)
        actual = file_pin(path)
        require(actual == pin, "runner output pin changed: " + rel)
        result[rel] = {"bytes": actual["bytes"], "sha256": actual["sha256"]}
    required = {"pools.jsonl", "shards.jsonl", "pool_observations.jsonl",
                "layer_selections.jsonl", "attempts.jsonl", "progress.jsonl",
                "loaded_modules.json", "training_summary.json"}
    require(required.issubset(result), "runner output pin map misses required evidence")
    return dict(sorted(result.items()))


def write_fresh_json(path: Path, value: dict) -> None:
    path = Path(path).resolve()
    require(not path.exists(), "fresh artifact required: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def reserve(args: argparse.Namespace) -> dict:
    reservation = Path(args.reservation).resolve()
    freeze = Path(args.freeze).resolve(strict=True)
    provenance = Path(args.runner_provenance).resolve(strict=True)
    run = Path(args.run).resolve()
    require(not reservation.exists(), "reservation already exists; no second attempt")
    pins = source_pins()
    # Pin only the manifest itself here; execute mode later verifies every
    # output file named by it.  Reserve-only therefore does not read the run.
    record = {
        "schema": RESERVATION_SCHEMA,
        "runner_schema": RUNNER_SCHEMA,
        "stage": "full_training_numeric_audit",
        "version": 2,
        "fix": "training_audit receipt parent mkdir before GREEN/RED write",
        "policy": "one heavy attempt; preserve failure receipt; no silent rerun",
        "run": str(run),
        "runner_provenance": file_pin(provenance),
        "input_freeze": file_pin(freeze),
        "expected": dict(EXPECTED, layer_status_rows=EXPECTED["arm_layer_rows"]),
        "objects": OBJECTS,
        "claims": {"pools": 41472, "arm_layer_claims": 82944,
                   "classifier": "bounded_classifier_v2_radius4_exact"},
        "budget": BUDGET,
        "auditor": file_pin(AUDITOR),
        "source_pins": pins,
        "output_pin_map": "generated at execute time from runner provenance files[] as run-relative keys",
        "reserved": True,
    }
    write_fresh_json(reservation, record)
    return record


def _load_and_verify_reservation(path: Path, args: argparse.Namespace) -> dict:
    data = _json(path)
    require(data.get("schema") == RESERVATION_SCHEMA and data.get("version") == 2
            and data.get("fix") == "training_audit receipt parent mkdir before GREEN/RED write"
            and data.get("reserved") is True,
            "invalid full-audit reservation")
    require(Path(data["run"]).resolve() == Path(args.run).resolve(), "reservation run differs")
    require(Path(data["runner_provenance"]["path"]).resolve() == Path(args.runner_provenance).resolve(),
            "reservation runner provenance differs")
    require(Path(data["input_freeze"]["path"]).resolve() == Path(args.freeze).resolve(),
            "reservation input freeze differs")
    for pin in data["source_pins"] + [data["runner_provenance"], data["input_freeze"], data["auditor"]]:
        check_pin(pin)
    require(data["budget"] == BUDGET and data["expected"] == dict(EXPECTED, layer_status_rows=EXPECTED["arm_layer_rows"]),
            "reservation budget or coverage changed")
    return data


def execute(args: argparse.Namespace) -> int:
    reservation = Path(args.reservation).resolve(strict=True)
    run = Path(args.run).resolve(strict=True)
    provenance = Path(args.runner_provenance).resolve(strict=True)
    freeze = Path(args.freeze).resolve(strict=True)
    output_pins = Path(args.output_pins).resolve()
    evidence = Path(args.evidence).resolve()
    execution = Path(args.execution).resolve()
    audit_output = evidence / "audit_output"
    receipt = audit_output / "INDEPENDENT_RECEIPT.json"
    runner_receipt = evidence / "RUNNER_RECEIPT.json"
    record = _load_and_verify_reservation(reservation, args)
    for path in (output_pins, evidence, execution, audit_output, receipt, runner_receipt):
        require(not path.exists(), "single-use audit artifact already exists: " + str(path))
    require(not output_pins.is_relative_to(run) and not evidence.is_relative_to(run)
            and not execution.is_relative_to(run),
            "audit evidence/execution must be outside run")
    evidence.mkdir(parents=True, exist_ok=False)
    pins = derive_output_pins(run, provenance)
    write_fresh_json(output_pins, pins)
    output_map_pin = file_pin(output_pins)
    command = [sys.executable, str(AUDITOR), "--run", str(run),
               "--output-pins", str(output_pins),
               "--output-pins-sha256", output_map_pin["sha256"],
               "--freeze", str(freeze), "--freeze-sha256", record["input_freeze"]["sha256"],
               "--receipt", str(receipt)]
    # Import only after reservation and fresh-artifact checks. The child is
    # watched process-wide and receives the exact one-shot resource ceilings.
    if str(EXPERIMENT) not in sys.path:
        sys.path.insert(0, str(EXPERIMENT))
    import execution_guard
    guard = execution_guard.run_guarded(
        command, dict(os.environ), HERE, audit_output, execution,
        maximum_seconds=BUDGET["wall_seconds"],
        maximum_rss_bytes=BUDGET["rss_bytes"],
        maximum_output_bytes=BUDGET["audit_output_bytes"],
        maximum_execution_bytes=BUDGET["execution_log_bytes"],
        minimum_free_bytes=0)
    passed = bool(guard.get("passed")) and receipt.is_file()
    if receipt.is_file():
        try:
            child = _json(receipt)
            passed = passed and child.get("numeric_training_audit_passed") is True
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            passed = False
    if not receipt.is_file():
        write_fresh_json(receipt, {"passed": False, "error": "audit child produced no receipt",
                                   "guard": guard, "real_training_accepted": False})
    final = {
        "schema": RUNNER_SCHEMA,
        "passed": passed,
        "reservation": file_pin(reservation),
        "runner_provenance": file_pin(provenance),
        "input_freeze": file_pin(freeze),
        "output_pin_map": output_map_pin,
        "guard": guard,
        "audit_receipt": file_pin(receipt),
        "source_pins": [file_pin(pin["path"]) for pin in record["source_pins"]],
        "one_shot": True,
        "failure_preserved": not passed,
        # Numeric audit success is still not source/runtime/quality acceptance.
        "real_training_accepted": False,
    }
    write_fresh_json(runner_receipt, final)
    print(json.dumps({"passed": passed, "receipt": str(runner_receipt),
                      "output_pins": str(output_pins)}))
    return 0 if passed else 2


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--runner-provenance", required=True, type=Path)
    parser.add_argument("--freeze", required=True, type=Path)
    parser.add_argument("--reservation", required=True, type=Path)
    parser.add_argument("--output-pins", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--execution", required=True, type=Path)
    parser.add_argument("--reserve-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(arguments)
    require(args.reserve_only ^ args.execute, "choose exactly one of --reserve-only or --execute")
    if args.reserve_only:
        record = reserve(args)
        print(json.dumps({"reserved": True, "reservation": str(Path(args.reservation).resolve()),
                          "source_pin_count": len(record["source_pins"]),
                          "run_opened": False}))
        return 0
    return execute(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"passed": False, "error_type": type(error).__name__,
                          "error": str(error)}), file=sys.stderr)
        raise SystemExit(2)
