"""Independent fixed V31 evidence contract; target helpers are never imported."""
from pathlib import Path
from evidence import need,loads,integer,pin_schema

OBJECTS=[1,2,5,8,12,17]
ARMS=('rgb_control','rgb_pooled_features','rgb_stratified_features')
PATHS=('fallback','fused')
COMPARISONS=ARMS[1:]
PROTOCOL_SHA='628b260bbca50bca666858f54b181afc5fb92e01eaab9b2ed46d6b4ac6e8f19b'
INHERITED_QUALITY_SHA='9659c119fa7c64dbd673d49397cc0b7dc86ef573aa4530a329fbc4da52f1ace6'
INHERITED_CLOSURE_SHA='9f0a6fd135716495cb51cde6918a022fd6514e2177941cd453ff6eb19a83f2ff'
HELDOUT={11,14,15,16,17,18,19,20}
STAGES={'old_gate':96,'pilot':288,'development':14400,'timing':29952}
BANK_KEYS=(('rgb_control','control_training','control_template_count'),
           ('rgb_pooled_features','pooled_training','pooled_template_count'),
           ('rgb_stratified_features','stratified_training','stratified_template_count'))
INPUT_VERSION='rgb_stratified_quality_inputs_v1'


def input_scope(inputs):
    need(inputs['version']==INPUT_VERSION and inputs['objects']==OBJECTS
         and inputs['arms']==list(ARMS) and inputs['total_matcher_call_budget']==44736,'quality input scope differs')
    for field in ('dataset_image_reads','image_decodes','matcher_calls','training_image_reads'):
        need(type(inputs[field]) is int and inputs[field]==0,'input declaration reads/calls differs')


def pin_map(records):
    need(isinstance(records,list),'pin list required')
    result={}
    for pin in records:
        pin_schema(pin); key=str(Path(pin['path']).resolve())
        need(key not in result,'duplicate declared numeric pin')
        result[key]=pin
    return result


def frozen_numeric_pin_map(inputs):
    """Two declared roles may share only the same frozen V30 closure pin."""
    shared=inputs['inherited_input_closure'];pin_schema(shared)
    source=Path(shared['path']);key=str(source.resolve())
    need(key==shared['path'] and source.name=='INPUT_CLOSURE.json' and
         source.parent.name=='rgb_dilated_mask_experiment' and source.parent.parent.name=='artifacts' and
         True,'fixed inherited V30 closure role differs')
    records=inputs['frozen_numeric_files'];need(isinstance(records,list),'pin list required')
    result={};shared_count=0
    for pin in records:
        pin_schema(pin);path=str(Path(pin['path']).resolve())
        if path==key:
            need(pin==shared,'shared inherited closure pin conflicts')
            shared_count+=1
            need(shared_count<=2,'inherited closure occurs more than two roles')
        else:need(path not in result,'duplicate declared numeric pin')
        result[path]=pin
    need(shared_count in (1,2),'inherited closure role missing from frozen numeric list')
    return result


def validate_accepted_report(report):
    need(report.get('passed') is True and report.get('schema')=='independent_stratified_training_geometry_audit_v1'
         and report.get('scope')=='training_and_exact_geometry' and report.get('numeric_audit_passed') is True
         and report.get('production_promotion') is False,
         'accepted independent report did not pass')


def receipt_bindings(report,acceptance):
    pins=report.get('input_pins'); need(isinstance(pins,(dict,list)),'accepted receipt input pins missing')
    if isinstance(pins,list): pins=pin_map(pins)
    for name in ('training_freeze','geometry_freeze'):
        expected=acceptance[name]; observed=pins.get(expected['path'],{})
        need(all(observed.get(k)==expected[k] for k in ('bytes','sha256')),
             'accepted receipt does not bind training/geometry freeze')


