"""Independent numeric reconstruction. Standard library only; no target imports.

Record: (class, template, match_x, match_y, score_bits_bytes, box,
         (training_image, angle_bits_bytes, scale_bits_bytes)).
"""
from collections import Counter, defaultdict
import csv
import gzip
import io
import math
from pathlib import Path
import re
import struct

RAW_HEADER = 'scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h'.split(',')

def need(condition, reason):
    if not condition: raise ValueError(reason)

def integer(value):
    text=str(value)
    need(re.fullmatch(r'-?(0|[1-9][0-9]*)',text) is not None,'Noncanonical integer')
    result=int(text); need(-2147483648<=result<=4294967295,'Integer range differs'); return result

def finite(value):
    result=float(value); need(math.isfinite(result),'Nonfinite number'); return result

def fbits(value):
    try: packed=struct.pack('<f',finite(value))
    except (OverflowError,struct.error) as error: raise ValueError('Unrepresentable binary32') from error
    need(math.isfinite(struct.unpack('<f',packed)[0]),'Nonfinite binary32'); return packed

def score(row):
    need(isinstance(row[4],bytes) and len(row[4])==4,'Invalid binary32 bits')
    value=struct.unpack('<f',row[4])[0]; need(math.isfinite(value),'Nonfinite score'); return value

def group_key(row):
    # C++ float == coalesces +0/-0. Finite values other than zero are exact.
    return row[0],row[2],row[3],score(row)

def v11_order(row):
    return -score(row),row[1],row[0],row[3],row[2]

def canonical(row):
    x,y,w,h=row[5]
    return -score(row),row[0],row[1],row[3],row[2],y,x,w,h

def consolidate(rows):
    groups=defaultdict(list)
    for row in rows: groups[group_key(row)].append(row)
    result=[]
    for members in groups.values():
        identity=min(row[1] for row in members)
        choices=[row for row in members if row[1]==identity]
        # V11's sort is unstable for a minimum-ID signed-zero tie. Do not
        # invent a representative's sign or claim deterministic bit recovery.
        need(len(set(choices))==1,'Representative is ambiguous for equal minimum template')
        result.append(choices[0])
    return sorted(result,key=v11_order)

def table(encoded,header):
    reader=csv.DictReader(io.StringIO(encoded.decode('utf-8-sig'),newline=''))
    need(reader.fieldnames==header,'CSV schema differs')
    rows=list(reader); need(all(None not in row and None not in row.values() for row in rows),'CSV width differs')
    return rows

def load_metadata(document,obj,expected=None):
    rows=document.get('templates'); need(isinstance(rows,list),'Missing template metadata')
    result={}
    for row in rows:
        identity=integer(row['template_id']); need(identity not in result and row['class_id']=='tless_object_'+str(obj),'Metadata identity differs')
        need(len(row['warped_mask_bbox'])==4 and min(map(finite,row['warped_mask_bbox'][2:]))>0,'Metadata box differs')
        finite(row['tl_x']); finite(row['tl_y']); fbits(row['angle']); fbits(row['scale']); integer(row['training_image_id'])
        result[identity]=row
    need(set(result)==set(range(len(result))) and (expected is None or len(result)==expected),'Metadata template count/gaps differ')
    return result

def parse_candidate(row,obj,metadata):
    cls='tless_object_'+str(obj); identity=integer(row['template_id'])
    need(row['class_id']==cls and identity in metadata,'Class/template identity differs')
    meta=metadata[identity]; need(meta['class_id']==cls and integer(meta['template_id'])==identity,'Metadata key differs')
    x,y=integer(row['match_x']),integer(row['match_y']); value=finite(row['score'])
    need(85<=value<=100,'Score outside Phase1 frozen threshold/range'); bits=fbits(value)
    box=tuple(finite(row['bbox_'+axis]) for axis in ('x','y','w','h'))
    sx,sy,w,h=map(finite,meta['warped_mask_bbox'])
    need(box==(x-64+sx-finite(meta['tl_x']),y-64+sy-finite(meta['tl_y']),w,h),'Metadata box/origin differs')
    pose=(integer(row['training_image']),fbits(row['angle']),fbits(row['scale']))
    need(pose==(integer(meta['training_image_id']),fbits(meta['angle']),fbits(meta['scale'])),'Metadata pose differs')
    return cls,identity,x,y,bits,box,pose

