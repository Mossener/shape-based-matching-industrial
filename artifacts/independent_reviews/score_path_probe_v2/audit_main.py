"""Read the one approved Phase2 freeze; never execute native or open images."""
import argparse
from collections import Counter,defaultdict
import csv
import gzip
from itertools import groupby
import json
from pathlib import Path
import time
import traceback

import evidence2 as e
import numeric2 as n
import traces as t

HERE=Path(__file__).resolve().parent
HEADERS={
 'jobs':'job_id,object_id,scene,image,arm,template_id,training_image,angle,scale,fine_features,coarse_features,gt_id,physical_x,physical_y',
 'feature_vectors':'kind,owner,feature_id,x,y,label,skipped,cells,response_digits',
 'native_cells':'kind,owner,row,col,native_raw,native_score_bits,computed,threshold_pass',
 'local_maxima':'window,center_x,center_y,base_x,base_y,raw,score_bits,row,col,ties,tie_mask',
 'physical_anchors':'job,gt_id,physical_x,physical_y,on_grid,in_physical_domain,raw,score_bits,feature_id,response',
 'parent_links':'job,gt_id,point_x,point_y,coarse_row,coarse_col,coarse_raw,coarse_score_bits,admitted,window,point_raw,point_score_bits,point_fine_pass,winner_x,winner_y,winner_raw,winner_score_bits,point_is_winner,predicts_emission,point_iou_gt',
 'occurrences':'job,gt_id,match_x,match_y,score_bits,traced_parents,full_pre_multiplicity,post_representative_template,post_rank,nms_selected_rank,nms_blocker,pre_box_x,pre_box_y,pre_box_w,pre_box_h,rep_box_x,rep_box_y,rep_box_w,rep_box_h,pre_iou_gt,rep_iou_gt',
 'fullclass_nms_assignment':'object_id,scene,image,arm,post_rank,template,match_x,match_y,score_bits,selected_rank,blocker_post_rank,blocker_iou,allGT_label,allGT_id',
 'layers':'arm,object_id,class_id,template_id,level,width,height,min_x,min_y,max_x,max_y,actual_features',
 'raw':'scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h',
 'selected':'object_id,scene,image,arm,rank,class_id,score,score_bits,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,eligible_label,eligible_id',
 'truth':'object_id,scene,image,gt_id,class_id,visibility,bbox_x,bbox_y,bbox_w,bbox_h',
}


def table(path,kind):
    path=e.safe(path);opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);n.need(reader.fieldnames==HEADERS[kind].split(','),'CSV schema differs: '+str(path))
        for row in reader:
            n.need(None not in row and None not in row.values(),'CSV width differs: '+str(path));yield row


def frame_key(row):return tuple(n.integer(row[field]) for field in ('object_id','scene','image'))+(row['arm'],)


def parse_record(row,obj,metadata):
    tid=n.integer(row['template_id']);n.need(row['class_id']=='tless_object_'+str(obj) and tid in metadata,'Raw class/template identity differs')
    meta=metadata[tid];x,y=map(n.integer,(row['match_x'],row['match_y']));bits=n.value_bits(row['score'])
    n.need(85<=n.bits_value(bits)<=100 and n.finite(row['score'])==n.bits_value(bits),'Raw score is not exact finite binary32 above threshold')
    box=tuple(n.finite(row['bbox_'+axis]) for axis in ('x','y','w','h'));n.need(box==t.box_at(x,y,meta),'Raw box differs from full template metadata')
    n.need(n.integer(row['training_image'])==n.integer(meta['training_image_id']) and n.value_bits(row['angle'])==n.value_bits(meta['angle']) and n.value_bits(row['scale'])==n.value_bits(meta['scale']),'Raw pose metadata differs')
    return dict(cls=row['class_id'],template=tid,x=x,y=y,bits=bits,box=box)


def load_metadata(prior):
    result={}
    for bank in prior['banks']:
        obj=bank['object_id']
        for arm,field in (('rgb','rgb_training'),('binary_empty_mask','binary_training')):
            document=e.read(Path(bank[field])/'template_metadata.json');records={}
            for row in document['templates']:
                tid=n.integer(row['template_id']);n.need(tid not in records and row['class_id']=='tless_object_'+str(obj),'Metadata class/duplicate differs')
                n.need(len(row['warped_mask_bbox'])==4 and min(map(n.finite,row['warped_mask_bbox'][2:]))>0,'Invalid metadata silhouette box')
                records[tid]=row
            n.need(set(records)==set(range(bank['rgb_template_count'] if arm=='rgb' else 3456)),'Metadata count/ID gaps differ');result[(obj,arm)]=records
    return result


