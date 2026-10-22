"""Independent standard-library map/descriptor oracle; no producer imports."""
from collections import Counter
import hashlib
import math
import struct


def need(value, reason):
    if not value:raise ValueError(reason)


def float_value(bits):
    return struct.unpack('<f',struct.pack('<I',bits))[0]


def read_map(record):
    """Validate canonical full-image RLE/hash and retain exact run intervals."""
    need(set(record)=={'width','height','dtype','rows','sha256'},'Map schema')
    width,height,dtype=record['width'],record['height'],record['dtype']
    need(type(width) is int and type(height) is int and 0<width<=2048 and 0<height<=2048,'Map dimensions')
    need(dtype in ('u8','f32bits') and len(record['rows'])==height,'Map dtype/height')
    result=[];digest=hashlib.sha256()
    for row in record['rows']:
        current=[];cursor=0;previous=None
        for run in row:
            need(isinstance(run,list) and len(run)==2,'Map run schema')
            value,count=run
            need(type(value) is int and type(count) is int and count>0 and cursor+count<=width,'Map run width/count')
            need(previous is None or previous!=value,'Noncanonical adjacent runs')
            if dtype=='u8':need(0<=value<=255,'Map byte range');encoded=bytes([value])
            else:
                need(0<=value<2**32,'Float bits range')
                alpha=float_value(value)
                need(math.isfinite(alpha) and 0<=alpha<=1,'Invalid alpha')
                encoded=struct.pack('<I',value)
            digest.update(encoded*count);current.append((cursor,cursor+count,value))
            cursor+=count;previous=value
        need(cursor==width,'Incomplete map row')
        result.append(current)
    need(digest.hexdigest()==record['sha256'],'Map SHA changed')
    return result


def shape(rows):
    need(rows and rows[0],'Empty map')
    return rows[0][-1][1],len(rows)


def value_at(rows,x,y):
    width,height=shape(rows)
    need(0<=x<width and 0<=y<height,'Map coordinate outside canvas')
    for begin,end,value in rows[y]:
        if begin<=x<end:return value
    raise ValueError('Map interval gap')


def signed_distance(rows,x,y,predicate):
    """Exact Chebyshev query from RLE, with zero exterior for inside points."""
    width,height=shape(rows)
    inside=bool(predicate(value_at(rows,x,y)))
    best=min(x+1,y+1,width-x,height-y) if inside else max(width,height)+1
    for delta in range(height):
        if delta>=best:break
        ys=[y] if delta==0 else [y-delta,y+delta]
        for row_index in ys:
            if not 0<=row_index<height:continue
            for begin,end,value in rows[row_index]:
                if bool(predicate(value))==inside:continue
                horizontal=begin-x if x<begin else x-end+1 if x>=end else 0
                best=min(best,max(delta,horizontal))
    need(0<best<=max(width,height),'No opposite region')
    return best if inside else -best


def feature_observation(maps,layer,feature,bbox):
    local_x,local_y,label=feature
    need(type(label) is int and 0<=label<8,'Feature label')
    x,y=local_x+layer['tl_x'],local_y+layer['tl_y']
    width,height=shape(maps['M'])
    need(all(shape(maps[k])==(width,height) for k in ('A','B')),'Layer map shape mismatch')
    mask=value_at(maps['M'],x,y)
    need(mask in (0,255),'Official mask is not binary')
    eroded=255
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            eroded=min(eroded,value_at(maps['M'],min(width-1,max(0,x+dx)),min(height-1,max(0,y+dy))))
    alpha_bits=value_at(maps['A'],x,y)
    alpha=float_value(alpha_bits)
    md=signed_distance(maps['M'],x,y,lambda v:v!=0)
    cd=signed_distance(maps['A'],x,y,lambda v:float_value(v)>0)
    edge=min(x,y,width-1-x,height-1-y)
    bx,by,bw,bh=bbox
    need(bw>0 and bh>0,'Official bbox is empty')
    cell=4*((y-by)*4//bh)+(x-bx)*4//bw if bx<=x<bx+bw and by<=y<by+bh else 16
    result=dict(absolute_x=x,absolute_y=y,label=label,official_value=mask,eroded_value=eroded,
                alpha_bits=alpha_bits,binary_value=value_at(maps['B'],x,y),mask_signed_distance=md,
                crop_signed_distance=cd,canvas_edge=edge,cell=cell)
    need(math.isfinite(alpha) and 0<=alpha<=1,'Feature alpha')
    for r in (4,5,6):
        result['mask_cross'+str(r)]=int(abs(md)<=r)
        result['crop_cross'+str(r)]=int(abs(cd)<=r)
        result['canvas_cross'+str(r)]=int(edge<r)
    return result


def descriptor_summary(observations,target):
    need(observations and type(target) is int and target>0,'Empty descriptor or target')
    labels=[0]*8;cells=[0]*17;counts=Counter()
    for q in observations:
        need(0<=q['label']<8 and 0<=q['cell']<17,'Descriptor label/cell')
        labels[q['label']]+=1;cells[q['cell']]+=1
        counts['official_inside']+=int(q['official_value']!=0)
        counts['eroded_inside']+=int(q['eroded_value']!=0)
        a=float_value(q['alpha_bits'])
        counts['alpha_absent']+=int(a==0);counts['alpha_partial']+=int(0<a<1);counts['alpha_full']+=int(a==1)
        for r in (4,5,6):
            for axis in ('mask','crop','canvas'):
                key=axis+'_cross'+str(r);counts[key]+=q[key]
    count=len(observations)
    entropy=-sum((v/count)*math.log2(v/count) for v in labels if v)
    return dict(actual_features=count,requested_target=target,target_deficit=max(0,target-count),
                target_surplus=max(0,count-target),label_counts=labels,cell_counts=cells,
                occupied_cells=sum(v>0 for v in cells),entropy_bits=entropy,region_counts=dict(counts),
                region_fractions={k:v/count for k,v in counts.items()})


def complete_usage(templates,selected,raw_counts,expected_frames):
    result={k:dict(raw=0,allGT_tp=0,allGT_fp=0,eligible_tp=0,eligible_fp=0,eligible_ignore=0,
                   negative_selected=0,positive_selected=0,distinct_selected_frames=0) for k in templates}
    frames={k:set() for k in templates}
    for key,count in raw_counts.items():
        need(key in result and type(count) is int and count>=0,'Unknown raw template or count')
        result[key]['raw']=count
    for row in selected:
        key=(row['family'],row['object_id'],row['template_id'])
        frame=(row['family'],row['object_id'],row['scene'],row['image'])
        need(key in result and frame in expected_frames,'Unknown usage template/frame')
        need(row['allGT_label'] in ('TP','FP') and row['eligible_label'] in ('TP','FP','IGNORE'),'Usage label')
        need(not row['negative'] or row['allGT_label']=='FP','Negative frame has TP')
        q=result[key];q['allGT_'+row['allGT_label'].lower()]+=1;q['eligible_'+row['eligible_label'].lower()]+=1
        q['negative_selected' if row['negative'] else 'positive_selected']+=1;frames[key].add(frame)
    for key in templates:result[key]['distinct_selected_frames']=len(frames[key])
    return result
