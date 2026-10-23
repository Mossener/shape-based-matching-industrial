"""Literal projection contracts; no real data or filesystem access.

Every rejection test removes a specific validation from the intended binder.
The positive fixture is hand-calculated; expected values do not call numeric
helpers or the binder. Comparison arms have complete zero-detection rows.
"""
from copy import deepcopy
import unittest

from c0_numeric_binding_v1 import bind_projection


def fixture():
    gt = [
        dict(object_id='1', scene='1', image='1', gt_id='7', class_id='tless_object_1',
             visibility='0.5', bbox_x='0', bbox_y='0', bbox_w='10', bbox_h='10'),
        dict(object_id='1', scene='1', image='1', gt_id='8', class_id='tless_object_1',
             visibility='0.25', bbox_x='20', bbox_y='0', bbox_w='10', bbox_h='10'),
        dict(object_id='2', scene='1', image='2', gt_id='9', class_id='tless_object_2',
             visibility='1', bbox_x='40', bbox_y='0', bbox_w='10', bbox_h='10'),
    ]
    # Literal values: raw, selected, TP, FP, FN, GT, eligible TP/FP/FN/GT,
    # ignored, all IoU sum, eligible IoU sum, negative FP.
    values = {
        (1, 1): ('4','3','2','1','0','2','1','1','0','1','1','2','1','0'),
        (1, 2): ('0','0','0','0','0','0','0','0','0','0','0','0','0','0'),
        (2, 1): ('1','1','0','1','0','0','0','1','0','0','0','0','0','1'),
        (2, 2): ('0','0','0','0','1','1','0','0','1','1','0','0','0','0'),
    }
    empty_values = {
        (1, 1): ('0','0','0','0','2','2','0','0','1','1','0','0','0','0'),
        (1, 2): ('0','0','0','0','0','0','0','0','0','0','0','0','0','0'),
        (2, 1): ('0','0','0','0','0','0','0','0','0','0','0','0','0','0'),
        (2, 2): ('0','0','0','0','1','1','0','0','1','1','0','0','0','0'),
    }
    fields = ('raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,eligible_gt,'
              'ignored,all_iou_sum,eligible_iou_sum,negative_fp').split(',')
    per = []
    for arm in ('rgb_control', 'rgb_pooled_features', 'rgb_stratified_features'):
        for obj, image in ((1,1),(1,2),(2,1),(2,2)):
            row = dict(object_id=str(obj), scene='1', image=str(image), arm=arm)
            row.update(zip(fields, (values if arm == 'rgb_control' else empty_values)[obj,image]))
            per.append(row)
    selected = [
        dict(object_id='1', scene='1', image='1', arm='rgb_control', rank='0', class_id='tless_object_1',
             score='95', score_bits='1119748096', template_id='0', training_image='6', angle='0', scale='1',
             match_x='64', match_y='64', bbox_x='0', bbox_y='0', bbox_w='10', bbox_h='10',
             allGT_label='TP', allGT_id='7', eligible_label='TP', eligible_id='7'),
        dict(object_id='1', scene='1', image='1', arm='rgb_control', rank='1', class_id='tless_object_1',
             score='90', score_bits='1119092736', template_id='1', training_image='12', angle='90', scale='1',
             match_x='84', match_y='64', bbox_x='20', bbox_y='0', bbox_w='10', bbox_h='10',
             allGT_label='TP', allGT_id='8', eligible_label='IGNORE', eligible_id='8'),
        dict(object_id='1', scene='1', image='1', arm='rgb_control', rank='2', class_id='tless_object_1',
             score='85', score_bits='1118437376', template_id='2', training_image='18', angle='180', scale='1',
             match_x='164', match_y='64', bbox_x='100', bbox_y='0', bbox_w='10', bbox_h='10',
             allGT_label='FP', allGT_id='-1', eligible_label='FP', eligible_id='-1'),
        dict(object_id='2', scene='1', image='1', arm='rgb_control', rank='0', class_id='tless_object_2',
             score='90', score_bits='1119092736', template_id='0', training_image='0', angle='0', scale='1',
             match_x='64', match_y='64', bbox_x='0', bbox_y='0', bbox_w='10', bbox_h='10',
             allGT_label='FP', allGT_id='-1', eligible_label='FP', eligible_id='-1'),
    ]
    return dict(objects=(1,2), frames=((1,1),(1,2)), gt_rows=gt, per_rows=per, selected_rows=selected)


