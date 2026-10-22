"""Own small fixtures. No probe/evaluator implementation imports."""
import copy
import csv
import gzip
import io
import json
import math
import struct
import unittest

import numeric as n

HEADER = 'scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h'.split(',')

def row(template=0, x=65, y=65, score=90., box=(0.,0.,10.,10.)):
    return ('tless_object_1',template,x,y,struct.pack('<f',score),box,(10+template,struct.pack('<f',0.),struct.pack('<f',1.)))

def metadata():
    return {0:dict(class_id='tless_object_1',template_id=0,training_image_id=10,angle=0.,scale=1.,tl_x=1,tl_y=1,warped_mask_bbox=[0.,0.,10.,10.]),1:dict(class_id='tless_object_1',template_id=1,training_image_id=11,angle=0.,scale=1.,tl_x=1,tl_y=1,warped_mask_bbox=[20.,20.,10.,10.])}

def archive(rows, variant='pre'):
    stream=io.StringIO(newline=''); writer=csv.writer(stream,lineterminator='\n'); writer.writerow(HEADER)
    for rank,r in enumerate(rows):
        cls,t,x,y,bits,box,pose=r
        writer.writerow([1,2,variant,cls,rank,format(struct.unpack('<f',bits)[0],'.17g'),t,pose[0],struct.unpack('<f',pose[1])[0],struct.unpack('<f',pose[2])[0],x,y,*box])
    raw=stream.getvalue().encode(); encoded=gzip.compress(raw,mtime=0)
    manifest=dict(scene_id=1,image_id=2,rgb='test_primesense/000001/rgb/000002.png',variant=variant,class_id='tless_object_1',class_ids=['tless_object_1'],raw_candidate_count=len(rows),format='gzip CSV; all candidates retained, 17 significant score digits',path='C:/synthetic/pre_raw.csv.gz',compressed_bytes=len(encoded),uncompressed_bytes=len(raw),zlib_version='synthetic')
    return encoded,manifest

class NumericTests(unittest.TestCase):
    def test_minimum_id_complete_record_and_duplicate_multiplicity(self):
        a=row(1,box=(20.,20.,10.,10.)); b=row(0)
        self.assertEqual(n.consolidate([a,a,b,b]),[b])
        d=n.diagnostics([a,a,b,b],[b],[dict(gt_id=3,bbox=[20.,20.,10.,10.])])
        self.assertEqual(d['per'],dict(pre=4,post=1,pre_unique_templates_in_collision_groups=2,cross_template_groups=1,same_template_duplicate_occurrences=2,zero_score_matches=0,fine_oracle_rows=4,exact_saved_raw=1))
        self.assertEqual(d['support'],[dict(gt_id=3,pre_hits=2,post_hits=0,pre_best_iou=1.,post_best_iou=0.,candidate_support_lost_at_consolidation=1)])
        self.assertEqual(d['representatives'][0]['discarded_occurrences'],2)
        self.assertEqual(d['representatives'][0]['discarded_x'],20.)

    def test_template_is_excluded_but_score_position_class_are_keys(self):
        a=row(0); b=row(1,box=(20.,20.,10.,10.)); self.assertEqual(n.group_key(a),n.group_key(b))
        for other in [row(x=69),row(y=69),row(score=91.),('other',*a[1:])]:
            self.assertNotEqual(n.group_key(a),n.group_key(other))

    def test_final_v11_then_adapter_canonical_order(self):
        a=row(0,y=69); b=('tless_object_2',1,65,65,struct.pack('<f',90.),(0.,0.,10.,10.),(11,struct.pack('<f',0.),struct.pack('<f',1.)))
        self.assertEqual(n.consolidate([b,a]),[a,b])
        self.assertEqual(sorted([b,a],key=n.canonical),[a,b])

    def test_zero_float_equality_normalized_and_ambiguous_min_id_rejected(self):
        p=row(score=0.); m=row(1,score=-0.)
        self.assertEqual(n.group_key(p),n.group_key(m)); self.assertEqual(n.consolidate([m,p]),[p])
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            n.consolidate([p,row(score=-0.)])

    def test_nan_and_infinity_rejected_before_grouping(self):
        for value in [float('nan'),float('inf'),-float('inf'),1e100]:
            with self.assertRaises(ValueError): n.fbits(value)
        with self.assertRaises(ValueError): n.consolidate([row(score=float('nan'))])

    def test_raw_exact_bits_metadata_and_manifest(self):
        rows=[row(),row(1,box=(20.,20.,10.,10.))]; data,m=archive(rows)
        self.assertEqual(n.parse_raw(data,m,(1,2),'pre',1,metadata(),'C:/synthetic/pre_raw.csv.gz'),rows)

    def test_raw_pose_box_rank_order_manifest_corruption_rejected(self):
        base=[row(),row(1,box=(20.,20.,10.,10.))]
        for key,value in [('raw_candidate_count',3),('class_ids',['other']),('rgb','test_primesense/000002/rgb/000002.png'),('path','elsewhere')]:
            data,m=archive(base); m[key]=value
            with self.assertRaises(ValueError): n.parse_raw(data,m,(1,2),'pre',1,metadata(),'C:/synthetic/pre_raw.csv.gz')
        for bad in [[row(box=(1.,0.,10.,10.))],[row(0,score=84.)],[row(0,score=101.)],[row(0,score=float('nan'))],list(reversed(base))]:
            data,m=archive(bad)
            with self.assertRaises(ValueError): n.parse_raw(data,m,(1,2),'pre',1,metadata(),'C:/synthetic/pre_raw.csv.gz')
        bad=list(row()); bad[-1]=(99,struct.pack('<f',0.),struct.pack('<f',1.)); data,m=archive([tuple(bad)])
        with self.assertRaises(ValueError): n.parse_raw(data,m,(1,2),'pre',1,metadata(),'C:/synthetic/pre_raw.csv.gz')

    def test_support_counts_occurrences_and_boundary(self):
        a=row(box=(0.,0.,10.,10.)); d=n.diagnostics([a,a],[a],[dict(gt_id=0,bbox=[0.,0.,20.,10.])])
        self.assertEqual(d['support'][0]['pre_hits'],2); self.assertEqual(d['support'][0]['post_hits'],1)
        self.assertEqual(d['support'][0]['pre_best_iou'],.5)

    def test_altered_post_or_lost_representative_rejected(self):
        a=row(); b=row(1,box=(20.,20.,10.,10.))
        for post in [[b],[],[a,a],[row(score=91.)]]:
            with self.assertRaises(ValueError): n.diagnostics([a,b],post,[])

if __name__=='__main__': unittest.main()
