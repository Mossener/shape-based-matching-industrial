"""Independent Phase2 joins and downstream audit; no target imports."""
from collections import Counter
from itertools import groupby,zip_longest
import numeric2 as n

def check_nms_frame(rows,post,truths,saved):
    selected,blocked=n.nms(post);kept=[post[rank] for rank in selected]
    allgt=n.assign(kept,truths);eligible=n.assign(kept,truths,True)
    n.need(len(saved)==len(kept),'Saved selected count differs')
    for index,(actual,record) in enumerate(zip(saved,kept)):
        n.need(actual['record']==record,'Full selected record fields/score bits differ')
        n.need((actual['allGT_label'],actual['allGT_id'])==allgt[index] and (actual['eligible_label'],actual['eligible_id'])==eligible[index],'Saved allGT/eligible assignment differs')
    selected_rank={rank:index for index,rank in enumerate(selected)};seen=0
    for rank,row in enumerate(rows):
        n.need(rank<len(post),'Extra fullclass NMS row');d=post[rank];sr=selected_rank.get(rank,-1);block=blocked[rank]
        label,gtid=allgt[sr] if sr>=0 else ('SUPPRESSED',-1)
        check_fields(row,dict(post_rank=rank,template=d['template'],match_x=d['x'],match_y=d['y'],score_bits=d['bits'],selected_rank=sr,blocker_post_rank=block,blocker_iou=n.iou(d['box'],post[block]['box']) if block>=0 else 0.,allGT_label=label,allGT_id=gtid),'fullclass NMS')
        seen+=1
    n.need(seen==len(post),'Missing fullclass NMS row');return selected,blocked


def check_occurrences(rows,ctx,predicted,pre,representatives,post,selected,blocked):
    n.reconcile_occurrences(predicted,pre,set(ctx['points']))
    by_key={}
    for rank,record in enumerate(post):
        key=(record['x'],record['y'],record['bits']);n.need(key not in by_key,'Duplicate full post equality key');by_key[key]=rank
    expected={}
    selected_ranks={rank:index for index,rank in enumerate(selected)}
    for key,multiplicity in sorted(predicted.items()):
        n.need(key in by_key and key in representatives,'Traced occurrence lacks full representative')
        rank=by_key[key];rep=post[rank]
        n.need(rep['template']==representatives[key],'Post representative is not complete pre minimum ID')
        x,y,bits=key;prebox=box_at(x,y,ctx['meta']);repbox=rep['box']
        for gt in ctx['targets']:
            truth=ctx['original'][gt]['bbox']
            want=dict(job=ctx['id'],gt_id=gt,match_x=x,match_y=y,score_bits=bits,traced_parents=multiplicity,full_pre_multiplicity=pre[key],post_representative_template=rep['template'],post_rank=rank,nms_selected_rank=selected_ranks.get(rank,-1),nms_blocker=blocked[rank],pre_iou_gt=n.iou(prebox,truth),rep_iou_gt=n.iou(repbox,truth))
            want.update(zip(('pre_box_x','pre_box_y','pre_box_w','pre_box_h'),prebox));want.update(zip(('rep_box_x','rep_box_y','rep_box_w','rep_box_h'),repbox))
            expected[(gt,x,y,bits)]=want
    seen=set()
    for row in rows:
        key=tuple(n.integer(row[field]) for field in ('gt_id','match_x','match_y','score_bits'))
        n.need(key in expected and key not in seen,'Unknown/duplicate occurrence row');seen.add(key);check_fields(row,expected[key],'occurrence')
    n.need(seen==set(expected),'Missing predicted occurrence row');return len(seen)