def load_layers(path):
    result={}
    for row in table(path,'layers'):
        obj,tid,level=map(n.integer,(row['object_id'],row['template_id'],row['level']));key=(row['arm'],obj,tid,level)
        n.need(key not in result and row['class_id']=='tless_object_'+str(obj) and level in (0,1),'Loaded layer identity differs')
        result[key]={field:n.integer(row[field]) for field in ('width','height','min_x','min_y','max_x','max_y','actual_features')}
    n.need(len(result)==77870,'Loaded layer coverage differs');return result


def saved_tables(prior,metadata):
    pinned={Path(row['path']).name:Path(row['path']) for row in prior['numeric_pins'] if Path(row['path']).name in ('selected_detections.csv','ground_truth.csv')}
    n.need(set(pinned)=={'selected_detections.csv','ground_truth.csv'},'Saved selected/GT numeric pins missing')
    saved=defaultdict(list);truths=defaultdict(list)
    for row in table(pinned['selected_detections.csv'],'selected'):
        key=frame_key(row);n.need(n.integer(row['rank'])==len(saved[key]),'Saved selected rank order differs')
        record=parse_record(row,key[0],metadata[(key[0],key[3])]);n.need(record['bits']==n.integer(row['score_bits']),'Saved selected binary32 bits differ')
        saved[key].append(dict(record=record,allGT_label=row['allGT_label'],allGT_id=n.integer(row['allGT_id']),eligible_label=row['eligible_label'],eligible_id=n.integer(row['eligible_id'])))
    for row in table(pinned['ground_truth.csv'],'truth'):
        key=tuple(n.integer(row[field]) for field in ('object_id','scene','image'));identity=n.integer(row['gt_id'])
        n.need(identity not in {item['id'] for item in truths[key]},'Duplicate saved GT identity')
        box=tuple(n.finite(row['bbox_'+axis]) for axis in ('x','y','w','h'));n.need(min(box[2:])>0,'Nonpositive saved GT box')
        truths[key].append(dict(id=identity,cls=row['class_id'],visibility=n.finite(row['visibility']),box=box))
    return saved,truths


def raw_loader(native,metadata):
    def load(key,template_ids,interesting):
        obj,scene,image,arm=key;directory=native/f'obj{obj}'/arm;pre={tid:Counter() for tid in template_ids};representatives={};post=[];precount=0
        for variant in ('pre','post'):
            path=directory/f's{scene}_i{image}_{variant}_raw.csv.gz';last=None
            for rank,row in enumerate(table(path,'raw')):
                n.need((n.integer(row['scene']),n.integer(row['image']),row['variant'],n.integer(row['rank']))==(scene,image,variant,rank),'Full raw frame/variant/rank differs')
                record=parse_record(row,obj,metadata[(obj,arm)]);order=n.canonical(record);n.need(last is None or last<=order,'Full raw canonical order differs');last=order
                rk=(record['x'],record['y'],record['bits'])
                if variant=='pre':
                    precount+=1
                    if record['template'] in pre:pre[record['template']][rk]+=1
                    if rk in interesting:representatives[rk]=min(representatives.get(rk,record['template']),record['template'])
                else:post.append(record)
        return pre,representatives,post,precount
    return load


