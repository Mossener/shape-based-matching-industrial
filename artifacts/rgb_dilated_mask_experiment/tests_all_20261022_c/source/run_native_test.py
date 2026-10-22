"""Run one previously built literal/spy executable only with a root CPU grant."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import freeze_private_sources as frozen
import native_provenance as p

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cpu-slot-granted',action='store_true')
    args=parser.parse_args()
    p.require(args.cpu_slot_granted,'Await coordinated native toy-test CPU slot')
    run=args.output.resolve();p.require(run.is_relative_to(HERE) and not run.exists(),'Test output must be fresh inside experiment')
    run.mkdir();exit_code=None
    try:
        build=json.loads(args.build_manifest.read_text())
        p.require(build['passed'] and build['target'] in ('literal-test','source-test'),'Actual literal/spy build required')
        p.require(build['actual_private_core']==str(HERE/('private_v11' if build['core_arm']=='treatment' else 'control_v11')/'line2Dup.cpp'),'Unexpected actual core')
        p.require(len(build['commands'])==5 and all(c['exit_code']==0 for c in build['commands']),'Build did not complete all five steps')
        pins=build['project_sources']+build['compiler_tools_and_link_libraries']+build['compiler_runtime_closure']['files']+build['executable_runtime_closure']['files']+[build['executable'],p.file_pin(args.build_manifest),p.file_pin(Path(__file__))]
        for unit in build['dependency_units']: pins+=unit['dependencies']+[unit['object'],unit['dependency_file']]
        for pin in pins:p.check_pin(pin)
        frozen.verify(HERE/'private_v11',json.loads((HERE/'PRIVATE_SOURCE_FREEZE.json').read_text()))
        command=[build['executable']['path']]
        env=dict(os.environ);env['PATH']=str(Path(build['compiler']).parent)+';'+str(Path(build['opencv'])/'build/bin')+';'+env.get('PATH','')
        receipt=dict(command=command,build=p.file_pin(args.build_manifest),runner=p.file_pin(Path(__file__)),native_exit_code=None,
                     expected_morphology=build['expected_morphology'],core_arm=build['core_arm'],image_decodes=0,matcher_calls=0,dataset_files_opened=0)
        (run/'execution_provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')
        with (run/'stdout.txt').open('wb') as stdout,(run/'stderr.txt').open('wb') as stderr:
            process=subprocess.run(command,cwd=HERE,env=env,stdout=stdout,stderr=stderr)
        exit_code=process.returncode;receipt['native_exit_code']=exit_code
        for pin in pins:p.check_pin(pin)
        frozen.verify(HERE/'private_v11',json.loads((HERE/'PRIVATE_SOURCE_FREEZE.json').read_text()))
        receipt['passed']=exit_code==0
        (run/'execution_provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')
        p.require(exit_code==0,'Native toy test failed; all diagnostics retained')
        print(json.dumps(dict(passed=True,target=build['target'],image_decodes=0,matcher_calls=0)))
    except Exception as error:
        (run/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),native_exit_code=exit_code,image_decodes=0,matcher_calls=0),indent=2)+'\n')
        raise


if __name__=='__main__':main()
