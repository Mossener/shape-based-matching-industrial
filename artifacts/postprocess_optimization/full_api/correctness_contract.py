"""Independent fixed whole-API audit using complete numeric archives only.

No file is read at import, and no native package is imported. A caller binds
the historic trace bytes and archive files to its reviewed filesystem pins.
This module validates schedules and complete ordered records independently
of native comparison booleans; it measures neither speed nor accuracy.
"""
from collections import Counter
import hashlib
import math
import re
import struct

from output_contract import Record, decode_output


COMMON25 = tuple(['LED_%d' % n for n in range(1, 9)] + ['case1'] +
                 ['tiny_s5_i%d' % n for n in (7, 70, 127, 215, 293, 353, 436, 493)] +
                 ['tiny_s2_i%d' % n for n in (3, 92, 153, 214, 295, 374, 446, 494)])
INPUTS = COMMON25 + ('LED_two_classes', 'synthetic_zero_maxima', 'LED_zero_mask',
                     'LED_full_mask', 'LED_partial_mask', 'LED_empty_candidates',
                     'LED_larger_same_detector')
BASE, CANDIDATE = 'exact_v11', 'index_reserve_copy_actual_match'
META_FIELDS = ('call_id', 'stage', 'route', 'variant', 'input', 'threads', 'flags',
               'pass', 'repeat', 'worker', 'step')
CLOCKS = ('api_wall_ms', 'internal_search_ms', 'internal_total_ms')
CALL_FIELDS = set(META_FIELDS) | {'output_file', 'output_bytes', 'record_count',
                                'output_sha256', 'has_internal_timing', *CLOCKS}
