"""Save fresh synthetic test output and exact sources; no repository Git writes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to(HERE) or out.exists():
        raise ValueError('Fresh synthetic output within release_v29 required')
    out.mkdir();snapshot=out/'source';snapshot.mkdir();pins={}
    for path in HERE.glob('*.py'):
        data=path.read_bytes();(snapshot/path.name).write_bytes(data)
        pins[path.name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    command=[sys.executable,'-B','-m','unittest','discover','-s',str(HERE),'-p','test_publication.py','-v']
    run=subprocess.run(command,capture_output=True)
    (out/'stdout.txt').write_bytes(run.stdout);(out/'stderr.txt').write_bytes(run.stderr)
    for name,expected in pins.items():
        data=(HERE/name).read_bytes()
        if expected!=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()):
            raise ValueError('Test source changed')
    result=dict(passed=run.returncode==0,exit_code=run.returncode,command=command,
                source_pins=pins,image_reads=0,matcher_calls=0,repository_git_writes=0)
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(run.stderr.decode(errors='replace'));print(json.dumps(result))
    raise SystemExit(run.returncode)


if __name__=='__main__':
    main()
