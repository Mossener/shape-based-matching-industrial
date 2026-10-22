"""Independent synthetic matrix and adversarial mutations; no file/native inputs."""
import copy
import hashlib
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import correctness_contract as c
from output_contract import Record

COMMON = tuple(['LED_%d' % n for n in range(1, 9)] + ['case1'] +
               ['tiny_s5_i%d' % n for n in (7, 70, 127, 215, 293, 353, 436, 493)] +
               ['tiny_s2_i%d' % n for n in (3, 92, 153, 214, 295, 374, 446, 494)])
INPUTS = COMMON + ('LED_two_classes', 'synthetic_zero_maxima', 'LED_zero_mask',
                   'LED_full_mask', 'LED_partial_mask', 'LED_empty_candidates',
                   'LED_larger_same_detector')
BASE, HASH = 'exact_v11', 'index_reserve_copy_actual_match'


def independent_schedule():
    calls, comparisons = [], []
    def call(stage, route, index, variant=BASE, flags=127, threads=4,
             pass_id=0, repeat=0, worker=-1, step=0):
        row = dict(call_id=len(calls), stage=stage, route=route, variant=variant,
                   input=INPUTS[index] if type(index) is int else index,
                   threads=threads, flags=flags, repeat=repeat, worker=worker, step=step)
        row['pass'] = pass_id
        calls.append(row)
        return row['call_id']
    def equal(actual, expected):
        comparisons.append(dict(comparison_id=len(comparisons), actual_call_id=actual,
                                expected_call_id=expected, full_ordered_equal=True, first_mismatch=None))
    for pass_id, threads in enumerate([1, 4, 2, 4]):
        for flags in [63, 127]:
            for index in range(32):
                oracle = call('core', 'oracle', index, flags=flags, threads=threads, pass_id=pass_id)
                equal(call('core', 'baseline_repeat', index, flags=flags, threads=threads,
                           pass_id=pass_id, repeat=1), oracle)
                for repeat in range(2):
                    equal(call('core', 'candidate', index, HASH, flags, threads, pass_id, repeat), oracle)
    for flags in range(128):
        for index in [0, 27, 8, 1, 26, 31]:
            oracle = call('flags', 'all_flags', index, flags=flags)
            equal(call('flags', 'all_flags', index, HASH, flags), oracle)
    for index in [28, 29, 30, 0]:
        for flags in [0, 55, 127]:
            oracle = call('flags', 'mask_restore', index, flags=flags)
            equal(call('flags', 'mask_restore', index, HASH, flags), oracle)
    oracle = call('flags', 'log_flag', 0)
    equal(call('flags', 'log_flag', 0, HASH), oracle)
    oracles = {127: [call('lifetime', 'oracle', index) for index in range(32)]}
    for index, route in [(0, 'pre_move'), (8, 'move_constructed'), (1, 'moved_from_reused'),
                         (8, 'assignment_destination_populated'), (0, 'move_assigned'),
                         (31, 'assignment_source_reused')]:
        equal(call('lifetime', route, index, HASH), oracles[127][index])
    for step, index in enumerate([0, 8, 1, 0]):
        oracle = call('lifetime', 'legacy_default', index, step=step)
        equal(call('lifetime', 'legacy_default', index, HASH, step=step), oracle)
        equal(call('lifetime', 'explicit_default', index, HASH, step=step), oracle)
    oracles[55] = [call('lifetime', 'oracle', index, flags=55) for index in range(32)]
    for worker, sequence in enumerate([[0, 8, 1, 27, 31, 0], [0, 31, 27, 1, 8, 0]]):
        for step, index in enumerate(sequence):
            for flags in [127, 55]:
                equal(call('lifetime', 'concurrent', index, HASH, flags, 1,
                           worker=worker, step=step), oracles[flags][index])
    for step in range(8):
        oracle = call('class_filter', 'filter', 25, step=step)
        equal(call('class_filter', 'filter', 25, HASH, step=step), oracle)
    for index in range(1, 8):
        name = 'M%02d' % index
        oracle = call('magnet_local', 'regression', name)
        equal(call('magnet_local', 'regression', name, HASH), oracle)
    return calls, comparisons


def records_for(row):
    name = row['input']
    if name in ('LED_zero_mask', 'LED_empty_candidates'):
        return ()
    if name == 'synthetic_zero_maxima':
        return (Record(-3, -3, 0, 0, b'zero'),)
    if name == 'LED_two_classes':
        allowed = {b'LED_A', b'LED_B'}
        if row['stage'] == 'class_filter':
            allowed = [{b'LED_A', b'LED_B'}, {b'LED_A'}, {b'LED_B'},
                       {b'LED_A', b'LED_B'}, {b'LED_A', b'LED_B'}, set(),
                       {b'LED_A'}, {b'LED_A'}][row['step']]
        return tuple(Record(x, y, template_id, bits, cls)
                     for x, y, template_id, bits in [(1, 2, 1, 0x42c00000), (3, 4, 2, 0x42bc0000)]
                     for cls in sorted(allowed))
    cls = b'magnet' if name.startswith('M') else b'test' if name == 'case1' else (
        b'tless_object_1' if name.startswith('tiny_') else b'LED')
    return (Record(1, 2, 1, 0x42c00000, cls), Record(3, 4, 2, 0x42bc0000, cls))