COMPARISON_FIELDS = {'comparison_id', 'actual_call_id', 'expected_call_id',
                     'full_ordered_equal', 'first_mismatch'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def expected_correctness_schedule():
    """Construct the frozen native archive schedule without reading its CSV."""
    calls, comparisons = [], []
    def add(stage, route, name, variant=BASE, flags=127, threads=4,
            pass_number=0, repeat=0, worker=-1, step=0):
        row = dict(call_id=len(calls), stage=stage, route=route, variant=variant,
                   input=name, flags=flags, threads=threads, repeat=repeat,
                   worker=worker, step=step)
        row['pass'] = pass_number
        calls.append(row)
        return row['call_id']
    def compare(actual, expected):
        comparisons.append(dict(comparison_id=len(comparisons), actual_call_id=actual,
                                expected_call_id=expected, full_ordered_equal=True,
                                first_mismatch=None))
    for pass_number, threads in enumerate((1, 4, 2, 4)):
        for flags in (63, 127):
            for name in INPUTS:
                oracle = add('core', 'oracle', name, flags=flags, threads=threads, pass_number=pass_number)
                compare(add('core', 'baseline_repeat', name, flags=flags, threads=threads,
                            pass_number=pass_number, repeat=1), oracle)
                for repeat in (0, 1):
                    compare(add('core', 'candidate', name, CANDIDATE, flags, threads,
                                pass_number, repeat), oracle)
    for flags in range(128):
        for index in (0, 27, 8, 1, 26, 31):
            oracle = add('flags', 'all_flags', INPUTS[index], flags=flags)
            compare(add('flags', 'all_flags', INPUTS[index], CANDIDATE, flags), oracle)
    for index in (28, 29, 30, 0):
        for flags in (0, 55, 127):
            oracle = add('flags', 'mask_restore', INPUTS[index], flags=flags)
            compare(add('flags', 'mask_restore', INPUTS[index], CANDIDATE, flags), oracle)
    oracle = add('flags', 'log_flag', INPUTS[0])
    compare(add('flags', 'log_flag', INPUTS[0], CANDIDATE), oracle)
    oracles = {127: [add('lifetime', 'oracle', name) for name in INPUTS]}
    for index, route in ((0, 'pre_move'), (8, 'move_constructed'), (1, 'moved_from_reused'),
                         (8, 'assignment_destination_populated'), (0, 'move_assigned'),
                         (31, 'assignment_source_reused')):
        compare(add('lifetime', route, INPUTS[index], CANDIDATE), oracles[127][index])
    for step, index in enumerate((0, 8, 1, 0)):
        oracle = add('lifetime', 'legacy_default', INPUTS[index], step=step)
        compare(add('lifetime', 'legacy_default', INPUTS[index], CANDIDATE, step=step), oracle)
        compare(add('lifetime', 'explicit_default', INPUTS[index], CANDIDATE, step=step), oracle)
    oracles[55] = [add('lifetime', 'oracle', name, flags=55) for name in INPUTS]
    forward = (0, 8, 1, 27, 31, 0)
    for worker, sequence in enumerate((forward, forward[::-1])):
        for step, index in enumerate(sequence):
            for flags in (127, 55):
                compare(add('lifetime', 'concurrent', INPUTS[index], CANDIDATE,
                            flags, 1, worker=worker, step=step), oracles[flags][index])
    for step in range(8):
        oracle = add('class_filter', 'filter', 'LED_two_classes', step=step)
        compare(add('class_filter', 'filter', 'LED_two_classes', CANDIDATE, step=step), oracle)
    for frame in range(1, 8):
        name = 'M%02d' % frame
        oracle = add('magnet_local', 'regression', name)
        compare(add('magnet_local', 'regression', name, CANDIDATE), oracle)
    need(len(calls) == 2722 and len(comparisons) == 1602, 'Internal fixed correctness budget differs')
    return calls, comparisons


def decode_v21_trace(raw):
    """Strict independent SBMHASH1 parser; preserves all signed fields/NUL bytes."""
    need(type(raw) is bytes and 32 <= len(raw) <= 1073741824, 'Invalid/truncated V21 trace bytes')
    need(raw[:8] == b'SBMHASH1', 'Unexpected V21 trace magic')
    version, endian, n, u = struct.unpack_from('<IIQQ', raw, 8)
    need(version == 1 and endian == 0x01020304, 'Unsupported V21 version/endian marker')
    need(n <= 10000000 and u <= 10000000 and n+u <= (len(raw)-32)//24,
         'V21 record count exceeds protocol or remaining minimum bytes')
    records, offset = [], 32
    for _ in range(n+u):
        need(len(raw)-offset >= 24, 'Truncated V21 fixed record')
        x, y, template_id, bits, length = struct.unpack_from('<iiiIQ', raw, offset)
        offset += 24
        need(bits & 0x7f800000 != 0x7f800000, 'Nonfinite V21 score')
        need(length <= 1048576 and length <= len(raw)-offset, 'Invalid/truncated V21 class bytes')
        records.append(Record(x, y, template_id, bits, raw[offset:offset+length]))
        offset += length
    need(offset == len(raw), 'Trailing V21 trace bytes')
    return tuple(records[:n]), tuple(records[n:])


def decode_v21_reference(raw):
    inputs, outputs = decode_v21_trace(raw)
    need(not inputs, 'Historical reference must contain zero input records')
    return outputs


def validate_record(record):
    need(type(record) is Record, 'Reference/output must contain exact Record values')
    for name in ('x', 'y', 'template_id'):
        value = getattr(record, name)
        need(type(value) is int and -(1 << 31) <= value < (1 << 31), 'Invalid signed32 record field: '+name)
    need(type(record.score_bits) is int and 0 <= record.score_bits < (1 << 32) and
         record.score_bits & 0x7f800000 != 0x7f800000, 'Invalid/nonfinite binary32 record score')
    need(type(record.class_id) is bytes, 'Class identifier must preserve complete bytes')


def class_domain(row):
    name = row['input']
    if name == 'LED_two_classes':
        classes = {b'LED_A', b'LED_B'}
        if row['stage'] == 'class_filter':
            classes = ({b'LED_A', b'LED_B'}, {b'LED_A'}, {b'LED_B'},
                       {b'LED_A', b'LED_B'}, {b'LED_A', b'LED_B'}, set(),
                       {b'LED_A'}, {b'LED_A'})[row['step']]
        return classes, 900
    if name == 'synthetic_zero_maxima':
        return {b'zero'}, 1
    if name == 'case1':
        return {b'test'}, 361
    if name.startswith('tiny_'):
        return {b'tless_object_1'}, 2212
    if name.startswith('M'):
        return {b'magnet'}, 3060
    return {b'LED'}, 900


def audit_correctness(rows, comparison_rows, read_output, reference_records):
    """Validate all 2722 archives and 1602 exact scheduled ordered comparisons.

    read_output is called exactly once per valid canonical output name. Its
    caller owns filesystem containment and historical SHA/origin binding.
    Zero correctness clocks are accepted; no speed ratio is computed here.
    """
    expected, expected_comparisons = expected_correctness_schedule()
    need(type(rows) is list and len(rows) == 2722, 'Correctness call count differs')
    need(type(comparison_rows) is list and len(comparison_rows) == 1602, 'Correctness comparison count differs')
    for row, wanted in zip(rows, expected):
        need(type(row) is dict and set(row) == CALL_FIELDS, 'Unexpected/missing correctness call fields')
        for field in META_FIELDS:
            need(type(row[field]) is type(wanted[field]) and row[field] == wanted[field],
                 'Fixed correctness schedule differs: '+field)
        need(type(row['output_file']) is str and row['output_file'] == 'outputs/call_%06d.bin' % row['call_id'],
             'Noncanonical correctness output path')
        for field in ('output_bytes', 'record_count'):
            need(type(row[field]) is int and 0 <= row[field] < (1 << 64), 'Invalid correctness '+field)
        need(type(row['output_sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['output_sha256']) is not None,
             'Canonical output SHA256 required')
        internal = row['route'] not in ('legacy_default', 'explicit_default')
        need(type(row['has_internal_timing']) is bool and row['has_internal_timing'] == internal,
             'Correctness internal timing presence differs')
        for clock in CLOCKS:
            value = row[clock]
            need(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                 'Invalid correctness clock: '+clock)
        need(row['internal_total_ms']+1e-8 >= row['internal_search_ms'], 'Internal search exceeds total clock')
        need(internal or (row['internal_search_ms'] == 0 and row['internal_total_ms'] == 0),
             'Legacy/default route fabricated internal timing')
    for row, wanted in zip(comparison_rows, expected_comparisons):
        need(type(row) is dict and set(row) == COMPARISON_FIELDS, 'Unexpected/missing comparison fields')
        for field in COMPARISON_FIELDS:
            need(type(row[field]) is type(wanted[field]) and row[field] == wanted[field],
                 'Fixed comparison pairing/result differs: '+field)
    need(type(reference_records) is dict and set(reference_records) == set(COMMON25),
         'Historical common25 reference membership differs')
    for records in reference_records.values():
        need(type(records) is tuple, 'Historical reference must be an ordered tuple')
        for record in records:
            validate_record(record)
    decoded, baseline_by_route, core_refs, filter_refs = {}, {}, {}, {}
    for row in rows:
        name, call_id = row['output_file'], row['call_id']
        try:
            raw = read_output(name)
        except (OSError, KeyError) as error:
            raise ValueError('Missing/unreadable correctness archive: '+name) from error
        need(type(raw) is bytes and len(raw) == row['output_bytes'], 'Correctness output byte length differs')
        need(hashlib.sha256(raw).hexdigest() == row['output_sha256'], 'Correctness output SHA256 differs')
        records = decode_output(raw, call_id).records
        need(len(records) == row['record_count'], 'Correctness decoded count differs')
        classes, templates = class_domain(row)
        for record in records:
            validate_record(record)
            need(record.class_id in classes and 0 <= record.template_id < templates,
                 'Output class/filter/template domain differs')
        if row['input'] in ('LED_zero_mask', 'LED_empty_candidates'):
            need(not records, 'Negative mask/threshold control is not empty')
        if row['input'] == 'synthetic_zero_maxima':
            need(bool(records) and all(record.score_bits == 0 for record in records),
                 'Actual zero-maxima control is empty or lacks exact positive-zero bits')
        decoded[call_id] = records
        if row['variant'] == BASE:
            if row['stage'] == 'class_filter':
                filter_refs[row['step']] = records
            else:
                key = (row['input'], row['flags'])
                if key in baseline_by_route:
                    need(records == baseline_by_route[key], 'Baseline output changed across thread/route/lifetime')
                else:
                    baseline_by_route[key] = records
            if row['stage'] == 'core' and row['route'] == 'oracle' and row['pass'] == 0 and row['flags'] == 127:
                core_refs[row['input']] = (call_id, records)
    for row in comparison_rows:
        need(decoded[row['actual_call_id']] == decoded[row['expected_call_id']],
             'Independent full ordered/score-bit comparison differs at comparison %d' % row['comparison_id'])
    for name in COMMON25:
        need(core_refs[name][1] == reference_records[name], 'Core pass0 flags127 differs from historical V21 reference: '+name)
    for flags in (0, 55, 63, 127):
        need(baseline_by_route[('LED_full_mask', flags)] == baseline_by_route[('LED_1', flags)],
             'Full-mask baseline differs from unmasked LED_1')
    full_two_classes = core_refs['LED_two_classes'][1]
    single_class = core_refs['LED_1'][1]
    class_expected = {cls: tuple(Record(record.x, record.y, record.template_id,
                                        record.score_bits, cls) for record in single_class)
                      for cls in (b'LED_A', b'LED_B')}
    combined = class_expected[b'LED_A']+class_expected[b'LED_B']
    def order_key(record):
        score = struct.unpack('<f', struct.pack('<I', record.score_bits))[0]
        return (-score, record.template_id, record.class_id, record.y, record.x)
    need(full_two_classes == tuple(sorted(combined, key=order_key)),
         'Two-class fixture differs from the identical renamed single-class bank')
    need(filter_refs[1] == class_expected[b'LED_A'] and filter_refs[2] == class_expected[b'LED_B'],
         'Single-class filters differ from the identical renamed single-class bank')
    for step in (0, 3, 4):
        need(filter_refs[step] == full_two_classes, 'All-class filter order changed complete output')
    for step in (6, 7):
        need(filter_refs[step] == filter_refs[1], 'Unknown/duplicate class filter changed single-class output')
    need(not filter_refs[5], 'Unknown-only class filter is not empty')
    stages = Counter(row['stage'] for row in rows)
    stage_comparisons = Counter(rows[row['actual_call_id']]['stage'] for row in comparison_rows)
    return dict(calls=len(rows), comparisons=len(comparison_rows),
                baseline_calls=sum(row['variant'] == BASE for row in rows),
                candidate_calls=sum(row['variant'] == CANDIDATE for row in rows),
                decoded_output_archives=len(decoded), full_ordered_equalities=len(comparison_rows),
                v21_reference_bindings=len(COMMON25),
                v21_reference_baseline_call_ids={name: core_refs[name][0] for name in COMMON25},
                stage_calls=dict(stages), stage_comparisons=dict(stage_comparisons),
                masked_negative_zero_and_class_controls=True,
                baseline_route_thread_lifetime_stability=True,
                dataset_image_bytes_opened=0, matcher_calls=0,
                speed_measurement=False, accuracy_improvement_claim=False)
