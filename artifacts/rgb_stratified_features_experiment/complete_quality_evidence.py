"""Root evidence joins; never trains, matches, or computes independent metrics."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARMS = ['rgb_control', 'rgb_pooled_features', 'rgb_stratified_features']


def need(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def pin(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def check(value):
    need(pin(value['path']) == value, 'Pinned bytes changed: ' + value['path'])
    return value


def fresh(path, value):
    path = Path(path).resolve()
    need(path.is_relative_to(HERE) and path.parent.is_dir(), 'Existing local output parent required')
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def validate_result(report, stage):
    need(report.get('schema') == 'independent_three_arm_quality_audit_v1' and
         report.get('passed') is True and report.get('numeric_audit_passed') is True and
         report.get('scope') == 'quality_all_three_arms' and report.get('stage') == 'development' and
         report.get('development_stage') == stage and report.get('production_promotion') is False,
         'Complete independent three-arm development report required')
    need(report.get('unique_frames') == 400 and report.get('object_frame_pairs') == 2400 and
         report.get('arms') == ARMS, 'Independent quality scope differs')
    for field in ('raw_and_selected_numeric_equality', 'common_padding_C0_full_raw_exact',
                  'pilot_overlap_full_raw_exact', 'original_padding_C0_full_raw_exact'):
        need(report.get(field) is True, 'Independent exact comparison missing: ' + field)
    for field in ('matcher_calls', 'image_reads', 'image_decodes'):
        need(type(report.get(field)) is int and report[field] == 0, 'Independent activity differs')
    need(stage in report.get('input_pins', []), 'Independent report lacks its complete stage pin')
    control, candidate = (report['pooled'][arm]['allGT'] for arm in (ARMS[0], ARMS[2]))
    need((control['tp'], control['fp'], control['fn'], control['gt']) == (215, 42112, 185, 400),
         'Independent C0 baseline differs')
    passed = candidate['tp'] >= 215 and candidate['fp'] < 42112
    need(type(report.get('primary_accuracy_hypothesis_passed')) is bool and
         report['primary_accuracy_hypothesis_passed'] == passed and
         type(report['quality_gate'].get('passed')) is bool and
         report['quality_gate']['passed'] == passed, 'Independent B hypothesis differs')


def quality_acceptance(runner_path, output):
    runner_pin = pin(runner_path)
    runner = load(runner_path)
    need(runner.get('schema') == 'independent_three_arm_quality_runner_v2' and
         runner.get('passed') is True and runner.get('numeric_audit_passed') is True and
         runner.get('one_shot') is True and runner.get('production_promotion') is False,
         'Successful one-shot independent quality runner required')
    stage_pin = check(runner['development_stage'])
    for value in runner['evidence_files'] + [runner['reservation'], runner['consumed']]:
        check(value)
    need(runner['source_pins_before'] == runner['source_pins_after'], 'Audit sources changed')
    for value in runner['source_pins_after']:
        check(value)
    reservation = load(runner['reservation']['path'])
    consumed = load(runner['consumed']['path'])
    need(reservation.get('schema') == 'independent_three_arm_quality_reservation_v2' and
         reservation.get('runner_schema') == runner['schema'] and reservation.get('reserved') is True and
         consumed.get('schema') == reservation['schema'] and consumed.get('development_stage') == stage_pin and
         reservation['development_stage'] == stage_pin and
         reservation['source_pins'] == runner['source_pins_before'] and
         reservation['evidence'] == str(Path(runner_path).resolve().parent) and
         consumed['reservation'] == runner['reservation'] and consumed['consumed'] is True,
         'Independent reservation/consumption binding differs')
    guard = runner['guard']
    need(guard.get('passed') is True and guard.get('exit_code') == 0 and
         guard.get('reason') is None and guard.get('command') == runner['command'],
         'Independent watchdog failed or command differs')
    workers = [item for item in runner['source_pins_before']
               if Path(item['path']).name == 'quality_audit.py']
    need(len(workers) == 1 and Path(workers[0]['path']).parent == HERE / 'independent_quality_v2',
         'Exact independently tested v2 worker required')
    expected_command = [runner['source_pins_before'][-1]['path'], '-B', workers[0]['path'],
        '--stage-freeze', stage_pin['path'], '--stage-sha256', stage_pin['sha256'],
        '--stage-bytes', str(stage_pin['bytes']), '--output',
        str(Path(runner_path).resolve().parent / 'audit_output')]
    need(runner['command'] == expected_command, 'Actual independent worker CLI differs')
    guard_path = Path(runner_path).resolve().parent / 'execution' / 'guard_receipt.json'
    need(load(guard_path) == guard and guard['working_directory'] == str(HERE / 'independent_quality_v2'),
         'Actual independent watchdog receipt or working directory differs')
    for key, expected in dict(maximum_seconds=14400, maximum_rss_bytes=1610612736,
            maximum_output_bytes=536870912, maximum_execution_bytes=67108864,
            minimum_free_bytes=2147483648).items():
        need(guard[key] == expected, 'Independent watchdog resource declaration differs: ' + key)
    report_pin = check(runner['independent_audit'])
    need(report_pin['path'] == str(Path(runner_path).resolve().parent / 'audit_output' / 'result.json'),
         'Independent report output location differs')
    need(report_pin in runner['evidence_files'], 'Report absent from complete audit output inventory')
    report = load(report_pin['path'])
    validate_result(report, stage_pin)
    need(runner['primary_accuracy_hypothesis_passed'] == report['primary_accuracy_hypothesis_passed'],
         'Runner/report accuracy result differs')
    # Native wrappers already rechecked their actual inputs before and after
    # execution. Recheck the current build/runtime/output inventories here;
    # this joins execution evidence and is not an independent numeric oracle.
    sys.path.insert(0, str(HERE / 'quality'))
    import run_quality as native
    p, inputs, contract, _, _ = native._modules()
    source_manifest, _ = native.quality_builder._source_manifest()
    stage = load(stage_pin['path'])
    _, build_pin = native.build_gate(stage['build_manifest']['path'], p, source_manifest)
    input_pin = p.file_pin(HERE / 'quality' / 'QUALITY_INPUT_FREEZE.json')
    inputs.verify(input_pin['path'])
    for mode, directory in [('selftest', Path(stage['selftest']['path']).parent),
                            ('pilot', Path(stage['previous_stage']['path']).parent),
                            ('development', Path(stage_pin['path']).parent)]:
        native.stage_gate(directory, mode, build_pin, input_pin, contract, p)
    value = dict(schema='rgb_stratified_root_quality_acceptance_v1',
        accepted_independent_audit=True, scope='quality_all_three_arms', numeric_audit_passed=True,
        production_promotion=False,
        primary_accuracy_hypothesis_passed=report['primary_accuracy_hypothesis_passed'],
        development_stage=stage_pin, independent_audit=report_pin,
        independent_runner=runner_pin, independent_guard=pin(guard_path), source=pin(__file__),
        limitations=['Development evidence only; holdout remains sealed',
            'Python executable and local audit sources pinned; full transitive Python runtime is not attested',
            'No new training, image decode, matcher call or independent gradient regeneration'])
    check(runner_pin)
    fresh(output, value)
    return value


def timing_inputs(stage_path, output):
    stage_pin = pin(stage_path)
    stage = load(stage_path)
    need(stage.get('stage') == 'timing' and stage.get('completed') is True and
         stage.get('native_exit_code') == 0 and stage.get('actual_matcher_calls') == 29952 and
         stage.get('post_verification_passed') is True, 'Complete timing stage required')
    audit = stage['quality_audit']
    value = dict(schema='rgb_stratified_independent_timing_inputs_v1', timing_stage=stage_pin,
        development_stage=stage['previous_stage'], quality_inputs=stage['quality_inputs'],
        build_manifest=stage['build_manifest'], selftest=stage['selftest'],
        development_audit=audit['independent_audit'], quality_acceptance=audit['acceptance'])
    for name, item in value.items():
        if name != 'schema':
            check(item)
    acceptance = load(value['quality_acceptance']['path'])
    need(acceptance['development_stage'] == value['development_stage'] and
         acceptance['independent_audit'] == value['development_audit'] and
         acceptance['numeric_audit_passed'] is True and acceptance['production_promotion'] is False,
         'Timing and accepted quality binding differ')
    fresh(output, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='mode', required=True)
    quality = subs.add_parser('quality')
    quality.add_argument('--numeric-runner', type=Path, required=True)
    quality.add_argument('--output', type=Path, required=True)
    timing = subs.add_parser('timing-inputs')
    timing.add_argument('--timing-stage', type=Path, required=True)
    timing.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = (quality_acceptance(args.numeric_runner, args.output) if args.mode == 'quality' else
             timing_inputs(args.timing_stage, args.output))
    print(json.dumps(dict(passed=True, schema=value['schema'], output=str(args.output.resolve()),
        primary_accuracy_hypothesis_passed=value.get('primary_accuracy_hypothesis_passed'),
        matcher_calls=0, image_decodes=0)))


if __name__ == '__main__':
    main()
