"""Literal fixtures for independently replayed full-bank numeric observations."""
import hashlib
import math
import struct
import unittest

import independent_numeric as n


def pack_map(rows, dtype='u8'):
    encoded=[]; data=bytearray()
    for row in rows:
        runs=[]
        for value in row:
            data.extend(bytes([value]) if dtype=='u8' else struct.pack('<I',value))
            if runs and runs[-1][0]==value:runs[-1][1]+=1
            else:runs.append([value,1])
        encoded.append(runs)
    return dict(width=len(rows[0]),height=len(rows),dtype=dtype,rows=encoded,
                sha256=hashlib.sha256(data).hexdigest())


class NumericTests(unittest.TestCase):
    def test_full_map_rle_and_exact_bits(self):
        q=n.read_map(pack_map([[0,0,255],[255,0,255]]))
        self.assertEqual(q, [[(0,2,0),(2,3,255)],[(0,1,255),(1,2,0),(2,3,255)]])
        a=n.read_map(pack_map([[0,0x3f000000,0x3f800000]],'f32bits'))
        self.assertEqual(a[0][1],(1,2,0x3f000000))

    def test_rle_wrong_width_hash_noncanonical_rejected(self):
        for alter in ('width','hash','adjacent','count','dtype','alpha'):
            q=pack_map([[0,255]], 'f32bits' if alter=='alpha' else 'u8')
            if alter=='width':q['width']=3
            elif alter=='hash':q['sha256']='0'*64
            elif alter=='adjacent':q['rows']=[[[0,1],[0,1]]]
            elif alter=='count':q['rows'][0][0][1]=0
            elif alter=='dtype':q['dtype']='float16'
            elif alter=='alpha':q['rows'][0][1][0]=0x7fc00000
            with self.subTest(alter=alter),self.assertRaises(ValueError):n.read_map(q)

    def test_signed_chebyshev_and_zero_exterior(self):
        rows=n.read_map(pack_map([[0,0,0,0,0],[0,255,255,255,0],[0,255,255,255,0],[0,255,255,255,0],[0,0,0,0,0]]))
        self.assertEqual(n.signed_distance(rows,2,2,lambda v:v!=0),2)
        self.assertEqual(n.signed_distance(rows,1,1,lambda v:v!=0),1)
        self.assertEqual(n.signed_distance(rows,0,0,lambda v:v!=0),-1)
        full=n.read_map(pack_map([[255]*3 for _ in range(3)]))
        self.assertEqual(n.signed_distance(full,1,1,lambda v:v!=0),2)

    def test_signed_distance_hole_and_far_exterior(self):
        rows=n.read_map(pack_map([[255,255,255],[255,0,255],[255,255,255]]))
        self.assertEqual(n.signed_distance(rows,1,1,lambda v:v!=0),-1)
        rows=n.read_map(pack_map([[255,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]))
        self.assertEqual(n.signed_distance(rows,4,2,lambda v:v!=0),-4)

    def test_absolute_coordinates_own_layer_origin_and_flags(self):
        mask=n.read_map(pack_map([[0,0,0,0,0],[0,255,255,255,0],[0,255,255,255,0],[0,255,255,255,0],[0,0,0,0,0]]))
        alpha=n.read_map(pack_map([[0x3f800000]*5 for _ in range(5)],'f32bits'))
        maps={'M':mask,'A':alpha,'B':mask}
        q=n.feature_observation(maps,{'tl_x':1,'tl_y':2},(1,0,7),(1,1,3,3))
        self.assertEqual((q['absolute_x'],q['absolute_y'],q['label']),(2,2,7))
        self.assertEqual((q['official_value'],q['eroded_value'],q['mask_signed_distance']),(255,255,2))
        self.assertEqual(q['alpha_bits'],0x3f800000)
        self.assertEqual(q['canvas_edge'],2)
        self.assertEqual(q['cell'],5)
        self.assertEqual((q['mask_cross4'],q['canvas_cross4']),(1,1))

    def test_invalid_feature_label_coordinate_or_empty_shape_rejected(self):
        maps={'M':n.read_map(pack_map([[255]])),'B':n.read_map(pack_map([[255]])),
              'A':n.read_map(pack_map([[0x3f800000]],'f32bits'))}
        for feature,bbox in [((1,0,0),(0,0,1,1)),((0,0,8),(0,0,1,1)),((0,0,0),(0,0,0,1))]:
            with self.subTest(feature=feature,bbox=bbox),self.assertRaises(ValueError):
                n.feature_observation(maps,{'tl_x':0,'tl_y':0},feature,bbox)

    def test_r4_r5_r6_crossings_include_neighbor_comparison_support(self):
        mask=n.read_map(pack_map([[255 if 3<=x<=13 and 3<=y<=13 else 0 for x in range(17)] for y in range(17)]))
        alpha=n.read_map(pack_map([[0x3f800000 if 3<=x<=13 and 3<=y<=13 else 0 for x in range(17)] for y in range(17)],'f32bits'))
        maps={'M':mask,'B':mask,'A':alpha}
        # Distance five: r4 center processing stays inside; r5 hysteresis and
        # r6 NMS comparison support can reach the opposite region.
        q=n.feature_observation(maps,{'tl_x':0,'tl_y':0},(7,8,0),(3,3,11,11))
        self.assertEqual(q['mask_signed_distance'],5)
        for axis in ('mask','crop'):
            self.assertEqual([q[axis+'_cross'+str(r)] for r in (4,5,6)],[0,1,1])
        # Distance six separates hysteresis support from NMS comparison support.
        q=n.feature_observation(maps,{'tl_x':0,'tl_y':0},(8,8,0),(3,3,11,11))
        self.assertEqual(q['mask_signed_distance'],6)
        self.assertEqual([q['mask_cross'+str(r)] for r in (4,5,6)],[0,0,1])

    def test_canvas_support_and_replicated_erosion_boundaries(self):
        mask=n.read_map(pack_map([[255]*17 for _ in range(17)]))
        alpha=n.read_map(pack_map([[0x3f800000]*17 for _ in range(17)],'f32bits'))
        maps={'M':mask,'B':mask,'A':alpha}
        q=n.feature_observation(maps,{'tl_x':0,'tl_y':0},(4,8,0),(0,0,17,17))
        self.assertEqual([q['canvas_cross'+str(r)] for r in (4,5,6)],[0,1,1])
        edge=n.feature_observation(maps,{'tl_x':0,'tl_y':0},(0,0,0),(0,0,17,17))
        self.assertEqual(edge['eroded_value'],255)
        self.assertEqual(edge['mask_signed_distance'],1)

    def test_actual_budget_targets_not_limits_and_all_orientation_bins(self):
        a={'label':0,'cell':16,'official_value':0,'eroded_value':0,'alpha_bits':0,'binary_value':0,
           'mask_signed_distance':-1,'crop_signed_distance':-1,'canvas_edge':9}
        for r in (4,5,6):
            for axis in ('mask','crop','canvas'):a[axis+'_cross'+str(r)]=int(axis!='canvas')
        b=dict(a,label=7,official_value=255,eroded_value=255,alpha_bits=0x3f800000,binary_value=255)
        q=n.descriptor_summary([a,b,b],2)
        self.assertEqual(q['actual_features'],3)
        self.assertEqual(q['target_surplus'],1)
        self.assertEqual(q['label_counts'],[1,0,0,0,0,0,0,2])
        self.assertAlmostEqual(q['entropy_bits'],-(math.log2(1/3)/3+2*math.log2(2/3)/3))

    def test_complete_usage_includes_unused_and_negative_tp_fp_same_template(self):
        templates={('rgb',1,0),('rgb',1,1)}
        events=[dict(family='rgb',object_id=1,template_id=0,scene=1,image=0,allGT_label='TP',eligible_label='TP',negative=False),
                dict(family='rgb',object_id=1,template_id=0,scene=1,image=1,allGT_label='FP',eligible_label='FP',negative=True)]
        q=n.complete_usage(templates,events,{('rgb',1,0):4}, {('rgb',1,1,0),('rgb',1,1,1)})
        self.assertEqual(q[('rgb',1,0)]['allGT_tp'],1)
        self.assertEqual(q[('rgb',1,0)]['negative_selected'],1)
        self.assertEqual(q[('rgb',1,1)]['raw'],0)
        self.assertEqual(q[('rgb',1,0)]['distinct_selected_frames'],2)

    def test_unknown_usage_template_or_frame_rejected(self):
        e=dict(family='rgb',object_id=1,template_id=1,scene=1,image=0,allGT_label='FP',eligible_label='FP',negative=True)
        with self.assertRaises(ValueError):n.complete_usage({('rgb',1,0)},[e],{}, {('rgb',1,1,0)})
        e['template_id']=0
        with self.assertRaises(ValueError):n.complete_usage({('rgb',1,0)},[e],{}, {('rgb',1,1,2)})


if __name__=='__main__':unittest.main()
