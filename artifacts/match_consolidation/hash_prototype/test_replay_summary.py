"""Synthetic route/ratio mutations; no compiler, image, matcher or real trace access."""
import copy
import unittest

from summarize_replay import FIELDS, METHODS, validate_rows


def fixture():
    cases = [dict(case_id='fixture', scenario='synthetic', input_count=4, output_count=2,
                  class_bytes=[1, 1, 1, 1], has_zero=False)]
    rows = []
    for phase, count in (('warmup', 3), ('measured', 31)):
        for round_index in range(count):
            rotation = round_index % 5
            values = list(range(rotation, 5))+list(range(rotation))
            if round_index % 2:
                values.reverse()
            for position, method in enumerate(values):
                baseline = 8 if round_index % 2 else (2 if round_index < 16 else 10)
                latency = baseline if method == 0 else baseline*(.5 if round_index % 2 else 2)
                rows.append(dict(zip(FIELDS, map(str, (0, 'fixture', 'synthetic', phase, round_index,
                    position, METHODS[method], 4, 2, 10000, .2,
                    latency, 0 if method == 0 else 7, 0)))))
    return rows, cases


class ReplaySummary(unittest.TestCase):
    def test_a_complete_rows_and_median_of_paired_ratios(self):
        rows, cases = fixture()
        result = validate_rows(rows, FIELDS, cases, 56)
        self.assertEqual(result['rows'], 170)
        self.assertEqual(result['measured_rows'], 155)
        #16 even rounds have ratio2;15 odd rounds have ratio.5. Median=2.
        self.assertEqual(result['traces'][0]['methods']['owning_hash_reserve']['paired_ratio_median'], 2)
        # Latency medians are 4/8: ratio-of-medians would incorrectly report .5.
        self.assertEqual(result['traces'][0]['methods']['v11_sort_unique']['consolidation_ms']['median'], 8)
        self.assertEqual(result['traces'][0]['methods']['owning_hash_reserve']['consolidation_ms']['median'], 4)
        self.assertEqual(len(result['traces'][0]['methods']['owning_hash_reserve']['paired_ratios']), 31)
        self.assertEqual(result['scenarios']['synthetic']['owning_hash_reserve']['regressions'], ['fixture'])

    def test_changed_variant_order_count_batch_fields_and_timing_rejected(self):
        rows, cases = fixture()
        for field, value in (('method', 'index_hash_reserve'), ('case', 'other'),
                             ('scenario', 'other'), ('round', '31'), ('order', '4'),
                             ('phase', 'measured'), ('input_count', '3'), ('output_count', '3'),
                             ('batch', '128'), ('copy_ms', '-1'), ('consolidation_ms', 'nan'),
                             ('zero_score_fallback', '1'), ('bucket_count', '1')):
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            with self.assertRaises(ValueError, msg=field):
                validate_rows(changed, FIELDS, cases, 56)
        for changed in (rows[:-1], rows+[rows[0]], [rows[1], rows[0]]+rows[2:]):
            with self.assertRaises(ValueError):
                validate_rows(changed, FIELDS, cases, 56)
        with self.assertRaises(ValueError):
            validate_rows(rows, list(reversed(FIELDS)), cases, 56)

    def test_missing_extra_nonfinite_and_diagnostic_drift_rejected(self):
        rows, cases = fixture()
        mutations = []
        for field, value in (('copy_ms', 'inf'), ('consolidation_ms', '0'),
                             ('consolidation_ms', '-1'), ('trace_index', '-1'),
                             ('input_count', '4.0'), ('bucket_count', str(1 << 64))):
            changed = copy.deepcopy(rows)
            changed[0][field] = value
            mutations.append(changed)
        missing = copy.deepcopy(rows)
        del missing[0]['case']
        extra = copy.deepcopy(rows)
        extra[0]['extra'] = '1'
        drift = copy.deepcopy(rows)
        drift[9]['bucket_count'] = '8'  # Owning hash reserve in odd reversed round.
        mutations += [missing, extra, drift]
        for changed in mutations:
            with self.assertRaises(ValueError):
                validate_rows(changed, FIELDS, cases, 56)

    def test_batch_cap_empty_and_signed_zero_fallback(self):
        rows, cases = fixture()
        # 4*(56+64+1,000,000)=4,000,480; floor(64MiB/estimate)=16.
        cases[0]['class_bytes'] = [1000000]*4
        cases[0]['has_zero'] = True
        for row in rows:
            row['batch'] = '16'
            if row['method'] != METHODS[0]:
                row['zero_score_fallback'] = '1'
                row['bucket_count'] = '0'
        result = validate_rows(rows, FIELDS, cases, 56)
        self.assertTrue(result['traces'][0]['methods']['index_hash_reserve']['zero_score_fallback'])
        cases[0].update(input_count=0, output_count=0, class_bytes=[], has_zero=False)
        for row in rows:
            row.update(input_count='0', output_count='0', batch='10000', bucket_count='0',
                       zero_score_fallback='0')
        self.assertEqual(validate_rows(rows, FIELDS, cases, 56)['rows'], 170)
        for bad_size in (0, -1, True):
            with self.assertRaises(ValueError):
                validate_rows(rows, FIELDS, cases, bad_size)


if __name__ == '__main__':
    unittest.main()
