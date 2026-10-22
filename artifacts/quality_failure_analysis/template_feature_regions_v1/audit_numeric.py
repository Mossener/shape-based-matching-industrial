"""Independent complete observation-pack, descriptor and usage replay.

No image bytes or native tools. Reconstructs numeric geometry from full packs;
does not independently reconstruct the native affine/pyramid pixels.
"""
import argparse
from collections import Counter,defaultdict
import csv
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import struct
import input_contract as c
import independent_numeric as n
import bank_reader


def rows(path):
    path=c.numeric_path(path)
    return csv.DictReader(gzip.open(path,'rt',newline='',encoding='utf-8-sig') if path.name.endswith('.gz') else path.open(newline='',encoding='utf-8-sig'))


def pose_key(row):
    return int(row['object_id']),int(row['image']),int(row['angle']),float(row['scale'])


def map_box(mask):
    points=[]
    for y,runs in enumerate(mask):
        for begin,end,value in runs:
            n.need(value in (0,255),'Nonbinary official map')
            if value:points.append((begin,end-1,y))
    n.need(points,'Empty official map')
    x=min(q[0] for q in points);right=max(q[1] for q in points);y=min(q[2] for q in points);bottom=max(q[2] for q in points)
    return x,y,right-x+1,bottom-y+1


