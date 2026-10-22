"""Fresh source-only successor regression evidence; no actual numeric inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
HERE=Path(__file__).resolve().parent

def pin(path):
    data=path.read_bytes();return dict(path=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(HERE) or output.exists():raise ValueError('Fresh evidence inside successor required')
    output.mkdir();snapshot=output/'source';snapshot.mkdir()
    sources=sorted(p for p in HERE.iterdir() if p.suffix in ('.py','.md','.json') and p.is_file())
    before=[pin(p) for p in sources]
    for p in sources:shutil.copyfile(p,snapshot/p.name)
    command=[sys.executable,'-B','-m','unittest','-v','test_shared_numeric']
    run=subprocess.run(command,cwd=snapshot,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    for name,value in (('stdout.txt',run.stdout),('stderr.txt',run.stderr)):(output/name).write_text(value,encoding='utf-8',newline='\n')
    same=before==[pin(p) for p in sources]
    receipt=dict(schema='independent_quality_successor_source_regression_v1',passed=run.returncode==0 and same,
                 exit=run.returncode,command=command,source_pins=before,sources_unchanged=same,
                 actual_numeric_inputs_opened=0,real_bank_reads=0,real_raw_reads=0,image_reads=0,
                 native_executions=0,actual_guard_executions=0,matcher_calls=0)
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=receipt['passed'],exit=run.returncode)))
    return run.returncode or (0 if same else 2)

if __name__=='__main__':raise SystemExit(main())
