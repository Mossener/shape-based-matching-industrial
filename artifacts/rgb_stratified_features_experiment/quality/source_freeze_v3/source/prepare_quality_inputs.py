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
VERSION = "rgb_stratified_quality_inputs_v1"
HELDOUT_SCENES = {11, 14, 15, 16, 17, 18, 19, 20}
INHERITED = EXPERIMENT.parent / "rgb_dilated_mask_experiment"
INHERITED_QUALITY_SHA256 = "9659c119fa7c64dbd673d49397cc0b7dc86ef573aa4530a329fbc4da52f1ace6"
INHERITED_CLOSURE_SHA256 = "9f0a6fd135716495cb51cde6918a022fd6514e2177941cd453ff6eb19a83f2ff"
# Original accepted pin from V30 QUALITY_AUDIT_ACCEPTANCE_V30.json, itself
# pinned by V30_COMPLETION_RECORD (SHA256 7ba43d02f3675e01c0ed08a0893fb6295e6e6ef957b697a340ee6dd4295dc470).
INHERITED_DEVELOPMENT_SHA256 = "c3073775ffea2c9f4a1d0058b2e1e884d7bcde9c97590a8cd6459063d03d0b88"
INHERITED_DEVELOPMENT_BYTES = 5825410
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
    audit = _load(a["independent_audit"]["path"])
    _require(audit.get("passed") is True and
             audit.get("schema") == "independent_stratified_training_geometry_audit_v1" and
             audit.get("scope") == "training_and_exact_geometry",
             "Pinned independent training/geometry report did not pass")
    audit_inputs = _audit_input_map(audit.get("input_pins"))
    for key in ("training_freeze", "geometry_freeze"):
        _require(audit_inputs.get(a[key]["path"]) == a[key],
                 "Combined independent report does not bind exact " + key)
    return a


def _audit_input_map(records):
    if isinstance(records, dict):
        count = len(records)
        records = [dict(path=name, **{key: value[key] for key in ("bytes", "sha256")})
                   for name, value in records.items()
                   if isinstance(value, dict) and value.get("path", name) == name and
                   set(value) in ({"bytes", "sha256"}, {"path", "bytes", "sha256"})]
        # Malformed dict members must not silently disappear.
        _require(len(records) == count and count > 0, "Malformed combined audit input pins")
    return _pin_map(records)


def _pin_map(records):
    """Validate an explicit member allowlist before opening any member."""
    contract = _source_imports()
    result = {}
    _require(isinstance(records, list), "Accepted file allowlist is missing")
    for pin in records:
        contract.validate_pin(pin)
        _require(Path(pin["path"]).is_absolute(), "Accepted member path must be absolute")
        name = str(Path(pin["path"]).resolve())
        _require(name == pin["path"] and name not in result, "Noncanonical/duplicate accepted member")
        result[name] = pin
    return result


def _accepted_file(path, expected, check_payloads):
    name = str(Path(path).resolve())
    _require(name in expected, "Required payload is absent from accepted allowlist: " + name)
    pin = expected[name]
    if check_payloads:
        _check_pin(pin)
    return dict(pin)


def _inherited_file_map(closure):
    base = Path(closure["inherited_frozen_root"]).resolve()
    result = {}
    for relative, record in closure["private_files"].items():
        member = Path(relative)
        _require(not member.is_absolute() and ".." not in member.parts, "Unsafe inherited member")
        result[str((base / member).resolve())] = dict(path=str((base / member).resolve()), **record)
    return _pin_map(list(result.values()))


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
        obj = raw.get("object_id")
        _require(type(obj) is int, "Accepted object id must be an integer")
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
        _require(all(Path(row[n]).is_absolute() for n in
                     ("control_training", "pooled_training", "stratified_training")),
                 "Accepted bank paths must be absolute")
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


