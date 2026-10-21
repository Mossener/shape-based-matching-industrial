"""Guard against mixing sealed frames or corrupt candidate rows into diagnosis."""
import unittest
from read_inputs import development_frames, parse_raw


HEADER = ('scene,image,variant,class_id,rank,score,template_id,training_image,'
          'angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h\n')
ROW = '1,2,fallback,tless_object_8,0,85,7,1,0,1,64,64,0,0,10,10\n'


class InputContracts(unittest.TestCase):
    def test_sealed_and_training_entries_are_excluded(self):
        index = dict(training=[dict(split='development', scene_id=9, image_id=9)],
                     test=[dict(split='heldout_scene', scene_id=11, image_id=0),
                           dict(split='development', scene_id=1, image_id=2)])
        self.assertEqual(set(development_frames(index)), {(1, 2)})
        index['test'].append(dict(split='development', scene_id=1, image_id=2))
        with self.assertRaises(ValueError):
            development_frames(index)

    def test_raw_frame_variant_rank_class_and_finite_score_are_enforced(self):
        rows = parse_raw((HEADER+ROW).encode(), (1, 2), 8)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['box'], (0., 0., 10., 10.))
        self.assertEqual(parse_raw(HEADER.encode(), (1, 2), 8), [])
        for row in [ROW.replace('1,2,', '1,3,'),
                    ROW.replace('fallback', 'fused'),
                    ROW.replace('object_8', 'object_25'),
                    ROW.replace(',0,85,', ',1,85,'),
                    ROW.replace(',0,85,', ',0,nan,'),
                    ROW.replace(',0,85,', ',0,84,')]:
            with self.assertRaises(ValueError, msg=row):
                parse_raw((HEADER+row).encode(), (1, 2), 8)


if __name__ == '__main__':
    unittest.main()
