"""Freeze and capture meaningful diagnostic tests without native execution."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve()
    if not out.is_relative_to(HERE) or out.exists():raise ValueError('Fresh contained output required')
    out.mkdir();source=out/'source';source.mkdir();pins=[]
    for name in ['numeric.py','run_analysis.py','test_diagnostic.py','run_tests.py','PROTOCOL.json','ORIGIN.json']:
        data=(HERE/name).read_bytes();(source/name).write_bytes(data)
        pins.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    r=subprocess.run([sys.executable,'-m','unittest','-v','test_diagnostic'],cwd=source,capture_output=True,text=True)
    (out/'stdout.txt').write_text(r.stdout,encoding='utf-8');(out/'stderr.txt').write_text(r.stderr,encoding='utf-8')
    report=dict(passed=r.returncode==0,exit_code=r.returncode,source_pins=pins,matcher_calls=0,image_decodes=0)
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
    raise SystemExit(r.returncode)


if __name__=='__main__':main()
