"""One retained read-only Phase1 numeric audit; no matcher/evaluator imports."""
import argparse
from collections import Counter,defaultdict
import csv
import io
import json
from pathlib import Path
import struct
import time
import traceback

import evidence as e
import numeric as n

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PROBE=ROOT/'artifacts/quality_failure_analysis/score_path_probe_v1'
EXPERIMENT=ROOT/'artifacts/silhouette_empty_mask_experiment'
PHASE_SHA='f2be7500b13fbe1cad2bb9bc8d223b7bbf37af71919441f5b2bc2d1251e0d5ed'
BUILD_SHA='515bc0638569cadf2f7c229d883da477a097deb9902207224f0409f89e7f70a0'
GREEN_SHA='2ebb1140c436517b87aae26c554c681ddb2b0a2665d46331e76bd47530ae446d'
PER='object_id,scene,image,arm,pre,post,pre_unique_templates_in_collision_groups,cross_template_groups,same_template_duplicate_occurrences,zero_score_matches,fine_oracle_rows,exact_saved_raw'.split(',')
SUPPORT='object_id,scene,image,arm,gt_id,pre_hits,post_hits,pre_best_iou,post_best_iou,candidate_support_lost_at_consolidation'.split(',')
REP='object_id,scene,image,arm,score_bits,match_x,match_y,representative_template,discarded_template,discarded_occurrences,representative_x,representative_y,representative_w,representative_h,discarded_x,discarded_y,discarded_w,discarded_h'.split(',')
GT='object_id,scene,image,gt_id,class_id,visibility,bbox_x,bbox_y,bbox_w,bbox_h'.split(',')
SELECTED='object_id,scene,image,arm,rank,class_id,score,score_bits,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,eligible_label,eligible_id'.split(',')

def rows(path,header): return n.table(e.safe(path).read_bytes(),header)

def verify_table(actual,expected,header,label):
    n.need(len(actual)==len(expected),label+' row count differs')
    for index,(row,want) in enumerate(zip(actual,expected)):
        n.need(set(row)==set(want)==set(header),label+' expected schema differs')
        for field in header:
            value=want[field]
            if isinstance(value,str): equal=row[field]==value
            elif isinstance(value,int): equal=n.integer(row[field])==value
            else: equal=n.finite(row[field])==value
            n.need(equal,f'{label} row {index} field {field} differs')

def manifest_path(archive):
    return Path(str(archive).replace('_raw.csv.gz','_raw_manifest.json'))

def candidate_archive(path,frame,variant,obj,meta):
    return n.parse_raw(e.safe(path).read_bytes(),e.read(manifest_path(path)),frame,variant,obj,meta,path)

def reconstruct_targets(plan,closure):
    native=EXPERIMENT/'run_quality_development_v1/native'
    truth={}
    for row in rows(native/'ground_truth.csv',GT):
        key=tuple(n.integer(row[k]) for k in ('object_id','scene','image','gt_id'))
        n.need(key not in truth,'Duplicate preserved GT identity'); truth[key]=row
    selected=rows(native/'selected_detections.csv',SELECTED); targets=defaultdict(list); binary=set(); rgb=set()
    for row in selected:
        if row['allGT_label']!='TP': continue
        identity=tuple(n.integer(row[k]) for k in ('object_id','scene','image','allGT_id'))
        if row['arm']=='binary_empty_mask': binary.add(identity)
        if row['arm']!='rgb': continue
        n.need(identity not in rgb,'Duplicate RGB TP identity'); rgb.add(identity); gt=truth[identity]
        target=dict(gt_id=identity[3],bbox=[n.finite(gt['bbox_'+axis]) for axis in ('x','y','w','h')],rgb_tp_box=[n.finite(row['bbox_'+axis]) for axis in ('x','y','w','h')],rgb_tp_template=n.integer(row['template_id']),rgb_tp_pose=[n.integer(row['training_image']),n.finite(row['angle']),n.finite(row['scale'])],rgb_tp_match=[n.integer(row['match_x']),n.integer(row['match_y'])],rgb_tp_score_bits=n.integer(row['score_bits']))
        n.need(struct.unpack('<I',n.fbits(row['score']))[0]==target['rgb_tp_score_bits'],'Selected RGB score bits differ')
        targets[identity[:3]].append(target)
    expected={(f['object_id'],f['scene'],f['image']):f['targets'] for f in plan['frames']}
    n.need({key:sorted(value,key=lambda x:x['gt_id']) for key,value in targets.items()}==expected,'Plan does not exactly reconstruct preserved RGB TP/GT targets')
    n.need(len(rgb)==215 and len(rgb-binary)==67 and len(rgb&binary)==148,'Lost/control identity composition differs')
    # Bind every numeric plan member to the already completed V22 audit's
    # input closure, independently of the preparer's selection logic.
    audit=e.read(plan['audit']['path']); n.need(audit.get('passed') is True and audit.get('stage')=='development','Prior independent development audit incomplete')
    old={str(Path(v['path']).resolve()):v for v in audit['input_pins']}
    n.need(all(old.get(str(Path(v['path']).resolve()))==v for v in plan['numeric_pins']),'Prepared numeric pin absent from prior audit')
    inputs=e.read(EXPERIMENT/'QUALITY_INPUT_FREEZE.json'); schedule={(r['scene_id'],r['image_id']):r for r in inputs['development']}
    n.need(len(schedule)==400 and {k[0] for k in schedule}==e.SCENES and tuple(inputs['objects'])==e.OBJECTS,'Frozen development schedule differs')
    declared={Path(v['path']).resolve():v for v in plan['permitted_image_pins']}
    for frame in plan['frames']:
        record=schedule[(frame['scene'],frame['image'])]; path=(Path(inputs['dataset_root'])/record['rgb']).resolve()
        n.need(declared.get(path)==dict(path=str(path),sha256=record['rgb_sha256'],bytes=record['rgb_bytes']) and frame['rgb_relative']==record['rgb'],'Image declarations differ from frozen development schedule')
    n.need(plan['common_padding_json']==inputs['common_padding_json'] and plan['banks']==[{k:b[k] for k in ('object_id','rgb_training','binary_training','rgb_template_count')} for b in inputs['rgb_banks']],'Bank/padding declarations differ from frozen inputs')
    return dict(rgb_tp_identities=215,binary_losses=67,retained_controls=148)

