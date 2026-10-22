"""Separately authorized, one-shot Phase2 native stages. No implicit dispatch."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import source_contract as c
import prepare_budget as prep

HERE=Path(__file__).resolve().parent
V1=HERE.parent/'score_path_probe_v1'
PLAN=HERE/'PHASE2_INPUTS_V1.json'
PLAN_SHA='830a77d629ad766df998aa59fbd1b6cf6bc207c900263afd04b890560eb9215a'
sys.path.insert(0,str(V1))
from probe_contract import pin,check,require,reserve


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def load_phase1_runtime():
    """Borrow only pinned read-only gates, file inventory and subprocess watchdog."""
    receipt,receipt_pin=prep.load_pinned(prep.RECEIPT,prep.RECEIPT_SHA)
    check(receipt['build_manifest'])
    old=load(receipt['build_manifest']['path'])
    for value in old['project_sources']:
        check(value)
    expected=next(value for value in old['project_sources'] if Path(value['path'])==V1/'run_probe.py')
    check(expected)
    spec=importlib.util.spec_from_file_location('pinned_phase1_probe_runtime',V1/'run_probe.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,expected


def build_gate(path,red):
    path=Path(path).resolve(strict=True);require(path.is_relative_to(HERE),'Build manifest must belong to this sibling')
    data=load(path)
    require(data.get('passed') is True and data.get('target')=='score_path_probe_phase2' and
            data.get('core_revision')=='b25df46f6ddf9c24fb43f5836f1414dc38c8caed' and data.get('red_controls') is red,
            'Wrong/incomplete Phase2 build')
    units=data['dependency_units'];commands=data['commands']
    require(len(units)==1 and Path(units[0]['source'])==HERE/'phase2.cpp' and
            len(commands)==3 and [row['label'] for row in commands]==['dependency_before','compile','link'] and
            all(row['exit_code']==0 for row in commands),'Actual single-TU Phase2 commands differ')
    require(Path(data['executable']['path'])==path.parent/'score_probe_v2.exe','Phase2 executable path differs')
    for command in commands[:2]:
        require(('-DSCORE_PATH_RED_CONTROLS' in command['command']) is red,'Phase2 RED compiler macro differs')
    values=data['project_sources']+data['phase1_project_sources']+data['compiler_tools_and_link_libraries']
    values+=data['compiler_runtime_closure']['files']+data['executable_runtime_closure']['files']
    values+=[data['executable'],data['preprocessing_extraction'],data['prior_phase1_receipt']]
    for unit in units:
        values+=unit['dependencies']+[unit['object'],unit['dependency_file'],unit['generated_preprocess_header']]
    for value in values:
        check(value)
    require(data['prior_phase1_receipt']['sha256']==prep.RECEIPT_SHA,'Build is not bound to the fixed Phase1 receipt')
    extraction=load(data['preprocessing_extraction']['path']);check(extraction['source']);check(extraction['generated_header'])
    transformed=c.extract(Path(extraction['source']['path']).read_bytes())
    require(Path(extraction['generated_header']['path']).read_bytes()==transformed['header'] and
            [value['utf8'].encode('utf-8') for value in extraction['components']]==transformed['components'] and
            extraction['original_source_edited'] is False and extraction['generated_file_is_transformed'] is True,
            'Exact preprocessing transformation no longer matches')
    return data,pin(path)


def plan_gate(path,runtime):
    path=Path(path).resolve(strict=True);require(path==PLAN,'Only the contained fixed Phase2 input plan may be opened')
    value=pin(path);require(value['sha256']==PLAN_SHA,'Phase2 input plan is not the approved fixed numeric plan')
    data=load(path)
    require(data.get('phase')=='phase2' and data.get('rgb_tp_identities')==215 and data.get('arm_identity_probes')==430 and
            data['prior_phase1_receipt']['sha256']==prep.RECEIPT_SHA and
            data['independent_phase1_audit']['sha256']==prep.PHASE1_AUDIT_SHA,'Phase2 fixed evidence gate differs')
    pins=[data[key] for key in ('prior_phase1_receipt','prior_input_plan','prior_v22_audit','independent_phase1_audit','loaded_layers_pin')]
    pins+=data['metadata_pins']+data['phase1_project_source_pins']+data['proposal_source_pins']
    for record in pins:
        check(record)
    audit=load(data['independent_phase1_audit']['path'])
    require(audit['passed'] is True and audit['stage']=='score_path_probe_v1_phase1' and
            audit['phase1_freeze']==data['prior_phase1_receipt'] and audit['input_plan']==data['prior_input_plan'],
            'Independent Phase1 audit is not passed/bound')
    prior,prior_pin=runtime.check_plan(data['prior_input_plan']['path'])
    require(prior_pin==data['prior_input_plan'],'Prior exact numeric plan differs')
    receipt=load(data['prior_phase1_receipt']['path'])
    runtime.runner_gates.verify_output(Path(data['prior_phase1_receipt']['path']).parent/'native',receipt['files'])
    for record in receipt['execution_files']:
        check(record)
    return data,value,prior


def stage_gate(run,fault,input_pin,runtime,build_pin=None):
    run=Path(run).resolve(strict=True);require(run.is_relative_to(HERE),'Stage receipt must belong to this sibling')
    path=run/'PHASE2_STAGE_FREEZE.json';data=load(path)
    require(data.get('completed') is True and data.get('stage')=='selftest' and data.get('fault')==fault and
            data['input_plan']==input_pin and data['image_hash_operations']==0 and data['unique_dataset_image_files_opened']==0,
            'Synthetic stage receipt differs')
    require(data['expected_native_failure'] is (fault!='none'),'Synthetic RED/GREEN failure contract differs')
    c.native_gate('selftest',fault,data['native_exit_code'],data['summary'],data['native_failure'])
    summary_path=run/'native/selftest_result.json';failure_path=run/'native/failure.json'
    require((load(summary_path) if summary_path.exists() else None)==data['summary'] and
            (load(failure_path) if failure_path.exists() else None)==data['native_failure'],
            'Frozen synthetic result differs from complete native files')
    if build_pin:
        require(data['build_manifest']==build_pin,'GREEN selftest not bound to this exact Phase2 build')
    for value in data['execution_files']+[data['build_manifest'],data['input_plan'],data['reservation']]+data.get('red_receipts',[]):
        check(value)
    runtime.runner_gates.verify_output(run/'native',data['files'])
    actual={p.resolve() for p in run.iterdir() if p.is_file()}
    expected={Path(value['path']).resolve() for value in data['execution_files']}|{path}
    require(actual==expected,'Complete synthetic execution file membership changed')
    return data,pin(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('selftest','phase2'),required=True)
    parser.add_argument('--fault',choices=('none','coarse','local','winner'),default='none')
    parser.add_argument('--build-manifest',type=Path,required=True);parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--selftest-run',type=Path)
    for fault in ('coarse','local','winner'):
        parser.add_argument('--red-'+fault+'-run',type=Path)
    parser.add_argument('--cpu-slot-granted',action='store_true');args=parser.parse_args()
    require(args.cpu_slot_granted,'Await explicit coordinated Phase2 native CPU grant')
    require(args.mode=='selftest' or args.fault=='none','Injected faults are synthetic-only')
    run=args.output.resolve();require(run.is_relative_to(HERE) and not run.exists() and run.parent.is_dir(),'Fresh contained Phase2 output required')
    run.mkdir();native=run/'native';reservation_pin=None;native_exit=None;freeze_path=run/'PHASE2_STAGE_FREEZE.json'
    try:
        runtime,runtime_pin=load_phase1_runtime()
        red=args.fault!='none';build,build_pin=build_gate(args.build_manifest,red)
        plan,input_pin,prior=plan_gate(args.plan,runtime)
        selftest_pin=None;red_pins=[];stage='selftest_red_'+args.fault if red else 'selftest_green' if args.mode=='selftest' else 'phase2'
        red_paths=[getattr(args,'red_'+fault+'_run') for fault in ('coarse','local','winner')]
        if args.mode=='phase2':
            require(args.selftest_run is not None and all(path is None for path in red_paths),'Dataset stage requires only its bound GREEN selftest')
            _,selftest_pin=stage_gate(args.selftest_run,'none',input_pin,runtime,build_pin)
        elif red:
            require(args.selftest_run is None and all(path is None for path in red_paths),'RED cannot depend on another native stage')
        else:
            require(args.selftest_run is None and all(path is not None for path in red_paths),'GREEN requires all three exact RED receipts')
            red_build_pin=None
            for fault,path in zip(('coarse','local','winner'),red_paths):
                receipt,receipt_pin=stage_gate(path,fault,input_pin,runtime);red_pins.append(receipt_pin)
                old,old_pin=build_gate(receipt['build_manifest']['path'],True)
                c.equivalent_build_inputs(old,build)
                require(red_build_pin is None or old_pin==red_build_pin,'Three RED fixtures must use one exact RED build')
                red_build_pin=old_pin
        reservation=reserve(HERE/'phase2_stage_reservations',stage,run,dict(build=build_pin,input_plan=input_pin,selftest=selftest_pin,red_receipts=red_pins))
        reservation_pin=pin(reservation)
        image_before=runtime.verify_images(prior) if args.mode=='phase2' else []
        command=[build['executable']['path'],'--mode',args.mode,'--fault',args.fault,'--plan',input_pin['path'],'--output',str(native)]
        env=dict(os.environ);env['PATH']=str(Path(build['compiler']).parent)+';'+str(Path(build['opencv'])/'build/bin')+';'+env.get('PATH','')
        execution=dict(command=command,working_directory=str(V1),mode=args.mode,fault=args.fault,
                       build_manifest=build_pin,input_plan=input_pin,selftest=selftest_pin,red_receipts=red_pins,
                       reservation=reservation_pin,borrowed_phase1_watchdog_source=runtime_pin,
                       runtime_path_prefix=[str(Path(build['compiler']).parent),str(Path(build['opencv'])/'build/bin')],
                       maximum_dataset_kernel_calls=0 if args.mode=='selftest' else 14800,
                       full_class_search_replays=0,public_detector_match_calls=0,native_exit_code=None,started_utc=time.time())
        (run/'execution_provenance.json').write_text(json.dumps(execution,indent=2)+'\n')
        watchdog=runtime.run_native(command,env,run);native_exit=watchdog['native_exit_code']
        execution['native_exit_code']=native_exit;execution['finished_utc']=time.time()
        (run/'execution_provenance.json').write_text(json.dumps(execution,indent=2)+'\n')
        (run/'watchdog.json').write_text(json.dumps(watchdog,indent=2)+'\n')
        image_after=runtime.verify_images(prior) if args.mode=='phase2' else []
        require(image_before==image_after,'Permitted dataset image bytes changed during Phase2')
        _,latest=build_gate(args.build_manifest,red);require(latest==build_pin,'Build manifest changed')
        _,latest,_=plan_gate(args.plan,runtime);require(latest==input_pin,'Phase2 input plan changed');check(runtime_pin);check(reservation_pin)
        if selftest_pin:
            stage_gate(args.selftest_run,'none',input_pin,runtime,build_pin);check(selftest_pin)
        for fault,path,value in zip(('coarse','local','winner'),red_paths,red_pins):
            stage_gate(path,fault,input_pin,runtime);check(value)
        summary_path=native/('selftest_result.json' if args.mode=='selftest' else 'stage_summary.json')
        summary=load(summary_path) if summary_path.exists() else None
        failure=load(native/'failure.json') if (native/'failure.json').exists() else None
        error=None
        try:
            require(watchdog['stop_reason'] is None,'Native watchdog stopped stage: '+str(watchdog['stop_reason']))
            c.native_gate(args.mode,args.fault,native_exit,summary,failure)
        except Exception as problem:
            error=str(problem)
            (run/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=error,partial_results_are_not_negatives=True),indent=2)+'\n')
        files=runtime.native_files(native);runtime.runner_gates.verify_output(native,files)
        execution_files=[pin(path) for path in sorted(run.iterdir()) if path.is_file()]
        require(sum(value['bytes'] for value in files+execution_files)<=1073741824,'Complete Phase2 numeric output exceeds one GiB')
        freeze=dict(stage=args.mode,fault=args.fault,completed=error is None,native_exit_code=native_exit,
                    expected_native_failure=red,build_manifest=build_pin,input_plan=input_pin,selftest=selftest_pin,
                    red_receipts=red_pins,reservation=reservation_pin,files=files,execution_files=execution_files,
                    image_before=image_before,image_after=image_after,image_hash_operations=len(image_before)+len(image_after),
                    unique_dataset_image_files_opened=len(image_before),summary=summary,native_failure=failure,
                    partial_results_are_not_negatives=error is not None,accuracy_improvement_claim=False)
        freeze_path.write_text(json.dumps(freeze,indent=2)+'\n')
        require(error is None,'Native stage failed; immutable reservation and partial evidence retained: '+str(error))
        print(json.dumps(dict(passed=True,stage=args.mode,fault=args.fault,full_class_search_replays=0,public_detector_match_calls=0)))
    except Exception as error:
        if not freeze_path.exists():
            (run/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),native_exit_code=native_exit,
                reservation=reservation_pin,partial_results_are_not_negatives=True,do_not_silently_rerun_reserved_stage=True),indent=2)+'\n')
        raise


if __name__=='__main__':
    main()
