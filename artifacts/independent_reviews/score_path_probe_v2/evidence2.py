"""Independent provenance gates. Image/template bytes and execution forbidden."""
import hashlib
import json
from pathlib import Path
import re
import numeric2 as n

PLAN_SHA='830a77d629ad766df998aa59fbd1b6cf6bc207c900263afd04b890560eb9215a'
FREEZE_SHA='b6933c13f9ce825c2acbab62290a3a4624e7dfb954c7988234428040424c9bc9'
PHASE1_SHA='f2be7500b13fbe1cad2bb9bc8d223b7bbf37af71919441f5b2bc2d1251e0d5ed'
PHASE1_AUDIT_SHA='67ff1b3967e762984bf9a35e358fa2a1a9d039124de88b7fc53c98eb18eacc06'
SOURCE_CHECK_SHA='bfb97fe7263e4d547526c184bd0089c852e4658351f953d7d8d20003b4c4f1b3'
EXPECTED_PHASE2=dict(coarse_similarity_calls=430,local_map_calls=7185,local_fused_maximum_calls=7185,coarse_cells=1185080,local_cells=1839360,feature_response_digits=73337912,rgb_positive_controls=215,decoded_operations=213,unique_image_files=175,job_identity_rows=430,unique_job_keys=430,physical_feature_probes=13534,fullclass_nms_frames=426,native_grid_points=751,point_parent_links=12016,full_class_search_replays=0,public_detector_match_calls=0,all_oracles_exact=1,all_occurrence_gates_exact=1,all_fullclass_nms_assignment_exact=1,accuracy_improvement_claim=0)
DENIED={'.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp','.smd','.smdx'}


def safe(path):
    path=Path(path).resolve()
    n.need(path.suffix.lower() not in DENIED and not path.name.lower().endswith(('.yml.gz','.yaml.gz')),'Image/serialized-template bytes are forbidden')
    return path


def pin(path):
    path=safe(path);digest=hashlib.sha256();size=0
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block);size+=len(block)
    return dict(path=str(path),sha256=digest.hexdigest(),bytes=size)


def validate_pin(value):
    n.need(type(value) is dict and set(value)=={'path','sha256','bytes'},'Pin schema differs')
    n.need(isinstance(value['path'],str) and type(value['bytes']) is int and value['bytes']>=0 and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None,'Invalid pin declaration')


def read(path):return json.loads(safe(path).read_text(encoding='utf-8-sig'))


def validate_stage(stage):
    mode,fault=stage.get('stage'),stage.get('fault');red=fault!='none';phase=mode=='phase2'
    n.need(mode in ('selftest','phase2') and fault in ('none','coarse','local','winner') and (not phase or not red),'Stage/fault scope differs')
    n.need(stage.get('completed') is True and stage.get('expected_native_failure') is red and stage.get('partial_results_are_not_negatives') is False and stage.get('accuracy_improvement_claim') is False,'Incomplete stage/claim boundary differs')
    n.need(stage.get('image_hash_operations')==(350 if phase else 0) and stage.get('unique_dataset_image_files_opened')==(175 if phase else 0),'Stage image budget differs')
    n.need(len(stage.get('image_before',[]))==len(stage.get('image_after',[]))==(175 if phase else 0),'Image declaration count differs')
    summary,failure=stage.get('summary'),stage.get('native_failure')
    if red:
        n.need(stage.get('native_exit_code')!=0 and summary is None and isinstance(failure,dict),'RED must fail native without summary')
        n.need(failure.get('reason')=='Independent '+fault+' oracle mismatch' and all(failure.get(key)==0 for key in ('decoded_operations_started','full_class_search_replays','public_detector_match_calls')),'Wrong RED failure or image/search execution');return
    n.need(stage.get('native_exit_code')==0 and failure is None and isinstance(summary,dict) and summary.get('passed')==1 and summary.get('stage')==mode,'GREEN/dataset native completion differs')
    expected=EXPECTED_PHASE2 if phase else dict(coarse_cells=12,local_cells=256,scalar_native_oracles=1,dataset_image_reads=0,full_class_search_replays=0,public_detector_match_calls=0)
    n.need(all(summary.get(key)==value for key,value in expected.items()),'Native exact scope/oracle/control budget differs')
    if phase:n.need(0<summary.get('peak_rss_bytes',-1)<=1610612736 and 0<=summary.get('numeric_output_bytes',-1)<=1073741824,'Native resource limit differs')


