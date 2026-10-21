#!/usr/bin/env python3
"""Offline provenance/coverage audit for the expanded fixed T-LESS acquisition."""
from collections import defaultdict
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import zlib

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('expanded_protocol',HERE/'fetch_tless_expanded.py')
protocol=importlib.util.module_from_spec(spec);spec.loader.exec_module(protocol)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def view(pose):
    r,t=pose['cam_R_m2c'],pose['cam_t_m2c']
    v=[-sum(r[3*row+col]*t[row] for row in range(3)) for col in range(3)]
    length=sum(x*x for x in v)**.5
    return [x/length for x in v]
def elevation(v):return math.degrees(math.asin(max(-1,min(1,v[2]))))

def verify(args):
    plan=load(args.plan);manifest=load(args.manifest);root=args.output.resolve();index=load(root/'index.json')
    assert manifest['status']=='complete' and manifest['plan_sha256']==sha(args.plan)==index['plan_sha256']
    assert manifest['download']['response_body_bytes']<=2_000_000_000
    assert not manifest['download']['whole_archives_downloaded'] and not manifest['download']['depth_saved']
    assert sum(r['body_bytes'] for r in manifest['download']['requests'])==manifest['download']['acquisition_response_body_bytes']
    assert sum(r['body_bytes'] for r in plan['metadata_survey']['requests'])==manifest['download']['metadata_response_body_bytes']
    assert manifest['download']['response_body_bytes']==manifest['download']['acquisition_response_body_bytes']+manifest['download']['metadata_response_body_bytes']
    expected=set(plan['members']['train']+plan['members']['test']);actual=set()
    for i,record in enumerate(manifest['files']):
        name=record['local_path'];assert name not in actual;actual.add(name)
        assert '/depth/' not in name
        path=protocol.base.safe_local(root,name);data=path.read_bytes()
        assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256'],name
        assert f'{zlib.crc32(data)&0xffffffff:08x}'==record['archive_crc32'],name
        if i%1000==0:print(f'Verified {i}/{len(manifest["files"])} original members',flush=True)
    assert actual==expected and len(actual)==6100
    assert len(index['training'])==576 and len(index['test'])==800
    assert not list(root.rglob('depth'))
    scene_rows=defaultdict(list);train_rows=defaultdict(list);seen=set()
    for row in index['test']:
        assert row['scene_id'] not in [2,3,5,9]
        key=(row['scene_id'],row['image_id']);assert key not in seen;seen.add(key)
        scene_rows[row['scene_id']].append(row)
        assert row['split']==plan['scenes'][str(row['scene_id'])]['split']
    for row in index['training']:train_rows[row['scene_id']].append(row)
    for row in index['training']+index['test']:
        assert protocol.base.png_dimensions(root/row['rgb'])==(row['width'],row['height'])
        prefix=str(Path(row['rgb']).parent.parent).replace('\\','/')
        gt=load(root/prefix/'scene_gt.json')[str(row['image_id'])]
        info=load(root/prefix/'scene_gt_info.json')[str(row['image_id'])]
        assert len(row['instances'])==len(gt)==len(info)
        for instance,pose,annotation in zip(row['instances'],gt,info):
            assert instance['obj_id']==pose['obj_id']
            for field in ['bbox_obj','bbox_visib','visib_fract']:assert instance[field]==annotation[field]
            for folder in ['mask','mask_visib']:
                if instance[folder]:assert protocol.base.png_dimensions(root/instance[folder])==(row['width'],row['height'])
    for scene,rows in scene_rows.items():
        assert len(rows)==50 and sorted(r['image_id'] for r in rows)==plan['scenes'][str(scene)]['frame_ids']
        prefix=root/f'test_primesense/{scene:06d}'
        reconstructed=protocol.summarize_scene(load(prefix/'scene_gt.json'),load(prefix/'scene_gt_info.json'),plan['objects'])
        assert reconstructed==plan['scenes'][str(scene)]['coverage']
    coverage={};object_split=defaultdict(lambda:defaultdict(lambda:defaultdict(int)))
    for obj,rows in train_rows.items():
        gt=load(root/f'train_primesense/{obj:06d}/scene_gt.json');ids=plan['training'][str(obj)]['image_ids']
        assert len(rows)==72 and sorted(r['image_id'] for r in rows)==ids
        assert ids==protocol.farthest_rotations(gt,72)
        selected=[view(gt[str(i)][0]) for i in ids];allviews=[view(p[0]) for p in gt.values()]
        errors=[math.degrees(math.acos(max(-1,min(1,max(sum(a*b for a,b in zip(v,w)) for w in selected))))) for v in allviews]
        coverage[str(obj)]={'available_real_views':len(gt),'selected_views':len(ids),
                            'selected_model_frame_elevation_deg':[min(map(elevation,selected)),max(map(elevation,selected))],
                            'available_model_frame_elevation_deg':[min(map(elevation,allviews)),max(map(elevation,allviews))],
                            'worst_nearest_selected_view_direction_angle_deg':max(errors)}
    for scene,row in plan['scenes'].items():
        for obj,stats in row['coverage']['objects'].items():
            for field,value in stats.items():object_split[obj][row['split']][field]+=value
    for obj in plan['objects']:
        for split in ['development','heldout_scene']:
            assert object_split[str(obj)][split]['positive_frames']>0
            assert object_split[str(obj)][split]['negative_frames']>0
    audit={'passed':True,'plan_sha256':sha(args.plan),'manifest_sha256':sha(args.manifest),'index_sha256':sha(root/'index.json'),
           'original_members':len(actual),'training_images':576,'test_images':800,
           'development_images':sum(r['split']=='development' for r in index['test']),
           'heldout_scene_images':sum(r['split']=='heldout_scene' for r in index['test']),
           'all_member_crc_sha_size_verified':True,'all_image_mask_dimensions_verified':True,
           'all_gt_instance_bbox_visibility_values_verified':True,'training_farthest_selection_recomputed':True,
           'no_depth_saved':True,'existing_tiny_scenes_excluded':True,'matching_run':False,
           'object_scene_split_coverage':object_split,'training_view_direction_coverage':coverage,
           'download':manifest['download']}
    protocol.dump(args.audit,audit)
    print(json.dumps({k:v for k,v in audit.items() if k not in ['download','object_scene_split_coverage','training_view_direction_coverage']},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('datasets/tless_expanded'))
    p.add_argument('--plan',type=Path,default=Path('artifacts/public_datasets/tless_expanded_plan.json'))
    p.add_argument('--manifest',type=Path,default=Path('artifacts/public_datasets/tless_expanded_manifest.json'))
    p.add_argument('--audit',type=Path,default=Path('artifacts/public_datasets/tless_expanded_audit.json'))
    verify(p.parse_args())
