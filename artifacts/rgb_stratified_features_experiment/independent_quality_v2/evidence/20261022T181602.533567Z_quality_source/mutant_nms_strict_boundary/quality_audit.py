"""Independent three-arm raw/NMS/GT replay. Standard library only.

No target evaluator, matcher or image library is imported.  Real evidence is
opened only through an externally trusted stage pin and its pinned manifests.
"""
from collections import Counter,defaultdict
import argparse
import gzip
import io
import json
from pathlib import Path
import sys

from evidence import Reader,need,loads,sha,integer,number,native_count,table,rows_by
from numeric import candidate_order,evaluate,finish,float_bits,nms,score
from contract import OBJECTS,ARMS,PATHS,COMPARISONS,BANK_KEYS,stage_gate,parent_stage,bindings,quality_gate,schedule

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
RAW_HEADER=('scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,'
            'match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h').split(',')
SELECTED_HEADER=('object_id,scene,image,arm,rank,class_id,score,score_bits,template_id,training_image,'
                 'angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,'
                 'eligible_label,eligible_id').split(',')
PER_HEADER=('object_id,scene,image,arm,raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,'
            'eligible_gt,ignored,all_iou_sum,eligible_iou_sum,negative_fp').split(',')
EQ_HEADER=('object_id,scene,image,arm,fallback_count,fused_count,exact_order_fields_score_bits,'
           'reference_exact,fallback_match_ms,fused_match_ms,fallback_external_ms,fused_external_ms').split(',')
GT_HEADER=('object_id,scene,image,gt_id,class_id,visibility,bbox_x,bbox_y,bbox_w,bbox_h').split(',')
RETENTION_HEADER=('object_id,scene,image,metric,gt_id,comparison_arm,rgb_control_detected,'
                  'comparison_detected,same_pose_if_both,identity_change').split(',')


def metadata(reader,directory,obj,count):
    records=reader.json(Path(directory)/'template_metadata.json')['templates']
    need(isinstance(records,list) and len(records)==count,'metadata count differs')
    result={}
    for index,m in enumerate(records):
        need(type(m['template_id']) is int and m['template_id']==index and m['class_id']==f'tless_object_{obj}',
             'metadata class/id/order differs')
        need(type(m['training_image_id']) is int and m['training_image_id']>=0,'metadata image differs')
        need(type(m['tl_x']) is int and type(m['tl_y']) is int,'metadata origins must be integer')
        need(isinstance(m['warped_mask_bbox'],list) and len(m['warped_mask_bbox'])==4,'metadata bbox differs')
        box=[number(v) for v in m['warped_mask_bbox']]
        need(box[2]>0 and box[3]>0,'metadata box extents differ')
        number(m['angle']); number(m['scale'],True)
        result[index]=m
    return result


def parse_candidate(row,obj,meta):
    template=integer(row['template_id'],0)
    need(row['class_id']==f'tless_object_{obj}' and template in meta,'raw class/template differs')
    m=meta[template]; bits=float_bits(number(row['score']))
    need(85<=score(bits)<=100,'raw score outside fixed threshold')
    x,y=integer(row['match_x']),integer(row['match_y'])
    box=tuple(number(row['bbox_'+a]) for a in ('x','y','w','h'))
    sx,sy,w,h=(number(v) for v in m['warped_mask_bbox'])
    need(box==(x-64+sx-m['tl_x'],y-64+sy-m['tl_y'],w,h),'official box/source-origin conversion differs')
    pose=(integer(row['training_image'],0),float_bits(number(row['angle'])),float_bits(number(row['scale'])))
    need(pose==(m['training_image_id'],float_bits(number(m['angle'])),float_bits(number(m['scale']))),
         'raw pose metadata differs')
    return row['class_id'],template,x,y,bits,box,pose


def bounded_gzip(encoded,expected):
    need(type(expected) is int and 0<=expected<=1024**3,'raw decoded byte bound differs')
    with gzip.GzipFile(fileobj=io.BytesIO(encoded),mode='rb') as archive:
        decoded=archive.read(expected+1)
    need(len(decoded)==expected,'raw decoded bytes differ')
    return decoded