def validate_build(build,red):
    n.need(build.get('passed') is True and build.get('target')=='score_path_probe_phase2' and build.get('core_revision')=='b25df46f6ddf9c24fb43f5836f1414dc38c8caed' and build.get('red_controls') is red,'Build identity differs')
    n.need(all(build.get(key)==0 for key in ('image_decodes','full_class_search_replays','public_detector_match_calls')),'Build execution scope differs')
    units,commands=build.get('dependency_units',[]),build.get('commands',[])
    n.need(len(units)==1 and Path(units[0]['source']).name=='phase2.cpp' and Path(units[0]['included_private_core']).name=='line2Dup.cpp','Single included-core TU differs')
    n.need(len(commands)==3 and [row['label'] for row in commands]==['dependency_before','compile','link'] and all(row.get('exit_code')==0 for row in commands),'Build command completion/order differs')
    for command in commands[:2]:
        n.need(('-DSCORE_PATH_RED_CONTROLS' in command['command']) is red and sum(Path(token).name=='phase2.cpp' for token in command['command'])==1,'Actual source/RED macro differs')
    n.need('-M' in commands[0]['command'] and '-c' in commands[1]['command'],'Dependency/compile mode differs')
    n.need([token for token in commands[2]['command'] if token.endswith('.o')]==[units[0]['object']['path']],'Extra/separately linked native object')


def equivalent_builds(red,green):
    normalized=[];headers=[]
    for build in (red,green):
        n.need(len(build['dependency_units'])==1,'Build equivalence requires one TU')
        hdr=build['dependency_units'][0]['generated_preprocess_header'];sources=build['project_sources']
        n.need(sources.count(hdr)==1 and sum(row['path']==hdr['path'] for row in sources)==1,'Generated header provenance is ambiguous')
        rest=[row for row in sources if row['path']!=hdr['path']]
        n.need(len({row['path'] for row in rest})==len(rest),'Duplicate project-source member')
        normalized.append(rest);headers.append((hdr['sha256'],hdr['bytes']))
    n.need(normalized[0]==normalized[1] and headers[0]==headers[1] and red['compiler_tools_and_link_libraries']==green['compiler_tools_and_link_libraries'],'RED/GREEN source/tool bytes differ')


