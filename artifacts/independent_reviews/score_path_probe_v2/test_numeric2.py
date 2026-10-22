"""Literal and mutation fixtures, independent of native/probe implementations."""
import copy
import struct
import unittest
import numeric2 as n


def feature(index,x=1,y=1,label=0,skip=0,digits='4'*256):
    return dict(feature_id=str(index),x=str(x),y=str(y),label=str(label),skipped=str(skip),cells=str(len(digits)),response_digits=digits)


def candidate(x,y=0,template=0,score=90.,box=None,cls='obj'):
    return dict(x=x,y=y,template=template,bits=struct.unpack('<I',struct.pack('<f',score))[0],box=box or (x,y,10,10),cls=cls)


class Arithmetic(unittest.TestCase):
    def test_normalization_and_threshold_boundary(self):
        self.assertEqual(n.score_bits(34,10),0x42aa0000)
        self.assertEqual(n.score_value(34,10),85.)
        self.assertFalse(n.score_value(34,10)>85.)
        self.assertTrue(n.score_value(34,10)>=85.)
        self.assertEqual(n.score_bits(0,3),0)
        self.assertEqual(n.score_bits(1,3),0x41055555)

    def test_invalid_denominator_or_raw_rejected(self):
        for raw,count in ((1,0),(1,8192),(-1,3),(13,3)):
            with self.subTest(raw=raw,count=count),self.assertRaises(ValueError):n.score_bits(raw,count)

    def test_flat_coarse_wrap_and_zero_tail(self):
        self.assertEqual(n.coarse_span(32,24,16,16),(3,4,7))
        row=feature(0,digits='444444400000')
        raw,signature=n.sum_features([row],1,12,(32,24),tail=7)
        self.assertEqual(list(raw),[4]*7+[0]*5)
        self.assertEqual(signature,[(1,1,0)])

    def test_zero_tail_mutation_rejected(self):
        with self.assertRaises(ValueError):n.sum_features([feature(0,digits='444444410000')],1,12,(32,24),tail=7)

    def test_skipped_feature_keeps_denominator(self):
        raw,_=n.sum_features([feature(0),feature(1,x=-1,skip=1,digits='0'*256)],2,256,(160,160))
        self.assertEqual(n.score_value(raw[0],2),50.)

    def test_bad_digits_skip_id_and_count_rejected(self):
        examples=[[feature(0,digits='5'*256)],[feature(0,x=-1,skip=0)],[feature(0,skip=1)],[feature(1)],[feature(0),feature(0)],[feature(0,digits='4'*255)]]
        for rows in examples:
            with self.subTest(rows=rows[0]['feature_id']),self.assertRaises(ValueError):n.sum_features(rows,1,256,(160,160))

    def test_skipped_nonzero_rejected(self):
        with self.assertRaises(ValueError):n.sum_features([feature(0,x=-1,skip=1)],1,256,(160,160))

    def test_feature_base_bounds_applies_once(self):
        raw,_=n.sum_features([feature(0,x=-5,y=0,skip=0)],1,256,(160,160),base=(8,8))
        self.assertEqual(raw[255],4)

    def test_zero_maximum_sentinel_and_ties(self):
        self.assertEqual(n.maximum([0]*256,3),dict(raw=0,bits=0,row=-1,col=-1,ties=256,tie_mask='1'*256))

    def test_first_strict_row_major_maximum(self):
        raw=[0]*256;raw[17]=raw[33]=7
        best=n.maximum(raw,2)
        self.assertEqual((best['row'],best['col'],best['raw'],best['bits'],best['ties']),(1,1,7,0x42af0000,2))
        self.assertEqual([i for i,x in enumerate(best['tie_mask']) if x=='1'],[17,33])

    def test_cell_schema_values_and_mutations(self):
        raw=[4,0]
        rows=[dict(row='0',col=str(i),native_raw=str(v),native_score_bits=str(n.score_bits(v,1)),computed=str(i<1 and 1 or 0),threshold_pass=str(v==4 and 1 or 0)) for i,v in enumerate(raw)]
        n.verify_cells(rows,raw,1,(1,2),'coarse',tail=1)
        for field,value in [('native_raw','3'),('native_score_bits','0'),('computed','0'),('threshold_pass','0'),('col','1')]:
            bad=copy.deepcopy(rows);bad[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):n.verify_cells(bad,raw,1,(1,2),'coarse',tail=1)
        with self.assertRaises(ValueError):n.verify_cells(rows[:1],raw,1,(1,2),'coarse',tail=1)

    def test_verify_maximum_checks_full_tie_mask(self):
        raw=[4]*256
        row=dict(window='0',center_x='64',center_y='64',base_x='32',base_y='32',raw='4',score_bits=str(0x42c80000),row='0',col='0',ties='256',tie_mask='1'*256)
        n.verify_maximum(row,raw,1,(64,64))
        for field,value in [('row','1'),('tie_mask','0'+'1'*255),('base_x','36'),('score_bits','0')]:
            bad=dict(row);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):n.verify_maximum(bad,raw,1,(64,64))