def wire(call_id, records):
    raw = b'HMOUT001' + struct.pack('<QQ', call_id, len(records))
    for record in records:
        raw += struct.pack('<iiiIQ', record.x, record.y, record.template_id,
                           record.score_bits, len(record.class_id)) + record.class_id
    return raw


def reference_wire(records, input_count=0):
    return b'SBMHASH1' + struct.pack('<IIQQ', 1, 0x01020304, input_count, len(records)) + wire(0, records)[24:]


def evidence():
    rows, comparisons = independent_schedule()
    outputs = {}
    for row in rows:
        data = wire(row['call_id'], records_for(row))
        name = 'outputs/call_%06d.bin' % row['call_id']
        outputs[name] = data
        internal = row['route'] not in ('legacy_default', 'explicit_default')
        row.update(output_file=name, output_bytes=len(data), output_sha256=hashlib.sha256(data).hexdigest(),
                   record_count=len(records_for(row)), api_wall_ms=0., has_internal_timing=internal,
                   internal_search_ms=0., internal_total_ms=0.)
    refs = {name: records_for(dict(input=name, stage='core')) for name in COMMON}
    return rows, comparisons, outputs, refs


class CorrectnessContract(unittest.TestCase):
    def test_literal_schedule_budget_boundaries_and_concurrent_archive_order(self):
        rows, comparisons = c.expected_correctness_schedule()
        self.assertEqual((len(rows), len(comparisons)), (2722, 1602))
        wanted, wanted_comparisons = independent_schedule()
        self.assertEqual(rows, wanted)
        self.assertEqual(comparisons, wanted_comparisons)
        self.assertEqual([(i, rows[i]['stage'], rows[i]['route']) for i in (0, 1024, 2586, 2692, 2708)],
                         [(0, 'core', 'oracle'), (1024, 'flags', 'all_flags'),
                          (2586, 'lifetime', 'oracle'), (2692, 'class_filter', 'filter'),
                          (2708, 'magnet_local', 'regression')])
        self.assertEqual([row['input'] for row in rows if row['route'] == 'concurrent' and row['flags'] == 127],
                         ['LED_1', 'case1', 'LED_2', 'LED_zero_mask', 'LED_larger_same_detector', 'LED_1',
                          'LED_1', 'LED_larger_same_detector', 'LED_zero_mask', 'LED_2', 'case1', 'LED_1'])

    def test_positive_archive_reference_and_full_matrix(self):
        rows, comparisons, outputs, refs = evidence()
        opened = []
        def read(name):
            opened.append(name)
            self.assertRegex(name, r'^outputs/call_[0-9]{6}\.bin$')
            return outputs[name]
        result = c.audit_correctness(rows, comparisons, read, refs)
        self.assertEqual(len(opened), 2722)
        for key, value in [('calls', 2722), ('comparisons', 1602), ('baseline_calls', 1376),
                           ('candidate_calls', 1346), ('v21_reference_bindings', 25),
                           ('full_ordered_equalities', 1602)]:
            self.assertEqual(result[key], value)

    def test_reference_literal_signed_fields_nul_and_score_bits(self):
        records = (Record(-2147483648, 2147483647, -3, 0x80000000, b'A\0B'),)
        self.assertEqual(c.decode_v21_reference(reference_wire(records)), records)
        self.assertEqual(c.decode_v21_reference(reference_wire(())), ())

    def test_general_trace_parses_both_vectors_but_reference_rejects_input(self):
        inputs = (Record(-7, 8, -9, 0xbf800000, b'in\0put'),)
        outputs = (Record(3, 4, 5, 0x3f800001, b'out'),)
        raw = (b'SBMHASH1'+struct.pack('<IIQQ', 1, 0x01020304, 1, 1)+
               wire(0, inputs)[24:]+wire(0, outputs)[24:])
        self.assertEqual(c.decode_v21_trace(raw), (inputs, outputs))
        with self.assertRaises(ValueError):
            c.decode_v21_reference(raw)
        with self.assertRaises(ValueError):
            c.decode_v21_trace(raw[:24]+struct.pack('<Q', 2)+raw[32:])

    def test_reference_rejects_truncation_extra_nonfinite_version_counts_and_limits(self):
        original = reference_wire((Record(-1, 2, 3, 0x3f800001, b'A\0B'),))
        mutations = [original[:size] for size in range(len(original))]
        mutations += [original+b'\0', b'wrongMAG'+original[8:],
                      original[:8]+struct.pack('<I', 2)+original[12:],
                      original[:12]+struct.pack('<I', 0x04030201)+original[16:],
                      reference_wire((), 1), original[:24]+struct.pack('<Q', 10000001)+original[32:],
                      original[:48]+struct.pack('<Q', 1048577)+original[56:]]
        for bits in (0x7f800000, 0xff800000, 0x7fc00001):
            mutations.append(original[:44]+struct.pack('<I', bits)+original[48:])
        for raw in mutations:
            with self.assertRaises(ValueError):
                c.decode_v21_reference(raw)
        for bad in (bytearray(original), None, 'bytes'):
            with self.assertRaises(ValueError):
                c.decode_v21_reference(bad)

    def test_rejects_schedule_fields_types_rows_order_and_comparison_pairings(self):
        rows, comparisons, outputs, refs = evidence()
        for field, value in [('call_id', True), ('stage', 'flags'), ('route', 'candidate'),
                             ('variant', HASH), ('input', 'heldout'), ('threads', 2),
                             ('flags', 127), ('pass', 1), ('repeat', 1), ('worker', 0), ('step', 1)]:
            changed = copy.deepcopy(rows);changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                c.audit_correctness(changed, comparisons, outputs.__getitem__, refs)
        for changed in (rows[:-1], rows+[rows[-1]], [rows[1], rows[0]]+rows[2:]):
            with self.assertRaises(ValueError):
                c.audit_correctness(changed, comparisons, outputs.__getitem__, refs)
        for field, value in [('comparison_id', True), ('actual_call_id', 2), ('expected_call_id', 3),
                             ('full_ordered_equal', 1), ('first_mismatch', 0)]:
            changed = copy.deepcopy(comparisons);changed[0][field] = value
            with self.assertRaises(ValueError):
                c.audit_correctness(rows, changed, outputs.__getitem__, refs)
        for changed in (comparisons[:-1], comparisons+[comparisons[-1]],
                        [comparisons[1], comparisons[0]]+comparisons[2:]):
            with self.assertRaises(ValueError):
                c.audit_correctness(rows, changed, outputs.__getitem__, refs)

    def test_rejects_clock_presence_nonfinite_negative_bool_and_extra_fields(self):
        rows, comparisons, outputs, refs = evidence()
        for clock in ('api_wall_ms', 'internal_search_ms', 'internal_total_ms'):
            for value in (True, '0', float('nan'), float('inf'), -1.):
                changed = copy.deepcopy(rows);changed[0][clock] = value
                with self.assertRaises(ValueError):
                    c.audit_correctness(changed, comparisons, outputs.__getitem__, refs)
        for row_id, field, value in [(0, 'has_internal_timing', False),
                                    (0, 'internal_search_ms', 1.),
                                    (2624, 'has_internal_timing', True),
                                    (2624, 'internal_total_ms', 1.),
                                    (0, 'unexpected', 1)]:
            changed = copy.deepcopy(rows);changed[row_id][field] = value
            with self.assertRaises(ValueError):
                c.audit_correctness(changed, comparisons, outputs.__getitem__, refs)

    def test_paths_hash_size_counts_and_missing_files_fail_without_noncanonical_read(self):
        rows, comparisons, outputs, refs = evidence()
        for field, value in [('output_file', '../secret.bmp'), ('output_file', 'outputs/call_000001.bin'),
                             ('output_sha256', '0'*64), ('output_bytes', False), ('record_count', 3)]:
            changed = copy.deepcopy(rows);changed[0][field] = value
            names = []
            def read(name):
                names.append(name)
                return outputs[name]
            with self.assertRaises(ValueError):
                c.audit_correctness(changed, comparisons, read, refs)
            self.assertTrue(all(name.startswith('outputs/call_') for name in names))
        del outputs[rows[-1]['output_file']]
        with self.assertRaises(ValueError):
            c.audit_correctness(rows, comparisons, outputs.__getitem__, refs)

    def changed_archive_rejected(self, rows, comparisons, outputs, refs, row_id, records):
        changed = copy.deepcopy(rows);archives = dict(outputs)
        raw = wire(row_id, records);name = changed[row_id]['output_file'];archives[name] = raw
        changed[row_id].update(output_bytes=len(raw), output_sha256=hashlib.sha256(raw).hexdigest(), record_count=len(records))
        with self.assertRaises(ValueError):
            c.audit_correctness(changed, comparisons, archives.__getitem__, refs)

    def test_records_fields_bits_order_length_and_duplicate_multiplicity(self):
        rows, comparisons, outputs, refs = evidence();original = records_for(rows[2])
        first = original[0]
        for field, value in [('x', first.x+1), ('y', first.y+1), ('template_id', first.template_id+1),
                             ('score_bits', first.score_bits^1), ('class_id', b'LED\0')]:
            values = dict(first.__dict__);values[field] = value
            self.changed_archive_rejected(rows, comparisons, outputs, refs, 2, (Record(**values), original[1]))
        for records in (original[::-1], original[:1], original+(first,)):
            self.changed_archive_rejected(rows, comparisons, outputs, refs, 2, records)

    def test_archive_call_identity_magic_truncation_and_extra_bytes_reject_after_rehash(self):
        rows, comparisons, outputs, refs = evidence()
        name = rows[2]['output_file'];raw = outputs[name]
        for replacement in (wire(3, records_for(rows[2])), b'wrongMAG'+raw[8:], raw[:-1], raw+b'\0'):
            changed = copy.deepcopy(rows);archives = dict(outputs);archives[name] = replacement
            changed[2].update(output_bytes=len(replacement), output_sha256=hashlib.sha256(replacement).hexdigest())
            with self.assertRaises(ValueError):
                c.audit_correctness(changed, comparisons, archives.__getitem__, refs)

    def test_reference_binding_detects_consistently_wrong_baseline_and_candidate(self):
        rows, comparisons, outputs, refs = evidence()
        refs = dict(refs);refs['LED_1'] = refs['LED_1'][::-1]
        with self.assertRaises(ValueError):
            c.audit_correctness(rows, comparisons, outputs.__getitem__, refs)
        for bad in ({}, dict(refs, extra=()), dict(refs, LED_1=list(refs['LED_1']))):
            with self.assertRaises(ValueError):
                c.audit_correctness(rows, comparisons, outputs.__getitem__, bad)

    def test_empty_negative_zero_and_full_mask_controls_are_independent(self):
        rows, comparisons, outputs, refs = evidence()
        for input_name, records in [('LED_zero_mask', records_for(rows[0])),
                                    ('LED_empty_candidates', records_for(rows[0])),
                                    ('synthetic_zero_maxima', ()),
                                    ('synthetic_zero_maxima', (Record(-3, -3, 0, 0x80000000, b'zero'),)),
                                    ('LED_full_mask', records_for(rows[0])[:1])]:
            changed = copy.deepcopy(rows);archives = dict(outputs)
            for row in changed:
                if row['input'] == input_name:
                    raw = wire(row['call_id'], records);archives[row['output_file']] = raw
                    row.update(output_bytes=len(raw), output_sha256=hashlib.sha256(raw).hexdigest(), record_count=len(records))
            with self.subTest(input=input_name), self.assertRaises(ValueError):
                c.audit_correctness(changed, comparisons, archives.__getitem__, refs)

    def test_class_filter_semantics_and_move_concurrent_routes_cannot_be_substituted(self):
        rows, comparisons, outputs, refs = evidence()
        for route, field, value in [('move_constructed', 'input', 'LED_2'),
                                    ('moved_from_reused', 'route', 'pre_move'),
                                    ('concurrent', 'threads', 4), ('concurrent', 'worker', 1)]:
            changed = copy.deepcopy(rows);row = next(x for x in changed if x['route'] == route);row[field] = value
            with self.assertRaises(ValueError):
                c.audit_correctness(changed, comparisons, outputs.__getitem__, refs)
        # Mutate both baseline/candidate unknown-filter outputs; native equality alone still passes.
        changed = copy.deepcopy(rows);archives = dict(outputs)
        for row in changed:
            if row['stage'] == 'class_filter' and row['step'] == 5:
                records = (Record(1, 2, 1, 0x42c00000, b'LED_A'),)
                raw = wire(row['call_id'], records);archives[row['output_file']] = raw
                row.update(output_bytes=len(raw), output_sha256=hashlib.sha256(raw).hexdigest(), record_count=1)
        with self.assertRaises(ValueError):
            c.audit_correctness(changed, comparisons, archives.__getitem__, refs)

    def test_two_class_outputs_must_match_the_identical_single_class_bank(self):
        rows, comparisons, outputs, refs = evidence()
        # All two-class invocations consistently omit one real record in each class.
        # Every native same-route equality, class domain and full-class subset still passes.
        changed = copy.deepcopy(rows);archives = dict(outputs)
        for row in changed:
            if row['input'] == 'LED_two_classes':
                records = tuple(record for record in records_for(row) if record.template_id == 1)
                raw = wire(row['call_id'], records);archives[row['output_file']] = raw
                row.update(output_bytes=len(raw), output_sha256=hashlib.sha256(raw).hexdigest(), record_count=len(records))
        with self.assertRaises(ValueError):
            c.audit_correctness(changed, comparisons, archives.__getitem__, refs)


if __name__ == '__main__':
    unittest.main()