def audit_numeric(plan,prior,native,metadata,layers,saved,truths,loader,progress=False):
    read=lambda kind:table(native/(kind+'.csv.gz'),kind)
    frames={(frame['object_id'],frame['scene'],frame['image']):frame for frame in prior['frames']}
    contexts,windows,owner_order=t.job_contexts(plan,read('jobs'),layers,metadata,frames)
    groups=lambda kind:groupby(read(kind),key=lambda row:(row['kind'],n.integer(row['owner'])))
    coarse,local,signatures,counters=t.check_maps(groups('feature_vectors'),groups('native_cells'),read('local_maxima'),contexts,windows,owner_order)
    if progress:print('AUDIT all feature digits/cells/maxima checked',flush=True)
    physical={}
    def physical_rows():
        for row in read('physical_anchors'):
            key=(n.integer(row['job']),n.integer(row['gt_id']))
            if key not in physical:physical[key]={field:row[field] for field in ('on_grid','in_physical_domain','raw','score_bits')}
            yield row
    counters['physical_feature_probes']=t.check_physical(physical_rows(),contexts,signatures)
    counters.update(t.check_links(read('parent_links'),contexts,coarse,local))
    predictions={jid:t.expected_emissions(ctx,coarse[jid],local) for jid,ctx in contexts.items()}
    occurrences=defaultdict(list)
    for row in read('occurrences'):
        jid=n.integer(row['job']);n.need(jid in contexts,'Unknown occurrence job');occurrences[jid].append(row)
    by_frame=defaultdict(list)
    for jid,ctx in contexts.items():by_frame[ctx['key'][:4]].append(jid)
    nms_groups=iter(groupby(read('fullclass_nms_assignment'),key=frame_key));next_group=next(nms_groups,None);diagnostics=[];frame_counts=Counter();arm_counts=defaultdict(Counter)
    for key,jobs in by_frame.items():
        tids={contexts[jid]['key'][4] for jid in jobs};interesting=set(rk for jid in jobs for rk in predictions[jid])
        pre,representatives,post,precount=loader(key,tids,interesting)
        if post:n.need(next_group is not None and next_group[0]==key,'Missing/misordered fullclass NMS frame');nms_rows=next_group[1]
        else:nms_rows=[]
        selected,blocked=t.check_nms_frame(nms_rows,post,truths[key[:3]],saved.get(key,[]))
        if post:next_group=next(nms_groups,None)
        frame_counts.update(fullclass_frames=1,pre_records=precount,post_records=len(post),selected_records=len(selected))
        for jid in jobs:
            ctx=contexts[jid];pred=predictions[jid];tid=ctx['key'][4]
            frame_counts['occurrence_rows']+=t.check_occurrences(occurrences.get(jid,[]),ctx,pred,pre[tid],representatives,post,selected,blocked)
            frame_counts['predicted_unique_occurrences']+=len(pred);frame_counts['traced_parent_emissions']+=sum(pred.values())
            for gt,target in ctx['targets'].items():
                links=[(point,pk) for point in map(t.pair,target['points']) for pk in ctx['points'][point]]
                fine_values=[];admitted=set();point_winners=set();emitted_parents=set()
                for point,pk in links:
                    p=ctx['parents'][pk];wid=p['window'];bx,by=p['base'];r,c=(point[1]-1-by)//4,(point[0]-1-bx)//4
                    fine_values.append(n.score_value(local[wid]['raw'][r*16+c],ctx['plan']['fine_features']))
                    if n.score_value(coarse[jid][pk[0]*53+pk[1]],ctx['plan']['coarse_features'])>85:admitted.add(pk)
                    best=local[wid]['best'];wx,wy=bx+4*best['col']+1,by+4*best['row']+1
                    if pk in admitted and n.bits_value(best['bits'])>=85:
                        emitted_parents.add(pk)
                        if (wx,wy)==point:point_winners.add(pk)
                phys=physical[(jid,gt)];domain=n.integer(phys['in_physical_domain'])==1
                good_rep=[];kept_good=[];target_tp=[]
                for rank,record in enumerate(post):
                    if (record['x'],record['y'],record['bits']) in pred and n.iou(record['box'],ctx['original'][gt]['bbox'])>=.5:
                        good_rep.append(rank)
                        if rank in selected:kept_good.append(rank)
                for index,rank in enumerate(selected):
                    if (post[rank]['x'],post[rank]['y'],post[rank]['bits']) in pred and saved.get(key,[])[index]['allGT_label']=='TP' and saved[key][index]['allGT_id']==gt:target_tp.append(rank)
                diagnostic=dict(job=jid,object_id=key[0],scene=key[1],image=key[2],arm=key[3],template_id=tid,gt_id=gt,on_grid=n.integer(phys['on_grid']),physical_domain=int(domain),physical_score=n.bits_value(n.integer(phys['score_bits'])) if domain else '',max_neighbor_fine_score=max(fine_values,default=0.),reachable_parents=len({pk for point,pk in links}),coarse_admitted_parents=len(admitted),emitting_parents=len(emitted_parents),neighbor_winning_parents=len(point_winners),traced_unique_occurrences=len(pred),same_template_complete_pre_occurrences=sum(pre[tid].values()),representative_iou_hits=len(good_rep),kept_representative_iou_hits=len(kept_good),selected_target_tp_hits=len(target_tp))
                diagnostics.append(diagnostic);arm=arm_counts[key[3]];arm['targets']+=1
                for label,value in dict(physical_score_ge85=domain and diagnostic['physical_score']>=85,neighbor_fine_score_ge85=diagnostic['max_neighbor_fine_score']>=85,any_coarse_admitted=bool(admitted),any_parent_emission=bool(emitted_parents),any_neighbor_winner=bool(point_winners),any_representative_iou_hit=bool(good_rep),any_kept_representative_iou_hit=bool(kept_good),any_traced_selected_target_tp=bool(target_tp)).items():arm[label]+=int(value)
        if progress:print('AUDIT frame',*key,'checked',frame_counts['fullclass_frames'],flush=True)
    n.need(next_group is None,'Extra fullclass NMS frame')
    counters.update(frame_counts);counters.update(jobs=len(contexts),target_rows=sum(len(ctx['targets']) for ctx in contexts.values()),windows=len(windows),native_grid_points=sum(len(ctx['points']) for ctx in contexts.values()))
    return dict(counters),diagnostics,{arm:dict(value) for arm,value in arm_counts.items()}