def parse_raw(encoded,manifest,frame,variant,obj,metadata,archive_path=None):
    contents=gzip.decompress(encoded); rows=table(contents,RAW_HEADER); cls='tless_object_'+str(obj)
    need((manifest.get('scene_id'),manifest.get('image_id'),manifest.get('variant'),manifest.get('raw_candidate_count'),manifest.get('compressed_bytes'),manifest.get('uncompressed_bytes'))==(*frame,variant,len(rows),len(encoded),len(contents)),'Raw manifest frame/count/size differs')
    need(manifest.get('class_id')==cls and manifest.get('class_ids')==[cls] and manifest.get('rgb')==f'test_primesense/{frame[0]:06d}/rgb/{frame[1]:06d}.png','Raw manifest class/RGB differs')
    need(manifest.get('format')=='gzip CSV; all candidates retained, 17 significant score digits' and isinstance(manifest.get('zlib_version'),str),'Raw manifest format differs')
    if archive_path is not None:
        need(Path(manifest['path']).resolve()==Path(archive_path).resolve(),'Raw manifest archive path differs')
    result=[]
    for rank,row in enumerate(rows):
        need((integer(row['scene']),integer(row['image']),row['variant'],integer(row['rank']))==(*frame,variant,rank),'Raw frame/rank differs')
        result.append(parse_candidate(row,obj,metadata))
    need(result==sorted(result,key=canonical),'Raw canonical order differs'); return result

def iou(a,b):
    x,y,w,h=map(finite,a); u,v,q,r=map(finite,b)
    need(min(w,h,q,r)>0,'Nonpositive IoU box')
    intersection=max(0.,min(x+w,u+q)-max(x,u))*max(0.,min(y+h,v+r)-max(y,v))
    return intersection/(w*h+q*r-intersection)

def diagnostics(pre,post,targets):
    expected=sorted(consolidate(pre),key=canonical)
    need(expected==post,'Complete ordered post representative fields/score bits differ')
    groups=defaultdict(list)
    for row in pre: groups[group_key(row)].append(row)
    representatives=[]; cross=unique=duplicate=0
    # C++ std::map Key order uses class,x,y,score_bits, not score order.
    for key,members in sorted(groups.items(),key=lambda pair:(pair[0][0],pair[0][1],pair[0][2],struct.unpack('<I',pair[1][0][4])[0])):
        counts=Counter(row[1] for row in members); duplicate+=sum(n-1 for n in counts.values())
        if len(counts)<2: continue
        cross+=1; unique+=len(counts); representative=min(counts)
        rep=next(row for row in members if row[1]==representative)
        for identity,count in sorted(counts.items()):
            if identity==representative: continue
            old=next(row for row in members if row[1]==identity)
            record=dict(score_bits=struct.unpack('<I',rep[4])[0],match_x=rep[2],match_y=rep[3],representative_template=representative,discarded_template=identity,discarded_occurrences=count)
            record.update(zip(('representative_x','representative_y','representative_w','representative_h'),rep[5]))
            record.update(zip(('discarded_x','discarded_y','discarded_w','discarded_h'),old[5])); representatives.append(record)
    support=[]
    for target in targets:
        before=[iou(row[5],target['bbox']) for row in pre]; after=[iou(row[5],target['bbox']) for row in post]
        before_hits=sum(v>=.5 for v in before); after_hits=sum(v>=.5 for v in after)
        support.append(dict(gt_id=integer(target['gt_id']),pre_hits=before_hits,post_hits=after_hits,pre_best_iou=max(before,default=0.),post_best_iou=max(after,default=0.),candidate_support_lost_at_consolidation=int(before_hits>0 and after_hits==0)))
    return dict(per=dict(pre=len(pre),post=len(post),pre_unique_templates_in_collision_groups=unique,cross_template_groups=cross,same_template_duplicate_occurrences=duplicate,zero_score_matches=sum(score(row)==0 for row in pre),fine_oracle_rows=len(pre),exact_saved_raw=1),support=support,representatives=representatives)