class Closure:
    def __init__(self,probe):self.probe=Path(probe).resolve();self.checked={};self.builds={};self.stages={};self.serialized_bank_declarations=[]

    def check(self,value):
        validate_pin(value);path=safe(value['path']);key=str(path)
        if key in self.checked:n.need(self.checked[key]==value,'Conflicting pin for '+key)
        else:n.need(pin(path)==value,'Pinned bytes changed: '+key);self.checked[key]=value
        return path

    def members(self,directory,values):
        directory=Path(directory).resolve();paths=[self.check(value) for value in values]
        n.need(len(paths)==len(set(paths)) and all(path.is_relative_to(directory) for path in paths),'Duplicate/outside native output member')
        actual={path.resolve() for path in directory.rglob('*') if path.is_file()}
        n.need(actual==set(paths),'Complete native output membership differs');return actual

    def pins_below(self,value):
        if isinstance(value,dict):
            if set(value)=={'path','sha256','bytes'}:self.check(value)
            else:
                for child in value.values():self.pins_below(child)
        elif isinstance(value,list):
            for child in value:self.pins_below(child)

    def build(self,value,red):
        path=self.check(value);n.need(path.is_relative_to(self.probe),'Outside Phase2 build')
        if str(path) in self.builds:
            build=self.builds[str(path)];validate_build(build,red);return build
        build=read(path);validate_build(build,red);self.pins_below(build)
        n.need(not(path.parent/'failure.json').exists() and read(path.parent/'attempts.json')==build['commands'],'Build failure/actual command log differs')
        unit=build['dependency_units'][0]
        n.need(Path(unit['source']).resolve()==self.probe/'phase2.cpp' and Path(build['executable']['path']).resolve()==path.parent/'score_probe_v2.exe','Actual build source/executable differs')
        project={Path(row['path']).resolve() for row in build['project_sources']};deps={Path(row['path']).resolve() for row in unit['dependencies']}
        n.need({self.probe/'phase2.cpp',Path(unit['included_private_core']).resolve(),Path(unit['generated_preprocess_header']['path']).resolve()}<=project&deps,'Compiler closure omits actual included source/header')
        extraction=read(build['preprocessing_extraction']['path']);self.pins_below(extraction)
        n.need(extraction.get('original_source_edited') is False and extraction.get('generated_file_is_transformed') is True,'Preprocessing extraction boundary differs')
        source=safe(extraction['source']['path']).read_bytes();markers=(b'using Memories = ',b'struct Maps { ',b'static Maps preprocess(',b'// Independent oracle:')
        n.need(all(source.count(marker)==1 for marker in markers),'Ambiguous exact preprocessing markers')
        a,m,s,z=[source.index(marker) for marker in markers];n.need(a<m<s<z,'Preprocessing source order differs')
        chunks=[source[a:source.index(b'\n',a)+1],source[m:source.index(b'\n',m)+1],source[s:z]]
        n.need([row['utf8'].encode() for row in extraction['components']]==chunks,'Exact preprocessing source slices differ')
        for row,chunk in zip(extraction['components'],chunks):n.need(row['sha256']==hashlib.sha256(chunk).hexdigest() and row['bytes']==len(chunk),'Preprocessing component digest differs')
        header=b'#pragma once\nnamespace probe_v2 {\n'+b''.join(chunks)+b'\n}\n'
        n.need(safe(extraction['generated_header']['path']).read_bytes()==header and extraction['generated_header']==unit['generated_preprocess_header'],'Generated preprocessing wrapper bytes differ')
        self.builds[str(path)]=build;return build

    def stage(self,value,mode,fault,plan_pin,images,expected_build=None):
        path=self.check(value);run=path.parent;n.need(path.name=='PHASE2_STAGE_FREEZE.json' and run.is_relative_to(self.probe),'Outside Phase2 stage')
        stage=read(path);validate_stage(stage);n.need(stage['stage']==mode and stage['fault']==fault and stage['input_plan']==plan_pin,'Stage identity/plan differs')
        if expected_build is not None:n.need(stage['build_manifest']==expected_build,'Dataset/GREEN build mismatch')
        red=fault!='none';build=self.build(stage['build_manifest'],red);native=run/'native';members=self.members(native,stage['files'])
        expected={native/'.gitignore'}
        if mode=='phase2':expected|={native/'stage_summary.json'}|{native/(name+'.csv.gz') for name in ('jobs','feature_vectors','native_cells','local_maxima','physical_anchors','parent_links','occurrences','fullclass_nms_assignment')}
        else:expected.add(native/('failure.json' if red else 'selftest_result.json'))
        n.need(members==expected,'Native numeric schema differs')
        n.need((native/'.gitignore').read_text()=='*\n','Native ignore file differs')
        summary=read(native/('stage_summary.json' if mode=='phase2' else 'selftest_result.json')) if not red else None
        failure=read(native/'failure.json') if red else None
        n.need(summary==stage['summary'] and failure==stage['native_failure'],'Frozen native result differs')
        execution=stage['execution_files'];n.need(len(execution)==4 and {Path(row['path']).name for row in execution}=={'execution_provenance.json','watchdog.json','native.stdout','native.stderr'},'Execution file schema differs')
        for row in execution:n.need(self.check(row).parent==run,'Outside execution file')
        n.need({file.resolve() for file in run.iterdir() if file.is_file()}=={Path(row['path']).resolve() for row in execution}|{path},'Complete runner file membership differs')
        n.need(sum(row['bytes'] for row in stage['files']+execution)<=1073741824,'Complete output exceeds 1 GiB')
        reservation=read(self.check(stage['reservation']));expected_stage='phase2' if mode=='phase2' else 'selftest_red_'+fault if red else 'selftest_green'
        expected_inputs=dict(build=stage['build_manifest'],input_plan=plan_pin,selftest=stage['selftest'],red_receipts=stage['red_receipts'])
        n.need(reservation.get('stage')==expected_stage and Path(reservation.get('output','')).resolve()==run and reservation.get('inputs')==expected_inputs and reservation.get('one_shot') is True and reservation.get('incomplete_run_still_consumes_reservation') is True,'One-shot reservation binding differs')
        execution=read(run/'execution_provenance.json');expected_command=[build['executable']['path'],'--mode',mode,'--fault',fault,'--plan',plan_pin['path'],'--output',str(native)]
        n.need(execution.get('command')==expected_command and execution.get('mode')==mode and execution.get('fault')==fault and execution.get('native_exit_code')==stage['native_exit_code'],'Actual native command/exit differs')
        for field in ('build_manifest','input_plan','selftest','red_receipts','reservation'):n.need(execution.get(field)==stage.get(field),'Execution '+field+' binding differs')
        self.check(execution['borrowed_phase1_watchdog_source'])
        n.need(execution.get('maximum_dataset_kernel_calls')==(14800 if mode=='phase2' else 0) and execution.get('full_class_search_replays')==execution.get('public_detector_match_calls')==0,'Execution kernel/search scope differs')
        n.need(execution.get('runtime_path_prefix')==[str(Path(build['compiler']).parent),str(Path(build['opencv'])/'build/bin')],'Execution runtime path differs')
        n.need(0<=n.finite(execution['finished_utc'])-n.finite(execution['started_utc'])<=3605,'Native execution duration differs')
        watchdog=read(run/'watchdog.json');n.need(watchdog.get('native_exit_code')==stage['native_exit_code'] and watchdog.get('stop_reason') is None and 0<=watchdog.get('elapsed_seconds',-1)<=3600 and 0<=watchdog.get('maximum_observed_rss_bytes',-1)<=1610612736 and 0<=watchdog.get('maximum_observed_output_bytes',-1)<=1073741824,'Watchdog budget/completion differs')
        n.need(stage['image_before']==stage['image_after']==images,'Image before/after declarations differ from allowlist')
        if mode=='phase2':
            n.need(stage['selftest'] is not None and stage['red_receipts']==[],'Dataset requires exact GREEN selftest only')
            self.stage(stage['selftest'],'selftest','none',plan_pin,[],stage['build_manifest'])
        elif red:n.need(stage['selftest'] is None and stage['red_receipts']==[],'RED unexpectedly depends on another stage')
        else:
            n.need(stage['selftest'] is None and len(stage['red_receipts'])==3,'GREEN needs all three exact RED controls')
            red_build=None
            for name,old_pin in zip(('coarse','local','winner'),stage['red_receipts']):
                old=self.stage(old_pin,'selftest',name,plan_pin,[]);old_build=self.build(old['build_manifest'],True);equivalent_builds(old_build,build)
                n.need(red_build is None or old['build_manifest']==red_build,'Three RED controls use different builds');red_build=old['build_manifest']
        self.stages[str(path)]=stage;return stage