def check_maps(vector_groups,cell_groups,maxima,contexts,windows,owner_order):
    maxima_by_id={}
    for row in maxima:
        wid=n.integer(row['window']);n.need(wid in windows and wid not in maxima_by_id,'Unknown/duplicate local maximum owner');maxima_by_id[wid]=row
    n.need(set(maxima_by_id)==set(windows),'Missing local maximum window')
    coarse={};local={};signatures={};coarse_signatures={};bank_signatures={};counts=Counter()
    def identity_rows(rows,key):
        for row in rows:
            n.need((row['kind'],n.integer(row['owner']))==key,'Wrong row kind/owner inside numeric group');yield row
    for expected,vg,cg in zip_longest(owner_order,vector_groups,cell_groups):
        n.need(expected is not None and vg is not None and cg is not None,'Missing/extra feature/cell owner group')
        n.need(vg[0]==cg[0]==expected,'Feature/cell/geometry owner group order differs')
        kind,owner=expected
        if kind=='coarse':
            ctx=contexts[owner];layer=ctx['coarse'];count=ctx['plan']['coarse_features'];size=(424,416);base=(0,0)
            height,width,tail=n.coarse_span(*size,layer['width'],layer['height']);cells=height*width
        else:
            win=windows[owner];ctx=contexts[win['job']];layer=ctx['fine'];count=ctx['plan']['fine_features'];size=(848,832);base=win['base'];height=width=16;tail=cells=256
        raw,signature=n.sum_features(identity_rows(vg[1],expected),count,cells,size,base,tail)
        bank_key=(ctx['key'][0],ctx['key'][3],ctx['key'][4],kind) if 'key' in ctx else (owner,kind)
        if bank_key in bank_signatures:n.need(bank_signatures[bank_key]==signature,'Serialized feature coordinates/order/labels changed between frames')
        else:bank_signatures[bank_key]=signature
        bounds=(min(x for x,y,label in signature),min(y for x,y,label in signature),max(x for x,y,label in signature),max(y for x,y,label in signature))
        n.need(bounds==tuple(layer[key] for key in ('min_x','min_y','max_x','max_y')),'Feature aggregate bounds differ from loaded layer evidence')
        n.verify_cells(identity_rows(cg[1],expected),raw,count,(height,width),kind,tail)
        if kind=='coarse':coarse[owner]=raw;coarse_signatures[owner]=signature
        else:
            jid=windows[owner]['job']
            if jid in signatures:n.need(signatures[jid]==signature,'Fine serialized feature order/coordinate/label changed across windows')
            else:signatures[jid]=signature
            best=n.verify_maximum(maxima_by_id[owner],raw,count,windows[owner]['center']);local[owner]=dict(raw=raw,best=best)
        counts[kind+'_cells']+=cells;counts[kind+'_features']+=count;counts['digits']+=cells*count;counts['owner_groups']+=1
    n.need(set(coarse)==set(contexts) and set(local)==set(windows) and set(signatures)==set(contexts),'Incomplete numeric map/feature coverage')
    return coarse,local,signatures,dict(counts)


def pair(value):return tuple(map(n.integer,value))


def check_fields(row,want,label):
    for key,value in want.items():
        if isinstance(value,str):actual=row[key]
        elif isinstance(value,int):actual=n.integer(row[key])
        else:actual=n.finite(row[key])
        n.need(actual==value,f'{label} field {key} differs')


def job_key(row):return tuple(n.integer(row[key]) for key in ('object_id','scene','image'))+(row['arm'],n.integer(row['template_id']))


def box_at(x,y,meta):
    sx,sy,w,h=map(n.finite,meta['warped_mask_bbox'])
    return (x-64+sx-n.integer(meta['tl_x']),y-64+sy-n.integer(meta['tl_y']),w,h)


