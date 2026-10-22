"""Small numeric pack build/test, without images, matcher or training."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
def pin(p):
    b=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--mode',choices=['missing-header-red','green'],required=True)
    args=ap.parse_args()
    out=args.output.resolve()
    if out.exists() or not out.is_relative_to(HERE): raise ValueError('Fresh contained output required')
    out.mkdir(); source=out/'source';source.mkdir()
    names=['pack_literal_tests.cpp','run_literal.py']+([] if args.mode=='missing-header-red' else ['numeric_pack.hpp'])
    before=[pin(HERE/n) for n in names]
    for n in names: (source/n).write_bytes((HERE/n).read_bytes())
    compiler=Path('F:/mysys2/ucrt64/bin/g++.exe');env=dict(os.environ);env['PATH']=str(compiler.parent)+';'+env.get('PATH','')
    exe=out/'pack_literal_tests.exe'
    command=[str(compiler),'-std=c++17','-O2','-Wall','-Wextra','-Werror',str(source/'pack_literal_tests.cpp'),'-lz','-lbcrypt','-o',str(exe)]
    c=subprocess.run(command,capture_output=True,env=env,timeout=120)
    (out/'compile.stdout').write_bytes(c.stdout);(out/'compile.stderr').write_bytes(c.stderr)
    r=None
    if c.returncode==0:
        r=subprocess.run([str(exe),str(out/'data')],capture_output=True,env=env,timeout=30)
        (out/'run.stdout').write_bytes(r.stdout);(out/'run.stderr').write_bytes(r.stderr)
    passed=(c.returncode!=0 and b'numeric_pack.hpp' in c.stderr if args.mode=='missing-header-red' else c.returncode==0 and r is not None and r.returncode==0)
    result=dict(passed=passed,mode=args.mode,command=command,compile_exit=c.returncode,run_exit=None if r is None else r.returncode,compiler=pin(compiler),source_pins=before,source_unchanged=before==[pin(HERE/n) for n in names],image_decodes=0,matcher_calls=0,training_poses=0)
    result['files']=[pin(p) for p in sorted(out.rglob('*')) if p.is_file()]
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','mode','compile_exit','run_exit','source_unchanged')}))
    if not passed or not result['source_unchanged']: raise SystemExit(1)

if __name__=='__main__':main()
