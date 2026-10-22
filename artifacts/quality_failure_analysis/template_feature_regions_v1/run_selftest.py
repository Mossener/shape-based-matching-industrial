"""Run the synthetic native fixture gate only after root's CPU-slot grant."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import input_contract as c
from run_observer import verify_build


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--cpu-slot-granted',action='store_true');args=parser.parse_args()
    c.need(args.cpu_slot_granted,'Await root CPU-slot grant');out=args.output.resolve()
    c.need(out.is_relative_to(c.HERE) and not out.exists(),'Fresh selftest run directory required');out.mkdir()
    try:
        build=c.load(args.build);verify_build(build);compiler=Path(build['compiler']);opencv=Path(build['opencv'])
        env=dict(os.environ);env['PATH']=str(compiler.parent)+';'+str(opencv/'build/bin')+';'+env.get('PATH','')
        command=[build['executable']['path'],'--selftest',str(out/'native')]
        run=subprocess.run(command,cwd=out,env=env,capture_output=True)
        (out/'stdout.txt').write_bytes(run.stdout);(out/'stderr.txt').write_bytes(run.stderr)
        verify_build(build);c.need(run.returncode==0,'Native selftest failed; diagnostics retained')
        result=dict(passed=True,native_exit=0,command=command,build=c.pin(args.build),files=[c.pin(q) for q in sorted((out/'native').iterdir()) if q.is_file()],image_bytes_opened=0,matcher_calls=0)
        (out/'SELFTEST_FREEZE.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,image_bytes_opened=0)))
    except Exception as error:
        (out/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),image_bytes_opened=0,matcher_calls=0),indent=2)+'\n');raise


if __name__=='__main__':main()
