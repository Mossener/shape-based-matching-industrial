"""Independent read-only evidence checks. Never opens a dataset image."""
import hashlib
import json
import math
from pathlib import Path
import re

from numeric import need

CORE='b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
PLAN_SHA='353615a753a0be27a2665997488301259fe99989858068895870d16fe32de91c'
AUDIT_SHA='38f9025da7c7320f2e42eb632381f9995c6718d64eaa40d7378e205d73047e68'
OBJECTS=(1,2,5,8,12,17)
SCENES={1,4,6,7,8,10,12,13}
IMAGES={'.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp','.smd','.smdx'}

def safe(path):
    path=Path(path).resolve()
    need(path.suffix.lower() not in IMAGES,'Image/private shape bytes are outside numeric auditor authority')
    return path

def pin(path):
    path=safe(path); digest=hashlib.sha256(); size=0
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): digest.update(block); size+=len(block)
    return dict(path=str(path),sha256=digest.hexdigest(),bytes=size)

def validate_pin(value):
    need(isinstance(value,dict) and set(value)=={'path','sha256','bytes'},'Pin schema differs')
    need(isinstance(value['path'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None and type(value['bytes']) is int and value['bytes']>=0,'Invalid pin declaration')

def verify_pin(value):
    validate_pin(value); path=safe(value['path']); need(pin(path)==value,'Pinned bytes differ: '+str(path)); return path

def read(path):
    return json.loads(safe(path).read_text(encoding='utf-8-sig'))

def output_members(directory,pins):
    directory=Path(directory).resolve(); paths=[safe(value['path']) for value in pins]
    need(len(paths)==len(set(paths)) and all(path.is_relative_to(directory) for path in paths),'Duplicate/outside output member')
    actual={path.resolve() for path in directory.rglob('*') if path.is_file()}
    need(actual==set(paths),'Complete output member set differs')
    for value in pins: verify_pin(value)
    return actual

def validate_build_fields(build,red):
    need(build.get('passed') is True and build.get('target')=='score_path_probe_phase1' and build.get('core_revision')==CORE and build.get('red_negative_control') is red,'Build identity/completion differs')
    need(all(build.get(key)==0 for key in ('image_decodes','full_class_search_replays','public_detector_match_calls')),'Build execution scope differs')
    units=build.get('dependency_units',[]); commands=build.get('commands',[])
    need(len(units)==1 and Path(units[0]['source']).name=='probe.cpp' and Path(units[0]['included_private_core']).name=='line2Dup.cpp','Single included-core translation unit differs')
    need(len(commands)==3 and [v['label'] for v in commands]==['dependency_before','compile','link'] and all(v.get('exit_code')==0 for v in commands),'Successful command sequence differs')
    for command in commands[:2]:
        need(('-DSCORE_PROBE_ORACLE_RED' in command['command']) is red,'Build RED macro differs')
        need(sum(Path(token).name=='probe.cpp' for token in command['command'])==1,'Compiler source differs')
    need('-M' in commands[0]['command'] and '-c' in commands[1]['command'],'Actual compile/dependency mode differs')
    objects=[token for token in commands[2]['command'] if token.endswith('.o')]
    need(objects==[units[0]['object']['path']],'Separately linked core/extra object forbidden')

def validate_stage_fields(stage,red,summary,failure):
    mode=stage.get('stage'); phase=mode=='phase1'
    need(mode in ('selftest','phase1') and stage.get('completed') is True and stage.get('expected_native_failure') is red and stage.get('partial_results_are_not_negatives') is False and stage.get('phase2_started') is False,'Stage completion/claim boundary differs')
    need(stage.get('actual_full_class_search_replays')==(426 if phase else 0) and stage.get('image_hash_operations')==(350 if phase else 0) and stage.get('unique_dataset_image_files_opened')==(175 if phase else 0),'Stage fixed replay/image scope differs')
    if red:
        need(not phase and stage.get('native_exit_code')!=0 and summary is None and failure is not None,'RED requires failed selftest and no summary')
        need(failure.get('reason')=='Independent scalar/native score mismatch' and failure.get('full_class_search_replays_started')==0 and failure.get('public_detector_match_calls')==0 and failure.get('phase2_started')==0 and failure.get('partial_results_are_not_negatives')==1,'RED failed for unintended reason'); return
    need(stage.get('native_exit_code')==0 and failure is None and isinstance(summary,dict) and summary.get('passed')==1,'Successful stage carries failure/incomplete summary')
    need(summary.get('public_detector_match_calls')==0,'Public matcher calls outside diagnostic')
    if not phase:
        need(all(summary.get(k)==v for k,v in dict(scalar_native_cells=256,cross_template_representative_fixture=1,dataset_image_reads=0,full_class_search_replays=0).items()),'Native synthetic coverage differs')
        need(stage.get('image_before')==[] and stage.get('image_after')==[],'Selftest image closure not empty'); return
    expected=dict(stage='phase1',full_class_search_replays=426,decoded_operations=213,unique_image_files=175,rgb_tp_identities=215,post_matches=227816,all_saved_raw_exact=1,all_fine_score_bits_exact=1,phase2_started=0,accuracy_improvement_claim=0)
    need(all(summary.get(k)==v for k,v in expected.items()),'Phase1 native gate/scope differs')
    need(summary.get('pre_matches',-1)>=227816 and summary.get('independent_scalar_fine_score_rows')==summary.get('pre_matches'),'Fine-score gate row coverage differs')
    need(0<=summary.get('numeric_output_bytes',-1)<=1073741824 and 0<summary.get('peak_rss_bytes',-1)<=1610612736,'Native resource gate differs')

class Closure:
    def __init__(self,probe,experiment):
        self.probe=Path(probe).resolve(); self.experiment=Path(experiment).resolve(); self.checked={}; self.builds={}; self.stages={}; self.build_declared={}

    def check(self,value):
        validate_pin(value); key=str(safe(value['path']))
        if key in self.checked: need(self.checked[key]==value,'Conflicting pin declarations')
        else: verify_pin(value); self.checked[key]=value
        return Path(key)

    def build(self,value,red):
        path=self.check(value); need(path.is_relative_to(self.probe),'Outside probe build manifest')
        if str(path) in self.builds:
            result=self.builds[str(path)]; validate_build_fields(result,red); return result
        result=read(path); validate_build_fields(result,red)
        need(not (path.parent/'failure.json').exists(),'Successful build contains failure.json')
        need(Path(result['executable']['path']).resolve()==path.parent/'score_probe.exe','Unexpected executable path')
        unit=result['dependency_units'][0]
        need(Path(unit['source']).resolve()==self.probe/'probe.cpp' and Path(unit['included_private_core']).resolve()==self.experiment/'private_v11/line2Dup.cpp','Frozen source/core path differs')
        need(read(path.parent/'attempts.json')==result['commands'],'Actual build attempts differ')
        values=result['project_sources']+result['compiler_tools_and_link_libraries']+result['compiler_runtime_closure']['files']+result['executable_runtime_closure']['files']+[result['executable']]+unit['dependencies']+[unit['object'],unit['dependency_file']]
        need(values and all(values),'Empty build provenance closure')
        # Hash pinned build members as inert bytes; never execute/import them.
        for item in values:
            validate_pin(item); key=str(safe(item['path']))
            if key in self.build_declared: need(self.build_declared[key]==item,'Conflicting build closure pin')
            else: self.build_declared[key]=item
            self.check(item)
        project={Path(v['path']).resolve() for v in result['project_sources']}; deps={Path(v['path']).resolve() for v in unit['dependencies']}
        need({self.probe/'probe.cpp',self.experiment/'private_v11/line2Dup.cpp'}<=project & deps,'Actual compiler dependencies omit frozen included source')
        self.builds[str(path)]=result; return result

    def stage(self,value,mode,red,plan_pin,images,expected_build=None):
        path=self.check(value); run=path.parent
        need(path.name=='PROBE_STAGE_FREEZE.json' and run.is_relative_to(self.probe),'Outside stage freeze')
        stage=read(path); need(stage.get('stage')==mode and stage.get('input_plan')==plan_pin,'Stage plan/mode differs')
        if expected_build is not None: need(stage.get('build_manifest')==expected_build,'Phase1/GREEN build mismatch')
        native=run/'native'; output_members(native,stage['files'])
        execution=stage['execution_files']; names={Path(p['path']).name for p in execution}
        need(names=={'execution_provenance.json','watchdog.json','native.stdout','native.stderr'} and len(execution)==4,'Runner execution member schema differs')
        need({p.resolve() for p in run.iterdir() if p.is_file()}=={Path(p['path']).resolve() for p in execution}|{path},'Runner complete output member set differs')
        for item in execution: self.check(item); need(Path(item['path']).parent.resolve()==run,'Outside execution member')
        need(sum(v['bytes'] for v in stage['files']+execution)<=1073741824,'Runner complete measured output exceeds 1 GiB')
        summary_name='stage_summary.json' if mode=='phase1' else 'selftest_result.json'
        summary=read(native/summary_name) if (native/summary_name).is_file() else None
        failure=read(native/'failure.json') if (native/'failure.json').is_file() else None
        need(stage.get('summary')==summary,'Freeze/native summary differs'); validate_stage_fields(stage,red,summary,failure)
        if mode=='selftest':
            expected={native/'.gitignore',native/('failure.json' if red else 'selftest_result.json')}
            need({Path(p['path']).resolve() for p in stage['files']}==expected,'Selftest complete native member schema differs')
        need((native/'.gitignore').read_text()=='*\n','Native output ignore contract differs')
        build=self.build(stage['build_manifest'],red)
        reservation=read(self.check(stage['reservation']))
        expected_stage='phase1' if mode=='phase1' else 'selftest_red' if red else 'selftest_green'
        expected_inputs=dict(build=stage['build_manifest'],input_plan=plan_pin,selftest=stage.get('selftest'),negative_control=stage.get('negative_control'))
        need(reservation.get('stage')==expected_stage and Path(reservation.get('output','')).resolve()==run and reservation.get('inputs')==expected_inputs and reservation.get('one_shot') is True and reservation.get('incomplete_run_still_consumes_reservation') is True,'One-shot stage reservation differs')
        receipt=read(run/'execution_provenance.json'); command=[build['executable']['path'],'--mode',mode,'--output',str(native),'--plan',plan_pin['path']]
        need(receipt.get('command')==command and receipt.get('mode')==mode and receipt.get('build_manifest')==stage['build_manifest'] and receipt.get('input_plan')==plan_pin and receipt.get('selftest')==stage.get('selftest') and receipt.get('negative_control')==stage.get('negative_control') and receipt.get('reservation')==stage['reservation'] and receipt.get('native_exit_code')==stage['native_exit_code'],'Execution command/receipt binding differs')
        need(receipt.get('maximum_full_class_search_replays')==(426 if mode=='phase1' else 0) and receipt.get('public_detector_match_calls')==0 and receipt.get('runtime_path_prefix')==[str(Path(build['compiler']).parent),str(Path(build['opencv'])/'build/bin')],'Execution budget/runtime differs')
        need(math.isfinite(receipt['started_utc']) and math.isfinite(receipt['finished_utc']) and 0<=receipt['finished_utc']-receipt['started_utc']<=3605,'Execution duration differs')
        watchdog=read(run/'watchdog.json')
        need(watchdog.get('native_exit_code')==stage['native_exit_code'] and watchdog.get('stop_reason') is None and 0<=watchdog.get('elapsed_seconds',-1)<=3600 and 0<=watchdog.get('maximum_observed_rss_bytes',-1)<=1610612736 and 0<=watchdog.get('maximum_observed_output_bytes',-1)<=1073741824,'Watchdog completion/budget differs')
        if mode=='phase1':
            need(stage.get('image_before')==images and stage.get('image_after')==images,'Declared before/after image allowlist differs')
            need(stage.get('selftest') is not None and stage.get('negative_control') is None,'Phase1 requires only bound GREEN selftest')
            self.stage(stage['selftest'],'selftest',False,plan_pin,[],stage['build_manifest'])
        elif red:
            need(stage.get('selftest') is None and stage.get('negative_control') is None,'RED unexpected inherited stage')
        else:
            need(stage.get('selftest') is None and stage.get('negative_control') is not None,'GREEN requires RED receipt')
            old=self.stage(stage['negative_control'],'selftest',True,plan_pin,[])
            old_build=self.build(old['build_manifest'],True)
            need(old_build['project_sources']==build['project_sources'] and old_build['compiler_tools_and_link_libraries']==build['compiler_tools_and_link_libraries'],'RED/GREEN source/tool closure mismatch')
        self.stages[str(path)]=stage; return stage

def check_plan(path,closure):
    value=pin(path); need(value['sha256']==PLAN_SHA and Path(path).resolve()==closure.probe/'PROBE_INPUTS_V1.json','Exact prepared plan differs')
    plan=read(path)
    expected=dict(version='score_path_probe_v1',stage='phase1',rgb_tp_identities=215,object_frames=213,image_frames=175,full_class_search_replays=426,public_detector_match_calls=0,rgb_reference_raw_rows=71178,binary_reference_raw_rows=156638,images_opened_by_preparer=0,matcher_calls=0,heldout_access=False,phase2_authorized=False)
    need(all(plan.get(k)==v for k,v in expected.items()),'Plan scope/control boundary differs')
    need(plan['audit']['sha256']==AUDIT_SHA and len(plan['numeric_pins'])==880,'Plan preserved audit/numeric count differs')
    for item in plan['numeric_pins']+[plan['audit']]: closure.check(item)
    images=plan['permitted_image_pins']; need(len(images)==175,'Declared permitted image count differs')
    image_paths=set()
    for image in images:
        validate_pin(image); image_path=Path(image['path']).resolve(); need(image_path.suffix=='.png' and image_path not in image_paths,'Invalid/duplicate image declaration'); image_paths.add(image_path)
    frames=plan['frames']; keys=[]; used_images=set(); counts={obj:0 for obj in OBJECTS}; identities={obj:0 for obj in OBJECTS}
    for frame in frames:
        obj,scene,image=frame['object_id'],frame['scene'],frame['image']; need(obj in OBJECTS and scene in SCENES and type(image) is int and image>=0,'Forbidden frame scope')
        keys.append((obj,scene,image)); counts[obj]+=1; identities[obj]+=len(frame['targets'])
        relative=f'test_primesense/{scene:06d}/rgb/{image:06d}.png'; need(frame['rgb_relative']==relative,'Exact development RGB relative path differs')
        image_path=Path(frame['image_path']).resolve(); need(image_path in image_paths and image_path.as_posix().endswith('/'+relative),'Frame/declared image binding differs'); used_images.add(image_path)
        need(len({v['gt_id'] for v in frame['targets']})==len(frame['targets']) and frame['targets']==sorted(frame['targets'],key=lambda v:v['gt_id']),'Target identity/order differs')
    need(len(keys)==len(set(keys))==213 and keys==sorted(keys) and used_images==image_paths,'Frame coverage/order differs')
    need(list(counts.values())==[37,67,22,1,36,50] and list(identities.values())==[37,69,22,1,36,50],'Per-object frame/identity counts differ')
    banks=plan['banks']; need([b['object_id'] for b in banks]==list(OBJECTS) and [b['rgb_template_count'] for b in banks]==[2153,2646,3416,3456,3372,3156],'Bank count/order differs')
    return plan,value