def _training_file_pins(training, rows):
    """Consume the accepted geometry declaration's explicit 18 bank groups."""
    if training.get("schema") != "rgb_stratified_geometry_inputs_v1":
        # An older independently accepted declaration may use a flat pin list.
        return list(_pin_map(training.get("files")).values())
    groups = training.get("bank_files")
    _require(isinstance(groups, list) and len(groups) == 18,
             "Accepted geometry input must list all 18 bank groups")
    expected = [(row, arm, key) for row in rows for arm, key in
                (("C0", "control"), ("P", "pooled"), ("B", "stratified"))]
    pins = []
    for group, (row, arm, key) in zip(groups, expected):
        _require(set(group) == {"arm", "object_id", "bank", "metadata"} and
                 group["arm"] == arm and type(group["object_id"]) is int and
                 group["object_id"] == row["object_id"], "Accepted bank group/order changed")
        directory = Path(row[key + "_training"]).resolve()
        for kind, name in (("metadata", "template_metadata.json"),
                           ("bank", "templates_tless_object_%s.yml.gz" % row["object_id"])):
            _source_imports().validate_pin(group[kind])
            _require(group[kind]["path"] == str(directory / name),
                     "Accepted bank file/directory binding changed")
            pins.append(group[kind])
    return list(_pin_map(pins).values())


def _training_numeric_pins(training):
    if training.get("schema") != "rgb_stratified_geometry_inputs_v1":
        return []
    _require(training.get("production_promotion") is False,
             "Geometry declaration cannot promote production")
    pins = [training[key] for key in ("source_numeric_audit", "training_execution_acceptance",
                                     "inherited_control_closure", "source")]
    originals = training.get("original_attempts")
    _require(isinstance(originals, list) and
             [row.get("object_id") for row in originals] == OBJECTS,
             "Geometry original-attempt closure differs")
    pins += [row["file"] for row in originals]
    for pin in pins:
        _source_imports().validate_pin(pin)
        _check_pin(pin)
    _require(training["inherited_control_closure"]["sha256"] == INHERITED_CLOSURE_SHA256,
             "Geometry inherited C0 origin differs")
    joined = _load(training["training_execution_acceptance"]["path"])
    _require(joined.get("schema") == "rgb_stratified_training_execution_acceptance_v1" and
             all(joined.get(key) is True for key in
                 ("real_training_accepted", "source_runtime_accepted", "numeric_audit_passed")) and
             joined.get("production_promotion") is False and
             joined.get("independent_audit") == training["source_numeric_audit"],
             "Geometry declaration lacks joined real-training acceptance")
    for key in ("independent_runner", "training_provenance", "source"):
        _source_imports().validate_pin(joined[key]);_check_pin(joined[key]);pins.append(joined[key])
    return _unique_pins(pins)


def _geometry(geometry_freeze):
    _require(geometry_freeze.get("passed", True) is True, "Accepted geometry freeze is incomplete")
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
    _require(_pin(quality_path)["sha256"] == INHERITED_QUALITY_SHA256 and
             _pin(closure_path)["sha256"] == INHERITED_CLOSURE_SHA256,
             "Inherited schedule/C0 origin changed")
    quality = _load(quality_path)
    closure = _load(closure_path)
    _require(quality.get("objects") == OBJECTS and len(quality.get("development", [])) == 400,
             "Inherited development schedule must contain exactly 400 frames")
    _require(not ({int(row["scene_id"]) for row in quality["development"]} & HELDOUT_SCENES),
             "Held-out scene leaked into development schedule")
    _require(quality.get("total_matcher_call_budget") == 22176,
             "Inherited declaration is not the frozen V30 schedule")
    common_stage_path = INHERITED / "run_quality_development_v1" / "QUALITY_STAGE_FREEZE.json"
    common_stage_pin = _pin(common_stage_path)
    _require(common_stage_pin["sha256"] == INHERITED_DEVELOPMENT_SHA256 and
             common_stage_pin["bytes"] == INHERITED_DEVELOPMENT_BYTES,
             "Accepted V30 common-padding development stage origin changed")
    common_stage = _load(common_stage_path)
    _require(common_stage.get("completed") is True and common_stage.get("stage") == "development" and
             common_stage.get("native_exit_code") == 0 and common_stage.get("actual_matcher_calls") == 9600,
             "Complete V30 common-padding development reference is required")
    return quality, closure, _pin(quality_path), _pin(closure_path), common_stage, common_stage_pin


