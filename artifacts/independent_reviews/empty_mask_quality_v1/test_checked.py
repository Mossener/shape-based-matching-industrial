"""Literal byte/identity mutations, with tiny in-memory gzip only."""
import copy
import csv
import gzip
import io
import struct
import unittest

from checked import RAW_HEADER, check_numeric, check_retention, check_selected, exact_stream, finish, parse_raw


META = {0: dict(class_id='tless_object_1', template_id=0, training_image_id=7,
                angle=30., scale=1.5, tl_x=11, tl_y=13, warped_mask_bbox=[17, 19, 23, 29])}


def rawrow(rank=0, score=90., x=100):
    return dict(zip(RAW_HEADER, [1, 2, 'fallback', 'tless_object_1', rank, repr(score), 0, 7,
                               30, 1.5, x, 200, x-58, 142, 23, 29]))


def archive(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=RAW_HEADER)
    writer.writeheader()
    writer.writerows(rows)
    text = stream.getvalue().encode()
    encoded = gzip.compress(text, mtime=0)
    manifest = dict(scene_id=1, image_id=2, variant='fallback', raw_candidate_count=len(rows),
                    compressed_bytes=len(encoded), uncompressed_bytes=len(text))
    return encoded, manifest


def parse(rows):
    return parse_raw(*archive(rows), (1, 2), 'fallback', 1, META)


class SerializationChecks(unittest.TestCase):
    def test_raw_literal_and_missing_frame_is_not_empty(self):
        expected = ('tless_object_1', 0, 100, 200, struct.pack('<f', 90.), (42., 142., 23., 29.), (7, 30., 1.5))
        self.assertEqual(parse([rawrow()]), [expected])
        self.assertEqual(parse([]), [])
        changed = rawrow(); changed['image'] = 3
        with self.assertRaises(ValueError):
            parse([changed])
        encoded, manifest = archive([]); manifest['image_id'] = 3
        with self.assertRaises(ValueError):
            parse_raw(encoded, manifest, (1, 2), 'fallback', 1, META)

    def test_score_bit_mutation_breaks_stream_equality(self):
        original = parse([rawrow()])
        changed_score = struct.unpack('<f', struct.pack('<I', struct.unpack('<I', struct.pack('<f', 90.))[0]+1))[0]
        changed = parse([rawrow(score=changed_score)])
        exact_stream(original, original)
        with self.assertRaises(ValueError):
            exact_stream(original, changed)

    def test_raw_order_and_origin_mutations_fail(self):
        with self.assertRaises(ValueError):
            parse([rawrow(0, 89.), rawrow(1, 90., 101)])
        changed = rawrow(); changed['bbox_x'] = 43
        with self.assertRaises(ValueError):
            parse([changed])

    def test_selected_complete_identity_and_bits_mutations_fail(self):
        kept = [('tless_object_1', 0, 100, 200, struct.pack('<f', 90.), (42., 142., 23., 29.), (7, 30., 1.5))]
        row = {k: str(v) for k, v in rawrow().items() if k != 'variant'}
        row.update(object_id='1', arm='rgb', score_bits=str(struct.unpack('<I', kept[0][4])[0]),
                   allGT_label='TP', allGT_id='4', eligible_label='TP', eligible_id='4')
        check_selected([row], (1, 2), 1, 'rgb', META, kept, [('TP', 4)], [('TP', 4)])
        changed = dict(row, score_bits=str(int(row['score_bits'])+1))
        with self.assertRaises(ValueError):
            check_selected([changed], (1, 2), 1, 'rgb', META, kept, [('TP', 4)], [('TP', 4)])
        changed = dict(row, allGT_id='5')
        with self.assertRaises(ValueError):
            check_selected([changed], (1, 2), 1, 'rgb', META, kept, [('TP', 4)], [('TP', 4)])

    def test_retention_identity_and_complete_coverage(self):
        key = (1, 1, 2, 'allGT', 4)
        row = dict(object_id='1', scene='1', image='2', metric='allGT', gt_id='4',
                   rgb_detected='1', binary_detected='0', same_pose_if_both='-1')
        check_retention([row], {key: (1, 0, -1)})
        with self.assertRaises(ValueError):
            check_retention([dict(row, gt_id='5')], {key: (1, 0, -1)})
        with self.assertRaises(ValueError):
            check_retention([], {key: (1, 0, -1)})

    def test_aggregate_count_mutation_and_zero_denominators(self):
        expected = dict(tp=0, fp=0, fn=0, gt=0, ignored=0, matched_iou_sum=0.,
                        precision=0., recall=0., f1=0., mean_tp_iou=0.)
        self.assertEqual(finish(dict(tp=0, fp=0, fn=0, gt=0, ignored=0, matched_iou_sum=0.)), expected)
        check_numeric(expected, expected, 'zero')
        changed = dict(expected, tp=1)
        with self.assertRaises(ValueError):
            check_numeric(changed, expected, 'mutated aggregate')


if __name__ == '__main__':
    unittest.main()
