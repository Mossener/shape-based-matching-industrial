"""Create and verify RGB dilated-mask quality inputs without image reads."""
import argparse
import hashlib
import json
from pathlib import Path

import native_provenance as p
import prepare_input_closure as inherited
import quality_contract as contract

HERE = Path(__file__).resolve().parent
PROTOCOL_SHA = "ee313755ba5fad4311e7f2d80ffcb0fc1277c878cf1735a0d1a92b0b99635b6f"
OBJECTS = [1, 2, 5, 8, 12, 17]
DEST = HERE / "QUALITY_INPUT_FREEZE.json"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build():
    closure = read(HERE / "INPUT_CLOSURE.json")
    bank = read(HERE / "run_training_v1" / "BANK_FREEZE.json")
    plan = read(HERE / "run_plan_v1" / "COMMON_PADDING_FREEZE.json")
    p.require(closure["version"] == "rgb_dilated_mask_input_closure_v1", "RGB input closure changed")
    p.require(closure["protocol_sha256"] == PROTOCOL_SHA, "RGB protocol pin changed")
    p.require(bank["native_exit_zero"] and bank["comparison_feasible"] and bank["training_attempts_complete"], "Training freeze is incomplete")
    p.require(bank["attempts"] == 20736 and bank["objects"] == OBJECTS, "Training scope changed")
    p.require(plan["passed"] and plan["plan"]["width"] == 848 and plan["plan"]["height"] == 832, "Strict common geometry gate failed")
    p.require(plan["plan"]["padding_ltrb"] == [64, 64, 64, 228], "Common padding changed")
    inherited.verify()
    p.require(bank.get("accepted_independent_audit") is True and plan.get("accepted_independent_audit") is True, "Independent training and plan acceptance required")
    counts = bank["successful_templates"]
    rows = []
    for item in closure["rgb_banks"]:
        obj = int(item["object_id"])
        p.require(obj in OBJECTS, "Unexpected quality object")
        row = dict(item)
        row["treatment_training"] = str(HERE / "run_training_v1" / f"obj{obj}")
        row["treatment_template_count"] = int(counts[str(obj)])
        rows.append(row)
    numeric = [p.file_pin(HERE / "run_training_v1" / "BANK_FREEZE.json"),
               p.file_pin(HERE / "run_plan_v1" / "COMMON_PADDING_FREEZE.json"),
               p.file_pin(HERE / "run_training_v1" / "training_audit.json"),
               p.file_pin(HERE / "run_plan_v1" / "plan_audit.json")]
    return dict(version="rgb_dilated_mask_quality_inputs_v1", objects=OBJECTS,
                dataset_root=closure["dataset_root"], development=closure["development"],
                rgb_banks=rows, common_padding_json=str(HERE / "run_plan_v1" / "common_padding_plan.json"),
                frozen_numeric_files=numeric, protocol_sha256=PROTOCOL_SHA,
                inherited_input_closure_sha256=sha256(HERE / "INPUT_CLOSURE.json"),
                stages={mode: contract.stage_spec(mode) for mode in contract.CALLS},
                total_matcher_call_budget=sum(contract.CALLS.values()),
                preparer=p.file_pin(Path(__file__)), stage_contract=p.file_pin(HERE / "quality_contract.py"),
                training_and_plan_build_sources_unchanged=True, dataset_image_reads=0,
                image_decodes=0, matcher_calls=0)


def verify():
    result = read(DEST)
    p.require(result["version"] == "rgb_dilated_mask_quality_inputs_v1", "Quality input version changed")
    p.require(result["objects"] == OBJECTS and result["total_matcher_call_budget"] == 22176, "Quality scope/budget changed")
    p.require(result["stages"] == {mode: contract.stage_spec(mode) for mode in contract.CALLS}, "Quality schedule changed")
    p.check_pin(result["preparer"]); p.check_pin(result["stage_contract"])
    for pin in result["frozen_numeric_files"]: p.check_pin(pin)
    inherited.verify()
    return dict(passed=True, quality_input_freeze=p.file_pin(DEST), numeric_pins=len(result["frozen_numeric_files"]), image_decodes=0, matcher_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.create:
        DEST.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    result = verify()
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
