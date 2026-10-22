"""Gated separate quality stages; no continuation beyond the requested CPU slot."""
import argparse
import json
import os
from pathlib import Path
import subprocess

import freeze_private_sources as frozen
import native_provenance as p
import prepare_input_closure as inherited
import prepare_quality_inputs as inputs
import quality_contract as contract

HERE=Path(__file__).resolve().parent


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def build_gate(path):
    manifest=load(path)
    p.require(manifest['passed'] is True and manifest['target']=='quality' and manifest['core_revision']==frozen.REV and
              manifest['actual_private_core']==str(HERE/'private_v11/line2Dup.cpp'),'Actual separate private quality build required')
    p.require(len(manifest['commands'])==5 and all(c['exit_code']==0 for c in manifest['commands']) and
              [u['source'] for u in manifest['dependency_units']]==[str(HERE/'private_v11/line2Dup.cpp'),str(HERE/'quality_eval.cpp')] and
              Path(manifest['executable']['path']).name=='quality_eval.exe','Actual quality translation units/commands differ')
    p.require(all('-DEMPTY_MASK_POLICY_RED_TEST' not in c['command'] for c in manifest['commands']),'Wrong-mask RED must never enter quality')
    pins=manifest['project_sources']+manifest['compiler_tools_and_link_libraries']+manifest['compiler_runtime_closure']['files']+manifest['executable_runtime_closure']['files']+[manifest['executable']]
    for unit in manifest['dependency_units']:
        pins+=unit['dependencies']+[unit['object'],unit['dependency_file']]
    for pin in pins:
        p.check_pin(pin)
    return manifest,p.file_pin(path)


