"""Literal independent oracles and mutation tests; no real data or native I/O."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import audit
import identity_strata
from numeric import evaluate, float_bits, nms, overlap, score


def literal():
    # Literals deliberately use nonzero crop/template/padding origins.
    return ('tless_object_1', 0, 100, 200, 1119092736, (22., 118., 23., 29.), (7, 1106247680, 1069547520))


def selected():
    return dict(object_id='1', scene='4', image='9', arm='rgb_empty_mask', rank='0', class_id='tless_object_1',
                score='90', score_bits='1119092736', template_id='0', training_image='7', angle='30', scale='1.5',
                match_x='100', match_y='200', bbox_x='22', bbox_y='118', bbox_w='23', bbox_h='29',
                allGT_label='TP', allGT_id='12', eligible_label='TP', eligible_id='12')


class LiteralAndMutations(unittest.TestCase):
    def test_score_float32_bits_and_order_are_exact(self):
        self.assertEqual(float_bits(90), 1119092736)
        self.assertEqual(score(1119092736), 90.)
        a = literal()
        b = list(a); b[4] += 1; b = tuple(b)
        audit.check_path_equality([a], [a])
        with self.assertRaises(ValueError):
            audit.check_path_equality([a], [b])
        c = list(a); c[2] += 1; c = tuple(c)
        with self.assertRaises(ValueError):
            audit.check_path_equality([a, c], [c, a])
        with self.assertRaises(ValueError):
            audit.check_path_equality([a], [a, a])

    def test_complete_schedule_and_zero_detection_frames(self):
        one = (1, 4, 9, 'rgb_empty_mask')
        two = (1, 4, 10, 'rgb_empty_mask')
        selected_rows = {one: [selected()]}
        audit.check_coverage({one: {}, two: {}}, selected_rows, [one, two], {one, two})
        self.assertEqual(selected_rows[two], [])
        for per, eq in [({one: {}}, [one, two]), ({one: {}, two: {}}, [one]),
                        ({one: {}, two: {}}, [one, one, two])]:
            with self.subTest(per=per, eq=eq), self.assertRaises(ValueError):
                audit.check_coverage(per, {}, eq, {one, two})
        with self.assertRaises(ValueError):
            audit.check_coverage({one: {}, two: {}}, {(25, 4, 10, 'rgb_empty_mask'): []}, [one, two], {one, two})

    def test_every_selected_field_mutation_is_rejected(self):
        row = selected()
        key = (1, 4, 9, 'rgb_empty_mask')
        audit.check_selected([row], [literal()], key, [('TP', 12)], [('TP', 12)])
        changes = dict(object_id='2', scene='5', image='10', arm='rgb_control', rank='1',
                       class_id='tless_object_2', score='90.00000762939453', score_bits='1119092737',
                       template_id='1', training_image='8', angle='60', scale='2', match_x='101', match_y='201',
                       bbox_x='23', bbox_y='119', bbox_w='24', bbox_h='30', allGT_label='FP', allGT_id='11',
                       eligible_label='IGNORE', eligible_id='11')
        self.assertEqual(set(changes), set(row))
        for field, value in changes.items():
            changed = dict(row, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.check_selected([changed], [literal()], key, [('TP', 12)], [('TP', 12)])
        with self.assertRaises(ValueError):
            audit.check_selected([], [literal()], key, [('TP', 12)], [('TP', 12)])

    def test_box_origin_metadata_mutations(self):
        row = selected()
        meta = {0: dict(class_id='tless_object_1', template_id=0, training_image_id=7,
                        angle=30, scale=1.5, tl_x=31, tl_y=37, warped_mask_bbox=[17, 19, 23, 29])}
        self.assertEqual(audit.parse_candidate(row, 1, meta), literal())
        for field, value in [('tl_x', 32), ('tl_y', 38), ('warped_mask_bbox', [18, 19, 23, 29])]:
            changed = copy.deepcopy(meta); changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.parse_candidate(row, 1, changed)
        for field, value in [('bbox_x', '21'), ('training_image', '8'), ('angle', 'nan'), ('score', '84.9')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.parse_candidate(dict(row, **{field: value}), 1, meta)

    def test_gt_geometry_and_attribution(self):
        gt = dict(gt_id=12, class_id='tless_object_1', bbox_obj=(22, 118, 23, 29), visib_fract=.9)
        row = dict(class_id='tless_object_1', visibility='.9', bbox_x='22', bbox_y='118', bbox_w='23', bbox_h='29')
        audit.check_gt_row(row, gt)
        for field, value in [('class_id', 'tless_object_2'), ('visibility', '.8'), ('bbox_x', '21'),
                             ('bbox_y', '117'), ('bbox_w', '24'), ('bbox_h', '30')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit.check_gt_row(dict(row, **{field: value}), gt)
        self.assertEqual(evaluate([literal()], [gt], False)[1], [('TP', 12)])
        # Equal boxes and scores select the smallest unused GT id exactly once.
        tie = dict(gt, gt_id=3)
        self.assertEqual(evaluate([literal(), literal()], [gt, tie], False)[1], [('TP', 3), ('TP', 12)])
        self.assertEqual(evaluate([literal()], [dict(gt, bbox_obj=(1000, 1000, 23, 29))], False)[1], [('FP', -1)])

    def test_nms_and_gt_threshold_boundaries(self):
        self.assertEqual(overlap((0, 0, 13, 1), (7, 0, 13, 1)), .3)
        a = list(literal()); a[5] = (0, 0, 13, 1); a = tuple(a)
        b = list(literal()); b[2] = 107; b[5] = (7, 0, 13, 1); b = tuple(b)
        self.assertEqual(nms([b, a]), [a, b])
        c = list(a); c[2] = 1; c[5] = (0, 0, 26, 1); c = tuple(c)
        gt = dict(gt_id=3, bbox_obj=(0, 0, 13, 1), visib_fract=.2)
        self.assertEqual(evaluate([c], [gt], False)[1], [('TP', 3)])
        self.assertEqual(evaluate([c], [gt], True)[1], [('IGNORE', 3)])

    def test_reader_pin_mutation_and_image_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'value.json'; path.write_bytes(b'{}')
            reader = audit.Reader(root)
            pin = reader.pin(path)
            self.assertEqual(reader.check(pin), b'{}')
            path.write_bytes(b'{"changed":1}')
            with self.assertRaises(ValueError):
                reader.check(pin)
            image = root / 'numeric.png'; image.write_bytes(b'not an image')
            with self.assertRaises(ValueError):
                reader.read(image)

    def test_empty_raw_csv_is_valid_not_a_missing_frame(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path = root / 's4_i9_fallback_raw.csv.gz'
            plain = (','.join(audit.RAW_HEADER) + '\n').encode()
            encoded = gzip.compress(plain); path.write_bytes(encoded)
            manifest = dict(scene_id=4, image_id=9, variant='fallback', raw_candidate_count=0,
                            compressed_bytes=len(encoded), uncompressed_bytes=len(plain))
            (root / 's4_i9_fallback_raw_manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(audit.parse_raw(audit.Reader(root), path, (4, 9), 'fallback', 1, {}), [])
            manifest['raw_candidate_count'] = 1
            (root / 's4_i9_fallback_raw_manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                audit.parse_raw(audit.Reader(root), path, (4, 9), 'fallback', 1, {})

    def test_historical_strata_do_not_hide_changed_control_or_missing_gt(self):
        old, new = {}, {}
        distributions = {'allGT': [148, 67, 59, 126], 'eligible': [147, 62, 56, 109]}
        for metric, counts in distributions.items():
            identity = 0
            for (rgb, binary), count in zip([(1, 1), (1, 0), (0, 1), (0, 0)], counts):
                for _ in range(count):
                    key = (1, 4, 9, metric, identity); identity += 1
                    old[key] = (rgb, binary, 0 if rgb and binary else -1)
                    new[key] = (rgb, rgb, 1 if rgb else -1)
        report, records = identity_strata.summarize(old, new)
        self.assertEqual(len(records), 774)
        totals = [r for r in report['groups'] if r['stratum'] == 'ALL' and r['object_id'] is None and r['scene'] is None]
        self.assertEqual({r['metric']: (r['control_tp'], r['treatment_tp'], r['net_tp']) for r in totals},
                         {'allGT': (215, 215, 0), 'eligible': (209, 209, 0)})
        missing = dict(new); missing.pop(next(iter(missing)))
        with self.assertRaises(ValueError):
            identity_strata.summarize(old, missing)
        changed = dict(new); key = next(iter(changed)); changed[key] = (0, 1, -1)
        with self.assertRaises(ValueError):
            identity_strata.summarize(old, changed)


if __name__ == '__main__':
    unittest.main()
