"""Fresh byte-only manifest writer. Run after all source reviews; never native."""
import argparse
import hashlib
import json
from pathlib import Path
from source_list import SOURCE_FILES, PREREQUISITES
from generate_sources import BASELINE, safe_relative
from build_policy import checked_manifest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name",default="FULL_API_SOURCE_MANIFEST.json")
    args=parser.parse_args()
    if Path(args.name).name!=args.name:raise ValueError("Direct manifest basename required")
    target=checked_manifest(HERE,HERE/args.name)
    if target.exists():raise ValueError("Preserve existing source manifest; no overwrite")
    files=[]
    for relative in SOURCE_FILES:
        raw=(HERE/safe_relative(relative)).read_bytes()
        files.append(dict(relative=relative,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    prerequisites=[]
    for relative,expected in PREREQUISITES:
        raw=(ROOT/safe_relative(relative)).read_bytes()
        actual=hashlib.sha256(raw).hexdigest()
        if actual!=expected:raise ValueError("Earlier evidence changed: "+relative)
        prerequisites.append(dict(relative=relative,bytes=len(raw),sha256=actual))
    result=dict(schema="whole_api_sources_v1",baseline_commit=BASELINE,
                sources=files,prerequisites=prerequisites)
    with target.open("x",encoding="utf-8",newline="\n") as out:
        json.dump(result,out,indent=2);out.write("\n")
    print(json.dumps(dict(manifest=str(target),source_files=len(files),
                         sha256=hashlib.sha256(target.read_bytes()).hexdigest())))


if __name__=="__main__":main()