def build(acceptance_path: Path, check_payloads=True):
    """Build an input freeze in memory; no output is written on rejection."""
    acceptance = _acceptance(acceptance_path)
    training_path = Path(acceptance["training_freeze"]["path"])
    geometry_path = Path(acceptance["geometry_freeze"]["path"])
    training = _load(training_path)
    geometry = _load(geometry_path)
    banks = _training_rows(training, acceptance_path)
    plan = _geometry(geometry)
    inherited, closure, inherited_quality_pin, inherited_closure_pin, common_stage, common_stage_pin = _inherited_declarations()
    _source_imports().validate_frames(inherited["development"])
    new_files = _pin_map(_training_file_pins(training, banks))
    training_numeric = _training_numeric_pins(training)
    inherited_files = _inherited_file_map(closure)
    common_files = _pin_map(common_stage.get("files"))

    inherited_banks = {int(row["object_id"]): row for row in inherited["rgb_banks"]}
    _require(set(inherited_banks) == set(OBJECTS), "Inherited C0 bank scope changed")
    rows = []
    bank_input_files = []
    raw_reference_files = []
    for row in banks:
        obj = row["object_id"]
        old = inherited_banks[obj]
        _require(Path(row["control_training"]).resolve() == Path(old["rgb_training"]).resolve() and
                 row["control_template_count"] == old["rgb_template_count"],
                 "Accepted C0 directory/count differs from frozen inherited control")
        # The old pilot is deliberately retained as an old-gate reference;
        # common C0 development references are the completed V30 C0 output.
        c0_common = INHERITED / "run_quality_development_v1" / "native" / ("obj" + str(obj)) / "rgb_control"
        for key in ("control_training", "pooled_training", "stratified_training"):
            bank_dir = Path(row[key]).resolve()
            expected = inherited_files if key == "control_training" else new_files
            if key == "control_training" and training.get("schema") == "rgb_stratified_geometry_inputs_v1":
                for filename in ("template_metadata.json", "templates_%s.yml.gz" % old["class_id"]):
                    name = str(bank_dir / filename)
                    _require(new_files.get(name) == inherited_files.get(name),
                             "Geometry C0 bank pin differs from inherited origin")
            bank_input_files.extend([_accepted_file(bank_dir / "template_metadata.json", expected, check_payloads),
                                     _accepted_file(bank_dir / ("templates_%s.yml.gz" % old["class_id"]), expected, check_payloads)])
        for frame in inherited["development"]:
            if frame.get("pilot"):
                for suffix in ("fallback", "fused"):
                    prefix = "s%s_i%s_%s_raw" % (frame["scene_id"], frame["image_id"], suffix)
                    directory = Path(old["original_pilot_raw"])
                    raw_reference_files.extend([_accepted_file(directory / (prefix + ".csv.gz"), inherited_files, check_payloads),
                                                _accepted_file(directory / (prefix + "_manifest.json"), inherited_files, check_payloads)])
            # The common C0 reference is needed for every development frame.
            common = INHERITED / "run_quality_development_v1" / "native" / ("obj" + str(obj)) / "rgb_control"
            for suffix in ("fallback", "fused"):
                prefix = "s%s_i%s_%s_raw" % (frame["scene_id"], frame["image_id"], suffix)
                raw_reference_files.extend([_accepted_file(common / (prefix + ".csv.gz"), common_files, check_payloads),
                                            _accepted_file(common / (prefix + "_manifest.json"), common_files, check_payloads)])
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
            common_stage_pin,
            _pin(protocol_path),
            _pin(acceptance_path),
        ] + training_numeric
    if dataset_index_pin is not None:
        frozen_numeric.append(dataset_index_pin)
    result = {
        "version": VERSION,
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
        "acceptance_pin": _pin(acceptance_path),
        "inherited_c0_development_stage": common_stage_pin,
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
    _require(data.get("version") == VERSION,
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
    _require(len(data.get("bank_input_files", [])) == 36,
             "Each of six objects and three arms needs two pinned bank files")
    _require(data.get("raw_reference_files"), "Raw reference allowlist is empty")
    _require(len(data.get("development", [])) == 400, "Development schedule is incomplete")
    _require(len(data.get("banks", [])) == len(OBJECTS), "Quality bank declarations incomplete")
    _check_pin(data["acceptance_pin"])
    expected = build(Path(data["acceptance_pin"]["path"]), check_payloads=False)
    plan_path = Path(path).resolve().parent / "COMMON_PADDING_FREEZE.json"
    _require(Path(data["common_padding_json"]).resolve() == plan_path,
             "Normalized common-padding path changed")
    _require(_load(plan_path) == expected["common_padding_plan"], "Normalized common-padding content changed")
    expected["common_padding_json"] = str(plan_path)
    expected["frozen_numeric_files"].append(_pin(plan_path))
    _require(data == expected, "Quality declarations differ from accepted sources")
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
