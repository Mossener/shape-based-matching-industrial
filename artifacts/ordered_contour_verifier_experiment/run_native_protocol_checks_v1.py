"""Malformed counted-token boundary checks against an already audited binary.

No rebuild, image or benchmark. Every native invocation is directly watched;
full huge-file/cumulative-output caps are not stress-tested by this suite.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
INHERITED = HERE.parent / 'rgb_stratified_features_experiment'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixtures():
    # Single defects where practical; all are literal supplied-graph records.
    base = 'Q1 77 3 0 0 0'
    return [
        ('negative_request_id', 'Q1 -1 3 0 0 0', 'UNSIGNED_DECIMAL'),
        ('overflow_request_id', 'Q1 18446744073709551616 3 0 0 0', 'UNSIGNED_OVERFLOW'),
        ('long_request_id', 'Q1 ' + '0' * 21 + ' 3 0 0 0', 'INTEGER_TOKEN_LIMIT'),
        ('negative_template_id', 'Q1 77 -1 0 0 0', 'UNSIGNED_DECIMAL'),
        ('template_bool_two', 'Q1 77 3 2 0 0', 'BOOLEAN_TOKEN'),
        ('template_bool_00', 'Q1 77 3 00 0 0', 'BOOLEAN_TOKEN'),
        ('sample_count_limit', 'Q1 77 3 0 9 0', 'COUNT_LIMIT'),
        ('scene_count_limit', 'Q1 77 3 0 0 17', 'COUNT_LIMIT'),
        ('negative_sample_id', 'Q1 77 3 0 1 0 -1 1', 'UNSIGNED_DECIMAL'),
        ('overflow_sample_id', 'Q1 77 3 0 1 0 18446744073709551616 1', 'UNSIGNED_OVERFLOW'),
        ('zero_weight', 'Q1 77 3 0 1 0 4 0', 'WEIGHT_NOT_POSITIVE'),
        ('negative_weight', 'Q1 77 3 0 1 0 4 -1', 'WEIGHT_DECIMAL'),
        ('floating_weight', 'Q1 77 3 0 1 0 4 1.0', 'WEIGHT_DECIMAL'),
        ('weight_token_limit', 'Q1 77 3 0 1 0 4 ' + '1' * 513, 'WEIGHT_TOKEN_LIMIT'),
        ('duplicate_sample', 'Q1 77 3 0 2 0 4 1 4 2', 'DUPLICATE_SAMPLE'),
        ('duplicate_unused_scene', 'Q1 77 3 0 0 2 7 0 0 0 7 0 0 0', 'DUPLICATE_SCENE_CHAIN'),
        ('unused_scene_bad_bool', 'Q1 77 3 0 0 1 7 2 0 0', 'BOOLEAN_TOKEN'),
        ('scene_pixel_count_limit', 'Q1 77 3 0 0 1 7 0 9 0', 'COUNT_LIMIT'),
        ('edge_count_limit', 'Q1 77 3 0 0 1 7 0 0 65', 'COUNT_LIMIT'),
        ('edge_capacity', 'Q1 77 3 0 0 1 7 0 0 1', 'EDGE_CAPACITY'),
        ('duplicate_unused_pixel', 'Q1 77 3 0 0 1 7 0 2 0 4 4', 'DUPLICATE_PIXEL'),
        ('negative_unused_pixel', 'Q1 77 3 0 0 1 7 0 1 0 -1', 'UNSIGNED_DECIMAL'),
        ('unknown_sample', 'Q1 77 3 0 1 1 4 1 7 0 1 1 8 5 8', 'UNKNOWN_EDGE_ENDPOINT'),
        ('unknown_pixel', 'Q1 77 3 0 1 1 4 1 7 0 1 1 8 4 9', 'UNKNOWN_EDGE_ENDPOINT'),
        ('duplicate_edge', 'Q1 77 3 0 2 1 4 1 5 1 7 0 1 2 8 4 8 4 8', 'DUPLICATE_EDGE'),
        ('missing_token', 'Q1 77', 'MISSING_TOKEN'),
        ('trailing_token', base + ' extra', 'EXTRA_TOKEN'),
        ('wrong_version', 'Q2 77 3 0 0 0', 'PROTOCOL_VERSION'),
        ('blank_line', '', 'EMPTY_REQUEST'),
        ('whitespace_line', ' \t\r\v\f', 'EMPTY_REQUEST'),
        ('nul_byte', base + '\x00', 'INPUT_CHARACTER'),
        ('nonascii_byte', base + '\x80', 'INPUT_CHARACTER'),
        ('line_limit', ' ' * 65537, 'LINE_LIMIT'),
    ]


def main():
    if len(sys.argv) != 3 or not re.fullmatch('[a-z][a-z0-9_]{0,80}', sys.argv[2]):
        raise SystemExit('usage: run_native_protocol_checks_v1.py audited_native_oracle_run fresh_directory')
    reference = (HERE / sys.argv[1]).resolve()
    assert reference.parent == HERE
    out = HERE / sys.argv[2]
    out.mkdir()
    p = load('_protocol_provenance', INHERITED / 'native_provenance.py')
    guard = load('_protocol_guard', INHERITED / 'execution_guard.py')
    receipt = json.loads((reference / 'receipt.json').read_bytes())
    assert receipt['passed'] and receipt['audit']['comparisons'] == 25024
    executable = Path(receipt['executable']['path'])
    source_names = ['native_ordered_match.hpp', 'native_ordered_match_batch_v1.cpp', 'NATIVE_BATCH_PROTOCOL_V1.json']
    before = [p.file_pin(Path(__file__).resolve()), p.file_pin(reference / 'receipt.json'),
              p.file_pin(INHERITED / 'execution_guard.py'), p.file_pin(INHERITED / 'native_provenance.py'),
              p.file_pin(Path(sys.executable)), receipt['executable']]
    for name in source_names:
        assert (HERE / name).read_bytes() == (reference / 'source' / name).read_bytes()
        before.append(p.file_pin(HERE / name))
    for pin in before + receipt['native_runtime_before']['files']:
        p.check_pin(pin)
    env = dict(os.environ)
    env['PATH'] = 'F:/mysys2/ucrt64/bin;' + env.get('PATH', '')
    result = dict(schema='native_protocol_checks_v1', passed=False, cases=[],
        reference=p.file_pin(reference / 'receipt.json'), input_pins=before,
        limitations=['No 64MiB whole-file or cumulative-output stress test',
                     'No allocation, OS I/O or work-counter-overflow fault injection',
                     'Per-invocation observed working-set watchdog, not OS allocation sandbox'])
    try:
        prefix = 'Q1 1 0 0 0 0\n'
        suffix = 'Q1 99 0 0 0 0\n'
        for index, (name, text, code) in enumerate(fixtures()):
            directory = out / f'{index:02d}_{name}'
            directory.mkdir()
            path = directory / 'request.txt'
            path.write_bytes((prefix + text + '\n' + suffix).encode('latin1'))
            observed = guard.run_guarded([str(executable), str(path)], env, directory,
                directory / 'payload', directory / 'execution', maximum_seconds=5,
                maximum_rss_bytes=536870912, maximum_output_bytes=1048576)
            lines = (directory / 'execution/stdout.txt').read_text(encoding='ascii').splitlines()
            assert observed['exit_code'] == 1 and observed['reason'] == 'process_exit_nonzero', (name, observed)
            assert len(lines) == 2 and lines[0].startswith('R1 1 0 '), (name, lines)
            error = lines[1].split()
            assert len(error) == 3 and error[0] == 'E1' and error[2] == code, (name, lines)
            assert error[1] in ('0', '77'), (name, lines)
            result['cases'].append(dict(name=name, detected=True, error=error,
                request=p.file_pin(path), guard=observed,
                stdout=p.file_pin(directory / 'execution/stdout.txt')))
        assert len(result['cases']) == 33
        result['passed'] = True
    except Exception as error:
        result['exception'] = repr(error)
        raise
    finally:
        try:
            for pin in before + receipt['native_runtime_before']['files']:
                p.check_pin(pin)
        except Exception as error:
            result['passed'] = False
            result['stability_exception'] = repr(error)
        (out / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(dict(passed=result['passed'], cases_completed=len(result['cases']))))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