def parse_raw(reader,path,frame,variant,obj,meta):
    encoded=reader.read(path)
    manifest=reader.json(Path(str(path).replace('.csv.gz','_manifest.json')))
    # A raw archive is independently bounded before decoding. The saved stage
    # contract also caps raw candidates at one million, including empty frames.
    need(len(encoded)<=1024**3,'raw archive byte bound differs')
    decoded=bounded_gzip(encoded,native_count(manifest['uncompressed_bytes'],1024**3))
    rows=table(decoded,RAW_HEADER); need(len(rows)<=1000000,'raw row bound exceeded')
    need((native_count(manifest['scene_id']),native_count(manifest['image_id']),manifest['variant'],
          native_count(manifest['raw_candidate_count'],1000000),native_count(manifest['compressed_bytes'],1024**3))==
         (*frame,variant,len(rows),len(encoded)),'raw manifest differs')
    result=[]
    for rank,row in enumerate(rows):
        need((integer(row['scene']),integer(row['image']),row['variant'],integer(row['rank']))==
             (*frame,variant,rank),'raw frame/path/rank differs')
        result.append(parse_candidate(row,obj,meta))
    need(result==sorted(result,key=candidate_order),'raw canonical order differs')
    return result


def check_path_equality(left,right): need(left==right,'full ordered raw fields/score bits differ')


def check_coverage(per,selected,equality,expected):
    need(set(per)==set(equality)==expected and set(selected).issubset(expected),'frame/arm coverage differs')
    for key in expected: selected.setdefault(key,[])


def check_selected(rows,kept,key,all_labels,eligible_labels):
    need(len(rows)==len(kept)==len(all_labels)==len(eligible_labels),'selected row count differs')
    for rank,(row,d) in enumerate(zip(rows,kept)):
        need((integer(row['object_id']),integer(row['scene']),integer(row['image']),row['arm'])==key and
             integer(row['rank'])==rank and row['class_id']==d[0] and integer(row['template_id'])==d[1]
             and integer(row['match_x'])==d[2] and integer(row['match_y'])==d[3]
             and integer(row['score_bits'])==d[4] and number(row['score'])==score(d[4])
             and tuple(number(row['bbox_'+a]) for a in ('x','y','w','h'))==d[5]
             and (integer(row['training_image']),float_bits(number(row['angle'])),float_bits(number(row['scale'])))==d[6]
             and (row['allGT_label'],integer(row['allGT_id']))==all_labels[rank]
             and (row['eligible_label'],integer(row['eligible_id']))==eligible_labels[rank],
             'selected candidate/labels differ')


def frame_result(raw,truth):
    kept=nms(raw)
    all_counts,all_labels=evaluate(kept,truth,False)
    eligible,eligible_labels=evaluate(kept,truth,True)
    return dict(raw=raw,kept=kept,allGT=all_counts,eligible=eligible,all_labels=all_labels,
                eligible_labels=eligible_labels,raw_candidates=len(raw),negative_frames=int(not truth),
                negative_frames_with_fp=int(not truth and all_counts['fp']>0),
                negative_fp=all_counts['fp'] if not truth else 0)


def frame_counts(r):
    a,e=r['allGT'],r['eligible']
    return dict(raw=len(r['raw']),selected=len(r['kept']),tp=a['tp'],fp=a['fp'],fn=a['fn'],gt=a['gt'],
                eligible_tp=e['tp'],eligible_fp=e['fp'],eligible_fn=e['fn'],eligible_gt=e['gt'],
                ignored=e['ignored'],all_iou_sum=a['matched_iou_sum'],eligible_iou_sum=e['matched_iou_sum'],
                negative_fp=r['negative_fp'])


def retention_for_frame(obj,frame,truth,results):
    need(set(results)==set(ARMS),'retention requires all three arms')
    expected={}
    for metric,labels in (('allGT','all_labels'),('eligible','eligible_labels')):
        for gt in truth:
            if metric=='eligible' and gt['visib_fract']<.5: continue
            detected={}
            for arm in ARMS:
                matches=[results[arm]['kept'][i] for i,label in enumerate(results[arm][labels])
                         if label==('TP',gt['gt_id'])]
                need(len(matches)<=1,'GT matched more than once')
                detected[arm]=matches[0] if matches else None
            c0=detected[ARMS[0]]
            for arm in COMPARISONS:
                other=detected[arm]; a,b=int(c0 is not None),int(other is not None)
                state='retained' if a and b else 'lost' if a else 'gained' if b else 'neither'
                same=int(c0[6]==other[6]) if a and b else -1
                expected[(obj,*frame,metric,gt['gt_id'],arm)]=(a,b,same,state)
    return expected


