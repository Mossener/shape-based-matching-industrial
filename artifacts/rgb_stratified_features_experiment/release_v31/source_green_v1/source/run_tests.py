"""Preserve isolated synthetic verifier evidence; never use the actual Git index."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
SOURCES=('verify_selection.py','test_publication.py','run_tests.py','README.md','SOURCE_PUBLICATION_PLAN.md','SOURCE_ORIGIN.json')


def pin(path):
    data=path.read_bytes(); return dict(path=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(); output=args.output.resolve()
    if output.exists() or not output.is_relative_to(HERE): raise SystemExit('fresh contained test output required')
    source=output/'source'; source.mkdir(parents=True)
    before=[pin(HERE/name) for name in SOURCES]
    for name in SOURCES: (source/name).write_bytes((HERE/name).read_bytes())
    command=[sys.executable,'-B','-m','unittest','discover','-s',str(source),'-p','test_publication.py','-v']
    result=subprocess.run(command,cwd=HERE,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),capture_output=True)
    (output/'stdout.txt').write_bytes(result.stdout); (output/'stderr.txt').write_bytes(result.stderr)
    counts=re.findall(rb'Ran (\d+) tests?',result.stderr); tests=int(counts[-1]) if counts else None
    unchanged=before==[pin(HERE/name) for name in SOURCES]
    receipt=dict(schema='v31_publication_source_tests_v1',passed=result.returncode==0 and unchanged,
                 exit_code=result.returncode,tests=tests,command=command,source_pins=before,
                 source_snapshot_pins=[pin(source/name) for name in SOURCES],source_unchanged=unchanged,
                 outputs=[pin(output/name) for name in ('stdout.txt','stderr.txt')],synthetic_only=True,
                 real_git_commands_run=0,real_index_reads=0,real_image_reads=0,real_bank_reads=0,
                 real_raw_archive_reads=0,matcher_calls=0,final_selection_created=False,
                 limitation='Temporary byte fixtures and mocked read-only Git; no actual publication or result acceptance')
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=receipt['passed'],tests=tests,receipt=str(output/'receipt.json'))))
    return 0 if receipt['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