def reference_bindings(inputs,inherited,closure,common_stage):
    need(common_stage['completed'] is True and common_stage['native_exit_code']==0 and
         common_stage['stage']=='development','inherited common C0 stage is incomplete')
    common_pins=pin_map(common_stage['files']); references=pin_map(inputs['raw_reference_files'])
    old_root=Path(closure['inherited_frozen_root']).resolve(); required={}
    inherited_banks={row['object_id']:row for row in inherited['rgb_banks']}
    common_native=Path(inputs['inherited_c0_development_stage']['path']).resolve().parent/'native'
    bank_pins=pin_map(inputs['bank_input_files'])
    frames=schedule(inputs); pilot_frames=set(schedule(inputs,pilot=True))
    for row in inputs['banks']:
        obj=row['object_id']; old=inherited_banks[obj]
        need(row['class_id']==f'tless_object_{obj}' and row['control_training']==old['rgb_training']
             and row['control_template_count']==old['rgb_template_count']
             and row['original_pilot_raw']==old['original_pilot_raw']
             and Path(row['c0_common_raw']).resolve()==common_native/f'obj{obj}'/ARMS[0],
             'C0 bank/reference source directory differs')
        for name in ('template_metadata.json',f'templates_tless_object_{obj}.yml.gz'):
            path=(Path(row['control_training'])/name).resolve()
            expected=dict(path=str(path),**closure['private_files'][path.relative_to(old_root).as_posix()])
            need(bank_pins.get(str(path))==expected,'C0 bank differs from inherited input closure')
        for frame in frames:
            for path in PATHS:
                prefix=f's{frame[0]}_i{frame[1]}_{path}_raw'
                for suffix in ('.csv.gz','_manifest.json'):
                    member=str((Path(row['c0_common_raw'])/(prefix+suffix)).resolve())
                    need(member in common_pins,'common C0 raw archive/manifest not in inherited stage')
                    required[member]=common_pins[member]
                    if frame in pilot_frames:
                        old_path=(Path(row['original_pilot_raw'])/(prefix+suffix)).resolve()
                        required[str(old_path)]=dict(path=str(old_path),
                            **closure['private_files'][old_path.relative_to(old_root).as_posix()])
    need(references==required,'complete C0 raw reference allowlist differs')


def validate_bank_bindings(inputs,training):
    original=training.get('banks',training.get('quality',{}).get('banks'))
    need(isinstance(original,list) and [r['object_id'] for r in original]==OBJECTS,'accepted training banks scope differs')
    need([r['object_id'] for r in inputs['banks']]==OBJECTS,'quality bank scope differs')
    directories={}; all_directories=set()
    for observed,expected in zip(inputs['banks'],original):
        obj=expected['object_id']
        for token,(_,directory,count) in zip(('C0','P','B'),BANK_KEYS):
            need(observed[directory]==expected[directory] and type(expected[count]) is int and
                 type(observed[count]) is int and observed[count]==expected[count]>0,
                 'accepted bank directory/count differs')
            path=Path(expected[directory]); need(path.is_absolute(),'absolute bank directory required')
            canonical=str(path.resolve()); need(canonical not in all_directories,'bank directories overlap')
            all_directories.add(canonical); directories[(obj,token)]=path.resolve()
    bank_pins=pin_map(inputs['bank_input_files']); need(len(bank_pins)==36,'18 banks need 36 input pins')
    need(isinstance(training.get('bank_files'),list) and len(training['bank_files'])==18,
         'accepted training must pin all 18 banks')
    identities=set(); expected_pins=set()
    for row in training['bank_files']:
        identity=(row['object_id'],row['arm']); need(identity not in identities,'duplicate accepted bank'); identities.add(identity)
        need(identity in directories,'accepted bank identity differs'); obj=identity[0]; directory=directories[identity]
        for name,filename in (('bank',f'templates_tless_object_{obj}.yml.gz'),('metadata','template_metadata.json')):
            pin=row[name]; pin_schema(pin); path=str(Path(pin['path']).resolve())
            need(path==str(directory/filename),'accepted bank metadata/payload origin differs')
            need(bank_pins.get(path)==pin,'quality bank pin differs from training freeze'); expected_pins.add(path)
    need(identities==set(directories) and set(bank_pins)==expected_pins,'accepted bank coverage differs')


