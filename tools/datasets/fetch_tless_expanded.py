#!/usr/bin/env python3
"""Plan/fetch a larger, fixed T-LESS slice without running a matcher.

The default stage surveys only official ZIP directories and GT/camera metadata.
It excludes all four tiny-slice scenes, including its sealed heldout scenes.
Image acquisition is a separate explicit --fetch stage using the saved plan.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import zlib

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('tless_range_protocol',HERE/'fetch_tless_tiny.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
OBJECTS=[1,2,5,8,12,17,25,29]
OBJECT_DEVELOPMENT=[1,2,5,8,12,17]
OBJECT_GENERALIZATION=[25,29]
DEV_SCENES=[1,4,6,7,8,10,12,13]
HOLD_SCENES=[11,14,15,16,17,18,19,20]
EXCLUDED_TINY_SCENES=[2,3,5,9]
BODY_LIMIT=2_000_000_000

def dump(path,value):base.dump_json(path,value)
def digest(data):return hashlib.sha256(data).hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8'))

def farthest_rotations(gt,count):
    """Greedy SO(3) coverage, no matcher/image content or ID-slice tuning."""
    ids=sorted(map(int,gt));rot={i:gt[str(i)][0]['cam_R_m2c'] for i in ids}
    if count>=len(ids):return ids
    chosen=[ids[0]];remaining=set(ids[1:]);nearest={i:float('inf') for i in remaining}
    while len(chosen)<count:
        last=rot[chosen[-1]]
        for i in remaining:
            distance=sum((a-b)**2 for a,b in zip(rot[i],last))
            nearest[i]=min(nearest[i],distance)
        winner=max(remaining,key=lambda i:(nearest[i],-i));chosen.append(winner);remaining.remove(winner)
    return sorted(chosen)

def local_member(client,archive,entry,root,records):
    path=base.safe_local(root,entry['path'])
    if path.exists():
        data=path.read_bytes()
        if len(data)!=entry['size'] or zlib.crc32(data)&0xffffffff!=entry['crc32']:
            raise ValueError('Cached member failed ZIP size/CRC: '+entry['path'])
    else:
        data=base.fetch_member(client,archive,entry);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    records[entry['path']]={'archive':archive,'local_path':entry['path'],'bytes':len(data),'sha256':digest(data),
                            'archive_crc32':f"{entry['crc32']:08x}",'compressed_bytes':entry['compressed_size']}
    return data

def summarize_scene(gt,info,targets):
    result={'frames':len(gt),'objects':{},'joint_target_positive_frames':0,'joint_target_negative_frames':0}
    stats={o:Counter() for o in targets}
    for frame,poses in gt.items():
        if len(poses)!=len(info[frame]):raise ValueError('GT/info length mismatch')
        present=set()
        for pose,entry in zip(poses,info[frame]):
            obj=pose['obj_id']
            if obj in stats:
                present.add(obj);stats[obj]['instances']+=1
                stats[obj]['eligible_visib_0_5_instances']+=entry['visib_fract']>=.5
        for obj in targets:stats[obj]['positive_frames' if obj in present else 'negative_frames']+=1
        result['joint_target_positive_frames' if present else 'joint_target_negative_frames']+=1
    result['objects']={str(o):dict(c) for o,c in stats.items()};return result

def estimate(index,names):
    entries=[index[n] for n in sorted(set(names))]
    # Exact compressed payload plus a conservative local-header extra allowance.
    return {'members':len(entries),'compressed_payload_bytes':sum(e['compressed_size'] for e in entries),
            'saved_member_bytes':sum(e['size'] for e in entries),
            'range_body_upper_bound_bytes':sum(e['compressed_size']+30+len(e['path'].encode())+65535 for e in entries)}

def acquisition_blocks(index,archive,scenes):
    blocks=[]
    for scene in scenes:
        prefix=f'{archive}_primesense/{scene:06d}/';own=[e for n,e in index.items() if n.startswith(prefix)]
        start=min(e['header_offset'] for e in own)
        later=[e['header_offset'] for n,e in index.items() if not n.startswith(prefix) and e['header_offset']>start]
        end=min(later) if later else min(base.ARCHIVES[archive]['bytes'],max(e['header_offset']+30+len(e['path'].encode())+e['compressed_size']+65535 for e in own))
        blocks.append({'archive':archive,'prefix':prefix,'start':start,'length':end-start})
    return blocks

def survey(args):
    if args.manifest.exists():raise ValueError('Acquisition manifest already exists; the saved plan is frozen')
    previous=load(args.plan) if args.plan.exists() else None
    root=args.metadata.resolve();root.mkdir(parents=True,exist_ok=True);(root/'.gitignore').write_text('*\n')
    client=base.RangeClient(min(args.max_download_bytes,50_000_000));indexes={};records={}
    for archive in ['train','test']:
        cached=root/(archive+'_zip_index.json')
        indexes[archive]=load(cached) if cached.exists() else base.read_index(client,archive)
        if not cached.exists():dump(cached,indexes[archive])
    test=indexes['test'];train=indexes['train'];scenes={};training={};members={'train':[],'test':[]}
    for scene in DEV_SCENES+HOLD_SCENES:
        assert scene not in EXCLUDED_TINY_SCENES
        prefix=f'test_primesense/{scene:06d}'
        for filename in ['scene_camera.json','scene_gt.json','scene_gt_info.json']:
            path=prefix+'/'+filename;local_member(client,'test',test[path],root,records);members['test'].append(path)
        gt=load(root/prefix/'scene_gt.json');info=load(root/prefix/'scene_gt_info.json');frames=sorted(map(int,gt))
        if len(frames)!=50:raise ValueError('Expected 50 official BOP19 frames per scene')
        scenes[str(scene)]={'split':'development' if scene in DEV_SCENES else 'heldout_scene',
                            'frame_ids':frames,'coverage':summarize_scene(gt,info,OBJECTS)}
        print(f'Surveyed test scene {scene}; body={client.transferred:,}',flush=True)
        for frame in frames:
            members['test'].append(f'{prefix}/rgb/{frame:06d}.png')
            for gt_id,pose in enumerate(gt[str(frame)]):
                # Preserve all-object GT in JSON; target masks support silhouette
                # evaluation without fetching every distractor-instance mask.
                if pose['obj_id'] in OBJECTS:
                    for folder in ['mask','mask_visib']:members['test'].append(f'{prefix}/{folder}/{frame:06d}_{gt_id:06d}.png')
    for obj in OBJECTS:
        prefix=f'train_primesense/{obj:06d}'
        for filename in ['scene_camera.json','scene_gt.json','scene_gt_info.json']:
            path=prefix+'/'+filename;local_member(client,'train',train[path],root,records);members['train'].append(path)
        gt=load(root/prefix/'scene_gt.json')
        if any(len(poses)!=1 or poses[0]['obj_id']!=obj for poses in gt.values()):raise ValueError('Expected isolated-object training GT')
        selected=farthest_rotations(gt,args.training_views)
        training[str(obj)]={'object_group':'development' if obj in OBJECT_DEVELOPMENT else 'heldout_object',
                            'available_real_views':len(gt),'image_ids':selected}
        print(f'Selected {len(selected)} training rotations for object {obj}; body={client.transferred:,}',flush=True)
        for frame in selected:
            for relative in [f'rgb/{frame:06d}.png',f'mask/{frame:06d}_000000.png',f'mask_visib/{frame:06d}_000000.png']:
                members['train'].append(prefix+'/'+relative)
    estimates={a:estimate(indexes[a],members[a]) for a in members}
    blocks=acquisition_blocks(train,'train',OBJECTS)+acquisition_blocks(test,'test',DEV_SCENES+HOLD_SCENES)
    total_saved=sum(v['saved_member_bytes'] for v in estimates.values())
    # Common ZIPs use no local extras. The strict fetch budget remains the final
    # guard; report exact payload and conservative header bounds separately.
    plan={'schema_version':1,'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
          'dataset':'T-LESS expanded real Primesense, metadata-fixed selection','sources':base.SOURCES,'license':base.LICENSE,
          'revision':base.REVISION,'archives':base.ARCHIVES,'objects':OBJECTS,'development_objects':OBJECT_DEVELOPMENT,
          'strict_object_generalization':OBJECT_GENERALIZATION,'excluded_existing_tiny_scenes':EXCLUDED_TINY_SCENES,
          'selection_policy':'All 50 official BOP19 frames in each of 16 scenes, excluding every tiny-slice scene. No matcher results or image ease criteria. Initial numeric split was balanced using GT only: scene11 moved development to heldout and scene13 moved heldout to development because objects5/8 otherwise had no heldout positives. Final split fixed before fetching RGB or matching.',
          'object_policy':'Eight predeclared object IDs spanning the ID range, including object-1 anchor and object-2; other 22 object IDs remain annotated distractors. Morphological diversity is a hypothesis to inspect from training data, not an asserted ID-to-shape mapping.',
          'training_selection':'72 (or explicit --training-views) deterministic greedy farthest rotations over all available real training poses; Frobenius rotation distance, first=min ID, ties=min ID. Covers full rotation set instead of one regular frame-ID slice. 3D poses select views only; not 2D angle ground truth.',
          'evaluation_protocol':'Development uses development objects in development scenes. Freeze all algorithm/policy choices before heldout_scene or heldout_object matching. Build heldout-object templates with the same frozen recipe; object-generalization tests include all 800 frames and remain a separate report. Do not tune per heldout object.',
          'scenes':scenes,'training':training,'members':members,'estimates':estimates,'acquisition_blocks':blocks,
          'summary':{'test_images':800,'development_scene_images':400,'heldout_scene_images':400,'training_images':sum(len(v['image_ids']) for v in training.values()),
                     'disk_bytes_original_members':total_saved,'free_disk_bytes':shutil.disk_usage(args.output.resolve().parent).free,
                     'download_body_limit_bytes':BODY_LIMIT,'planned_block_body_bytes':sum(b['length'] for b in blocks)},
          'metadata_survey':{'response_body_bytes':client.transferred+(previous['metadata_survey']['response_body_bytes'] if previous else 0),
                            'requests':(previous['metadata_survey']['requests'] if previous else [])+client.requests,'members':list(records.values())},
          'metadata_index_sha256':{a:digest((root/(a+'_zip_index.json')).read_bytes()) for a in indexes},
          'metadata_root':str(root),'dataset_root':str(args.output.resolve())}
    dump(args.plan,plan)
    print(json.dumps({'plan':str(args.plan),'summary':plan['summary'],'estimates':estimates},indent=2),flush=True)

def fetch(args):
    plan=load(args.plan)
    if plan['revision']!=base.REVISION or plan['excluded_existing_tiny_scenes']!=EXCLUDED_TINY_SCENES:raise ValueError('Unexpected plan provenance')
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True);(root/'.gitignore').write_text('*\n')
    meta=Path(plan['metadata_root']);records={}
    manifest=args.manifest
    ledger_path=root/'download_ledger.json';ledger=load(ledger_path) if ledger_path.exists() else {'response_body_bytes':0,'requests':[]}
    budget=min(args.max_download_bytes,BODY_LIMIT)-plan['metadata_survey']['response_body_bytes']-ledger['response_body_bytes']
    if budget<0:raise ValueError('Cumulative metadata/acquisition body budget exhausted')
    client=base.RangeClient(budget)
    indexes={a:load(meta/(a+'_zip_index.json')) for a in ['train','test']}
    for a in indexes:
        if digest((meta/(a+'_zip_index.json')).read_bytes())!=plan['metadata_index_sha256'][a]:raise ValueError('Cached ZIP index hash drift')
    if shutil.disk_usage(root).free<plan['summary']['disk_bytes_original_members']+200_000_000:raise ValueError('Insufficient free disk reserve')
    for block_number,block in enumerate(plan['acquisition_blocks']):
        archive=block['archive'];index=indexes[archive];names=[n for n in plan['members'][archive] if n.startswith(block['prefix'])]
        missing=[]
        for name in names:
            cached=meta/name;target=base.safe_local(root,name)
            if cached.exists() and not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(cached,target)
            if target.exists():local_member(client,archive,index[name],root,records)
            else:missing.append(name)
        if missing:
            print(f'Block {block_number+1}/{len(plan["acquisition_blocks"])} {block["prefix"]}: {block["length"]:,} range bytes, retaining {len(missing)} requested members only',flush=True)
            data=client.get(archive,block['start'],block['length'])
            # Persist response accounting before processing. Depth and other
            # unused members exist only in this temporary in-memory block.
            dump(ledger_path,{'response_body_bytes':ledger['response_body_bytes']+client.transferred,
                              'requests':ledger['requests']+client.requests})
            for name in missing:
                entry=index[name];payload=base.member_from_block(entry,data,block['start']);target=base.safe_local(root,name)
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
                local_member(client,archive,entry,root,records)
            del data
        dump(manifest,{'status':'acquiring','plan_sha256':digest(args.plan.read_bytes()),'files':list(records.values()),
                       'download_response_body_bytes':plan['metadata_survey']['response_body_bytes']+ledger['response_body_bytes']+client.transferred})
    index={'schema_version':2,'dataset':'T-LESS expanded real fixed slice','plan_sha256':digest(args.plan.read_bytes()),
           'root':'.','objects':plan['objects'],'development_objects':plan['development_objects'],
           'target_object_ids':plan['objects'],'development_target_object_ids':plan['development_objects'],
           'strict_object_generalization':plan['strict_object_generalization'],
           'class_id_format':'tless_object_<decimal-object-id>',
           'bbox_format':'[x,y,width,height], original RGB pixels, top-left origin; no image resize',
           'pose_warning':'Official R/t stay in original JSON; no 2D angle/scale ground truth inferred',
           'training':[],'test':[]}
    selections=[('train',int(o),row['image_ids'],row['object_group']) for o,row in plan['training'].items()]
    selections += [('test',int(s),row['frame_ids'],row['split']) for s,row in plan['scenes'].items()]
    for archive,scene,frames,split in selections:
        prefix=f'{"train_primesense" if archive=="train" else "test_primesense"}/{scene:06d}'
        gt=load(root/prefix/'scene_gt.json');info=load(root/prefix/'scene_gt_info.json')
        for frame in frames:
            rgb=f'{prefix}/rgb/{frame:06d}.png';width,height=base.png_dimensions(root/rgb);instances=[]
            for gt_id,(pose,item) in enumerate(zip(gt[str(frame)],info[str(frame)])):
                obj=pose['obj_id']
                group='development' if obj in plan['development_objects'] else 'heldout_object' if obj in plan['strict_object_generalization'] else 'distractor'
                row={'gt_id':gt_id,'obj_id':obj,'class_id':f'tless_object_{obj}','object_group':group,
                     'bbox_obj':item['bbox_obj'],'bbox_visib':item['bbox_visib'],'visib_fract':item['visib_fract']}
                for folder in ['mask','mask_visib']:
                    name=f'{prefix}/{folder}/{frame:06d}_{gt_id:06d}.png';row[folder]=name if (root/name).exists() else None
                instances.append(row)
            row={'split':split,'scene_id':scene,'image_id':frame,'rgb':rgb,'width':width,'height':height,'instances':instances}
            if archive=='train':row.update({'target_obj_id':scene,'class_id':f'tless_object_{scene}',
                                            'mask':instances[0]['mask'],'mask_visib':instances[0]['mask_visib'],'object_group':split})
            index['training' if archive=='train' else 'test'].append(row)
    dump(root/'index.json',index)
    dump(manifest,{'schema_version':1,'plan_sha256':digest(args.plan.read_bytes()),'revision':base.REVISION,'sources':base.SOURCES,'license':base.LICENSE,
                   'status':'complete','archives':{a:{**v,'whole_archive_sha256_verified':False} for a,v in base.ARCHIVES.items()},
                   'files':sorted(records.values(),key=lambda r:r['local_path']),'download':{
                       'response_body_bytes':plan['metadata_survey']['response_body_bytes']+ledger['response_body_bytes']+client.transferred,
                       'metadata_response_body_bytes':plan['metadata_survey']['response_body_bytes'],
                       'acquisition_response_body_bytes':ledger['response_body_bytes']+client.transferred,
                       'body_limit_bytes':min(args.max_download_bytes,BODY_LIMIT),'requests':ledger['requests']+client.requests,
                       'whole_archives_downloaded':False,'depth_saved':False},
                   'summary':{'training_images':len(index['training']),'test_images':len(index['test']),'member_bytes':sum(r['bytes'] for r in records.values())}})
    (root/'LICENSE-SOURCE.txt').write_text(base.LICENSE['attribution']+'\n'+base.LICENSE['url']+'\nSelected subset; original members unchanged; index.json derived.\n',encoding='utf-8')
    print(f'Fetched and CRC/SHA recorded {len(records)} members; {client.transferred:,} response bytes',flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fetch',action='store_true');p.add_argument('--output',type=Path,default=Path('datasets/tless_expanded'))
    p.add_argument('--metadata',type=Path,default=Path('datasets/tless_expanded_metadata'))
    p.add_argument('--plan',type=Path,default=Path('artifacts/public_datasets/tless_expanded_plan.json'))
    p.add_argument('--manifest',type=Path,default=Path('artifacts/public_datasets/tless_expanded_manifest.json'))
    p.add_argument('--training-views',type=int,default=72);p.add_argument('--max-download-bytes',type=int,default=BODY_LIMIT)
    args=p.parse_args()
    if args.training_views<1:raise ValueError('Need positive training view count')
    if args.fetch:fetch(args)
    else:survey(args)

if __name__=='__main__':main()
