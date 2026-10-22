"""Apply the existing process watchdog to one reserved eighteen-bank scan.

The scanner keeps its own one-shot reservation and consumed marker. This
wrapper adds a separate launch marker before process creation, so a killed
child cannot leave a launch eligible for an accidental retry.
"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
sys.path.insert(0, str(EXPERIMENT))
import execution_guard
import native_provenance as pins

LIMITS = dict(maximum_seconds=1800, maximum_rss_bytes=1610612736,
              maximum_output_bytes=268435456, maximum_execution_bytes=33554432)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def fresh_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def launch(reservation, execution, receipt):
    reservation, execution, receipt = [Path(path).resolve() for path in (reservation, execution, receipt)]
    declaration = read(reservation)
    pins.require(declaration.get('schema') == 'rgb_stratified_geometry_reservation_v1' and
                 declaration.get('reserved') is True and
                 declaration.get('stage') == 'all_eighteen_bank_geometry', 'Reserved full scan required')
    output = Path(declaration['output']).resolve()
    marker = reservation.with_name(reservation.name + '.guard_launch.json')
    consumed = reservation.with_name(reservation.name + '.consumed.json')
    for path in (output, execution, receipt, marker, consumed):
        pins.require(not path.exists(), 'Fresh scan launch required: ' + str(path))
    for path in (output, execution, receipt, marker):
        pins.require(path.parent.is_dir(), 'Existing output parent required: ' + str(path))
    pins.require(not receipt.is_relative_to(output) and not receipt.is_relative_to(execution),
                 'Runner receipt must be outside child and watchdog directories')
    source = [pins.file_pin(path) for path in
              (Path(__file__), EXPERIMENT/'execution_guard.py', EXPERIMENT/'native_provenance.py',
               Path(sys.executable))]
    for value in declaration['source_pins'] + [declaration['input_freeze'], declaration['source_numeric_audit']]:
        pins.check_pin(value)
    command = [sys.executable, '-B', str(HERE/'run_geometry.py'), '--execute', '--reservation', str(reservation)]
    start = dict(schema='rgb_stratified_guarded_geometry_launch_v1', reserved=True,
        reservation=pins.file_pin(reservation), command=command, source_pins=source,
        execution=str(execution), output=str(output), receipt=str(receipt), limits=LIMITS)
    fresh_json(marker, start)
    guard = execution_guard.run_guarded(command, dict(os.environ), EXPERIMENT.parents[1],
                                        output, execution, **LIMITS)
    result = dict(schema='rgb_stratified_guarded_geometry_runner_v1', passed=False,
        launch=pins.file_pin(marker), guard=pins.file_pin(execution/'guard_receipt.json'),
        source_pins=source, native_executions=0, image_decodes=0, matcher_calls=0)
    try:
        pins.require(guard['passed'] is True, 'Geometry child/watchdog failed')
        for value in source + declaration['source_pins']:
            pins.check_pin(value)
        pins.check_pin(start['reservation'])
        child = read(output/'receipt.json')
        pins.require(child['passed'] is True and child['scanned_banks'] == 18 and
                     child['reservation'] == start['reservation'], 'Complete full-bank scan receipt required')
        for key in ('geometry_freeze', 'geometry_report', 'common_padding_plan'):
            pins.check_pin(child[key])
        result.update(passed=True, scanner_receipt=pins.file_pin(output/'receipt.json'),
                      geometry_freeze=child['geometry_freeze'])
    except (ValueError, KeyError, OSError) as error:
        result.update(error_type=type(error).__name__, error=str(error), failure_preserved=True)
    fresh_json(receipt, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reservation', type=Path, required=True)
    parser.add_argument('--execution', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    result = launch(args.reservation, args.execution, args.receipt)
    print(json.dumps(result))
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