def padding(plan):
    need(isinstance(plan,dict),'padding object required')
    w,h=plan['width'],plan['height']; a=plan['padding_ltrb']
    need(type(w) is int and type(h) is int and isinstance(a,list) and len(a)==4 and
         all(type(x) is int for x in a),'integer padding required')
    need(plan['banks']==18 and plan['geometry_feasible'] in (True,1),'18 feasible banks required')
    need(a[0]==a[1]==64 and a[2]>=64 and a[3]>=228 and w==720+a[0]+a[2] and h==540+a[1]+a[3]
         and w>=848 and h>=832 and w%16==h%16==0 and max(w,h)<=2048 and w*h<=2097152
         and w*h*512<=1073741824,'padding formula/resource bound differs')
    return dict(width=w,height=h,padding_ltrb=a,banks=18,geometry_feasible=1)


def schedule(inputs,timing=False,pilot=False):
    rows=inputs['development']; need(isinstance(rows,list) and len(rows)==400,'400 development frames required')
    keys=[]; chosen=[]
    for row in rows:
        scene,image=integer(row['scene_id'],1),integer(row['image_id'],0)
        need(scene not in HELDOUT,'heldout scene refused')
        key=(scene,image); need(key not in keys,'duplicate development frame'); keys.append(key)
        need(type(row['pilot']) is bool and type(row['timing']) is bool,'strict frame flags required')
        if (not timing and not pilot) or (timing and row['timing']) or (pilot and row['pilot']): chosen.append(key)
    need(len(chosen)==(64 if timing else 8 if pilot else 400),'fixed selected frame count differs')
    return chosen


def stage_gate(reader,pin,mode):
    stage=loads(reader.check(pin))
    need(mode in STAGES and stage['stage']==mode and stage['completed'] is True
         and type(stage['native_exit_code']) is int and stage['native_exit_code']==0
         and type(stage['actual_matcher_calls']) in (int,float) and stage['actual_matcher_calls']==STAGES[mode]
         and stage['maximum_matcher_calls']==STAGES[mode],'complete fixed stage required')
    need(stage['post_verification_passed'] is True and stage['missing_frames_are_not_negatives'] is True
         and stage['heldout_images_allowed'] is False,'stage completion policy differs')
    summary=stage['summary']; frames=64 if mode=='timing' else 400 if mode=='development' else 8
    need(type(summary['passed']) is int and summary['passed']==1 and summary['stage']==mode and summary['objects']==OBJECTS
         and summary['unique_frames']==frames and summary['object_frame_combinations']==6*frames
         and summary['matcher_calls']==STAGES[mode],'stage summary scope differs')
    for field in ('files','execution_files'):
        need(isinstance(stage[field],list),'stage inventory missing')
        paths=[str(Path(p['path']).resolve()) for p in stage[field]]
        need(len(paths)==len(set(paths)),'duplicate stage inventory pin')
        for item in stage[field]: reader.register(item)
    native=Path(pin['path']).resolve().parent/'native'
    actual={str(p.resolve()) for p in native.rglob('*') if p.is_file() and p.name!='.gitignore'}
    need(actual=={str(Path(p['path']).resolve()) for p in stage['files']},'native inventory differs')
    # Explicit complete acquisition hashes, including archives subsequently read.
    for item in stage['files']+stage['execution_files']: reader.check(item)
    need(reader.json(native/'stage_summary.json')==summary,'embedded/native stage summary differs')
    return stage,native


def parent_stage(reader,stage,mode):
    parent,native=stage_gate(reader,stage['previous_stage'],mode)
    need(all(parent[field]==stage[field] for field in ('quality_inputs','build_manifest','selftest')),
         'parent input/build/selftest binding differs')
    return parent,native


