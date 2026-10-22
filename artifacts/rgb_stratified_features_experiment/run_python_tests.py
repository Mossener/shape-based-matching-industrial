"""Capture isolated guard fault tests and exact sources; no dataset access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
def pin(path):
    data=path.read_bytes();return dict(path=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--mode',choices=['missing-guard-red','green'],required=True);args=ap.parse_args()
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(HERE):raise ValueError('Fresh contained test directory required')
    out.mkdir();source=out/'source';source.mkdir();names=['test_execution_guard.py','run_python_tests.py']+([] if args.mode=='missing-guard-red' else ['execution_guard.py'])
    before=[pin(HERE/n) for n in names]
    for n in names:(source/n).write_bytes((HERE/n).read_bytes())
    env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1';env.pop('PYTHONPATH',None)
    result=subprocess.run([sys.executable,str(source/'test_execution_guard.py')],cwd=source,capture_output=True,env=env,timeout=30)
    (out/'stdout.txt').write_bytes(result.stdout);(out/'stderr.txt').write_bytes(result.stderr)
    passed=(result.returncode!=0 and b"No module named 'execution_guard'" in result.stderr) if args.mode=='missing-guard-red' else (result.returncode==0 and b'Ran 8 tests' in result.stderr and b'OK' in result.stderr)
    receipt=dict(passed=passed,mode=args.mode,exit_code=result.returncode,source_pins=before,source_unchanged=before==[pin(HERE/n) for n in names],python=pin(Path(sys.executable)),image_decodes=0,matcher_calls=0,training_poses=0)
    receipt['files']=[pin(f) for f in sorted(out.rglob('*')) if f.is_file()];(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('passed','mode','exit_code','source_unchanged')}))
    if not passed or not receipt['source_unchanged']:raise SystemExit(1)
if __name__=='__main__':main()