def job_contexts(plan,rows,layers,metadata,prior_frames):
    planned={tuple(job['key']):job for job in plan['jobs']}
    n.need(len(planned)==len(plan['jobs']),'Duplicate planned job key')
    contexts={};targets_seen=set();keys_seen=set();windows={};owner_order=[]
    for job_id,group in groupby(rows,key=lambda row:n.integer(row['job_id'])):
        group=list(group);n.need(job_id==len(contexts) and group,'Duplicate/nonsequential native job ID')
        key=job_key(group[0]);n.need(key in planned and key not in keys_seen,'Unknown/duplicate actual job key');keys_seen.add(key)
        job=planned[key];obj,scene,image,arm,tid=key
        n.need((obj,arm) in metadata and tid in metadata[(obj,arm)],'Missing job template metadata')
        meta=metadata[(obj,arm)][tid];fine=layers[(arm,obj,tid,0)];coarse=layers[(arm,obj,tid,1)]
        n.need(n.integer(meta['template_id'])==tid and meta['class_id']=='tless_object_'+str(obj),'Job metadata identity differs')
        n.need(job['fine_features']==fine['actual_features'] and job['coarse_features']==coarse['actual_features'],'Plan/loaded feature count differs')
        targets={n.integer(target['gt_id']):target for target in job['targets']}
        n.need(len(targets)==len(job['targets']),'Duplicate plan target')
        original={n.integer(target['gt_id']):target for target in prior_frames[(obj,scene,image)]['targets']}
        seen=set()
        for row in group:
            n.need(job_key(row)==key,'One job ID has multiple keys')
            gt=n.integer(row['gt_id']);n.need(gt in targets and gt not in seen and gt in original,'Unknown/duplicate actual job target');seen.add(gt)
            target,old=targets[gt],original[gt];anchor=pair(target['physical_anchor'])
            check_fields(row,dict(training_image=n.integer(meta['training_image_id']),fine_features=job['fine_features'],coarse_features=job['coarse_features'],physical_x=anchor[0],physical_y=anchor[1]),'job')
            n.need(n.value_bits(row['angle'])==n.value_bits(meta['angle']) and n.value_bits(row['scale'])==n.value_bits(meta['scale']),'Actual job pose differs')
            pose=old['rgb_tp_pose']
            n.need(n.integer(meta['training_image_id'])==n.integer(pose[0]) and n.value_bits(meta['angle'])==n.value_bits(pose[1]) and n.value_bits(meta['scale'])==n.value_bits(pose[2]),'Same-pose arm identity differs')
            sx,sy,_,_=map(n.finite,meta['warped_mask_bbox'])
            calculated=(n.integer(old['rgb_tp_box'][0]+64-sx+n.integer(meta['tl_x'])),n.integer(old['rgb_tp_box'][1]+64-sy+n.integer(meta['tl_y'])))
            n.need(anchor==calculated,'Physical anchor differs from preserved RGB box')
            points=list(map(pair,target['points']));n.need(len(points)==len(set(points)) and set(points)==set(n.neighbors(anchor)),'Target neighboring grid domain differs')
            n.need(target['off_native_grid'] is (((anchor[0]-1)%4!=0) or ((anchor[1]-1)%4!=0)),'Plan off-grid declaration differs')
            if arm=='rgb':n.need(tid==old['rgb_tp_template'] and anchor==pair(old['rgb_tp_match']),'Original RGB identity/anchor differs')
            targets_seen.add((job_id,gt))
        n.need(seen==set(targets) and job['physical_anchors']==len(targets),'Missing actual target row')
        wanted_points=set(point for target in targets.values() for point in map(pair,target['points']))
        points={};parents={};size=(fine['width'],fine['height'])
        for node in job['point_plan']:
            point=pair(node['point']);n.need(point in wanted_points and point not in points,'Unknown/duplicate point plan')
            expected=n.reachable(point,size);declared={}
            for entry in node['parents']:
                pk=(n.integer(entry['row']),n.integer(entry['col']));n.need(pk in expected and pk not in declared,'Unknown/duplicate planned reachable parent')
                center,base=expected[pk]
                n.need(pair(entry['start'])==center and pair(entry['base'])==base and (n.integer(entry['coarse_x']),n.integer(entry['coarse_y']))==(pk[1]*8+3,pk[0]*8+3),'Declared parent geometry differs')
                declared[pk]=(center,base);parents[pk]=dict(center=center,base=base)
            n.need(set(declared)==set(expected),'Missing complete reachable parent')
            points[point]=set(expected)
        n.need(set(points)==wanted_points,'Missing planned grid point')
        owner_order.append(('coarse',job_id));by_base={}
        for pk in sorted(parents):
            p=parents[pk];base=p['base']
            if base not in by_base:
                wid=len(windows);by_base[base]=wid
                windows[wid]=dict(job=job_id,center=p['center'],base=base);owner_order.append(('local',wid))
            p['window']=by_base[base]
        n.need((job['native_grid_points'],job['parent_point_links'],job['unique_reachable_parents'],job['unique_local_windows'])==(len(points),sum(map(len,points.values())),len(parents),len(by_base)),'Per-job numeric geometry budget differs')
        contexts[job_id]=dict(id=job_id,key=key,plan=job,meta=meta,fine=fine,coarse=coarse,targets=targets,original=original,points=points,parents=parents,windows=list(by_base.values()))
    n.need(keys_seen==set(planned),'Missing actual job identity')
    return contexts,windows,owner_order


