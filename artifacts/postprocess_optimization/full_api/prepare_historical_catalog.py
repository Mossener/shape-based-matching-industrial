"""Freeze25 historical manifest/trace/reference pins, reading JSON metadata only."""
import hashlib
import json
from pathlib import Path
from output_contract import FIXTURES
from generate_sources import BASELINE

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
CAPTURE=ROOT/"artifacts/match_consolidation/hash_prototype/run_20261022_capture_actual85"


def pin(path):
    raw=path.read_bytes();return dict(path=str(path.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    destination=HERE/"HISTORICAL_TRACE_PINS.json"
    if destination.exists():raise ValueError("Preserve historical metadata catalog; no overwrite")
    fixture=json.loads((HERE/"generated_fixtures/FIXTURE_SOURCE_MANIFEST.json").read_bytes())
    approved={item["path"]:item for item in fixture["metadata_pins"]}
    rows=[]
    for name in FIXTURES:
        directory=CAPTURE/name;manifest_path=directory/"manifest.json";protocol_path=directory/"protocol.json"
        manifest_pin=pin(manifest_path);protocol_pin=pin(protocol_path)
        if approved[str(protocol_path.resolve())]!=protocol_pin:raise ValueError("Earlier protocol metadata changed")
        manifest=json.loads(manifest_path.read_bytes())
        if not(manifest["core_revision"]==BASELINE and manifest["case"]["case_id"]==name and
               manifest["protocol_sha256"]==protocol_pin["sha256"] and
               manifest["trace"]["path"]=="capture.bin" and manifest["reference"]["path"]=="reference.bin" and
               type(manifest["reference"]["input_count"]) is int and manifest["reference"]["input_count"]==0):
            raise ValueError("Historical manifest identity differs")
        rows.append(dict(fixture=name,manifest=manifest_pin,protocol=protocol_pin,
                         trace=manifest["trace"],reference=manifest["reference"]))
    result=dict(schema="whole_api_historical_numeric_pins_v1",baseline_commit=BASELINE,fixtures=rows,
                source_only=True,trace_or_reference_bytes_opened=0,image_smd_bank_bytes_opened=0,
                limitation="Metadata copied from existing accepted historical captures; actual numeric archives rehashed by granted native stages")
    with destination.open("x",encoding="utf-8",newline="\n") as out:json.dump(result,out,indent=2);out.write("\n")
    print(json.dumps(pin(destination)))


if __name__=="__main__":main()
