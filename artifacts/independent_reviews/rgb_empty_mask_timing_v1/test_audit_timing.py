"""Small generated corruption fixtures; no experiment/native/image execution."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

import audit_timing as audit


def fixture():
    variants = [('rgb_control', 'fallback'), ('rgb_control', 'fused'),
                ('rgb_empty_mask', 'fallback'), ('rgb_empty_mask', 'fused')]
    rows = []
    for rnd in range(8):
        for order in range(4):
            idx = (rnd + order) % 4
            arm, path = variants[idx]
            rows.append(dict(object_id='1', scene='2', image='3', round=str(rnd),
                             warmup=str(int(rnd == 0)), order=str(order), arm=arm,
                             path=path, match_ms=str([10, 20, 5, 20][idx]),
                             external_call_ms=str([12, 22, 6, 21][idx]),
                             raw=str([100, 100, 40, 40][idx]), selected=str([10, 10, 4, 4][idx]),
                             exact_own_reference='1'))
    refs = {(1, 2, 3, 'rgb_control'): (100, 10), (1, 2, 3, 'rgb_empty_mask'): (40, 4)}
    summary = dict(passed=1, stage='timing', objects=[1], unique_frames=1,
                   object_frame_combinations=1, matcher_calls=32, warmup_rounds=1,
                   measured_rounds=7, exact_own_reference_every_call=1,
                   decode_and_bank_load_excluded_from_external_call=1,
                   paired_performance_benchmark=1, variants=[], paired_empty_mask_over_rgb=[])
    for idx, (arm, path) in enumerate(variants):
        summary['variants'].append(dict(arm=arm, path=path, samples=7,
            match_median_ms=[10,20,5,20][idx], match_p95_ms=[10,20,5,20][idx],
            external_median_ms=[12,22,6,21][idx], external_p95_ms=[12,22,6,21][idx]))
    for path, m, e in [('fallback', .5, .5), ('fused', 1., 21/22)]:
        summary['paired_empty_mask_over_rgb'].append(dict(path=path, samples=7,
            match_ratio_median=m, match_ratio_p95=m, external_ratio_median=e, external_ratio_p95=e))
    return rows, summary, [1], [(2,3)], refs


class AuditTests(unittest.TestCase):
    def test_nearest_rank_uses_lower_middle_and_ceil_p95(self):
        self.assertEqual(audit.nearest_rank([9,1], .5), 1)
        self.assertEqual(audit.nearest_rank(list(range(1,21)), .95), 19)

    def test_valid_schedule_and_both_clocks(self):
        result = audit.audit_numeric(*fixture())
        self.assertIsInstance(result, dict)
        self.assertEqual(result['rows'], 32)
        self.assertEqual(result['formal_rows'], 28)
        self.assertEqual(result['paired_ratios'][1]['external_ratio_median'], 21/22)

    def test_rejects_missing_pair_row(self):
        args = fixture(); args[0].pop()
        with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_duplicated_call(self):
        args = fixture(); args[0][-1] = copy.deepcopy(args[0][-2])
        with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_wrong_rotating_order(self):
        args = fixture(); args[0][0]['order'] = '1'
        with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_wrong_warmup(self):
        args = fixture(); args[0][0]['warmup'] = '0'
        with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_wrong_frame_schedule(self):
        args = fixture(); args[0][0]['image'] = '4'
        with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_nonfinite_or_nonpositive_clock(self):
        for field, value in [('match_ms','0'), ('external_call_ms','nan'), ('external_call_ms','-1')]:
            with self.subTest(field=field, value=value):
                args = fixture(); args[0][0][field] = value
                with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_external_shorter_than_matcher(self):
        args = fixture(); args[0][0]['external_call_ms'] = '1'
        with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_quality_reference_count_mismatch(self):
        for field in ['raw','selected']:
            with self.subTest(field=field):
                args = fixture(); args[0][0][field] = '99'
                with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_false_reference_flag(self):
        args = fixture(); args[0][0]['exact_own_reference'] = '0'
        with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_corrupt_summary_two_clocks_and_pairs(self):
        for section, field in [('variants','match_median_ms'),('variants','external_p95_ms'),
                               ('paired_empty_mask_over_rgb','match_ratio_p95'),
                               ('paired_empty_mask_over_rgb','external_ratio_median')]:
            with self.subTest(section=section,field=field):
                args=fixture(); args[1][section][0][field] += .01
                with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_rejects_wrong_call_count(self):
        args=fixture(); args[1]['matcher_calls']=31
        with self.assertRaises(ValueError): audit.audit_numeric(*args)

    def test_pin_accepts_exact_bytes_and_rejects_modified_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as td:
            path=Path(td)/'source.cpp'; path.write_bytes(b'original\n')
            pin=dict(path=str(path), bytes=9, sha256=hashlib.sha256(b'original\n').hexdigest())
            self.assertTrue(audit.verify_pin(pin))
            path.write_bytes(b'modified\n')
            with self.assertRaises(ValueError): audit.verify_pin(pin)

    def test_pin_rejects_size_mismatch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as td:
            path=Path(td)/'source.cpp'; path.write_bytes(b'ok')
            pin=dict(path=str(path), bytes=3, sha256=hashlib.sha256(b'ok').hexdigest())
            with self.assertRaises(ValueError): audit.verify_pin(pin)


if __name__ == '__main__':
    unittest.main(verbosity=2)
