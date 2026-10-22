"""Join the complete numeric audit with the original training execution evidence.

This is the root execution acceptance, not a second sampling oracle. It does
not run native code, decode images or repeat the expensive candidate audit.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_training as training


def require(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    return training.p.file_pin(Path(path).resolve())


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def same(actual, expected, message):
    require(json.dumps(actual, sort_keys=True, allow_nan=False) ==
            json.dumps(expected, sort_keys=True, allow_nan=False), message)


PHASES = [
    ('begin_pose', 0, 0, 0, 0, 0, 0, 0),
    ('collector_call', 0, 0, 0, 0, 0, 0, 0),
    ('sampler_call', 0, 0, 0, 0, 0, 1, 0),
    ('sampler_call', 0, 1, 0, 0, 0, 1, 1),
    ('write_complete_pool', 0, 1, 0, 0, 0, 1, 2),
    ('collector_call', 1, 1, 0, 1, 2, 1, 2),
    ('sampler_call', 1, 0, 0, 1, 2, 2, 2),
    ('sampler_call', 1, 1, 0, 1, 2, 2, 3),
    ('write_complete_pool', 1, 1, 0, 1, 2, 2, 4),
    ('pose_complete', 1, 1, 1, 2, 4, 2, 4),
]


def verify_progress(rows, summary, poses=20736):
    """Check every pre-call observation, including failed-template poses."""
    previous = [0, 0]
    count = 0
    for count, row in enumerate(rows, 1):
        pose, index = divmod(count - 1, 10)
        require(pose < poses, 'extra progress row')
        phase, level, arm, completed, pools, layers, collectors, samplers = PHASES[index]
        expected = dict(phase=phase, pose_id=pose, level=level, arm=arm,
                        completed_poses=pose + completed, written_pools=2 * pose + pools,
                        written_layer_rows=4 * pose + layers, written_attempt_rows=2 * pose,
                        rgb_decodes=pose // 48 + 1, mask_decodes=pose // 48 + 1,
                        collector_calls_started=2 * pose + collectors,
                        sampler_calls_started=4 * pose + samplers, incomplete=False)
        require(set(row) == set(expected) | {'reserved_logical_bytes', 'reserved_physical_bytes'},
                'progress schema differs')
        same({key: row[key] for key in expected}, expected, 'progress phase/count differs')
        for i, (name, ceiling, total) in enumerate([
                ('reserved_logical_bytes', 32 * 1024**3, summary['logical_payload_bytes']),
                ('reserved_physical_bytes', 4 * 1024**3, summary['physical_bytes_before_summary'])]):
            value = row[name]
            require(type(value) is int and previous[i] <= value <= min(ceiling, total),
                    'progress byte accounting differs')
            previous[i] = value
    require(count == 10 * poses, 'missing progress rows')
    return {'rows': count, 'poses': poses, 'collector_calls_observed': 2 * poses,
            'sampler_calls_observed': 4 * poses,
            'limitation': 'Native observations, not an independent attestation of native calls'}


def jsonl(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        for line in stream:
            require(bool(line.strip()), 'blank JSONL row')
            yield json.loads(line)


def accept(numeric_runner_path, output):
    require(not output.exists(), 'fresh acceptance required')
    numeric_runner = load(numeric_runner_path)
    require(numeric_runner['passed'] is True and numeric_runner['guard']['passed'] is True,
            'complete numeric audit runner required')
    training.p.check_pin(numeric_runner['audit_receipt'])
    numeric = load(numeric_runner['audit_receipt']['path'])
    require(numeric.get('numeric_training_audit_passed') is True and
            numeric.get('public_numeric_training_complete') is True and
            numeric.get('comparison_feasible') is True and numeric.get('literal_only') is False,
            'full public numeric audit required')
    training.p.check_pin(numeric_runner['runner_provenance'])
    provenance = load(numeric_runner['runner_provenance']['path'])
    require(provenance['passed'] is True and provenance['mode'] == 'train',
            'normally completed original training required')
    directory = Path(provenance['command'][provenance['command'].index('--output') + 1]).resolve()
    expected_command = [provenance['command'][0], '--mode', 'train', '--output', str(directory),
                        '--inputs', str(HERE / 'TRAINING_INPUT_FREEZE.json')]
    same(provenance['command'], expected_command, 'training command scope differs')
    for key in ('build_manifest', 'input_freeze', 'reservation', 'guard'):
        training.p.check_pin(provenance[key])
    build = training.build_gate(Path(provenance['build_manifest']['path']))
    require(expected_command[0] == build['executable']['path'], 'training executable differs')
    _, image_pins = training.inputs_gate(True)
    same(image_pins, provenance['image_pins'], 'complete training image allowlist changed')
    reservation = load(provenance['reservation']['path'])
    require(reservation['passed'] is False, 'initial reservation must remain incomplete')
    same({key: value for key, value in reservation.items() if key != 'passed'},
         {key: provenance[key] for key in reservation if key != 'passed'},
         'original one-shot reservation differs')
    for value in provenance['script_pins']:
        training.p.check_pin(value)
    maps = {}
    for value in provenance['files']:
        path = Path(value['path']).resolve()
        require(path.is_relative_to(directory), 'output pin escaped training directory')
        training.p.check_pin(value)
        name = path.relative_to(directory).as_posix()
        require(name not in maps, 'duplicate training output pin')
        maps[name] = {key: value[key] for key in ('bytes', 'sha256')}
    same(numeric['output_pins_before'], maps, 'numeric input map differs from original training')
    same(numeric['output_pins_after'], maps, 'numeric final map differs from original training')
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob('*') if path.is_file()}
    require(actual == set(maps) and 'native_failure.json' not in actual,
            'complete training inventory differs')
    summary = load(directory / 'training_summary.json')
    same(summary, numeric['summary'], 'numeric/native summary differs')
    same(summary, provenance['summary'], 'runner/native summary differs')
    progress = verify_progress(jsonl(directory / 'progress.jsonl'), summary)
    limits = dict(maximum_seconds=5400, maximum_rss_bytes=1610612736,
                        maximum_output_bytes=4294967296, minimum_free_bytes=8589934592,
                        maximum_execution_bytes=67108864)
    guard = load(provenance['guard']['path'])
    require(guard['passed'] is True and guard['started'] is True and
            guard['exit_code'] == 0 and guard['reason'] is None, 'training guard failure')
    for key, value in limits.items():
        same(guard[key], value, 'training guard resource limit changed')
    require(0 <= guard['elapsed_seconds'] < 5400 and
            0 < guard['peak_rss_bytes'] <= 1610612736, 'training guard wall/RSS ceiling')
    execution = Path(provenance['guard']['path']).parent
    same(guard['command'], expected_command, 'guard/native command differs')
    telemetry = list(jsonl(execution / 'guard_telemetry.jsonl'))
    require(telemetry, 'missing guard telemetry')
    same(telemetry[-1], load(execution / 'guard_latest.json'), 'final guard snapshot differs')
    previous_time = previous_samples = previous_peak = previous_bytes = 0
    total_bytes = sum(value['bytes'] for value in maps.values())
    for row in telemetry:
        require(row['pid'] == guard['pid'] and
                previous_time <= row['elapsed_seconds'] <= guard['elapsed_seconds'] and
                previous_samples < row['samples'] <= guard['samples'] and
                previous_peak <= row['peak_rss_bytes'] <= guard['peak_rss_bytes'] and
                previous_bytes <= row['native_output_bytes'] <= total_bytes and
                row['execution_bytes'] <= 67108864 and
                row['native_output_bytes'] + row['execution_bytes'] <= 4294967296,
                'training guard telemetry differs')
        previous_time, previous_samples = row['elapsed_seconds'], row['samples']
        previous_peak, previous_bytes = row['peak_rss_bytes'], row['native_output_bytes']
    same(guard['native_output_bytes'], total_bytes, 'training guard final bytes differ')
    modules = training.verify_modules(directory, build)
    require(provenance['physical_bytes'] == numeric['physical_bytes'] == total_bytes,
            'physical accounting differs')
    require(provenance['logical_bytes'] == numeric['logical_bytes'], 'logical accounting differs')
    return dict(schema='rgb_stratified_training_execution_acceptance_v1',
                real_training_accepted=True, source_runtime_accepted=True,
                numeric_audit_passed=True, quality_tested=False, production_promotion=False,
                independent_runner=pin(numeric_runner_path),
                independent_audit=numeric_runner['audit_receipt'],
                training_provenance=pin(numeric_runner['runner_provenance']['path']),
                successful_templates=numeric['successful_templates'],
                progress=progress, physical_bytes=total_bytes,
                logical_bytes=numeric['logical_bytes'], modules=modules,
                source=pin(__file__), image_byte_files_checked=len(image_pins),
                native_calls=0, image_decodes=0, heldout_image_reads=0,
                limitations=numeric['limitations'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--numeric-runner', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = accept(args.numeric_runner.resolve(), args.output.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, receipt=str(args.output.resolve()),
                         quality_tested=False, native_calls=0, image_decodes=0)))


if __name__ == '__main__':
    main()