def prior_numeric(closure,prior):
    # The historical field is named numeric_pins but includes serialized bank
    # files. Never weaken safe(): compare precisely the expected bank paths as
    # declarations, with their authority inherited from the pinned Phase1 audit.
    expected={str((Path(bank[field])/('templates_tless_object_'+str(bank['object_id'])+'.yml.gz')).resolve()) for bank in prior['banks'] for field in ('rgb_training','binary_training')}
    seen=set();declarations=[]
    for value in prior['numeric_pins']:
        validate_pin(value);path=Path(value['path']).resolve()
        if path.name.lower().endswith(('.yml.gz','.yaml.gz')):
            key=str(path);n.need(key in expected and key not in seen,'Unknown/duplicate inherited serialized-bank declaration');seen.add(key);declarations.append(value)
        else:closure.check(value)
    n.need(seen==expected,'Missing inherited serialized-bank declaration')
    closure.serialized_bank_declarations=declarations
    return declarations


def prepare(freeze_path):
    probe=Path(__file__).resolve().parents[2]/'quality_failure_analysis/score_path_probe_v2'
    closure=Closure(probe);freeze_pin=pin(freeze_path)
    n.need(freeze_pin['sha256']==FREEZE_SHA and Path(freeze_path).resolve()==probe/'probe_phase2_v1/PHASE2_STAGE_FREEZE.json','Unapproved immutable Phase2 freeze')
    plan_path=probe/'PHASE2_INPUTS_V1.json';plan_pin=pin(plan_path);n.need(plan_pin['sha256']==PLAN_SHA,'Unapproved Phase2 plan')
    plan=read(plan_path);n.need(plan.get('phase')=='phase2' and plan.get('rgb_tp_identities')==215 and plan.get('arm_identity_probes')==430 and len(plan['jobs'])==430,'Fixed Phase2 scope differs')
    for field in ('prior_phase1_receipt','prior_input_plan','prior_v22_audit','independent_phase1_audit','loaded_layers_pin'):closure.check(plan[field])
    for field in ('metadata_pins','phase1_project_source_pins','proposal_source_pins'):
        for value in plan[field]:closure.check(value)
    n.need(plan['prior_phase1_receipt']['sha256']==PHASE1_SHA and plan['independent_phase1_audit']['sha256']==PHASE1_AUDIT_SHA,'Prior completed Phase1 authority differs')
    old_audit=read(plan['independent_phase1_audit']['path']);n.need(old_audit.get('passed') is True and old_audit.get('stage')=='score_path_probe_v1_phase1' and old_audit['phase1_freeze']==plan['prior_phase1_receipt'] and old_audit['input_plan']==plan['prior_input_plan'],'Independent Phase1 audit is not bound/passed')
    prior=read(plan['prior_input_plan']['path']);n.need(prior.get('rgb_tp_identities')==215 and prior.get('object_frames')==213 and prior.get('image_frames')==175,'Prior scope differs')
    n.need(len(prior_numeric(closure,prior))==12,'Inherited serialized-bank declaration coverage differs')
    for value in prior['permitted_image_pins']:validate_pin(value)
    old_freeze=read(plan['prior_phase1_receipt']['path']);n.need(old_freeze.get('completed') is True and old_freeze.get('stage')=='phase1' and old_freeze['input_plan']==plan['prior_input_plan'],'Prior Phase1 freeze completion differs')
    closure.members(Path(plan['prior_phase1_receipt']['path']).parent/'native',old_freeze['files'])
    for value in old_freeze['execution_files']:closure.check(value)
    source_check=pin(probe/'source_check_v1/result.json');n.need(source_check['sha256']==SOURCE_CHECK_SHA,'Frozen Phase2 source check differs');closure.check(source_check)
    stage=closure.stage(freeze_pin,'phase2','none',plan_pin,prior['permitted_image_pins'])
    n.need(stage['build_manifest']['sha256']=='24beff8fd290a23fd05a611ee84bda38621b3b6e9022ca2f5ff462f85ed618e1' and stage['selftest']['sha256']=='de3ccc0a5f6aeb76522cbf6d5bb09f4ab65e9b959a92692be2be2fe9cbf0af60','Approved build/GREEN pins differ')
    return closure,plan,prior,stage,freeze_pin,plan_pin
