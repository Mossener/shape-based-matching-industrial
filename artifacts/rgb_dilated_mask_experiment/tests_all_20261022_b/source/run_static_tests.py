"""Capture fresh standard-library tests and exact source bytes, no native code."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--slice',choices=['source','all'],default='all')
    args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to(HERE) or out.exists():raise ValueError('Fresh test output inside experiment required')
    out.mkdir();snap=out/'source';snap.mkdir();pins=[]
    for p in HERE.iterdir():
        if p.is_file() and p.suffix in ('.py','.hpp','.cpp','.json'):
            shutil.copyfile(p,snap/p.name)
            pins.append(dict(name=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
    # Run the live source suite (snapshot retained for exact byte provenance).
    # This suite's path contracts deliberately resolve the experiment's real root.
    command=[sys.executable,'-B',str(HERE/'test_source_contract.py')]
    if args.slice=='source':
        sys.path.insert(0,str(HERE));import test_source_contract as tests
        names=sorted(n for n in dir(tests.SourceContractTests) if n.startswith('test_') and n!='test_build_and_run_have_cpu_gate_and_fresh_output')
        command+=['SourceContractTests.'+n for n in names]
    p=subprocess.run(command,capture_output=True)
    (out/'stdout.txt').write_bytes(p.stdout);(out/'stderr.txt').write_bytes(p.stderr)
    result=dict(passed=p.returncode==0,exit_code=p.returncode,slice=args.slice,command=command,source_pins=pins,image_decodes=0,matcher_calls=0,native_compilations=0)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(p.stderr.decode(errors='replace'));print(json.dumps(dict(passed=result['passed'],exit_code=p.returncode,native_compilations=0)))
    raise SystemExit(p.returncode)


if __name__=='__main__':main()
