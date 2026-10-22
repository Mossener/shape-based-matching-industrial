"""Fresh source snapshots and receipt for independent synthetic geometry tests."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def pin(path):
    data=path.read_bytes()
    return dict(path=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(HERE) or output.exists():raise ValueError('Fresh evidence directory inside geometry required')
    output.mkdir();snapshot=output/'source';snapshot.mkdir()
    sources=[HERE/name for name in ('independent_geometry_audit.py','run_independent_geometry_audit.py',
                                   'test_independent_geometry.py','run_independent_tests.py')]
    sources += [HERE.parent/'independent/strict_bank_reader.py',HERE.parent/'execution_guard.py',
                HERE.parent/'PROTOCOL.json',HERE.parent/'frozen_helpers/padding_plan.hpp']
    before=[pin(path) for path in sources]
    for path in sources:(snapshot/path.name).write_bytes(path.read_bytes())
    command=[sys.executable,'-B','-m','unittest','discover','-s',str(HERE),'-p','test_independent_geometry.py','-v']
    run=subprocess.run(command,cwd=HERE,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    (output/'stdout.txt').write_text(run.stdout,encoding='utf-8',newline='\n')
    (output/'stderr.txt').write_text(run.stderr,encoding='utf-8',newline='\n')
    after=[pin(path) for path in sources];unchanged=before==after
    receipt=dict(schema='independent_geometry_source_tests_v1',passed=run.returncode==0 and unchanged,
                 command=command,exit=run.returncode,source_pins_before=before,source_pins_after=after,
                 interpreter=pin(Path(sys.executable)),source_unchanged=unchanged,
                 synthetic_numeric_payloads_only=True,real_bank_files_opened=0,
                 actual_guard_executions=0,native_executions=0,image_reads=0,image_decodes=0,
                 matcher_calls=0,quality_claim=False,performance_claim=False)
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=receipt['passed'],exit=run.returncode)))
    return 0 if receipt['passed'] else (run.returncode or 1)


if __name__=='__main__':raise SystemExit(main())