def audit(freeze_path):
    began=time.time();closure,plan,prior,stage,freeze_pin,plan_pin=e.prepare(freeze_path)
    native=Path(freeze_path).resolve().parent/'native';metadata=load_metadata(prior);layers=load_layers(plan['loaded_layers_pin']['path']);saved,truths=saved_tables(prior,metadata)
    prior_native=Path(plan['prior_phase1_receipt']['path']).parent/'native'
    counts,diagnostics,arms=audit_numeric(plan,prior,native,metadata,layers,saved,truths,raw_loader(prior_native,metadata),True)
    expected=dict(jobs=430,target_rows=430,windows=7185,coarse_cells=1185080,local_cells=1839360,digits=73337912,physical_feature_probes=13534,parent_links=12016,rgb_positive_controls=215,fullclass_frames=426,pre_records=1312006,post_records=227816,native_grid_points=751)
    n.need(all(counts.get(field)==value for field,value in expected.items()),'Independently reconstructed complete dataset totals differ')
    numeric_bytes=sum(row['bytes'] for row in stage['files'] if Path(row['path']).name!='stage_summary.json')
    n.need(stage['summary']['numeric_output_bytes']==numeric_bytes,'Native measured numeric bytes differ')
    # All observed source/build/output pins are rehashed as inert bytes after
    # the numeric work. Image pins remain declarations and are never opened.
    for value in closure.checked.values():n.need(e.pin(value['path'])==value,'Evidence changed during independent audit')
    source_names=('audit_main.py','evidence2.py','numeric2.py','traces.py','test_numeric2.py','test_traces.py','test_evidence2.py','test_driver.py','DESIGN.md','numeric_red.txt','trace_red.txt','map_stream_red.txt','fullframe_red.txt','evidence_red.txt','bank_declarations_red.txt','all_green_v4.txt')
    result=dict(passed=True,stage='score_path_probe_v2_numeric_audit',phase2_freeze=freeze_pin,input_plan=plan_pin,elapsed_seconds=time.time()-began,independent_standard_library_only=True,probe_evaluator_or_matcher_imports=False,native_calls=0,dataset_image_bytes_opened=0,serialized_template_bytes_opened=0,serialized_bank_pins_declaration_only=len(closure.serialized_bank_declarations),image_decodes=0,matcher_calls=0,heldout_frames_processed=0,reserved_objects_processed=0,accuracy_improvement_claim=False,reconstructed=counts,diagnostics_by_arm=arms,checked_pin_count=len(closure.checked),native_output_members=len(stage['files']),native_numeric_output_bytes=numeric_bytes,source_pins=[e.pin(HERE/name) for name in source_names],limitations=['Response digits and serialized feature coordinates are frozen native numeric observations, not independently derived from image/template bytes.','Twelve historical serialized-bank pins are compared only as declarations from the immutable prior plan and its pinned passed Phase1 audit; this auditor does not rehash or open those bank bytes.','Feature bounds/counts and within-job feature order/labels are checked against loaded-layer aggregates; complete serialized template feature bytes are outside this auditor authority.','Same-pose path support and GT assignment diagnostics are not a measured accuracy improvement or a speed benchmark.','Native executable/compiler/runtime closure is hashed as inert bytes and is never executed.'])
    return result,diagnostics


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();n.need(output.is_relative_to(HERE) and not output.exists(),'Fresh contained independent audit output required');output.mkdir();(output/'.gitignore').write_text('*\n')
    try:
        result,diagnostics=audit(args.freeze)
        with (output/'diagnostics.csv').open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(diagnostics[0]));writer.writeheader();writer.writerows(diagnostics)
        result['diagnostics']=e.pin(output/'diagnostics.csv');(output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(passed=True,result=e.pin(output/'result.json'))),flush=True)
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),traceback=traceback.format_exc(),native_calls=0,image_bytes_opened=0,serialized_template_bytes_opened=0,matcher_calls=0),indent=2)+'\n',encoding='utf-8');raise


if __name__=='__main__':main()
