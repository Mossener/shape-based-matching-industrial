"""Run one reserved V31 quality stage with fail-closed provenance gates."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent


def _modules():
    sys.dont_write_bytecode = True
    for path in (HERE, EXPERIMENT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import native_provenance as provenance  # pylint: disable=import-outside-toplevel
    import prepare_quality_inputs as inputs  # pylint: disable=import-outside-toplevel
    import quality_contract as contract  # pylint: disable=import-outside-toplevel
    import quality_execution_inputs as execution_inputs  # pylint: disable=import-outside-toplevel
    return provenance, inputs, contract, execution_inputs


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _require(value, message):
    if not value:
        raise ValueError(message)


def build_gate(path, provenance, source_manifest):
    manifest = _load(path)
    _require(manifest.get("passed") is True and
             manifest.get("target") == "rgb_stratified_quality" and
             manifest.get("core_revision") == source_manifest["git_revision"] and
             manifest.get("actual_core") == str(EXPERIMENT / "control_v11" / "line2Dup.cpp"),
             "Actual separate V31 quality build is required")
    _require(len(manifest.get("commands", [])) == 5 and
             all(c.get("exit_code") == 0 for c in manifest["commands"]),
             "V31 build command closure is incomplete")
    _require([u["source"] for u in manifest.get("dependency_units", [])] ==
             [str(EXPERIMENT / "control_v11" / "line2Dup.cpp"), str(HERE / "quality_eval.cpp")],
             "V31 translation-unit closure changed")
    _require(Path(manifest["executable"]["path"]).name == "quality_eval.exe",
             "V31 executable name changed")
    pins = (manifest["project_sources"] + manifest["compiler_tools_and_link_libraries"] +
            manifest["compiler_runtime_closure"]["files"] + manifest["executable_runtime_closure"]["files"] +
            [manifest["executable"]])
    for unit in manifest["dependency_units"]:
        pins += unit["dependencies"] + [unit["object"], unit["dependency_file"]]
    for pin in pins:
        provenance.check_pin(pin)
    return manifest, provenance.file_pin(path)


def stage_gate(run, expected, build_pin, input_pin, contract, provenance):
    run = Path(run).resolve(strict=True)
    _require(run.is_relative_to(HERE), "Previous stage must belong to V31 quality")
    freeze_file = run / "QUALITY_STAGE_FREEZE.json"
    manifest = _load(freeze_file)
    _require(manifest.get("completed") is True and manifest.get("stage") == expected and
             manifest.get("native_exit_code") == 0 and
             manifest.get("actual_matcher_calls") == (0 if expected == "selftest" else contract.CALLS[expected]) and
             manifest.get("build_manifest") == build_pin and
             manifest.get("quality_inputs") == input_pin,
             "Previous V31 stage completion/source/budget gate differs")
    for pin in manifest.get("files", []) + manifest.get("execution_files", []):
        provenance.check_pin(pin)
    native = run / "native"
    expected_files = {record["path"] for record in manifest.get("files", [])}
    actual = {str(path.resolve()) for path in native.rglob("*")
              if path.is_file() and path.name != ".gitignore"}
    _require(actual == expected_files, "Previous complete native output member set changed")
    if manifest.get("reservation"):
        provenance.check_pin(manifest["reservation"])
    return manifest, provenance.file_pin(freeze_file)


def _quality_audit_gate(path, development_pin, contract):
    data = _load(path)
    contract.validate_quality_acceptance(data, development_pin)
    return data


def main():
    provenance, inputs, contract, execution_inputs = _modules()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("selftest", *contract.CALLS), required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selftest-run", type=Path)
    parser.add_argument("--previous-run", type=Path)
    parser.add_argument("--quality-audit", type=Path, default=HERE / "QUALITY_AUDIT_ACCEPTANCE.json")
    parser.add_argument("--cpu-slot-granted", action="store_true")
    args = parser.parse_args()
    _require(args.cpu_slot_granted, "Await coordinated native quality CPU slot")
    run = args.output.resolve()
    _require(run.is_relative_to(HERE) and not run.exists(), "Quality run directory must be fresh")
    run.mkdir(parents=True)
    native = run / "native"
    native.mkdir()
    (native / ".gitignore").write_text("*\n", encoding="utf-8")
    native_exit = None
    reservation_pin = None
    post_valid = False
    actual_calls = None
    try:
        source_manifest = _load(EXPERIMENT / "TRAINING_SOURCE_FREEZE.json")
        build, build_pin = build_gate(args.build_manifest, provenance, source_manifest)
        input_path = HERE / "QUALITY_INPUT_FREEZE.json"
        input_pin = provenance.file_pin(input_path)
        inputs.verify(input_path)
        script_pins = [provenance.file_pin(HERE / name) for name in
                       ("run_quality.py", "quality_contract.py", "prepare_quality_inputs.py",
                        "quality_execution_inputs.py", "build_quality.py", "quality_eval.cpp",
                        "quality_support.hpp")]
        previous_pin = None
        selftest_pin = None
        previous = None
        if args.mode != "selftest":
            _require(args.selftest_run is not None, "Native selftest must complete first")
            _, selftest_pin = stage_gate(args.selftest_run, "selftest", build_pin, input_pin,
                                          contract, provenance)
            expected = contract.PREVIOUS[args.mode]
            if expected:
                _require(args.previous_run is not None, "Fixed previous stage is required")
                _, previous_pin = stage_gate(args.previous_run, expected, build_pin, input_pin,
                                             contract, provenance)
                previous = Path(args.previous_run).resolve()
            else:
                _require(args.previous_run is None, "Original-padding gate has no previous stage")
            contract.reserve(HERE / "quality_stage_reservations", args.mode, run, previous_pin)
            reservation_pin = provenance.file_pin(HERE / "quality_stage_reservations" / (args.mode + ".json"))
        else:
            _require(args.selftest_run is None and args.previous_run is None,
                     "Selftest cannot depend on a matching stage")
        # Timing is only a measurement of the fixed candidate after an
        # independent all-three-arms numeric audit. Accuracy failure remains a
        # recorded outcome and never becomes a promotion signal.
        if args.mode == "timing":
            _require(previous_pin is not None, "Timing requires the complete development stage")
            _quality_audit_gate(args.quality_audit, previous_pin, contract)
        before = inputs.verify(input_path)
        image_before = execution_inputs.verify(args.mode, input_path)
        (run / "verified_before.json").write_text(json.dumps({"inputs": before, "images": image_before}, indent=2) + "\n", encoding="utf-8")
        command = [build["executable"]["path"], "--mode", args.mode,
                   "--output", str(native), "--inputs", str(input_path)]
        if previous:
            command += ["--previous", str(previous / "native")]
        env = dict(os.environ)
        env["PATH"] = str(Path(build["compiler"]).parent) + ";" + str(Path(build["opencv"]) / "build/bin") + ";" + env.get("PATH", "")
        execution = {"command": command, "mode": args.mode, "build_manifest": build_pin,
                     "quality_inputs": input_pin, "selftest": selftest_pin,
                     "previous_stage": previous_pin, "reservation": reservation_pin,
                     "script_pins": script_pins, "native_exit_code": None,
                     "maximum_matcher_calls": 0 if args.mode == "selftest" else contract.CALLS[args.mode]}
        (run / "execution_provenance.json").write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")
        with (run / "native.stdout").open("wb") as stdout, (run / "native.stderr").open("wb") as stderr:
            process = subprocess.run(command, cwd=HERE, env=env, stdout=stdout, stderr=stderr)
        native_exit = process.returncode
        execution["native_exit_code"] = native_exit
        (run / "execution_provenance.json").write_text(json.dumps(execution, indent=2) + "\n", encoding="utf-8")
        after = inputs.verify(input_path)
        image_after = execution_inputs.verify(args.mode, input_path)
        _require(before == after and image_before == image_after,
                 "Input verification scope changed during quality stage")
        build_gate(args.build_manifest, provenance, source_manifest)
        provenance.check_pin(build_pin)
        provenance.check_pin(input_pin)
        for pin in script_pins:
            provenance.check_pin(pin)
        if selftest_pin:
            stage_gate(args.selftest_run, "selftest", build_pin, input_pin, contract, provenance)
        if previous_pin:
            stage_gate(previous, contract.PREVIOUS[args.mode], build_pin, input_pin, contract, provenance)
        if reservation_pin:
            provenance.check_pin(reservation_pin)
        (run / "verified_after.json").write_text(json.dumps({"inputs": after, "images": image_after}, indent=2) + "\n", encoding="utf-8")
        post_valid = True
        summary_path = native / ("selftest_result.json" if args.mode == "selftest" else "stage_summary.json")
        summary = _load(summary_path) if summary_path.exists() else None
        failure = _load(native / "failure.json") if (native / "failure.json").exists() else None
        actual_calls = summary.get("matcher_calls") if summary else failure.get("matcher_invocations_started") if failure else None
        completed = bool(native_exit == 0 and summary and summary.get("passed") == 1 and
                         actual_calls == (0 if args.mode == "selftest" else contract.CALLS[args.mode]))
        files = [provenance.file_pin(path) for path in sorted(native.rglob("*"))
                 if path.is_file() and path.name != ".gitignore"]
        execution_files = [provenance.file_pin(path) for path in sorted(run.iterdir()) if path.is_file()]
        freeze = {"stage": args.mode, "completed": completed, "native_exit_code": native_exit,
                  "actual_matcher_calls": actual_calls,
                  "maximum_matcher_calls": 0 if args.mode == "selftest" else contract.CALLS[args.mode],
                  "build_manifest": build_pin, "quality_inputs": input_pin,
                  "selftest": selftest_pin, "previous_stage": previous_pin,
                  "reservation": reservation_pin, "files": files,
                  "execution_files": execution_files, "summary": summary,
                  "post_verification_passed": post_valid,
                  "missing_frames_are_not_negatives": True, "heldout_images_allowed": False}
        (run / "QUALITY_STAGE_FREEZE.json").write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
        _require(completed, "Native quality stage incomplete; partial evidence was preserved")
        print(json.dumps({"passed": True, "stage": args.mode, "matcher_calls": actual_calls,
                          "heldout_images_read": 0}))
    except Exception as error:
        (run / "failure.json").write_text(json.dumps({
            "incomplete": True, "reason": str(error), "native_exit_code": native_exit,
            "post_verification_passed": post_valid, "actual_matcher_calls": actual_calls,
            "reservation": reservation_pin, "missing_frames_are_not_negatives": True,
            "do_not_silently_rerun_reserved_stage": True,
        }, indent=2) + "\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