def bindings(reader,stage):
    inputs=loads(reader.check(stage['quality_inputs']))
    input_scope(inputs)
    for field in ('frozen_numeric_files','bank_input_files','raw_reference_files'):
        need(isinstance(inputs[field],list) and inputs[field],'complete numeric allowlist required')
        if field=='frozen_numeric_files':frozen_numeric_pin_map(inputs)
        else:pin_map(inputs[field])
        for pin in inputs[field]: reader.check(pin)
    protocol=loads(reader.check(inputs['protocol']))
    need(inputs['protocol']['sha256']==PROTOCOL_SHA and protocol['quality']['stages']==STAGES
         and protocol['quality']['primary_hypothesis']=='B allGT TP>=215 AND FP<42112 after exact common-padding C0 reproduction',
         'fixed protocol or primary hypothesis differs')
    acceptance=inputs['acceptance']
    need(loads(reader.check(inputs['acceptance_pin']))==acceptance,'pinned acceptance envelope differs')
    need(acceptance['schema'] in ('rgb_stratified_training_geometry_acceptance_v1',
         'rgb_stratified_training_and_geometry_acceptance_v1') and
         acceptance['accepted_independent_audit'] is True and acceptance['numeric_audit_passed'] is True
         and acceptance['scope']=='training_and_exact_geometry' and acceptance['production_promotion'] is False,
         'independent training/geometry acceptance required')
    accepted={name:loads(reader.check(acceptance[name])) for name in
              ('training_freeze','geometry_freeze','independent_audit')}
    training=accepted['training_freeze']; geometry=accepted['geometry_freeze']
    validate_accepted_report(accepted['independent_audit'])
    receipt_bindings(accepted['independent_audit'],acceptance)
    need(training.get('production_promotion') is False,'training freeze promotion refused')
    need(geometry['training_freeze']==acceptance['training_freeze'],'geometry training binding differs')
    plan=padding(geometry.get('plan',geometry.get('geometry')))
    need(padding(inputs['common_padding_plan'])==plan,'quality padding differs from accepted plan')
    need(padding(reader.json(inputs['common_padding_json']))==plan,'native common padding differs')
    validate_bank_bindings(inputs,training)
    inherited=loads(reader.check(inputs['inherited_quality_input_freeze']))
    closure=loads(reader.check(inputs['inherited_input_closure']))
    need(inputs['inherited_quality_input_freeze']['sha256']==INHERITED_QUALITY_SHA and
         inputs['inherited_input_closure']['sha256']==INHERITED_CLOSURE_SHA and
         inherited['development']==inputs['development'] and inherited['dataset_root']==inputs['dataset_root'],
         'inherited schedule/index binding differs')
    common_stage=loads(reader.check(inputs['inherited_c0_development_stage']))
    reference_bindings(inputs,inherited,closure,common_stage)
    frozen=frozen_numeric_pin_map(inputs)
    required=[inputs[k] for k in ('acceptance_pin','protocol','inherited_quality_input_freeze',
              'inherited_input_closure','inherited_c0_development_stage')]+list(acceptance[k] for k in
              ('training_freeze','geometry_freeze','independent_audit'))
    need(all(frozen.get(str(Path(p['path']).resolve()))==p for p in required),
         'required binding missing from frozen numeric allowlist')
    index=Path(inputs['dataset_root'])/'index.json'
    expected=closure['private_files']['frozen_inputs/dataset_index.json']
    reader.register(dict(path=str(index.resolve()),**expected))
    schedule(inputs)
    return inputs,plan


def quality_gate(pooled):
    c0=pooled[ARMS[0]]['allGT']; b=pooled[ARMS[2]]['allGT']
    need((c0['tp'],c0['fp'])==(215,42112),'C0 baseline differs')
    return dict(passed=b['tp']>=215 and b['fp']<42112,comparison_arm=ARMS[2],metric='allGT',
                required_tp_minimum=215,required_fp_strictly_below=42112,
                observed_tp=b['tp'],observed_fp=b['fp'],production_promotion=False)
