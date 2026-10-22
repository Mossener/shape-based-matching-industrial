import unittest
import audit_numeric as a
import independent_numeric as n
from test_numeric import pack_map


class QualityLiteralTests(unittest.TestCase):
    def test_nearest_half_is_not_grayscale_pyrdown(self):
        full=[[255 if x<3 else 0 for x in range(16)] for _ in range(16)]
        half=[[255 if x<2 else 0 for x in range(8)] for _ in range(8)]
        a.validate_nearest_pyramid(n.read_map(pack_map(full)),n.read_map(pack_map(half)))
        half[0][1]=191
        with self.assertRaises(ValueError):a.validate_nearest_pyramid(n.read_map(pack_map(full)),n.read_map(pack_map(half)))
    def test_nms_boundary_is_strict_point_three(self):
        self.assertAlmostEqual(a.overlap((0,0,13,1),(7,0,13,1)),.3)

    def test_gt_boundary_half_and_tie_choose_lowest_id(self):
        d=[{'box':(0,0,2,1)}]
        gt=[{'id':4,'visibility':1.,'box':(0,0,1,1)},{'id':2,'visibility':1.,'box':(0,0,1,1)}]
        self.assertEqual(a.assign(d,gt,False),[['TP',2]])

    def test_eligible_targets_before_low_visibility_ignore(self):
        d=[{'box':(0,0,2,2)},{'box':(0,0,2,2)}]
        gt=[{'id':0,'visibility':.2,'box':(0,0,2,2)},{'id':1,'visibility':.5,'box':(0,0,2,2)}]
        self.assertEqual(a.assign(d,gt,True),[['TP',1],['IGNORE',0]])

    def test_raw_pose_score_and_box_are_bound(self):
        meta={0:dict(class_id='tless_object_1',training_image_id=6,angle=30.,scale=1.,tl_x=2,tl_y=4,warped_mask_bbox=[3,5,8,9])}
        row=dict(template_id='0',score='85',match_x='65',match_y='64',bbox_x='2',bbox_y='1',bbox_w='8',bbox_h='9',class_id='tless_object_1',training_image='6',angle='30',scale='1')
        self.assertEqual(a.raw_record(row,meta)['box'],(2.,1.,8.,9.))
        for key,value in [('angle','60'),('bbox_x','3'),('score','nan'),('template_id','1'),('score','85.1')]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):a.raw_record(dict(row,**{key:value}),meta)


if __name__=='__main__':unittest.main()