def audit(freeze_path):
    start=time.time(); freeze_pin=e.pin(freeze_path)
    n.need(freeze_pin['sha256']==PHASE_SHA and Path(freeze_path).resolve()==PROBE/'probe_phase1_v2/PROBE_STAGE_FREEZE.json','Unapproved Phase1 completion freeze')
    closure=e.Closure(PROBE,EXPERIMENT); plan,plan_pin=e.check_plan(PROBE/'PROBE_INPUTS_V1.json',closure)
    composition=reconstruct_targets(plan,closure)
    freeze=closure.stage(freeze_pin,'phase1',False,plan_pin,plan['permitted_image_pins'])
    n.need(freeze['build_manifest']['sha256']==BUILD_SHA and freeze['selftest']['sha256']==GREEN_SHA,'Pinned root GREEN build/selftest differs')
    native=Path(freeze_path).resolve().parent/'native'
    expected_paths={native/'.gitignore',native/'stage_summary.json',native/'per_frame.csv',native/'gt_support.csv',native/'representatives.csv'}
    expected_per=[]; expected_support=[]; expected_representatives=[]; counters=Counter(); arms=defaultdict(Counter); objects=defaultdict(Counter); frame_audit=[]
    pins={Path(v['path']).resolve():v for v in plan['numeric_pins']}
    for bank in plan['banks']:
        obj=bank['object_id']; metadata={}
        for arm,field,expected_count in [('rgb','rgb_training',bank['rgb_template_count']),('binary_empty_mask','binary_training',3456)]:
            path=Path(bank[field])/'template_metadata.json'; n.need(path.resolve() in pins,'Unpinned metadata')
            metadata[arm]=n.load_metadata(e.read(path),obj,expected_count)
        for frame in plan['frames']:
            if frame['object_id']!=obj: continue
            scene,image=frame['scene'],frame['image']; key=dict(object_id=obj,scene=scene,image=image)
            for arm,reference_field in [('rgb','rgb_raw'),('binary_empty_mask','binary_raw')]:
                directory=native/f'obj{obj}'/arm; streams={}
                for variant in ('pre','post'):
                    path=directory/f's{scene}_i{image}_{variant}_raw.csv.gz'; expected_paths|={path,manifest_path(path)}
                    streams[variant]=candidate_archive(path,(scene,image),variant,obj,metadata[arm])
                pre,post=streams['pre'],streams['post']; n.need(len(pre)<=1000000,'Per-replay candidate budget exceeded')
                reference=Path(frame[reference_field]); n.need(reference.resolve() in pins and manifest_path(reference).resolve() in pins,'Unpinned reference archive/manifest')
                saved=candidate_archive(reference,(scene,image),'fallback',obj,metadata[arm]); n.need(post==saved,'Full ordered post versus preserved V22 reference fields/bits differ')
                d=n.diagnostics(pre,post,frame['targets']); n.need(d['per']['zero_score_matches']==0,'Positive threshold emitted zero score')
                expected_per.append(dict(**key,arm=arm,**d['per']))
                expected_support.extend(dict(**key,arm=arm,**value) for value in d['support'])
                expected_representatives.extend(dict(**key,arm=arm,**value) for value in d['representatives'])
                totals=dict(pre=len(pre),post=len(post),cross_template_groups=d['per']['cross_template_groups'],same_template_duplicate_occurrences=d['per']['same_template_duplicate_occurrences'],discarded_template_mapping_rows=len(d['representatives']),candidate_support_losses=sum(v['candidate_support_lost_at_consolidation'] for v in d['support']))
                counters.update(totals); arms[arm].update(totals); objects[obj].update(totals)
                frame_audit.append(dict(**key,arm=arm,**totals))
            print(f'NUMERIC object={obj} scene={scene} image={image} audited_replays={len(expected_per)}',flush=True)
    n.need({Path(v['path']).resolve() for v in freeze['files']}==expected_paths,'Phase1 complete native schema differs')
    verify_table(rows(native/'per_frame.csv',PER),expected_per,PER,'per_frame')
    verify_table(rows(native/'gt_support.csv',SUPPORT),expected_support,SUPPORT,'gt_support')
    verify_table(rows(native/'representatives.csv',REP),expected_representatives,REP,'representatives')
    numeric_bytes=sum(v['bytes'] for v in freeze['files'] if Path(v['path']).name not in ('.gitignore','stage_summary.json'))
    summary=freeze['summary']; wanted=dict(pre_matches=counters['pre'],post_matches=counters['post'],independent_scalar_fine_score_rows=counters['pre'],cross_template_collision_groups=counters['cross_template_groups'],candidate_support_losses_at_consolidation=counters['candidate_support_losses'],numeric_output_bytes=numeric_bytes)
    n.need(all(summary.get(k)==v for k,v in wanted.items()),'Native summary reconstructed totals differ')
    n.need(arms['rgb']['post']==71178 and arms['binary_empty_mask']['post']==156638 and len(expected_per)==426 and len(expected_support)==430,'Reference/GT/replay coverage differs')
    # Recheck the full pinned numeric evidence set at the end. No image file
    # bytes are opened at any stage, including before/after declarations.
    for value in plan['numeric_pins']+[plan['audit'],plan_pin,freeze_pin]+freeze['files']+freeze['execution_files']: e.verify_pin(value)
    return dict(passed=True,stage='score_path_probe_v1_phase1',phase1_freeze=freeze_pin,input_plan=plan_pin,elapsed_seconds=time.time()-start,independent_standard_library_only=True,probe_or_evaluator_imports=False,dataset_image_bytes_opened=0,image_decodes=0,matcher_calls=0,heldout_frames_processed=0,reserved_objects_processed=0,phase2_started=False,accuracy_improvement_claim=False,scope=dict(object_frame_pairs=213,unique_scene_image_pairs=175,full_class_search_replays=426,gt_arm_rows=430,**composition),reconstruction=dict(counters),by_arm={key:dict(value) for key,value in arms.items()},by_object={str(key):dict(value) for key,value in objects.items()},raw_reference_full_fields_and_binary32_bits_exact=True,pre_post_full_representative_records_exact=True,complete_native_members=1709,native_numeric_output_bytes=numeric_bytes,native_physical_output_bytes=sum(v['bytes'] for v in freeze['files']),runner_measured_numeric_output_bytes=sum(v['bytes'] for v in freeze['files']+freeze['execution_files']),runner_measured_output_excludes_freeze_itself=True,checked_numeric_and_receipt_pin_count=len(closure.checked),inherited_build_closure_declared_pin_count=len(closure.build_declared),limitations=['Native LM/scalar feature scores are not independently recomputed by this numeric auditor; it verifies the pinned native exact-score gate receipt and one covered row per pre candidate.','Pinned build executable/compiler/runtime/dependency/source members are independently SHA256-checked as inert bytes; no build member is executed or imported.','Image before/after hashes are compared as pinned declarations; image bytes are never opened by this auditor.','Candidate support is a pre/post consolidation diagnostic, not a recovered TP, precision/recall measurement or speed improvement.'],frame_audit=frame_audit,source_pins=[e.pin(HERE/name) for name in ('audit_main.py','evidence.py','numeric.py','test_evidence.py','test_numeric.py','synthetic_red.txt','evidence_red.txt','synthetic_green.txt')])

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--freeze',type=Path,required=True); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    output=args.output.resolve(); n.need(output.is_relative_to(HERE) and not output.exists(),'Fresh contained audit output required'); output.mkdir()
    (output/'.gitignore').write_text('*\n')
    try:
        result=audit(args.freeze); (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8'); print(json.dumps(dict(passed=True,result=e.pin(output/'result.json'))))
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),dataset_image_bytes_opened=0,matcher_calls=0),indent=2)+'\n',encoding='utf-8'); raise

if __name__=='__main__': main()
