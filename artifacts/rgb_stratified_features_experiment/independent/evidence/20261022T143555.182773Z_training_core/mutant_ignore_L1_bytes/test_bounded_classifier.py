"""Equivalence tests written before bounded classifier implementation."""
import importlib.util
import random
import unittest

import numeric_oracle

SPEC=importlib.util.find_spec('bounded_classifier_v2')
if SPEC is not None:
    import bounded_classifier_v2 as bounded


class Availability(unittest.TestCase):
    def test_bounded_classifier_v2_exists(self):
        self.assertIsNotNone(SPEC,'independent bounded_classifier_v2 is missing')


@unittest.skipIf(SPEC is None,'missing bounded implementation; availability is RED')
class BoundedEquivalence(unittest.TestCase):
    def candidate(self,ordinal,x,y):
        return numeric_oracle.Candidate(ordinal,x,y,ordinal%8,0x3F800000,0x7FC00000+ordinal)

    def compare(self,mask,width,height):
        distances=numeric_oracle.signed_chebyshev(mask,width,height)
        valid=[]; expected=[]; rejected=[]
        for y in range(2,height-2):
            for x in range(2,width-2):
                distance=distances[y*width+x]
                candidate=self.candidate(len(valid),x,y)
                if distance is None or distance < -4:
                    rejected.append(candidate)
                else:
                    valid.append(candidate); expected.append('S' if distance<=4 else 'I')
        self.assertEqual(bounded.classify(valid,mask,width,height),expected)
        self.assertEqual(numeric_oracle.classify(valid,mask,width,height),expected)
        for candidate in rejected:
            with self.assertRaises(ValueError): bounded.classify([candidate],mask,width,height)
        for x,y in [(1,2),(2,1),(width-2,2),(2,height-2),(-1,0)]:
            with self.assertRaises(ValueError): bounded.classify([self.candidate(0,x,y)],mask,width,height)

    def test_literals_more_than_nine_pixels_boundary_four_vs_five(self):
        candidates=[self.candidate(0,3,7),self.candidate(1,4,7),self.candidate(2,5,7)]
        self.assertEqual(bounded.classify(candidates,bytes([7]*225),15,15),['S','I','I'])
        mask=bytearray(225); mask[7*15+7]=1
        self.assertEqual(bounded.classify([self.candidate(0,3,7),self.candidate(1,7,7)],bytes(mask),15,15),['S','S'])
        with self.assertRaises(ValueError): bounded.classify([self.candidate(0,2,7)],bytes(mask),15,15)
        for width,height in [(11,13),(17,19),(28,16)]:
            for value in [1,7,128,255]: self.compare(bytes([value]*(width*height)),width,height)
            self.compare(bytes(width*height),width,height)

    def test_holes_thin_components_and_exact_zero_exterior(self):
        width,height=25,21
        masks=[bytes(7 if (x in (2,12,22) or y in (2,10,18)) else 0 for y in range(height) for x in range(width)),
               bytes(0 if 8<=x<=16 and 6<=y<=14 else 1 for y in range(height) for x in range(width)),
               bytes(255 if 5<=x<=19 and 4<=y<=16 else 0 for y in range(height) for x in range(width)),
               bytes(1 if x==12 and y==10 else 0 for y in range(height) for x in range(width))]
        for mask in masks: self.compare(mask,width,height)

    def test_deterministic_random_masks_all_scan_positions(self):
        generator=random.Random(731241)
        for width,height in [(13,11),(18,23),(31,29),(12,26)]:
            for probability in [.005,.03,.1,.35,.8,.97]:
                mask=bytes(generator.choice([1,7,128,255]) if generator.random()<probability else 0
                           for _ in range(width*height))
                self.compare(mask,width,height)

    def test_pure_validation_and_duplicate_coordinate_equivalence(self):
        pool=[self.candidate(9,5,5),self.candidate(2,5,5)]
        self.assertEqual(bounded.classify(pool,bytes([1]*225),15,15),['I','I'])
        with self.assertRaises(ValueError): bounded.classify([pool[0],pool[0]],bytes([1]*225),15,15)
        with self.assertRaises(ValueError): bounded.classify(pool,bytes(224),15,15)

    def test_runtime_small_equivalence_gate_is_explicit(self):
        self.assertTrue(hasattr(bounded,'verify_equivalence_fixture'),'runtime equivalence fixture is missing')
        result=bounded.verify_equivalence_fixture()
        self.assertTrue(result['passed'])
        self.assertGreaterEqual(result['mask_cases'],4)
        self.assertGreater(result['compared_candidate_positions'],100)


if __name__=='__main__': unittest.main(verbosity=2)
