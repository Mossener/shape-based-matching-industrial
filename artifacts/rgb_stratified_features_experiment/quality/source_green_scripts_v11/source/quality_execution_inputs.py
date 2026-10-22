"""Verify the byte allowlist for one fixed V31 quality stage.

Verification reads only pinned metadata, bank payloads and scheduled image
bytes after an accepted input freeze exists.  It does not decode images or
invoke the native matcher.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
OBJECTS = [1, 2, 5, 8, 12, 17]
HELDOUT_SCENES = {11, 14, 15, 16, 17, 18, 19, 20}


def _modules():
    sys.dont_write_bytecode = True
    for path in (HERE, EXPERIMENT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    import native_provenance as provenance  # pylint: disable=import-outside-toplevel
    import prepare_quality_inputs as declarations  # pylint: disable=import-outside-toplevel
    return provenance, declarations


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _require(value, message):
    if not value:
        raise ValueError(message)


def _checked(pin, observed, provenance):
    provenance.check_pin(pin)
    observed.append(pin)


def _closure(data, provenance):
    pin = data["inherited_input_closure"]
    provenance.check_pin(pin)
    closure_path = Path(pin["path"])
    _require(closure_path.name == "INPUT_CLOSURE.json" and closure_path.is_file(),
             "Inherited input closure path changed")
    return _load(closure_path), closure_path


def verify(mode, quality_path=None):
    _require(mode in ("selftest", "old_gate", "pilot", "development", "timing"),
             "Unknown fixed quality stage")
    provenance, declarations = _modules()
    quality_path = Path(quality_path or HERE / "QUALITY_INPUT_FREEZE.json")
    result = declarations.verify(quality_path)
    data = _load(quality_path)
    closure, closure_path = _closure(data, provenance)
    _require(data["objects"] == OBJECTS and len(data["development"]) == 400,
             "Quality scope changed")
    _require(not ({int(frame["scene_id"]) for frame in data["development"]} & HELDOUT_SCENES),
             "Held-out scene leaked into quality stage")
    observed = []
    for pin in data["frozen_numeric_files"]:
        _checked(pin, observed, provenance)

    # The accepted training/geometry pins are checked as a complete closure.
    acceptance = data["acceptance"]
    _require(acceptance.get("accepted_independent_audit") is True and
             acceptance.get("scope") == "training_and_exact_geometry",
             "Missing accepted training/geometry audit")
    for name in ("training_freeze", "geometry_freeze", "independent_audit"):
        _checked(acceptance[name], observed, provenance)

    required = set()
    declared = {}
    for pin in data.get("bank_input_files", []) + data.get("raw_reference_files", []):
        _require(pin["path"] not in declared, "Duplicate quality input pin")
        declared[pin["path"]] = pin
    for bank in data["banks"]:
        obj = int(bank["object_id"])
        _require(obj in OBJECTS, "Unexpected quality bank")
        class_id = str(bank["class_id"])
        for arm, key in (("rgb_control", "control_training"),
                         ("rgb_pooled_features", "pooled_training"),
                         ("rgb_stratified_features", "stratified_training")):
            directory = Path(bank[key]).resolve()
            _require(directory.is_dir(), "Quality bank directory is missing: " + str(directory))
            expected_count = int(bank[arm.replace("rgb_", "") + "_template_count"])
            # The template metadata and serialized detector bank are the only
            # files the native loader is allowed to consume from a bank.
            required.add((directory / "template_metadata.json", None))
            required.add((directory / ("templates_%s.yml.gz" % class_id), None))
            _require(expected_count > 0, "Quality bank count must be positive")
        if mode == "old_gate":
            raw = Path(bank["original_pilot_raw"]).resolve()
            _require(raw.is_dir(), "Old-pilot raw directory is missing")
            for frame in data["development"]:
                if frame.get("pilot"):
                    for path in ("fallback", "fused"):
                        prefix = "s%s_i%s_%s_raw" % (frame["scene_id"], frame["image_id"], path)
                        required.add((raw / (prefix + ".csv.gz"), None))
                        required.add((raw / (prefix + "_manifest.json"), None))
        if mode in ("pilot", "development", "timing"):
            common = Path(bank["c0_common_raw"]).resolve()
            _require(common.is_dir(), "C0 common raw directory is missing")
            for frame in data["development"]:
                use = mode == "development" or (mode == "timing" and frame.get("timing")) or (mode == "pilot" and frame.get("pilot"))
                if use:
                    for path in ("fallback", "fused"):
                        prefix = "s%s_i%s_%s_raw" % (frame["scene_id"], frame["image_id"], path)
                        required.add((common / (prefix + ".csv.gz"), None))
                        required.add((common / (prefix + "_manifest.json"), None))

    for path, _ in sorted(required, key=lambda item: str(item[0])):
        path = path.resolve()
        _require(str(path) in declared, "Unlisted quality input: " + str(path))
        _checked(declared[str(path)], observed, provenance)

    dataset = Path(data["dataset_root"]).resolve()
    index_pin = next((pin for pin in data.get("frozen_numeric_files", [])
                      if Path(pin["path"]).name == "index.json"), None)
    if index_pin is not None:
        _checked(index_pin, observed, provenance)
    images = []
    if mode != "selftest":
        wanted = (400 if mode == "development" else 64 if mode == "timing" else 8)
        for frame in data["development"]:
            use = mode == "development" or (mode == "timing" and frame.get("timing")) or (mode == "pilot" and frame.get("pilot"))
            if use:
                pin = {"path": str((dataset / frame["rgb"]).resolve()),
                       "sha256": frame["rgb_sha256"], "bytes": frame["rgb_bytes"]}
                _checked(pin, observed, provenance)
                images.append(pin)
        _require(len(images) == wanted, "Quality image verification schedule changed")
    else:
        _require(not images, "Selftest must not verify dataset images")
    return {"passed": True, "stage": mode, "pins": observed,
            "image_byte_files_checked": len(images), "image_decodes": 0,
            "matcher_calls": 0, "training_image_files_checked": 0,
            "heldout_images_checked": 0}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("selftest", "old_gate", "pilot", "development", "timing"), required=True)
    parser.add_argument("--quality-inputs", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.mode, args.quality_inputs)))


if __name__ == "__main__":
    main()
