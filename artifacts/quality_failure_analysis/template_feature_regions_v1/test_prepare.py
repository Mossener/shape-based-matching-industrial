import copy
import unittest
from prepare_inputs import validate_pose_attempts


def fixtures():
    r=dict(object_id=1,class_id='tless_object_1',training_image='0',angle='30',scale='1',success='1',template_id='0',source_crop_x='5',source_crop_y='6',source_crop_w='9',source_crop_h='7',canvas='48',mask_x='15',mask_y='16',mask_w='9',mask_h='7',templ_tl_x='14',templ_tl_y='16',features_l0='7',features_l1='5',error='')
    failed=dict(r,training_image='6',success='0',template_id='-1',features_l0='0',features_l1='0',error='insufficient_features')
    m=dict(class_id='tless_object_1',template_id=0,training_image_id=0,angle=30.,scale=1.,tl_x=14,tl_y=16,warped_mask_bbox=[15.,16.,9.,7.])
    return {'rgb':[r,failed],'binary':[copy.deepcopy(r),copy.deepcopy(failed)]},{'rgb':[m],'binary':[copy.deepcopy(m)]},{(1,0,30,1.),(1,6,30,1.)}


class PoseTests(unittest.TestCase):
    def test_full_pose_product_retains_failure(self):
        a,m,k=fixtures();rows=validate_pose_attempts(a,m,k)
        self.assertEqual(len(rows),4)
        self.assertEqual([q for q in rows if not q['success']][0]['counts'],[-1,-1])
        self.assertEqual(rows[0]['geometry'],[5,6,9,7,48,15,16,9,7])

    def test_missing_failed_pose_and_wrong_geometry_are_rejected(self):
        for fault in ('missing','geometry','pose','id','tl','maskbox'):
            a,m,k=fixtures()
            if fault=='missing':a['binary'].pop()
            elif fault=='geometry':a['binary'][0]['source_crop_x']='7'
            elif fault=='pose':m['binary'][0]['angle']=60.
            elif fault=='id':m['binary'][0]['template_id']=1
            elif fault=='tl':m['binary'][0]['tl_y']=17
            else:m['binary'][0]['warped_mask_bbox'][0]=18.
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_pose_attempts(a,m,k)


if __name__=='__main__':unittest.main()