class Geometry(unittest.TestCase):
    def test_parent_clamp_and_cpp_truncation(self):
        self.assertEqual(n.parent(0,0,(80,80)),((32,32),(0,0)))
        self.assertEqual(n.parent(51,52,(80,80)),((736,720),(704,688)))
        # min(max(x,32), negative_high) intentionally produces negative center.
        self.assertEqual(n.parent(0,0,(883,867)),((-67,-67),(-96,-96)))

    def test_neighbors_integer_on_grid_and_off_grid(self):
        self.assertEqual(n.neighbors((5,9)),[(5,9)])
        self.assertEqual(set(n.neighbors((6,10))),{(5,9),(9,9),(5,13),(9,13)})
        self.assertEqual(set(n.neighbors((-2,-2))),{(-3,-3),(1,-3),(-3,1),(1,1)})
        with self.assertRaises(ValueError):n.neighbors((1.5,1))

    def test_complete_reachable_parent_set(self):
        got=n.reachable((473,417),(80,80))
        self.assertEqual(set(got),{(r,c) for r in range(24,28) for c in range(28,32)})
        self.assertEqual(got[(24,28)],((455,391),(420,356)))
        with self.assertRaises(ValueError):n.reachable((474,417),(80,80))


class Downstream(unittest.TestCase):
    def test_occurrence_subset_and_probed_actual_coverage(self):
        key=(5,9,0x42aa0000)
        self.assertEqual(n.reconcile_occurrences({key:2},{key:3},{(5,9)}),1)
        for pred,pre,points in [({key:4},{key:3},{(5,9)}),({},{key:1},{(5,9)}),({key:1},{},{(5,9)}),({key:0},{key:3},{(5,9)})]:
            with self.assertRaises(ValueError):n.reconcile_occurrences(pred,pre,points)

    def test_nms_full_frame_order_first_blocker_and_class(self):
        rows=[candidate(0,score=99),candidate(2,score=98),candidate(30,score=97),candidate(1,score=96,cls='other')]
        selected,blocked=n.nms(rows)
        self.assertEqual(selected,[0,2,3]);self.assertEqual(blocked,[-1,0,-1,-1])
        with self.assertRaises(ValueError):n.nms(list(reversed(rows)))

    def test_nms_strict_iou_boundary(self):
        # equal intersection/union = 3/10; exact threshold must survive.
        rows=[candidate(0,score=99,box=(0,0,6.5,1)),candidate(0,score=98,box=(3.5,0,6.5,1))]
        self.assertEqual(n.iou(rows[0]['box'],rows[1]['box']),.3)
        self.assertEqual(n.nms(rows)[0],[0,1])

    def test_assignment_greedy_ties_and_eligible_ignore(self):
        rows=[candidate(0),candidate(0,score=89),candidate(40,score=88)]
        truths=[dict(id=5,cls='obj',visibility=.3,box=(0,0,10,10)),dict(id=2,cls='obj',visibility=1.,box=(0,0,10,10))]
        self.assertEqual(n.assign(rows,truths),[('TP',2),('TP',5),('FP',-1)])
        self.assertEqual(n.assign(rows,truths,True),[('TP',2),('IGNORE',5),('FP',-1)])

    def test_assignment_iou_inclusive_and_gt_uniqueness(self):
        rows=[candidate(0,box=(0,0,2,1))]
        truths=[dict(id=0,cls='obj',visibility=1.,box=(0,0,1,1))]
        self.assertEqual(n.assign(rows,truths),[('TP',0)])
        with self.assertRaises(ValueError):n.assign(rows,truths*2)


if __name__=='__main__':unittest.main()
