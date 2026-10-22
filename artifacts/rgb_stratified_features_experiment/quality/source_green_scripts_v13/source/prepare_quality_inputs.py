"""Prepare the V31 quality-input declaration after independent acceptance.

This preparer only turns already accepted, byte-pinned declarations into the
quality input freeze.  It deliberately refuses to infer successful training
counts or geometry.  In particular, it cannot create a freeze from the
design-only V31 files or from a partial training directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
ROOT = EXPERIMENT.parents[1]
OBJECTS = [1, 2, 5, 8, 12, 17]
ARMS = ["rgb_control", "rgb_pooled_features", "rgb_stratified_features"]
HELDOUT_SCENES = {11, 14, 15, 16, 17, 18, 19, 20}
INHERITED = EXPERIMENT.parent / "rgb_dilated_mask_experiment"
DEFAULT_ACCEPTANCE = HERE / "TRAINING_GEOMETRY_ACCEPTANCE.json"
DEFAULT_OUTPUT = HERE / "QUALITY_INPUT_FREEZE.json"


def _load(name: str):
    path = Path(name)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _require(value, message: str):
    if not value:
        raise ValueError(message)


def _pin(path: Path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}


def _check_pin(pin):
    _require(isinstance(pin, dict) and set(pin) == {"path", "bytes", "sha256"},
             "Complete file pin required")
    _require(Path(pin["path"]).is_file(), "Pinned file is missing: " + str(pin["path"]))
    _require(_pin(pin["path"]) == pin, "Pinned file changed: " + str(pin["path"]))


def _pin_equal(path: Path, expected):
    actual = _pin(path)
    _require(actual == expected, "Acceptance pin does not match " + str(path))


def _unique_pins(pins):
    seen = set()
    result = []
    for pin in pins:
        if pin["path"] not in seen:
            seen.add(pin["path"])
            result.append(pin)
    return result


def _source_imports():
    """Load the sibling contract without creating a repository __pycache__."""
    sys.dont_write_bytecode = True
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import quality_contract as contract  # pylint: disable=import-outside-toplevel
    return contract


def _acceptance(path: Path):
    """Validate the independent training plus geometry acceptance envelope."""
    a = _load(path)
    _require(a.get("schema") in ("rgb_stratified_training_geometry_acceptance_v1",
                                  "rgb_stratified_training_and_geometry_acceptance_v1"),
             "V31 training/geometry acceptance schema is required")
    _require(a.get("accepted_independent_audit") is True,
             "Independent training and geometry acceptance is required")
    _require(a.get("scope") == "training_and_exact_geometry",
             "Acceptance scope must cover training and exact geometry")
    _require(a.get("numeric_audit_passed") is True,
             "Independent training/geometry numeric audit did not pass")
    _require(a.get("production_promotion") is False,
             "Quality experiment cannot promote production")
    for name in ("training_freeze", "geometry_freeze", "independent_audit"):
        _check_pin(a[name])
    return a


def _training_rows(freeze, acceptance_path: Path):
    """Read the explicit three-arm bank rows from the accepted freeze.

    Two equivalent accepted layouts are supported: ``banks`` at the top
    level, or ``banks`` under ``quality``.  Each row must contain real output
    directories and observed successful counts for all three arms.
    """
    rows = freeze.get("banks")
    if rows is None and isinstance(freeze.get("quality"), dict):
        rows = freeze["quality"].get("banks")
    _require(isinstance(rows, list) and len(rows) == len(OBJECTS),
             "Accepted training freeze must enumerate six quality banks")
    by_object = {}
    for raw in rows:
        _require(isinstance(raw, dict), "Malformed accepted bank row")
        obj = int(raw.get("object_id", -1))
        _require(obj in OBJECTS and obj not in by_object, "Unexpected/duplicate accepted object")
        by_object[obj] = raw
    _require(list(by_object) == OBJECTS,
             "Accepted bank order must be [1,2,5,8,12,17]")
    required = ("control_training", "control_template_count",
                "pooled_training", "pooled_template_count",
                "stratified_training", "stratified_template_count")
    result = []
    for obj in OBJECTS:
        row = by_object[obj]
        for name in required:
            _require(name in row, "Accepted bank row omits " + name)
        _require(all(isinstance(row[n], str) for n in
                     ("control_training", "pooled_training", "stratified_training")),
                 "Accepted bank paths must be strings")
        for name in ("control_template_count", "pooled_template_count", "stratified_template_count"):
            _require(type(row[name]) is int and row[name] > 0,
                     "Accepted bank count must be a positive integer")
        result.append({"object_id": obj, **{name: row[name] for name in required}})
    # Do not accept an accidental pointer back to this acceptance file.
    for row in result:
        for name in ("control_training", "pooled_training", "stratified_training"):
            _require(Path(row[name]).resolve() != acceptance_path.resolve(),
                     "Bank directory points at acceptance metadata")
    return result


def _geometry(geometry_freeze):
    plan = geometry_freeze.get("plan", geometry_freeze.get("geometry"))
    _require(isinstance(plan, dict), "Accepted geometry freeze omits plan")
    contract = _source_imports()
    contract.validate_padding(plan)
    return {"width": int(plan["width"]), "height": int(plan["height"]),
            "padding_ltrb": [int(x) for x in plan["padding_ltrb"]],
            "banks": int(plan["banks"]), "geometry_feasible": 1}


def _inherited_declarations():
    """Use only the inherited public schedule and old C0 references.

    V31's new training banks are never inferred from this legacy declaration.
    """
    quality_path = INHERITED / "QUALITY_INPUT_FREEZE.json"
    closure_path = INHERITED / "INPUT_CLOSURE.json"
    _require(quality_path.is_file() and closure_path.is_file(),
             "Inherited schedule/C0 closure is missing")
    quality = _load(quality_path)
    closure = _load(closure_path)
    _require(quality.get("objects") == OBJECTS and len(quality.get("development", [])) == 400,
             "Inherited development schedule must contain exactly 400 frames")
    _require(not ({int(row["scene_id"]) for row in quality["development"]} & HELDOUT_SCENES),
             "Held-out scene leaked into development schedule")
    _require(quality.get("total_matcher_call_budget") == 22176,
             "Inherited declaration is not the frozen V30 schedule")
    return quality, closure, _pin(quality_path), _pin(closure_path)


def build(acceptance_path: Path):
    """Build an input freeze in memory; no output is written on rejection."""
    acceptance = _acceptance(acceptance_path)
    training_path = Path(acceptance["training_freeze"]["path"])
    geometry_path = Path(acceptance["geometry_freeze"]["path"])
    training = _load(training_path)
    geometry = _load(geometry_path)
    banks = _training_rows(training, acceptance_path)
    plan = _geometry(geometry)
    inherited, closure, inherited_quality_pin, inherited_closure_pin = _inherited_declarations()

    inherited_banks = {int(row["object_id"]): row for row in inherited["rgb_banks"]}
    _require(set(inherited_banks) == set(OBJECTS), "Inherited C0 bank scope changed")
    rows = []
    bank_input_files = []
    raw_reference_files = []
    for row in banks:
        obj = row["object_id"]
        old = inherited_banks[obj]
        # The old pilot is deliberately retained as an old-gate reference;
        # common C0 development references are the completed V30 C0 output.
        c0_common = INHERITED / "run_quality_development_v1" / "native" / ("obj" + str(obj)) / "rgb_control"
        for key in ("control_training", "pooled_training", "stratified_training"):
            bank_dir = Path(row[key]).resolve()
            bank_input_files.extend([_pin(bank_dir / "template_metadata.json"),
                                     _pin(bank_dir / ("templates_%s.yml.gz" % old["class_id"]))])
        for frame in inherited["development"]:
            if frame.get("pilot"):
                for suffix in ("fallback", "fused"):
                    prefix = "s%s_i%s_%s_raw" % (frame["scene_id"], frame["image_id"], suffix)
                    for directory in (Path(old["original_pilot_raw"]),
                                      INHERITED / "run_quality_development_v1" / "native" /
                                      ("obj" + str(obj)) / "rgb_control"):
                        raw_reference_files.extend([_pin(directory / (prefix + ".csv.gz")),
                                                    _pin(directory / (prefix + "_manifest.json"))])
            # The common C0 reference is needed for every development frame.
            common = INHERITED / "run_quality_development_v1" / "native" / ("obj" + str(obj)) / "rgb_control"
            for suffix in ("fallback", "fused"):
                prefix = "s%s_i%s_%s_raw" % (frame["scene_id"], frame["image_id"], suffix)
                raw_reference_files.extend([_pin(common / (prefix + ".csv.gz")),
                                            _pin(common / (prefix + "_manifest.json"))])
        rows.append({
            **row,
            "class_id": old["class_id"],
            "original_pilot_raw": old["original_pilot_raw"],
            "c0_common_raw": str(c0_common.resolve()),
        })
    bank_input_files = _unique_pins(bank_input_files)
    raw_reference_files = _unique_pins(raw_reference_files)
    protocol_path = EXPERIMENT / "PROTOCOL.json"
    dataset_index_pin = None
    dataset_index_expected = closure.get("private_files", {}).get("frozen_inputs/dataset_index.json")
    if dataset_index_expected is not None:
        dataset_index = Path(inherited["dataset_root"]) / "index.json"
        dataset_index_pin = _pin(dataset_index)
        _require(dataset_index_pin["sha256"] == dataset_index_expected["sha256"] and
                 dataset_index_pin["bytes"] == dataset_index_expected["bytes"],
                 "Inherited dataset index pin changed")
    frozen_numeric = [
            _pin(Path(acceptance["training_freeze"]["path"])),
            _pin(Path(acceptance["geometry_freeze"]["path"])),
            _pin(Path(acceptance["independent_audit"]["path"])),
            inherited_quality_pin,
            inherited_closure_pin,
            _pin(protocol_path),
        ]
    if dataset_index_pin is not None:
        frozen_numeric.append(dataset_index_pin)
    result = {
        "version": "rgb_stratified_features_quality_inputs_v1",
        "objects": OBJECTS,
        "arms": ARMS,
        "dataset_root": inherited["dataset_root"],
        "development": inherited["development"],
        "banks": rows,
        # Rewritten to a small OpenCV-FileStorage-compatible plan by main();
        # the accepted geometry freeze remains separately pinned below.
        "common_padding_json": "",
        "common_padding_plan": plan,
        "frozen_numeric_files": frozen_numeric,
        "acceptance": acceptance,
        "protocol": _pin(protocol_path),
        "inherited_quality_input_freeze": inherited_quality_pin,
        "inherited_input_closure": inherited_closure_pin,
        "stages": {mode: _source_imports().stage_spec(mode)
                    for mode in _source_imports().CALLS},
        "total_matcher_call_budget": _source_imports().TOTAL_CALLS,
        "preparer": _pin(Path(__file__)),
        "stage_contract": _pin(HERE / "quality_contract.py"),
        "training_image_reads": 0,
        "dataset_image_reads": 0,
        "image_decodes": 0,
        "matcher_calls": 0,
        "status": "declarations_only_pending_native_quality_execution",
        "bank_input_files": bank_input_files,
        "raw_reference_files": raw_reference_files,
    }
    # Retain closure provenance as a digestable declaration, without copying
    # its broad private allowlist into the public quality freeze.
    result["inherited_closure_schema"] = closure.get("version", closure.get("schema"))
    return result


def verify(path: Path = DEFAULT_OUTPUT):
    """Verify an existing quality freeze and every numeric source pin."""
    data = _load(path)
    _require(data.get("version") == "rgb_stratified_features_quality_inputs_v1",
             "Quality input version changed")
    _require(data.get("objects") == OBJECTS and data.get("arms") == ARMS,
             "Quality object/arm scope changed")
    contract = _source_imports()
    _require(data.get("stages") == {mode: contract.stage_spec(mode) for mode in contract.CALLS},
             "Quality schedule changed")
    _require(data.get("total_matcher_call_budget") == contract.TOTAL_CALLS,
             "Quality budget changed")
    contract.validate_padding(data["common_padding_plan"])
    _require(Path(data.get("common_padding_json", "")).is_file(),
             "Common-padding JSON is missing")
    _require(any(pin.get("path") == str(Path(data["common_padding_json"]).resolve())
                for pin in data["frozen_numeric_files"]),
             "Common-padding JSON is not pinned")
    _check_pin(data["preparer"])
    _check_pin(data["stage_contract"])
    _check_pin(data["protocol"])
    for pin in data["frozen_numeric_files"]:
        _check_pin(pin)
    for pin in data.get("bank_input_files", []) + data.get("raw_reference_files", []):
        _check_pin(pin)
    _require(len(data.get("bank_input_files", [])) == 36,
             "Each of six objects and three arms needs two pinned bank files")
    _require(data.get("raw_reference_files"), "Raw reference allowlist is empty")
    _require(len(data.get("development", [])) == 400, "Development schedule is incomplete")
    _require(len(data.get("banks", [])) == len(OBJECTS), "Quality bank declarations incomplete")
    for row in data["banks"]:
        _require(row["object_id"] in OBJECTS, "Unexpected quality bank")
        for name in ("control_training", "pooled_training", "stratified_training"):
            _require(Path(row[name]).is_dir(), "Accepted training bank directory missing: " + row[name])
        for name in ("original_pilot_raw", "c0_common_raw"):
            _require(Path(row[name]).is_dir(), "C0 raw reference directory missing: " + row[name])
    return {"passed": True, "quality_input_freeze": _pin(path),
            "numeric_pins": len(data["frozen_numeric_files"]),
            "image_decodes": 0, "matcher_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    _require(args.create or args.verify, "Choose --create or --verify")
    if args.create:
        _require(not args.output.exists(), "Preserve an existing quality input freeze")
        data = build(args.acceptance)
        plan_path = args.output.parent / "COMMON_PADDING_FREEZE.json"
        _require(not plan_path.exists(), "Preserve an existing common-padding freeze")
        plan_path.write_text(json.dumps(data["common_padding_plan"], indent=2) + "\n", encoding="utf-8")
        data["common_padding_json"] = str(plan_path.resolve())
        data["frozen_numeric_files"].append(_pin(plan_path))
        args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    result = verify(args.output)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