def check_physical(rows,contexts,signatures):
    expected={(jid,gt) for jid,ctx in contexts.items() for gt in ctx['targets']};seen=set();count=0
    for key,group in groupby(rows,key=lambda row:(n.integer(row['job']),n.integer(row['gt_id']))):
        n.need(key in expected and key not in seen,'Unknown/duplicate physical target');seen.add(key)
        jid,gt=key;ctx=contexts[jid];anchor=pair(ctx['targets'][gt]['physical_anchor']);signature=signatures[jid]
        domain=all(0<=x+anchor[0]-1<848 and 0<=y+anchor[1]-1<832 for x,y,label in signature)
        raw=0;group=list(group);n.need(len(group)==len(signature),'Physical feature coverage differs')
        for fi,(row,(x,y,label)) in enumerate(zip(group,signature)):
            valid=0<=x+anchor[0]-1<848 and 0<=y+anchor[1]-1<832
            check_fields(row,dict(physical_x=anchor[0],physical_y=anchor[1],on_grid=int((anchor[0]-1)%4==(anchor[1]-1)%4==0),in_physical_domain=int(domain),feature_id=fi),'physical')
            response=n.integer(row['response']);n.need((0<=response<=4) if valid else response==-1,'Physical contribution/domain differs')
            if valid:raw+=response
        for row in group:
            if domain:check_fields(row,dict(raw=raw,score_bits=n.score_bits(raw,len(signature))),'physical sum')
            else:n.need(row['raw']==row['score_bits']=='','Out-of-domain physical score is defined')
        count+=len(group)
    n.need(seen==expected,'Missing physical target');return count


def expected_emissions(context,coarse,local):
    predicted=Counter();fine_count=context['plan']['fine_features'];coarse_count=context['plan']['coarse_features']
    for (row,col),parent in context['parents'].items():
        best=local[parent['window']]['best']
        if n.score_value(coarse[row*53+col],coarse_count)>85 and n.bits_value(best['bits'])>=85:
            bx,by=parent['base'];predicted[(bx+best['col']*4+1,by+best['row']*4+1,best['bits'])]+=1
    return predicted


def check_links(rows,contexts,coarse,local):
    expected={(jid,gt,point,pk) for jid,ctx in contexts.items() for gt,target in ctx['targets'].items() for point in map(pair,target['points']) for pk in ctx['points'][point]}
    seen=set();controls=set();count=0
    for row in rows:
        jid,gt=map(n.integer,(row['job'],row['gt_id']));point=(n.integer(row['point_x']),n.integer(row['point_y']));pk=(n.integer(row['coarse_row']),n.integer(row['coarse_col']));key=(jid,gt,point,pk)
        n.need(key in expected and key not in seen,'Unknown/duplicate parent link');seen.add(key)
        ctx=contexts[jid];p=ctx['parents'][pk];wid=p['window'];window=local[wid];best=window['best'];bx,by=p['base']
        ry,cx=(point[1]-1-by)//4,(point[0]-1-bx)//4;n.need(0<=ry<16 and 0<=cx<16,'Linked point outside local window')
        cr=coarse[jid][pk[0]*53+pk[1]];pr=window['raw'][ry*16+cx];cc=ctx['plan']['coarse_features'];fc=ctx['plan']['fine_features']
        wx,wy=bx+4*best['col']+1,by+4*best['row']+1;same=(wx,wy)==point;admitted=n.score_value(cr,cc)>85;emitted=admitted and n.bits_value(best['bits'])>=85
        check_fields(row,dict(coarse_raw=cr,coarse_score_bits=n.score_bits(cr,cc),admitted=int(admitted),window=wid,point_raw=pr,point_score_bits=n.score_bits(pr,fc),point_fine_pass=int(n.score_value(pr,fc)>=85),winner_x=wx,winner_y=wy,winner_raw=best['raw'],winner_score_bits=best['bits'],point_is_winner=int(same),predicts_emission=int(emitted)),'parent link')
        truth=ctx['original'][gt]['bbox'];n.need(n.finite(row['point_iou_gt'])==n.iou(box_at(*point,ctx['meta']),truth),'Linked point IoU differs')
        if ctx['key'][3]=='rgb' and point==pair(ctx['targets'][gt]['physical_anchor']) and same and emitted and best['bits']==ctx['original'][gt]['rgb_tp_score_bits']:controls.add((jid,gt))
        count+=1
    n.need(seen==expected,'Missing complete parent links')
    wanted_controls={(jid,gt) for jid,ctx in contexts.items() if ctx['key'][3]=='rgb' for gt in ctx['targets']}
    n.need(controls==wanted_controls,'Missing original RGB positive-control path')
    return dict(parent_links=count,rgb_positive_controls=len(controls))