def check_retention(rows,expected):
    actual=rows_by(rows,lambda r:(integer(r['object_id']),integer(r['scene']),integer(r['image']),
                                r['metric'],integer(r['gt_id']),r['comparison_arm']))
    values={k:(integer(r['rgb_control_detected']),integer(r['comparison_detected']),
               integer(r['same_pose_if_both']),r['identity_change']) for k,r in actual.items()}
    need(values==expected,'P/C0 or B/C0 GT retention/pose differs')
    groups=defaultdict(Counter)
    for key,(a,b,_,state) in expected.items():
        obj,scene,_,metric,_,arm=key
        for scope in ((arm,metric,None,None),(arm,metric,obj,None),(arm,metric,None,scene),(arm,metric,obj,scene)):
            groups[scope].update(dict(identities=1,control_tp=a,comparison_tp=b,**{state:1}))
    result=[]
    for (arm,metric,obj,scene),counts in sorted(groups.items(),key=lambda x:str(x[0])):
        values={k:counts[k] for k in ('identities','control_tp','comparison_tp','retained','lost','gained','neither')}
        need(values['identities']==sum(values[k] for k in ('retained','lost','gained','neither')),
             'retention identity accounting differs')
        result.append(dict(comparison_arm=arm,metric=metric,object_id=obj,scene=scene,**values,
                           net_tp=counts['gained']-counts['lost']))
    return result


def add_totals(total,r):
    for metric in ('allGT','eligible'):
        c=total.setdefault(metric,Counter())
        c.update({k:r[metric][k] for k in ('tp','fp','fn','gt','ignored')})
        c['matched_iou_sum']+=r[metric]['matched_iou_sum']
    for key in ('raw_candidates','negative_frames','negative_frames_with_fp','negative_fp'):
        total[key]=total.get(key,0)+r[key]


def finished(total):
    return dict({m:finish(total[m]) for m in ('allGT','eligible')},
                **{k:total[k] for k in ('raw_candidates','negative_frames','negative_frames_with_fp','negative_fp')})


def same_numeric(a,b):
    if isinstance(a,dict) and isinstance(b,dict): return set(a)==set(b) and all(same_numeric(a[k],b[k]) for k in a)
    if type(a) in (int,float) and type(b) in (int,float):
        return abs(number(a)-number(b))<=1e-11*max(1.,abs(a),abs(b))
    return type(a) is type(b) and a==b


def check_summary(observed,expected):
    native=dict(expected); native['visibility_ge_0_5']=native.pop('eligible')
    need(same_numeric(observed,native),'numeric metrics summary differs')


def gt_schedule(reader,inputs):
    index=reader.json(Path(inputs['dataset_root'])/'index.json')
    source=rows_by([r for r in index['test'] if r['split']=='development'],lambda r:(r['scene_id'],r['image_id']))
    frames={}
    for row in inputs['development']:
        key=(row['scene_id'],row['image_id']); need(key in source,'frozen frame absent from index')
        item=source[key]
        need(item['rgb']==row['rgb'] and (item['width'],item['height'])==(720,540),'frame source geometry/path differs')
        truth=[]; identities=set()
        need(isinstance(item['instances'],list),'GT instances must be a list')
        for g in item['instances']:
            gid,obj=integer(g['gt_id'],0),integer(g['obj_id'],1)
            need(gid not in identities,'duplicate GT identity'); identities.add(gid)
            need(obj<=30 and g['class_id']==f'tless_object_{obj}','GT object/class binding differs')
            need(isinstance(g['bbox_obj'],list) and len(g['bbox_obj'])==4,'GT box width differs')
            box=tuple(number(v) for v in g['bbox_obj']); visibility=number(g['visib_fract'])
            need(box[2]>0 and box[3]>0 and 0<=visibility<=1,'GT extents/visibility differs')
            truth.append(dict(gt_id=gid,class_id=g['class_id'],obj_id=obj,bbox_obj=box,visib_fract=visibility))
        frames[key]=truth
    return frames


def raw_path(root,obj,arm,frame,path):
    return Path(root)/f'obj{obj}'/arm/f's{frame[0]}_i{frame[1]}_{path}_raw.csv.gz'


