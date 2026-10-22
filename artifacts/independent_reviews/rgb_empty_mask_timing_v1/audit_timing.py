"""Audit frozen RGB empty-mask timing evidence using only the Python standard library.

Reads numeric evidence and pinned text sources. Never imports experiment code,
executes a subprocess/native binary, or opens images/template banks/raw archives.
Each invocation writes one new receipt directory and never overwrites evidence.
"""
import argparse
import csv
import hashlib
import json
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

OBJECTS = [1, 2, 5, 8, 12, 17]
VARIANTS = [('rgb_control', 'fallback'), ('rgb_control', 'fused'),
            ('rgb_empty_mask', 'fallback'), ('rgb_empty_mask', 'fused')]
FIELDS = ['object_id', 'scene', 'image', 'round', 'warmup', 'order', 'arm',
          'path', 'match_ms', 'external_call_ms', 'raw', 'selected', 'exact_own_reference']
ROOT_FREEZE_SHA256 = 'cf561362c82493ae87ce8a88fef7fbdf6d6967ada9b8ea2f223b31feb50be584'
ROOT_FREEZE_BYTES = 5841
TEXT_SUFFIXES = {'.json', '.csv', '.py', '.cpp', '.h', '.hpp', '.hxx',
                 '.txt', '.stdout', '.stderr', '.md'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nearest_rank(values, quantile):
    require(bool(values) and 0 < quantile <= 1, 'invalid quantile input')
    return sorted(values)[math.ceil(len(values) * quantile) - 1]


def file_pin(path):
    path = Path(path).resolve()
    require(path.suffix.lower() in TEXT_SUFFIXES, 'non-text read forbidden: ' + str(path))
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def verify_pin(pin):
    actual = file_pin(pin['path'])
    require(actual['bytes'] == pin['bytes'], 'pin size mismatch: ' + pin['path'])
    require(actual['sha256'] == pin['sha256'], 'pin hash mismatch: ' + pin['path'])
    return actual


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_csv(path, fields=None):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if fields is not None:
            require(reader.fieldnames == fields, 'CSV schema changed')
        rows = list(reader)
    require(all(None not in row and all(v is not None for v in row.values()) for row in rows),
            'ragged CSV row')
    return rows


def check_statistics(actual, expected, name):
    require(actual.keys() == expected.keys(), name + ' fields changed')
    for key, value in actual.items():
        # Parsing and division are IEEE binary64 in both producer and this audit.
        # A tiny tolerance accommodates serialized floating-point round trips.
        if isinstance(value, float):
            require(math.isfinite(float(expected[key])) and
                    math.isclose(value, expected[key], rel_tol=1e-12, abs_tol=1e-12),
                    name + ': ' + key + ' mismatch')
        else:
            require(value == expected[key], name + ': ' + key + ' mismatch')


def audit_numeric(rows, summary, objects, frames, references):
    expected_count = len(objects) * len(frames) * 8 * 4
    require(len(rows) == expected_count, 'incomplete or extra timing rows')
    fixed = dict(passed=1, stage='timing', objects=objects, unique_frames=len(frames),
        object_frame_combinations=len(objects)*len(frames), matcher_calls=expected_count,
        warmup_rounds=1, measured_rounds=7, exact_own_reference_every_call=1,
        decode_and_bank_load_excluded_from_external_call=1, paired_performance_benchmark=1)
    for key, value in fixed.items():
        require(summary.get(key) == value, 'summary ' + key + ' mismatch')
    samples = {v: {'match': [], 'external': []} for v in VARIANTS}
    paired = {path: {'match': [], 'external': []} for path in ['fallback', 'fused']}
    seen = set()
    cursor = 0
    for obj in objects:
        for scene, image in frames:
            for rnd in range(8):
                clocks = {}
                for order in range(4):
                    row = rows[cursor]; cursor += 1
                    variant = VARIANTS[(rnd + order) % 4]
                    expected = (obj, scene, image, rnd, int(rnd == 0), order, *variant)
                    actual = tuple(int(row[key]) for key in
                                   ['object_id','scene','image','round','warmup','order'])
                    actual += (row['arm'], row['path'])
                    require(actual == expected, 'schedule/rotation/warmup mismatch at row ' + str(cursor))
                    identity = (obj, scene, image, rnd, *variant)
                    require(identity not in seen, 'duplicate paired identity')
                    seen.add(identity)
                    require(row['exact_own_reference'] == '1', 'false own-reference flag')
                    ref_key = (obj, scene, image, variant[0])
                    require(ref_key in references, 'missing quality own-reference count')
                    counts = (int(row['raw']), int(row['selected']))
                    require(counts == references[ref_key], 'quality own-reference counts mismatch')
                    require(0 <= counts[1] <= counts[0], 'invalid raw/selected count')
                    match = float(row['match_ms']); external = float(row['external_call_ms'])
                    require(math.isfinite(match) and math.isfinite(external) and match > 0 and external > 0,
                            'nonfinite/nonpositive clock')
                    require(external + 1e-9 >= match, 'external interval shorter than matcher')
                    clocks[variant] = (match, external)
                    if rnd:
                        samples[variant]['match'].append(match)
                        samples[variant]['external'].append(external)
                if rnd:
                    for path in paired:
                        control = clocks[('rgb_control', path)]
                        treatment = clocks[('rgb_empty_mask', path)]
                        paired[path]['match'].append(treatment[0] / control[0])
                        paired[path]['external'].append(treatment[1] / control[1])
    variants = []
    for arm, path in VARIANTS:
        values = samples[(arm, path)]
        result = dict(arm=arm, path=path, samples=len(values['match']))
        for clock in ['match','external']:
            result[clock+'_median_ms'] = nearest_rank(values[clock], .5)
            result[clock+'_p95_ms'] = nearest_rank(values[clock], .95)
        variants.append(result)
    ratios = []
    for path, values in paired.items():
        result = dict(path=path, samples=len(values['match']))
        for clock in ['match','external']:
            result[clock+'_ratio_median'] = nearest_rank(values[clock], .5)
            result[clock+'_ratio_p95'] = nearest_rank(values[clock], .95)
        ratios.append(result)
    require(len(summary['variants']) == 4 and len(summary['paired_empty_mask_over_rgb']) == 2,
            'summary variants/pairs cardinality mismatch')
    for actual, expected in zip(variants, summary['variants']):
        check_statistics(actual, expected, 'variant')
    for actual, expected in zip(ratios, summary['paired_empty_mask_over_rgb']):
        check_statistics(actual, expected, 'paired ratio')
    return dict(rows=len(rows), formal_rows=sum(len(x['match']) for x in samples.values()),
                warmup_rows=len(rows)//8, paired_ratios=ratios, variants=variants,
                schedule_exact=True, all_recorded_own_reference_flags_one=True,
                all_counts_equal_quality_own_arm_reference=True)


def audit_evidence(experiment):
    experiment = Path(experiment).resolve()
    timing = experiment / 'run_quality_timing_v2'
    verified = {}

    def check(pin):
        actual = verify_pin(pin)
        verified[actual['path']] = actual
        return Path(actual['path'])

    root_pin = dict(path=str(timing/'QUALITY_STAGE_FREEZE.json'),
                    bytes=ROOT_FREEZE_BYTES, sha256=ROOT_FREEZE_SHA256)
    freeze = read_json(check(root_pin))
    require(freeze['stage'] == 'timing' and freeze['completed'] is True and
            freeze['native_exit_code'] == 0 and freeze['post_verification_passed'] is True,
            'timing stage incomplete')
    require(freeze['actual_matcher_calls'] == freeze['maximum_matcher_calls'] == 12288,
            'frozen timing call budget changed')
    for key in ['build_manifest','quality_inputs','selftest','previous_stage','reservation']:
        check(freeze[key])
    for pin in freeze['files'] + freeze['execution_files']:
        check(pin)
    summary = read_json(timing/'native/stage_summary.json')
    require(summary == freeze['summary'], 'stage summary differs from frozen embedded copy')
    execution = read_json(timing/'execution_provenance.json')
    for key in ['build_manifest','quality_inputs','selftest','previous_stage','reservation']:
        require(execution[key] == freeze[key], 'execution/freeze pin discrepancy: ' + key)
    require(execution['native_exit_code'] == 0 and execution['mode'] == 'timing' and
            execution['maximum_matcher_calls'] == 12288, 'execution timing contract changed')
    for pin in execution['script_pins']:
        check(pin)
    build = read_json(freeze['build_manifest']['path'])
    require(build['passed'] is True and build['target'] == 'quality', 'unaccepted build manifest')
    for pin in build['project_sources']:
        check(pin)
    # All private core/MIPP/helper text bytes are checked against their own source freeze,
    # in addition to their build project-source pins. No executable/DLL bytes are opened.
    private = read_json(experiment/'PRIVATE_SOURCE_FREEZE.json')
    for name, pin in private['files'].items():
        check(dict(path=str(experiment/'private_v11'/name), **pin))
    for name, pin in private['helpers'].items():
        check(dict(path=str(experiment/'frozen_helpers'/name),
                   bytes=pin['bytes'], sha256=pin['sha256']))
    inputs = read_json(freeze['quality_inputs']['path'])
    require(inputs['objects'] == OBJECTS, 'input object scope changed')
    require(len(inputs['development']) == 400, 'development frame count changed')
    frames = [(int(x['scene_id']), int(x['image_id'])) for x in inputs['development'] if x['timing']]
    require(len(frames) == len(set(frames)) == 64, 'timing frame schedule changed')
    protocol = read_json(experiment/'PROTOCOL.json')
    require(file_pin(experiment/'PROTOCOL.json')['sha256'] == inputs['protocol_sha256'],
            'protocol input pin mismatch')
    require(protocol['timing']['warmup_rounds'] == 1 and protocol['timing']['measured_rounds'] == 7
            and protocol['timing']['calls'] == 12288, 'protocol timing contract changed')
    previous_freeze = read_json(freeze['previous_stage']['path'])
    require(previous_freeze['stage'] == 'development' and previous_freeze['completed'] is True,
            'own-reference development incomplete')
    previous_native = Path(freeze['previous_stage']['path']).parent/'native'
    numeric_names = {'per_frame_metrics.csv', 'candidate_equality.csv', 'stage_summary.json'}
    selected_pins = {Path(x['path']).name: x for x in previous_freeze['files']
                     if Path(x['path']).name in numeric_names}
    require(set(selected_pins) == numeric_names, 'missing frozen quality numeric reference')
    for pin in selected_pins.values():
        check(pin)
    per_frame = read_csv(previous_native/'per_frame_metrics.csv')
    equality = read_csv(previous_native/'candidate_equality.csv')
    require(len(per_frame) == len(equality) == 4800, 'quality reference count changed')
    references = {}
    for row in per_frame:
        key = tuple(int(row[x]) for x in ['object_id','scene','image']) + (row['arm'],)
        require(key not in references, 'duplicate quality own-reference row')
        references[key] = (int(row['raw']), int(row['selected']))
    equality_keys = set()
    for row in equality:
        key = tuple(int(row[x]) for x in ['object_id','scene','image']) + (row['arm'],)
        require(key in references and key not in equality_keys, 'quality equality identity mismatch')
        equality_keys.add(key)
        require(int(row['fallback_count']) == int(row['fused_count']) == references[key][0],
                'quality fallback/fused/reference count mismatch')
        require(row['exact_order_fields_score_bits'] == row['reference_exact'] == '1',
                'quality recorded equality flag false')
    require(equality_keys == references.keys(), 'quality reference identity coverage mismatch')
    result = audit_numeric(read_csv(timing/'native/timing_samples.csv', FIELDS), summary,
                           OBJECTS, frames, references)
    result.update(passed=True, schema='independent_rgb_empty_mask_timing_v1',
        experiment=str(experiment), root_freeze_pin=root_pin,
        verified_pins=list(verified.values()), verified_pin_count=len(verified),
        project_source_pins_checked=len(build['project_sources']),
        execution_script_pins_checked=len(execution['script_pins']),
        quality_own_reference_rows=len(references), unique_frames=len(frames),
        object_frame_combinations=len(OBJECTS)*len(frames),
        quantile_method='nearest-rank: sorted_values[ceil(q*n)-1]; median is lower middle for even n',
        pairing_key=['object_id','scene','image','round','path'],
        ratio_direction='rgb_empty_mask / rgb_control',
        clock_semantics='CSV match_ms and external_call_ms audited separately; no clock remeasurement',
        limitations=[
            'Timing CSV stores durations, raw/selected counts, and a producer comparison flag; it does not archive complete timed-call raw/selected output fields or float32 score bits.',
            'This audit independently verifies counts and recorded flags, but cannot independently reproduce full timed-call output equality from timing CSV.',
            'No native execution, image decode, template-bank byte read, or quality raw-archive read. Runtime/executable closure bytes are not rehashed by this numeric/source audit.',
            'Source pins verify current text bytes against frozen build/script/private pins; no claim of independent runtime instrumentation or industrial generalization.'
        ], counters=dict(native_runs=0, native_compilations=0, matcher_calls=0,
                         dataset_image_decodes=0, dataset_image_reads=0,
                         template_bank_byte_reads=0, raw_archive_reads=0))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', type=Path,
                        default=Path(__file__).resolve().parents[2]/'rgb_empty_mask_experiment')
    parser.add_argument('--receipt-root', type=Path, default=Path(__file__).resolve().parent/'fresh')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = args.receipt_root / (stamp+'_'+uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    try:
        result = audit_evidence(args.experiment)
        result['created_utc'] = datetime.now(timezone.utc).isoformat()
        result['audit_source'] = file_pin(__file__)
        result['test_source'] = file_pin(Path(__file__).with_name('test_audit_timing.py'))
        result['python_version'] = sys.version
        name = 'receipt.json'
        status = 0
    except Exception as exc:
        result = dict(passed=False, error_type=type(exc).__name__, error=str(exc))
        name = 'failure.json'
        status = 1
    destination = output/name
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], receipt=str(destination)), ensure_ascii=False))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