class ProjectionTests(unittest.TestCase):
    def rejected(self, data):
        with self.assertRaises(ValueError):
            bind_projection(**data)

    def test_complete_literal_projection_preserves_zeros_negatives_and_ids(self):
        result = bind_projection(**fixture())
        keys = {(1,1,1),(1,1,2),(2,1,1),(2,1,2)}
        for field in ('truth','per','selected','all_labels','eligible_labels'):
            self.assertEqual(set(result[field]), keys)
        self.assertEqual(result['truth'][(1,1,1)], [
            dict(gt_id=7, class_id='tless_object_1', obj_id=1, bbox_obj=(0.,0.,10.,10.), visib_fract=.5),
            dict(gt_id=8, class_id='tless_object_1', obj_id=1, bbox_obj=(20.,0.,10.,10.), visib_fract=.25)])
        self.assertEqual(result['truth'][(1,1,2)], [])
        self.assertEqual(result['truth'][(2,1,1)], [])
        self.assertEqual(result['truth'][(2,1,2)], [
            dict(gt_id=9, class_id='tless_object_2', obj_id=2, bbox_obj=(40.,0.,10.,10.), visib_fract=1.)])
        self.assertEqual(result['selected'][(1,1,1)], [
            ('tless_object_1',0,64,64,1119748096,(0.,0.,10.,10.),(6,0,1065353216)),
            ('tless_object_1',1,84,64,1119092736,(20.,0.,10.,10.),(12,1119092736,1065353216)),
            ('tless_object_1',2,164,64,1118437376,(100.,0.,10.,10.),(18,1127481344,1065353216))])
        self.assertEqual(result['selected'][(1,1,2)], [])
        self.assertEqual(result['selected'][(2,1,2)], [])
        self.assertEqual(result['selected'][(2,1,1)], [
            ('tless_object_2',0,64,64,1119092736,(0.,0.,10.,10.),(0,0,1065353216))])
        self.assertEqual(result['all_labels'][(1,1,1)], [('TP',7),('TP',8),('FP',-1)])
        self.assertEqual(result['eligible_labels'][(1,1,1)], [('TP',7),('IGNORE',8),('FP',-1)])
        self.assertEqual(result['per'][(1,1,1)], dict(raw=4,selected=3,tp=2,fp=1,fn=0,gt=2,
            eligible_tp=1,eligible_fp=1,eligible_fn=0,eligible_gt=1,ignored=1,
            all_iou_sum=2.,eligible_iou_sum=1.,negative_fp=0))
        self.assertEqual(result['per'][(1,1,2)], dict(raw=0,selected=0,tp=0,fp=0,fn=0,gt=0,
            eligible_tp=0,eligible_fp=0,eligible_fn=0,eligible_gt=0,ignored=0,
            all_iou_sum=0.,eligible_iou_sum=0.,negative_fp=0))
        self.assertEqual(result['per'][(2,1,1)]['negative_fp'], 1)
        self.assertEqual(result['per'][(2,1,2)]['fn'], 1)
        self.assertEqual(result['retained_gt_ids'], ((1,1,1,7),(1,1,1,8)))
        self.assertEqual(result['eligible_retained_gt_ids'], ((1,1,1,7),))
        self.assertIs(result['gt_projection_independently_reconstructed'], False)

    def test_missing_zero_per_combination(self):
        d=fixture(); del d['per_rows'][1]; self.rejected(d)

    def test_extra_unknown_object(self):
        d=fixture(); d['per_rows'][0]['object_id']='17'; self.rejected(d)

    def test_unknown_frame(self):
        d=fixture(); d['selected_rows'][0]['image']='3'; self.rejected(d)

    def test_unknown_arm(self):
        d=fixture(); d['per_rows'][0]['arm']='C0'; self.rejected(d)

    def test_duplicate_gt(self):
        d=fixture(); d['gt_rows'].append(deepcopy(d['gt_rows'][0])); self.rejected(d)

    def test_gt_identity_reused_across_objects(self):
        d=fixture(); d['gt_rows'][2].update(image='1',gt_id='7'); self.rejected(d)

    def test_duplicate_per(self):
        d=fixture(); d['per_rows'].append(deepcopy(d['per_rows'][0])); self.rejected(d)

    def test_duplicate_rank(self):
        d=fixture(); d['selected_rows'][1]['rank']='0'; self.rejected(d)

    def test_gapped_rank(self):
        d=fixture(); d['selected_rows'][2]['rank']='3'; self.rejected(d)

    def test_out_of_order_rank(self):
        d=fixture(); d['selected_rows'][0],d['selected_rows'][1]=d['selected_rows'][1],d['selected_rows'][0]; self.rejected(d)

    def test_wrong_gt_class(self):
        d=fixture(); d['gt_rows'][0]['class_id']='tless_object_2'; self.rejected(d)

    def test_wrong_selected_class(self):
        d=fixture(); d['selected_rows'][0]['class_id']='tless_object_2'; self.rejected(d)

    def test_nonfinite_gt_box(self):
        for value in ('nan','inf','-inf'):
            with self.subTest(value=value):
                d=fixture(); d['gt_rows'][0]['bbox_x']=value; self.rejected(d)

    def test_nonpositive_gt_extents(self):
        for value in ('0','-1'):
            with self.subTest(value=value):
                d=fixture(); d['gt_rows'][0]['bbox_w']=value; self.rejected(d)

    def test_visibility_out_of_range(self):
        for value in ('nan','-0.1','1.1'):
            with self.subTest(value=value):
                d=fixture(); d['gt_rows'][0]['visibility']=value; self.rejected(d)

    def test_nonfinite_selected_box(self):
        d=fixture(); d['selected_rows'][0]['bbox_y']='nan'; self.rejected(d)

    def test_nonpositive_selected_extents(self):
        d=fixture(); d['selected_rows'][0]['bbox_h']='0'; self.rejected(d)

    def test_score_bits_decimal_mismatch(self):
        d=fixture(); d['selected_rows'][0]['score_bits']='1119092736'; self.rejected(d)

    def test_bad_gt_label_reference(self):
        d=fixture(); d['selected_rows'][0]['allGT_id']='99'; self.rejected(d)

    def test_nonfinite_metric(self):
        d=fixture(); d['per_rows'][0]['all_iou_sum']='inf'; self.rejected(d)

    def test_counts_conservation(self):
        d=fixture(); d['per_rows'][0]['fp']='2'; self.rejected(d)

    def test_selected_count_vs_rows(self):
        d=fixture(); d['per_rows'][0]['raw']='5'; d['per_rows'][0]['selected']='4'; self.rejected(d)

    def test_eligible_ignore_visibility(self):
        d=fixture(); d['selected_rows'][0].update(eligible_label='IGNORE',eligible_id='7'); self.rejected(d)

    def test_missing_schema_field(self):
        d=fixture(); del d['gt_rows'][0]['class_id']; self.rejected(d)

    def test_extra_schema_field(self):
        d=fixture(); d['selected_rows'][0]['variant']='fallback'; self.rejected(d)

    def test_missing_or_duplicate_schedule_identity(self):
        for objects,frames in (((1,1),((1,1),(1,2))),((1,2),((1,1),(1,1))),((1,2),())):
            with self.subTest(objects=objects,frames=frames):
                d=fixture(); d.update(objects=objects,frames=frames); self.rejected(d)

    def test_bool_integer_refused(self):
        d=fixture(); d['gt_rows'][0]['gt_id']=True; self.rejected(d)


if __name__ == '__main__':
    unittest.main()