def validate_nearest_pyramid(m0,m1):
    w,h=n.shape(m0);n.need(n.shape(m1)==(w//2,h//2),'Nearest resize shape')
    # All actual training canvases are aligned to16. INTER_NEAREST half-size
    # selects exact even source pixels; do not substitute grayscale pyrDown.
    n.need(w%16==0 and h%16==0,'Actual canvas alignment')
    for y in range(h//2):
        expected=[]
        for begin,end,value in m0[2*y]:
            left,right=(begin+1)//2,(end+1)//2
            if left>=right:continue
            if expected and expected[-1][2]==value:
                expected[-1]=(expected[-1][0],right,value)
            else:expected.append((left,right,value))
        n.need(m1[y]==expected,'Nearest resize values')


def load_banks(observer):
    output={};metadata={};attempts={}
    for record in observer['banks']:
        key=record['family'],record['object_id']
        with gzip.open(c.numeric_path(record['bank_path']),'rt',encoding='utf-8') as stream:
            bank=bank_reader.parse_bank(stream.read(),record['class_id'])
        n.need(len(bank)==record['expected_templates'],'Independent bank count')
        output[key]=bank
        meta=c.load(record['metadata_path'])['templates']
        n.need(len(meta)==len(bank),'Metadata count')
        metadata[key]={int(q['template_id']):q for q in meta}
        attempts[key]=list(rows(record['attempts_path']))
        for ordinal,q in enumerate(meta):
            n.need(q['class_id']==record['class_id'] and int(q['template_id'])==ordinal,'Metadata class/dense IDs')
            n.need(bank[ordinal][0]['tl_x']==int(q['tl_x']) and bank[ordinal][0]['tl_y']==int(q['tl_y']),'Metadata origin')
    return output,metadata,attempts


def verify_attempt_layers(observer,banks,metadata,attempts,table):
    expected_pose_keys={(m['object_id'],m['image_id'],angle,scale) for m in observer['masks'] for angle in range(0,360,30) for scale in (.75,1.,1.5,2.)}
    plan={pose_key(q):q for q in observer['poses']}
    n.need(set(plan)==expected_pose_keys and len(plan)==20736,'Independent shared pose product')
    all_rows={}
    for row in rows(table):
        key=row['family'],*pose_key(row),int(row['level'])
        n.need(key not in all_rows,'Duplicate attempt-layer row');all_rows[key]=row
    n.need(len(all_rows)==124416,'Complete attempt-layer table')
    success=0
    for (family,obj),source_rows in attempts.items():
        n.need(len(source_rows)==3456,'Original attempts count');seen=set();successful_ids=set()
        fi=observer['families'].index(family)
        for row in source_rows:
            key=obj,int(row['training_image']),int(row['angle']),float(row['scale'])
            n.need(key in plan and key not in seen,'Original attempt pose');seen.add(key);pose=plan[key]
            geometry=[int(row[k]) for k in ('source_crop_x','source_crop_y','source_crop_w','source_crop_h','canvas','mask_x','mask_y','mask_w','mask_h')]
            n.need(geometry==pose['geometry'],'Independent attempt geometry')
            tid=int(row['template_id']);ok=int(row['success']);n.need(ok in (0,1),'Attempt success flag')
            n.need(tid==pose['template_ids'][fi],'Independent pose ID')
            if ok:
                n.need(tid>=0 and tid not in successful_ids,'Dense successful template identity');successful_ids.add(tid);success+=1
                meta=metadata[family,obj][tid]
                n.need(int(meta['training_image_id'])==key[1] and float(meta['angle'])==key[2] and float(meta['scale'])==key[3],'Independent metadata pose')
                n.need(tuple(meta['warped_mask_bbox'])==tuple(geometry[5:9]) and int(meta['tl_x'])==int(row['templ_tl_x']) and int(meta['tl_y'])==int(row['templ_tl_y']),'Independent metadata geometry')
            else:n.need(tid==-1 and row['error'],'Independent failure status')
            for level in (0,1):
                actual=len(banks[family,obj][tid][level]['features']) if ok else None
                declared=int(row['features_l'+str(level)])
                n.need(declared==(actual if ok else 0) and pose['expected_counts'][fi][level]==(actual if ok else -1),'Independent feature count/failed placeholder')
                saved=all_rows.get((family,*key,level));n.need(saved is not None,'Missing attempt-layer row')
                n.need(int(saved['success'])==ok and int(saved['template_id'])==tid and int(saved['requested_features'])==(32 if level==0 else 16),'Attempt-layer identity/target')
                n.need(saved['actual_features']==(str(actual) if ok else '') and saved['error']==row['error'] and json.loads(saved['geometry'])==geometry,'Attempt-layer actual/error/geometry')
        n.need(successful_ids==set(range(len(banks[family,obj]))),'Missing successful template attempt')
    n.need(success==59647,'Independent successful-template coverage')


def overlap(a,b):
    if min(a[2],a[3],b[2],b[3])<=0:return 0.
    v=max(0.,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0.,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))
    return v/(a[2]*a[3]+b[2]*b[3]-v)


def canonical(row):
    return (-row['score'],row['class_id'],row['template_id'],row['match_y'],row['match_x'],row['box'][1],row['box'][0],row['box'][2],row['box'][3])


def raw_record(row,meta):
    tid=int(row['template_id']);n.need(tid in meta,'Raw template outside metadata')
    m=meta[tid];score=float(row['score']);sb=struct.unpack('<I',struct.pack('<f',score))[0]
    n.need(math.isfinite(score) and score>=85 and struct.unpack('<f',struct.pack('<I',sb))[0]==score,'Raw float32 score')
    x,y=int(row['match_x']),int(row['match_y']);box=tuple(float(row[k]) for k in ('bbox_x','bbox_y','bbox_w','bbox_h'))
    official=m['warped_mask_bbox'];expected=(x-64+official[0]-m['tl_x'],y-64+official[1]-m['tl_y'],official[2],official[3])
    n.need(box==expected and row['class_id']==m['class_id'] and int(row['training_image'])==int(m['training_image_id']) and float(row['angle'])==float(m['angle']) and float(row['scale'])==float(m['scale']),'Raw geometry/pose')
    return dict(score=score,score_bits=sb,class_id=row['class_id'],template_id=tid,match_x=x,match_y=y,box=box)


def assign(detections,gt,eligible):
    used=set();labels=[['FP',-1] for _ in detections]
    for ignore in ([False,True] if eligible else [False]):
        for ordinal,d in enumerate(detections):
            if labels[ordinal][0]!='FP':continue
            candidates=[]
            for truth in gt:
                if truth['id'] in used:continue
                if eligible and ((truth['visibility']<.5)!=ignore):continue
                value=overlap(d['box'],truth['box'])
                if value>=.5:candidates.append((value,-truth['id'],truth['id']))
            if candidates:
                best=max(candidates)[2];used.add(best);labels[ordinal]=['IGNORE' if ignore else 'TP',best]
    return labels


def usage_replay(freeze,observer,metadata,descriptors,out):
    templates={(b['family'],b['object_id'],tid) for b in observer['banks'] for tid in range(b['expected_templates'])}
    gt_by=defaultdict(list);quality=freeze['quality'];shared_gt=None
    for experiment in quality:
        path=Path(experiment['base'])/'ground_truth.csv';allrows=list(rows(path))
        signature=[tuple(q.items()) for q in allrows]
        if shared_gt is None:shared_gt=signature
        else:n.need(signature==shared_gt,'Ground truth cross-stage mismatch')
    for row in allrows:
        obj,scene,image=int(row['object_id']),int(row['scene']),int(row['image'])
        gt_by[obj,scene,image].append(dict(id=int(row['gt_id']),visibility=float(row['visibility']),box=tuple(float(row[k]) for k in ('bbox_x','bbox_y','bbox_w','bbox_h'))))
    n.need(sum(map(len,gt_by.values()))==400,'All GT coverage')
    raw_counts=Counter();events=[];expected_frames=set();distinct_raw=defaultdict(set);gt_links=[];rgb_signatures={}
    group_usage=defaultdict(Counter)
    with gzip.open(out/'usage_events.csv.gz','wt',newline='',encoding='utf-8') as stream:
        writer=None
        for experiment in quality:
            base=Path(experiment['base']);selected_by=defaultdict(list)
            for row in rows(base/'selected_detections.csv'):
                if row['arm'] in experiment['arms']:selected_by[row['arm'],int(row['object_id']),int(row['scene']),int(row['image'])].append(row)
            metric_rows=[q for q in rows(base/'per_frame_metrics.csv') if q['arm'] in experiment['arms']]
            n.need(len(metric_rows)==2400*len(experiment['arms']),'All quality frame coverage')
            seen=set()
            for metric in metric_rows:
                arm=metric['arm'];family=experiment['arms'][arm];obj,scene,image=int(metric['object_id']),int(metric['scene']),int(metric['image'])
                frame=(family,obj,scene,image);n.need(frame not in seen and scene in (1,4,6,7,8,10,12,13),'Duplicate or forbidden quality frame');seen.add(frame);expected_frames.add(frame)
                family_meta=metadata[family,obj];raw=[]
                for route in ('fallback','fused'):
                    records=[];path=base/f'obj{obj}'/arm/f's{scene}_i{image}_{route}_raw.csv.gz'
                    for rank,row in enumerate(rows(path)):
                        n.need(int(row['scene'])==scene and int(row['image'])==image and row['variant']==route and int(row['rank'])==rank,'Raw scope/rank')
                        records.append(raw_record(row,family_meta))
                    n.need(all(canonical(records[i])<=canonical(records[i+1]) for i in range(len(records)-1)),'Raw ordering')
                    if route=='fallback':raw=records
                    else:n.need(records==raw,'Fallback/fused complete output mismatch')
                n.need(len(raw)==int(metric['raw']),'Raw per-frame count')
                if family=='rgb_official_mask':rgb_signatures[obj,scene,image]=raw
                kept=[]
                for d in raw:
                    tid=d['template_id'];raw_counts[family,obj,tid]+=1;distinct_raw[family,obj,tid].add(frame)
                    if all(overlap(d['box'],old['box'])<=.3 for old in kept):kept.append(d)
                selected=selected_by.get((arm,obj,scene,image),[]);n.need(len(selected)==len(kept)==int(metric['selected']),'Selected count')
                truths=gt_by.get((obj,scene,image),[]);labels=assign(kept,truths,False);eligible=assign(kept,truths,True)
                for rank,(row,d,all_label,eligible_label) in enumerate(zip(selected,kept,labels,eligible)):
                    n.need(int(row['rank'])==rank and int(row['score_bits'])==d['score_bits'] and raw_record(row,family_meta)==d,'Selected exact row identity')
                    n.need([row['allGT_label'],int(row['allGT_id'])]==all_label and [row['eligible_label'],int(row['eligible_id'])]==eligible_label,'Selected label/GT')
                    event=dict(family=family,object_id=obj,template_id=d['template_id'],scene=scene,image=image,allGT_label=all_label[0],eligible_label=eligible_label[0],negative=not truths)
                    events.append(event);saved=dict(row,family=family,negative=int(not truths))
                    for level in (0,1):
                        descriptor=descriptors[family,obj,d['template_id'],level]
                        for name in ('actual_features','entropy_bits','label_counts','region_counts','region_fractions'):
                            value=descriptor[name];saved[f'l{level}_'+name]=json.dumps(value,sort_keys=True,separators=(',',':')) if isinstance(value,(dict,list)) else value
                    for metric_name,label in [('allGT',all_label),('eligible',eligible_label)]:
                        for level in (0,1):
                            descriptor=descriptors[family,obj,d['template_id'],level]
                            for group_key in [(family,'ALL','ALL',metric_name,label[0],level),
                                              (family,str(obj),'ALL',metric_name,label[0],level),
                                              (family,str(obj),str(scene),metric_name,label[0],level)]:
                                aggregate=group_usage[group_key];aggregate['events']+=1;aggregate['features']+=descriptor['actual_features']
                                for name,count in descriptor['region_counts'].items():aggregate[name]+=count
                                for label_index,count in enumerate(descriptor['label_counts']):aggregate['label_'+str(label_index)]+=count
                    if writer is None:writer=csv.DictWriter(stream,fieldnames=list(saved));writer.writeheader()
                    writer.writerow(saved)
                n.need(sum(v[0]=='TP' for v in labels)==int(metric['tp']) and sum(v[0]=='FP' for v in labels)==int(metric['fp']),'Per-frame labels')
                n.need(sum(v[0]=='TP' for v in eligible)==int(metric['eligible_tp']) and sum(v[0]=='FP' for v in eligible)==int(metric['eligible_fp']),'Per-frame eligible labels')
                for truth in truths:
                    for metric_name,label_rows in [('allGT',labels),('eligible',eligible)]:
                        links=[(rank,d) for rank,(d,label) in enumerate(zip(kept,label_rows)) if label==['TP',truth['id']]]
                        n.need(len(links)<=1,'GT duplicate TP')
                        gt_links.append(dict(family=family,object_id=obj,scene=scene,image=image,gt_id=truth['id'],metric=metric_name,
                           in_metric_gt=int(metric_name=='allGT' or truth['visibility']>=.5),visibility=truth['visibility'],
                           matched=int(bool(links)),template_id=links[0][1]['template_id'] if links else -1,selected_rank=links[0][0] if links else -1))
    n.need(len(expected_frames)==7200 and len(events)==64618 and len(gt_links)==2400,'Complete usage/GT coverage')
    # Verify the duplicate historical RGB control rather than count it twice.
    binary_stage=next(q for q in quality if q['experiment']=='silhouette_empty_mask_experiment')
    for (obj,scene,image),reference in rgb_signatures.items():
        for route in ('fallback','fused'):
            path=Path(binary_stage['base'])/f'obj{obj}/rgb/s{scene}_i{image}_{route}_raw.csv.gz'
            historical=[raw_record(row,metadata['rgb_official_mask',obj]) for row in rows(path)]
            n.need(historical==reference,'Historical/current RGB raw control mismatch')
    all_gt={(q['family'],q['object_id'],q['scene'],q['image'],q['gt_id'],q['metric']):q for q in gt_links}
    pose_ids={(family,obj,int(meta['training_image_id']),float(meta['angle']),float(meta['scale'])):tid
              for (family,obj),metas in metadata.items() for tid,meta in metas.items()}
    strata=defaultdict(Counter)
    for q in gt_links:
        obj,scene,image,gt_id,metric=q['object_id'],q['scene'],q['image'],q['gt_id'],q['metric']
        original=all_gt['rgb_official_mask',obj,scene,image,gt_id,metric]['matched']
        binary=all_gt['binary_empty_mask',obj,scene,image,gt_id,metric]['matched']
        current=all_gt['rgb_empty_mask',obj,scene,image,gt_id,metric]['matched']
        prior_name={(1,1):'prior_both',(1,0):'prior_rgb_only',(0,1):'prior_binary_only',(0,0):'prior_neither'}[original,binary]
        current_name={(1,1):'retained',(1,0):'lost',(0,1):'gained',(0,0):'neither'}[original,current]
        q['historical_stratum']=prior_name;q['v27_identity_change']=current_name
        reference=all_gt['rgb_official_mask',obj,scene,image,gt_id,metric]
        reference_meta=metadata['rgb_official_mask',obj][reference['template_id']] if reference['matched'] else None
        q['rgb_reference_image']=reference_meta['training_image_id'] if reference_meta else ''
        q['rgb_reference_angle']=reference_meta['angle'] if reference_meta else ''
        q['rgb_reference_scale']=reference_meta['scale'] if reference_meta else ''
        same_id=pose_ids.get((q['family'],obj,int(reference_meta['training_image_id']),float(reference_meta['angle']),float(reference_meta['scale']))) if reference_meta else None
        q['same_pose_status']='no_rgb_tp_reference' if reference_meta is None else 'successful_serialized_descriptor' if same_id is not None else 'failed_no_serialized_descriptor'
        q['same_pose_template_id']=same_id if same_id is not None else ''
        for level in (0,1):
            descriptor=descriptors[q['family'],obj,same_id,level] if same_id is not None else None
            q[f'same_pose_l{level}_actual_features']=descriptor['actual_features'] if descriptor else ''
            q[f'same_pose_l{level}_region_counts']=json.dumps(descriptor['region_counts'],sort_keys=True,separators=(',',':')) if descriptor else ''
        for stratum in (prior_name,current_name):
            key=(q['family'],metric,stratum)
            aggregate=strata[key];aggregate['identities']+=1;aggregate['in_metric_gt']+=q['in_metric_gt'];aggregate['matched']+=q['matched']
            if q['matched']:
                for level in (0,1):
                    descriptor=descriptors[q['family'],obj,q['template_id'],level]
                    aggregate[f'l{level}_features']+=descriptor['actual_features']
                    for name,count in descriptor['region_counts'].items():aggregate[f'l{level}_'+name]+=count
                    for label_index,count in enumerate(descriptor['label_counts']):aggregate[f'l{level}_label_'+str(label_index)]+=count
    usage=n.complete_usage(templates,events,raw_counts,expected_frames)
    with (out/'raw_template_usage.csv').open('w',newline='',encoding='utf-8') as stream:
        fields=['family','object_id','template_id',*next(iter(usage.values())),'distinct_raw_frames'];writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for key in sorted(usage):writer.writerow(dict(zip(('family','object_id','template_id'),key),**usage[key],distinct_raw_frames=len(distinct_raw[key])))
    with (out/'all_gt_usage.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(gt_links[0]));writer.writeheader();writer.writerows(gt_links)
    totals={}
    for family in observer['families']:
        keys=[k for k in usage if k[0]==family]
        totals[family]=dict(raw=sum(usage[k]['raw'] for k in keys),selected=sum(usage[k]['allGT_tp']+usage[k]['allGT_fp'] for k in keys),tp=sum(usage[k]['allGT_tp'] for k in keys),fp=sum(usage[k]['allGT_fp'] for k in keys),unique_templates=len(keys))
    # Explicit zero event cells make missing objects/scenes/labels visible.
    for family in observer['families']:
        for obj in observer['objects']:
            for scene in (1,4,6,7,8,10,12,13):
                for metric_name,label_names in [('allGT',('TP','FP')),('eligible',('TP','FP','IGNORE'))]:
                    for label in label_names:
                        for level in (0,1):group_usage.setdefault((family,str(obj),str(scene),metric_name,label,level),Counter())
    return dict(totals=totals,event_weighted_regions=[dict(family=k[0],object_id=k[1],scene=k[2],metric=k[3],label=k[4],level=k[5],counts=dict(v)) for k,v in sorted(group_usage.items())],
                historical_identity_regions=[dict(family=k[0],metric=k[1],stratum=k[2],counts=dict(v)) for k,v in sorted(strata.items())])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--observation',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    out=args.output.resolve();c.need(out.is_relative_to(c.HERE) and not out.exists(),'Fresh audit output inside experiment required');out.mkdir();source_pins=[c.pin(c.HERE/n) for n in ('audit_numeric.py','independent_numeric.py','bank_reader.py','input_contract.py')]
    try:
        stage=c.load(args.observation);c.need(stage['completed'] and stage['native_exit']==0,'Incomplete observation')
        for q in stage['files']+stage['execution_files']+stage['sources']+[stage['build'],stage['inputs'],stage['selftest']]:c.check(q)
        native=Path(stage['files'][0]['path']).parent
        c.need({q.resolve() for q in native.iterdir() if q.is_file()}=={Path(q['path']).resolve() for q in stage['files']},'Observation member set')
        freeze=c.load(stage['inputs']['path'])
        for q in freeze['files']+freeze['sources']+freeze['members']:c.check(q)
        observer=c.load(next(q['path'] for q in freeze['members'] if Path(q['path']).name=='observer_inputs.json'))
        banks,metadata,attempts=load_banks(observer)
        attempt_source=next(q['path'] for q in freeze['members'] if Path(q['path']).name=='attempt_layers.csv')
        verify_attempt_layers(observer,banks,metadata,attempts,attempt_source)
        expected={(q['object_id'],q['image'],q['angle'],q['scale']):q for q in observer['poses']};seen=set();descriptor_keys=set();feature_count=0
        feature_iter=iter(rows(native/'feature_observations.csv.gz'));pending=next(feature_iter,None)
        summary_counts=Counter();descriptors={};unique_regions=defaultdict(Counter)
        with gzip.open(out/'features.csv.gz','wt',newline='',encoding='utf-8') as fs,(out/'template_layers.csv').open('w',newline='',encoding='utf-8') as ts:
            fw=tw=None
            for mask in sorted(observer['masks'],key=lambda q:(q['object_id'],q['image_id'])):
                pack=native/f"maps_o{mask['object_id']}_i{mask['image_id']}.jsonl.gz"
                with gzip.open(pack,'rt',encoding='utf-8') as stream:
                    lines=iter(stream)
                    while True:
                        first=next(lines,None)
                        if first is None:break
                        records=[json.loads(first)]+[json.loads(next(lines)) for _ in range(4)]
                        key=pose_key(records[0]);n.need(key in expected and key not in seen,'Duplicate/unknown map pose');seen.add(key)
                        n.need(all(pose_key(q)==key for q in records) and [q['name'] for q in records]==['M0','M1','B1','A0','A1'],'Map membership/order')
                        maps={q['name']:n.read_map(q['map']) for q in records};pose=expected[key];side=pose['geometry'][4]
                        n.need(n.shape(maps['M0'])==(side,side) and all(n.shape(maps[name])==(side//2,side//2) for name in ('M1','B1','A1')) and n.shape(maps['A0'])==(side,side),'Map dimensions')
                        n.need(map_box(maps['M0'])==tuple(pose['geometry'][5:9]),'Map official bbox');validate_nearest_pyramid(maps['M0'],maps['M1'])
                        for fi,family in enumerate(observer['families']):
                            tid=pose['template_ids'][fi]
                            if tid<0:continue
                            template=banks[family,key[0]][tid]
                            for level,layer in enumerate(template):
                                member=(family,key[0],tid,level);n.need(member not in descriptor_keys,'Repeated descriptor');descriptor_keys.add(member)
                                current={'M':maps['M1' if level else 'M0'],'A':maps['A1' if level else 'A0'],'B':maps['B1' if level else 'M0']};bbox=map_box(current['M']);observations=[]
                                n.need(len(layer['features'])==pose['expected_counts'][fi][level],'Bank feature count')
                                for ordinal,feature in enumerate(layer['features']):
                                    row=pending;n.need(row is not None,'Missing feature observation');pending=next(feature_iter,None)
                                    n.need(pose_key(row)==key and row['family']==family and int(row['template_id'])==tid and int(row['level'])==level and int(row['feature_ordinal'])==ordinal,'Feature full identity/order')
                                    q=n.feature_observation(current,layer,feature,bbox)
                                    for name,value in [('local_x',feature[0]),('local_y',feature[1]),('tl_x',layer['tl_x']),('tl_y',layer['tl_y']),('bbox_x',bbox[0]),('bbox_y',bbox[1]),('bbox_w',bbox[2]),('bbox_h',bbox[3])]:n.need(int(row[name])==value,'Feature geometry field: '+name)
                                    for name in ('absolute_x','absolute_y','label','official_value','binary_value','alpha_bits'):n.need(int(row[name])==q[name],'Feature map observation: '+name)
                                    observations.append(q);saved=dict(row,**{k:v for k,v in q.items() if k not in row})
                                    if fw is None:fw=csv.DictWriter(fs,fieldnames=list(saved));fw.writeheader()
                                    fw.writerow(saved);feature_count+=1
                                q=n.descriptor_summary(observations,32 if level==0 else 16)
                                descriptors[family,key[0],tid,level]=q
                                for group in [(family,'ALL',level),(family,str(key[0]),level)]:
                                    aggregate=unique_regions[group];aggregate['templates']+=1;aggregate['features']+=q['actual_features']
                                    for name,count in q['region_counts'].items():aggregate[name]+=count
                                    for label,count in enumerate(q['label_counts']):aggregate['label_'+str(label)]+=count
                                    aggregate['actual_count_'+str(q['actual_features'])]+=1
                                q=dict(family=family,object_id=key[0],image=key[1],angle=key[2],scale=key[3],template_id=tid,level=level,**q)
                                for name in ('label_counts','cell_counts','region_counts','region_fractions'):q[name]=json.dumps(q[name],sort_keys=True,separators=(',',':'))
                                if tw is None:tw=csv.DictWriter(ts,fieldnames=list(q));tw.writeheader()
                                tw.writerow(q);summary_counts[family,level]+=1
        n.need(pending is None and len(seen)==20736 and len(descriptor_keys)==119294 and feature_count==stage['summary']['feature_rows'],'Complete feature/pose coverage')
        # Preserve the complete failure/layer table from the pinned numeric
        # preparer. It contains 124416 rows, including unavailable counts.
        source=next(q['path'] for q in freeze['members'] if Path(q['path']).name=='attempt_layers.csv');(out/'attempt_layers.csv').write_bytes(c.data(source))
        usage=usage_replay(freeze,observer,metadata,descriptors,out);totals=usage['totals']
        spec=c.specification()
        for family in spec['families']:
            actual=totals[family['name']]
            n.need(all(actual[k]==family[k] for k in ('raw','selected','tp','fp')),'Frozen family usage totals')
        for q in source_pins+stage['files']+freeze['files']+freeze['sources']+freeze['members']:c.check(q)
        outputs=[c.pin(q) for q in sorted(out.iterdir()) if q.is_file()]
        result=dict(passed=True,poses=20736,attempt_layers=124416,serialized_layers=119294,features=feature_count,usage=usage,
                    unique_template_regions=[dict(family=k[0],object_id=k[1],level=k[2],counts=dict(v)) for k,v in sorted(unique_regions.items())],
                    sources=source_pins,observation=c.pin(args.observation),outputs=outputs,image_bytes_opened=0,image_decodes=0,matcher_calls=0,
                    limitation='Independent full numeric pack/descriptor/usage replay; native warp/pyrDown pixel generation is not independently reproduced; region association is not causal proof; raw IDs are post-consolidation representatives')
        (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,features=feature_count,matcher_calls=0,image_decodes=0)))
    except Exception as error:
        (out/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),sources=source_pins,image_bytes_opened=0,matcher_calls=0),indent=2)+'\n');raise


if __name__=='__main__':main()
