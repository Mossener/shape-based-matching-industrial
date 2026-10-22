"""Literal independent fixtures and corruptions; no images or native process."""
from dataclasses import replace
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from numeric import (Candidate, assign, bits, check_complete_scope, check_raw_paths,
                     check_selected, diagnose, iou, nms_trace)
from run_analysis import Evidence, parse_candidate


def c(box=(0,0,10,10),score=90.,template=0,cls='tless_object_1',x=0,y=0):
    return Candidate(cls,template,x,y,bits(score),tuple(box),(7,30.,1.5))


def gt(box=(0,0,10,10),gid=0,visibility=1.):
    return dict(gt_id=gid,box=box,visibility=visibility)


class DiagnosticTests(unittest.TestCase):
    def test_strict_nms_boundary_and_half_gt_iou(self):
        self.assertEqual(iou((0,0,13,1),(7,0,13,1)),.3)
        raw=[c((0,0,13,1),99,0),c((7,0,13,1),98,1)]
        self.assertEqual(nms_trace(raw),([0,1],{}))
        self.assertEqual(iou((0,0,2,2),(0,0,1,2)),.5)
        self.assertEqual(assign([c((0,0,2,2))],[0],[gt((0,0,1,2))]),[('TP',0)])

    def test_first_blocker_is_canonical_kept_not_best_iou(self):
        raw=[c((0,0,13,1),99,0),c((7,0,13,1),98,1),c((5,0,13,1),97,2)]
        kept,blockers=nms_trace(raw)
        self.assertEqual(kept,[0,1]);self.assertEqual(blockers,{2:0})
        truth=[gt((5,0,13,1))]; labels=assign(raw,kept,truth)
        self.assertLess(iou(raw[0].box,raw[2].box),iou(raw[1].box,raw[2].box))
        d=diagnose(0,truth,raw,kept,blockers,labels)
        self.assertEqual(d['suppression'][0]['blocker_raw_rank'],0)
        with self.assertRaises(ValueError):
            diagnose(0,truth,raw,kept,{2:1},labels)

    def test_suppressed_candidate_cannot_block_later_candidate(self):
        raw=[c((0,0,10,10),99,0),c((4,0,10,10),98,1),c((8,0,10,10),97,2)]
        self.assertEqual(nms_trace(raw),([0,2],{1:0}))

    def test_classes_and_score_ties(self):
        raw=[c(template=2),c(template=1)]
        self.assertEqual(nms_trace(raw),([1],{0:1}))
        self.assertEqual(nms_trace([c(cls='A'),c(cls='B')]),([0,1],{}))
        raw=[c(template=0,x=3),c(template=0,x=1)]
        self.assertEqual(nms_trace(raw),([1],{0:1}))

    def test_fp_and_tp_other_first_blockers_are_distinct(self):
        raw=[c((4,0,10,10),99,0),c((0,0,10,10),90,1)]
        kept,blockers=nms_trace(raw)
        for truth,label,isfp in [([gt()],('FP',-1),True),([gt(),gt((4,0,10,10),1)],('TP',1),False)]:
            labels=assign(raw,kept,truth)
            self.assertEqual(labels,[label])
            d=diagnose(0,truth,raw,kept,blockers,labels)
            self.assertEqual(d['category'],'nms_loss')
            self.assertEqual(d['suppression'],[dict(raw_rank=1,blocker_raw_rank=0,blocker_label=label[0],
                                                  blocker_gt_id=label[1],blocker_is_fp=isfp)])

    def test_assignment_competition_and_tie_identity(self):
        raw=[c((1,0,10,10))];truth=[gt(),gt((1,0,10,10),7)]
        kept,blockers=nms_trace(raw);labels=assign(raw,kept,truth)
        self.assertEqual(labels,[('TP',7)])
        self.assertEqual(diagnose(0,truth,raw,kept,blockers,labels)['category'],'assignment_competition')
        self.assertEqual(assign(raw,kept,[gt((1,0,10,10),7),gt((1,0,10,10),3)]),[('TP',3)])
        with self.assertRaises(ValueError):
            diagnose(0,truth,raw,kept,blockers,[('FP',-1)])

    def test_raw_gap_and_matched_are_exhaustive(self):
        truth=[gt()]
        self.assertEqual(diagnose(0,truth,[],[],{},[])['category'],'raw_gap')
        raw=[c()];labels=assign(raw,[0],truth)
        d=diagnose(0,truth,raw,[0],{},labels)
        self.assertEqual((d['category'],d['best_raw_iou'],d['matched_raw_rank']),('matched',1.,0))

    def test_eligible_tp_assignment_precedes_ignore(self):
        raw=[c()];truth=[gt(gid=0,visibility=.2),gt(gid=1,visibility=1.)]
        self.assertEqual(assign(raw,[0],truth,True),[('TP',1)])
        self.assertEqual(assign(raw,[0],[truth[0]],True),[('IGNORE',0)])

    def test_bits_order_multiplicity_and_selected_corruption(self):
        raw=[c(),c((30,0,10,10),89,1)]
        check_raw_paths(raw,list(raw))
        corruptions=[[replace(raw[0],score_bits=raw[0].score_bits+1),raw[1]],list(reversed(raw)),raw[:-1],raw+[raw[0]]]
        for altered in corruptions:
            with self.subTest(altered=altered),self.assertRaises(ValueError):
                check_raw_paths(raw,altered)
        labels=[('TP',0),('FP',-1)]
        actual=[(raw[0],labels[0],labels[0]),(raw[1],labels[1],labels[1])]
        check_selected(raw,[0,1],actual,labels,labels)
        for index,changed in [(0,(replace(raw[0],x=1),labels[0],labels[0])),
                              (0,(replace(raw[0],score_bits=raw[0].score_bits+1),labels[0],labels[0])),
                              (1,(raw[1],('TP',0),labels[1]))]:
            altered=list(actual);altered[index]=changed
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                check_selected(raw,[0,1],altered,labels,labels)

    def test_full_negative_frame_cannot_be_omitted(self):
        expected={(1,4,1,'rgb_control'),(1,4,2,'rgb_control')}
        check_complete_scope(list(expected),expected)
        for altered in [list(expected)[:-1],list(expected)+[next(iter(expected))]]:
            with self.assertRaises(ValueError):
                check_complete_scope(altered,expected)

    def test_official_origin_pose_and_score_are_validated(self):
        row=dict(class_id='tless_object_1',template_id='0',score='90',match_x='100',match_y='200',
                 bbox_x='22',bbox_y='118',bbox_w='23',bbox_h='29',training_image='7',angle='30',scale='1.5')
        meta={0:dict(tl_x=31,tl_y=37,warped_mask_bbox=[17,19,23,29],training_image_id=7,angle=30,scale=1.5)}
        self.assertEqual(parse_candidate(row,1,meta).box,(22.,118.,23.,29.))
        for field,value in [('tl_x',32),('tl_y',38),('warped_mask_bbox',[17,19,24,29]),('angle',60)]:
            changed=copy.deepcopy(meta);changed[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                parse_candidate(row,1,changed)
        for field,value in [('score','nan'),('score','90.0000001'),('score','84'),('class_id','tless_object_25')]:
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                parse_candidate(dict(row,**{field:value}),1,meta)

    def test_numeric_pin_mutation_and_forbidden_image(self):
        # Fixture is contained in the diagnostic artifacts subtree; no real
        # dataset or image bytes are read.
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root=Path(temporary);file=root/'fixture.json';file.write_bytes(b'{}')
            pin=dict(path=str(file),bytes=2,sha256=hashlib.sha256(b'{}').hexdigest())
            e=Evidence([pin]);self.assertEqual(e.read(file),b'{}')
            file.write_bytes(b'{"x":1}')
            with self.assertRaises(ValueError):e.read(file)
            image=root/'fixture.png';image.touch()
            with self.assertRaises(ValueError):e.read(image)


if __name__=='__main__':
    unittest.main()
