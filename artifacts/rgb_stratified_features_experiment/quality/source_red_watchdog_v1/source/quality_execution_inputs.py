"""Verify the byte allowlist for one fixed V31 quality stage.

Verification reads only pinned metadata, bank payloads and scheduled image
bytes after an accepted input freeze exists.  It does not decode images or
invoke the native matcher.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import quality_contract as contract

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


def selected_frames(mode, rows):
    _require(mode in ('selftest','old_gate','pilot','development','timing'),'Unknown fixed quality stage')
    if mode=='selftest':return []
    contract.validate_frames(rows)
    if mode=='development':return list(rows)
    flag='timing' if mode=='timing' else 'pilot'
    return [frame for frame in rows if frame[flag]]


def required_payload_paths(mode, data):
    _require(mode in ('selftest','old_gate','pilot','development','timing'),'Unknown fixed quality stage')
    if mode=='selftest':return []
    frames=selected_frames(mode,data['development']);required=[]
    for bank in data['banks']:
        obj=bank['object_id'];_require(obj in OBJECTS,'Unexpected quality object')
        specs=[('control_training','control_template_count')]
        if mode!='old_gate':specs += [('pooled_training','pooled_template_count'),('stratified_training','stratified_template_count')]
        for directory_key,count_key in specs:
            _require(type(bank[count_key]) is int and bank[count_key]>0,'Observed positive template count required')
            directory=Path(bank[directory_key])
            required += [directory/'template_metadata.json',directory/('templates_%s.yml.gz'%bank['class_id'])]
        if mode in ('old_gate','pilot','development'):
            directory=Path(bank['original_pilot_raw'] if mode=='old_gate' else bank['c0_common_raw'])
            for frame in frames:
                for path_name in ('fallback','fused'):
                    prefix=f's{frame["scene_id"]}_i{frame["image_id"]}_{path_name}_raw'
                    required += [directory/(prefix+'.csv.gz'),directory/(prefix+'_manifest.json')]
    return sorted(set(required),key=str)


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

    required = required_payload_paths(mode,data)
    declared = {}
    for pin in data.get("bank_input_files", []) + data.get("raw_reference_files", []):
        _require(pin["path"] not in declared, "Duplicate quality input pin")
        declared[pin["path"]] = pin
    for path in required:
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
        for frame in selected_frames(mode,data['development']):
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