def audit(stage_pin,output,root=ROOT):
    reader=Reader(root); stage,native=stage_gate(reader,stage_pin,'development')
    inputs,plan=bindings(reader,stage); frames=gt_schedule(reader,inputs)
    previous,pilot_native=parent_stage(reader,stage,'pilot')
    # The pilot's parent old gate is independently pinned and complete.
    old_gate,old_native=parent_stage(reader,previous,'old_gate')
    per=rows_by(table(reader.read(native/'per_frame_metrics.csv'),PER_HEADER),
                lambda r:(integer(r['object_id']),integer(r['scene']),integer(r['image']),r['arm']))
    equality=rows_by(table(reader.read(native/'candidate_equality.csv'),EQ_HEADER),
                     lambda r:(integer(r['object_id']),integer(r['scene']),integer(r['image']),r['arm']))
    selected=defaultdict(list)
    for row in table(reader.read(native/'selected_detections.csv'),SELECTED_HEADER):
        selected[(integer(row['object_id']),integer(row['scene']),integer(row['image']),row['arm'])].append(row)
    expected={(obj,*frame,arm) for obj in OBJECTS for frame in frames for arm in ARMS}
    check_coverage(per,selected,equality,expected)
    gt_rows=rows_by(table(reader.read(native/'ground_truth.csv'),GT_HEADER),
                    lambda r:tuple(integer(r[k]) for k in ('object_id','scene','image','gt_id')))
    bank_rows={r['object_id']:r for r in inputs['banks']}; banks={}; templates={}
    for obj in OBJECTS:
        row=bank_rows[obj]; banks[obj]={arm:metadata(reader,row[d],obj,row[c]) for arm,d,c in BANK_KEYS}
        templates[obj]={a:len(m) for a,m in banks[obj].items()}
        # Original-padding C0 is a separate gate from common-padding quality.
        # Check saved rows ourselves; a native reference_exact flag is not proof.
        for frame in schedule(inputs,pilot=True):
            paths={path:parse_raw(reader,raw_path(old_native,obj,ARMS[0],frame,path),frame,path,obj,banks[obj][ARMS[0]])
                   for path in PATHS}
            check_path_equality(paths['fallback'],paths['fused'])
            for path in PATHS:
                reference=Path(row['original_pilot_raw'])/f's{frame[0]}_i{frame[1]}_{path}_raw.csv.gz'
                check_path_equality(paths[path],parse_raw(reader,reference,frame,path,obj,banks[obj][ARMS[0]]))
    totals={obj:{a:{} for a in ARMS} for obj in OBJECTS}
    scene_totals=defaultdict(lambda:{a:{} for a in ARMS})
    object_scene=defaultdict(lambda:{a:{} for a in ARMS})
    pooled_totals={a:{} for a in ARMS}; retention={}; per_frame=[]
    pilot_frames=set(schedule(inputs,pilot=True))
    expected_gt=set()
    for obj in OBJECTS:
        for frame in schedule(inputs):
            truth=[g for g in frames[frame] if g['obj_id']==obj]
            for gt in truth:
                key=(obj,*frame,gt['gt_id']); expected_gt.add(key); need(key in gt_rows,'GT projection missing')
                row=gt_rows[key]
                need(row['class_id']==gt['class_id'] and number(row['visibility'])==gt['visib_fract'] and
                     tuple(number(row['bbox_'+a]) for a in ('x','y','w','h'))==gt['bbox_obj'],'GT projection differs')
            results={}
            for arm in ARMS:
                paths={path:parse_raw(reader,raw_path(native,obj,arm,frame,path),frame,path,obj,banks[obj][arm]) for path in PATHS}
                check_path_equality(paths['fallback'],paths['fused'])
                if arm==ARMS[0]:
                    for path in PATHS:
                        reference=Path(bank_rows[obj]['c0_common_raw'])/f's{frame[0]}_i{frame[1]}_{path}_raw.csv.gz'
                        check_path_equality(paths[path],parse_raw(reader,reference,frame,path,obj,banks[obj][arm]))
                if frame in pilot_frames:
                    for path in PATHS:
                        check_path_equality(paths[path],parse_raw(reader,raw_path(pilot_native,obj,arm,frame,path),frame,path,obj,banks[obj][arm]))
                r=frame_result(paths['fallback'],truth); results[arm]=r; key=(obj,*frame,arm)
                counts=frame_counts(r)
                for field,value in counts.items(): need(number(per[key][field])==value,'per-frame metric differs: '+field)
                check_selected(selected[key],r['kept'],key,r['all_labels'],r['eligible_labels'])
                eq=equality[key]
                need(integer(eq['fallback_count'])==integer(eq['fused_count'])==len(r['raw']) and
                     eq['exact_order_fields_score_bits']==eq['reference_exact']=='1','equality flag/count differs')
                per_frame.append(dict(object_id=obj,scene=frame[0],image=frame[1],arm=arm,**counts))
                for group in (totals[obj][arm],scene_totals[frame[0]][arm],object_scene[(obj,frame[0])][arm],pooled_totals[arm]): add_totals(group,r)
            retention.update(retention_for_frame(obj,frame,truth,results))
    need(set(gt_rows)==expected_gt,'extra GT projection rows')
    retention_groups=check_retention(table(reader.read(native/'gt_retention.csv'),RETENTION_HEADER),retention)
    pooled={a:finished(pooled_totals[a]) for a in ARMS}
    per_object={o:{a:finished(totals[o][a]) for a in ARMS} for o in OBJECTS}
    per_scene={s:{a:finished(v[a]) for a in ARMS} for s,v in scene_totals.items()}
    for arm in ARMS: check_summary(stage['summary'][arm],pooled[arm])
    summary_scenes=rows_by(stage['summary']['per_scene'],lambda r:r['scene_id'])
    need(set(summary_scenes)==set(per_scene),'pooled scene coverage differs')
    for scene in per_scene:
        for arm in ARMS: check_summary(summary_scenes[scene][arm],per_scene[scene][arm])
    for obj in OBJECTS:
        document=reader.json(native/f'obj{obj}/metrics.json'); need(document['object_id']==obj,'object metrics identity differs')
        for arm in ARMS: check_summary(document[arm],per_object[obj][arm])
        scenes=rows_by(document['per_scene'],lambda r:r['scene_id'])
        expected_scenes={s for o,s in object_scene if o==obj}; need(set(scenes)==expected_scenes,'object scene coverage differs')
        for scene in expected_scenes:
            for arm in ARMS: check_summary(scenes[scene][arm],finished(object_scene[(obj,scene)][arm]))
    gate=quality_gate(pooled)
    macro={a:{m:{f:sum(per_object[o][a][m][f] for o in OBJECTS)/6
          for f in ('precision','recall','f1','mean_tp_iou')} for m in ('allGT','eligible')} for a in ARMS}
    reader.recheck(); output=Path(output).resolve(); need(not output.exists(),'fresh quality audit output required')
    output.mkdir(parents=True)
    (output/'per_frame_audit.json').write_text(json.dumps(per_frame,indent=2)+'\n',encoding='utf-8')
    (output/'retention.json').write_text(json.dumps(retention_groups,indent=2)+'\n',encoding='utf-8')
    result=dict(schema='independent_three_arm_quality_audit_v1',passed=True,numeric_audit_passed=True,
                scope='quality_all_three_arms',
                primary_accuracy_hypothesis_passed=gate['passed'],production_promotion=False,
                stage='development',unique_frames=400,object_frame_pairs=2400,arms=list(ARMS),
                development_stage=stage_pin,common_geometry=plan,template_counts=templates,
                pooled=pooled,micro=pooled,per_object=per_object,per_scene=per_scene,object_macro=macro,
                retention=retention_groups,quality_gate=gate,raw_and_selected_numeric_equality=True,
                common_padding_C0_full_raw_exact=True,pilot_overlap_full_raw_exact=True,
                original_padding_C0_full_raw_exact=True,
                matcher_calls=0,image_reads=0,image_decodes=0,input_pins=list(reader.seen.values()),
                limitations=['Saved numeric replay only; no RGB gradient/NMS candidate regeneration',
                             'Native calls/resources/runtime/source closure remain separate root evidence',
                             'No heldout confirmation or industrial generalization claim'])
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage-freeze',required=True,type=Path); p.add_argument('--stage-sha256',required=True)
    p.add_argument('--stage-bytes',required=True,type=int); p.add_argument('--output',required=True,type=Path)
    args=p.parse_args(); pin=dict(path=str(args.stage_freeze.resolve()),bytes=args.stage_bytes,sha256=args.stage_sha256)
    need(not args.output.exists(),'fresh audit output required')
    try: result=audit(pin,args.output)
    except Exception as error:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'failure.json').write_text(json.dumps(dict(passed=False,error=repr(error),matcher_calls=0,image_reads=0),indent=2)+'\n')
        raise
    print(json.dumps(dict(passed=result['passed'],numeric_audit_passed=True,primary_accuracy_hypothesis_passed=result['quality_gate']['passed'])))


if __name__=='__main__': main()