def stage_gate(run,expected,build_pin,input_pin):
    run=Path(run).resolve(strict=True);p.require(run.is_relative_to(HERE),'Previous stage must belong to this experiment')
    file=run/'QUALITY_STAGE_FREEZE.json';manifest=load(file)
    p.require(manifest['completed'] is True and manifest['stage']==expected and manifest['native_exit_code']==0 and
              manifest['actual_matcher_calls']==(0 if expected=='selftest' else contract.CALLS[expected]) and
              manifest['build_manifest']==build_pin and manifest['quality_inputs']==input_pin,'Previous stage completion/source/budget gate differs')
    for pin in manifest['files']+manifest['execution_files']:
        p.check_pin(pin)
    native=run/'native';expected_files={record['path'] for record in manifest['files']}
    actual={str(path.resolve()) for path in native.rglob('*') if path.is_file() and path.name!='.gitignore'}
    p.require(actual==expected_files,'Previous complete native output member set changed')
    if manifest['reservation']:
        p.check_pin(manifest['reservation'])
    return manifest,p.file_pin(file)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['selftest',*contract.CALLS],required=True)
    parser.add_argument('--build-manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--selftest-run',type=Path);parser.add_argument('--previous-run',type=Path)
    parser.add_argument('--cpu-slot-granted',action='store_true');args=parser.parse_args()
    p.require(args.cpu_slot_granted,'Await coordinated native quality CPU slot')
    run=args.output.resolve();p.require(run.is_relative_to(HERE) and not run.exists(),'Quality run directory must be fresh inside successor')
    run.mkdir();native=run/'native';native_exit=None;reservation_pin=None;post_valid=False;actual_calls=None
    try:
        build,build_pin=build_gate(args.build_manifest);input_pin=p.file_pin(HERE/'QUALITY_INPUT_FREEZE.json');inputs.verify()
        frozen.verify(HERE/'private_v11',load(HERE/'PRIVATE_SOURCE_FREEZE.json'))
        script_pins=[p.file_pin(HERE/name) for name in ['run_quality.py','quality_contract.py','prepare_quality_inputs.py','prepare_input_closure.py','native_provenance.py']]
        previous_pin=None;selftest_pin=None;previous=None
        if args.mode!='selftest':
            p.require(args.selftest_run is not None,'Native numeric/raw/origin selftest must complete first')
            _,selftest_pin=stage_gate(args.selftest_run,'selftest',build_pin,input_pin)
            expected=contract.PREVIOUS[args.mode]
            if expected:
                p.require(args.previous_run is not None,'Fixed prior stage is required')
                _,previous_pin=stage_gate(args.previous_run,expected,build_pin,input_pin);previous=args.previous_run.resolve()
            else:
                p.require(args.previous_run is None,'Original-padding gate has no previous matching stage')
            contract.reserve(HERE/'quality_stage_reservations',args.mode,run,previous_pin)
            reservation_pin=p.file_pin(HERE/'quality_stage_reservations'/(args.mode+'.json'))
        else:
            p.require(args.previous_run is None and args.selftest_run is None,'Selftest must not depend on matching/image stages')
        before=inputs.verify();image_before=inherited.verify()
        (run/'verified_before.json').write_text(json.dumps(dict(inputs=before,images=image_before),indent=2)+'\n')
        command=[build['executable']['path'],'--mode',args.mode,'--output',str(native),'--inputs',str(HERE/'QUALITY_INPUT_FREEZE.json')]
        if previous:
            command+=['--previous',str(previous/'native')]
        env=dict(os.environ);env['PATH']=str(Path(build['compiler']).parent)+';'+str(Path(build['opencv'])/'build/bin')+';'+env.get('PATH','')
        execution=dict(command=command,mode=args.mode,build_manifest=build_pin,quality_inputs=input_pin,selftest=selftest_pin,
                       previous_stage=previous_pin,reservation=reservation_pin,script_pins=script_pins,native_exit_code=None,
                       runtime_path_prefix=[str(Path(build['compiler']).parent),str(Path(build['opencv'])/'build/bin')],
                       maximum_matcher_calls=0 if args.mode=='selftest' else contract.CALLS[args.mode])
        (run/'execution_provenance.json').write_text(json.dumps(execution,indent=2)+'\n')
        with (run/'native.stdout').open('wb') as stdout,(run/'native.stderr').open('wb') as stderr:
            process=subprocess.run(command,cwd=HERE,env=env,stdout=stdout,stderr=stderr)
        native_exit=process.returncode;execution['native_exit_code']=native_exit
        (run/'execution_provenance.json').write_text(json.dumps(execution,indent=2)+'\n')
        after=inputs.verify();image_after=inherited.verify()
        p.require(before==after and image_before==image_after,'Input verification scope changed during quality stage')
        build_gate(args.build_manifest);p.check_pin(build_pin);p.check_pin(input_pin)
        for pin in script_pins:
            p.check_pin(pin)
        if selftest_pin:
            stage_gate(args.selftest_run,'selftest',build_pin,input_pin);p.check_pin(selftest_pin)
        if previous_pin:
            stage_gate(previous,contract.PREVIOUS[args.mode],build_pin,input_pin);p.check_pin(previous_pin)
        if reservation_pin:
            p.check_pin(reservation_pin)
        (run/'verified_after.json').write_text(json.dumps(dict(inputs=after,images=image_after),indent=2)+'\n');post_valid=True
        summary_path=native/('selftest_result.json' if args.mode=='selftest' else 'stage_summary.json')
        summary=load(summary_path) if summary_path.exists() else None
        failure=load(native/'failure.json') if (native/'failure.json').exists() else None
        actual_calls=(summary.get('matcher_calls') if summary else failure.get('matcher_invocations_started') if failure else None)
        completed=bool(native_exit==0 and summary and summary['passed']==1 and actual_calls==(0 if args.mode=='selftest' else contract.CALLS[args.mode]))
        files=[p.file_pin(path) for path in sorted(native.rglob('*')) if path.is_file() and path.name!='.gitignore']
        execution_files=[p.file_pin(path) for path in sorted(run.iterdir()) if path.is_file()]
        freeze=dict(stage=args.mode,completed=completed,native_exit_code=native_exit,actual_matcher_calls=actual_calls,
                    maximum_matcher_calls=0 if args.mode=='selftest' else contract.CALLS[args.mode],build_manifest=build_pin,
                    quality_inputs=input_pin,selftest=selftest_pin,previous_stage=previous_pin,reservation=reservation_pin,
                    files=files,execution_files=execution_files,summary=summary,post_verification_passed=post_valid,
                    missing_frames_are_not_negatives=True,heldout_images_allowed=False)
        (run/'QUALITY_STAGE_FREEZE.json').write_text(json.dumps(freeze,indent=2)+'\n')
        p.require(completed,'Native quality stage incomplete; all partial evidence and its budget reservation are preserved')
        print(json.dumps(dict(passed=True,stage=args.mode,matcher_calls=actual_calls,heldout_images_read=0)))
    except Exception as error:
        (run/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),native_exit_code=native_exit,
            post_verification_passed=post_valid,actual_matcher_calls=actual_calls,reservation=reservation_pin,
            missing_frames_are_not_negatives=True,do_not_silently_rerun_reserved_stage=True),indent=2)+'\n');raise


if __name__=='__main__':
    main()
