"""Retain source-only unit-test stdout/stderr, source snapshots and pin receipts."""
import sys
sys.dont_write_bytecode=True
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE=Path(__file__).resolve().parent


def pin(path):
    data=path.read_bytes()
    return dict(path=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--test',default='test_quality_source')
    ap.add_argument('--expect',choices=['red','green'],default='green')
    ap.add_argument('--failure-text')
    a=ap.parse_args();out=a.output.resolve()
    if not out.is_relative_to(HERE) or out.exists():raise ValueError('Fresh contained receipt required')
    out.mkdir();(out/'source').mkdir()
    sources=[p for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.hpp','.cpp','.md') and p.is_file()]
    originals=[pin(p) for p in sources]
    for source in sources:shutil.copyfile(source,out/'source'/source.name)
    command=[sys.executable,'-B','-m','unittest',a.test,'-v']
    process=subprocess.run(command,cwd=out/'source',capture_output=True,timeout=60)
    (out/'stdout.txt').write_bytes(process.stdout);(out/'stderr.txt').write_bytes(process.stderr)
    text=(process.stdout+process.stderr).decode('utf-8')
    correct=(process.returncode==0 if a.expect=='green' else process.returncode==1 and
             'FAIL:' in text and 'ERROR:' not in text and a.failure_text and a.failure_text in text)
    if originals!=[pin(p) for p in sources]:raise ValueError('Source changed during tests')
    record=dict(passed=bool(correct),expected=a.expect,exit_code=process.returncode,command=command,
        original_sources=originals,snapshot_sources=[pin(out/'source'/p.name) for p in sources],
        stdout=pin(out/'stdout.txt'),stderr=pin(out/'stderr.txt'),python_executable=pin(Path(sys.executable)),
        python_version=sys.version,native_runs=0,image_decodes=0,matcher_calls=0,bank_payload_reads=0,
        limitation='Python behavior and static native-source contracts only; no C++ compilation/execution claim')
    (out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(passed=bool(correct),expected=a.expect,exit_code=process.returncode,native_runs=0)))
    if not correct:raise SystemExit(1)


if __name__=='__main__':main()
