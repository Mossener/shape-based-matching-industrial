"""Re-audit retained native outputs with explicitly active Python assertions.

No compilation or native solver invocation. Original runs remain unchanged.
The child ignores Python environment options and records its actual flags.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition, message):
    if not condition:
        raise ValueError(message)


def child(root, output):
    require(__debug__ and sys.flags.optimize == 0 and sys.flags.ignore_environment == 1,
            'Active assertions and -E are required')
    output.mkdir()
    reference = root / 'native_oracle_green_v1'
    protocol = root / 'native_protocol_green_v1'
    p = load('_safe_native_pins', root.parent / 'rgb_stratified_features_experiment/native_provenance.py')
    receipt = json.loads((reference / 'receipt.json').read_bytes())
    require(receipt['passed'] and receipt['sources_stable'], 'Original native run failed')
    sys.path.insert(0, str(reference / 'source'))
    fixture = load('_safe_native_fixture_audit', reference / 'source/native_oracle_fixtures_v1.py')
    paths = [reference / 'source' / name for name in
             ('native_oracle_fixtures_v1.py', 'weighted_ordered_match.py', 'independent_tiny_oracle.py')]
    paths += [reference / 'fixtures' / name for name in ('generation.json', 'requests.txt', 'expected.jsonl')]
    paths += [reference / 'receipt.json', reference / 'native_execution/stdout.txt', protocol / 'receipt.json',
              root / 'run_native_protocol_checks_v1.py', Path(__file__).resolve()]
    pins = [p.file_pin(path) for path in paths]
    fixture.audit(reference / 'fixtures', reference / 'native_execution/stdout.txt', output / 'audit')
    old = json.loads((protocol / 'receipt.json').read_bytes())
    protocol_source = load('_safe_native_protocol_source', root / 'run_native_protocol_checks_v1.py')
    literals = protocol_source.fixtures()
    require(old['passed'] and len(old['cases']) == len(literals) == 33, 'Incomplete protocol evidence')
    before_id = {'negative_request_id', 'overflow_request_id', 'long_request_id', 'wrong_version',
                 'blank_line', 'whitespace_line', 'nul_byte', 'nonascii_byte', 'line_limit'}
    for row, (name, text, code) in zip(old['cases'], literals):
        require(row['name'] == name, 'Protocol order/name mismatch')
        directory = Path(row['request']['path']).parent
        p.check_pin(row['request'])
        p.check_pin(row['stdout'])
        require(Path(row['request']['path']).read_bytes() ==
                ('Q1 1 0 0 0 0\n' + text + '\nQ1 99 0 0 0 0\n').encode('latin1'), 'Changed literal request')
        lines = Path(row['stdout']['path']).read_text(encoding='ascii').splitlines()
        require(len(lines) == 2, 'Protocol produced missing/extra lines')
        identity, template_id, result, counters = fixture.parse_response(lines[0])
        require(identity == 1 and template_id == 0 and result.numerator == 0 and
                result.independent_numerator == 0 and result.total_weight == 0 and
                result.case is None and result.witness == () and not any(counters.values()),
                'Incorrect prefix R1')
        expected_error = ['E1', '0' if name in before_id else '77', code]
        require(lines[1].split() == expected_error and row['error'] == expected_error,
                'Incorrect exact error identity/code')
        guard = json.loads((directory / 'execution/guard_receipt.json').read_bytes())
        require(guard == row['guard'] and guard['exit_code'] == 1 and
                guard['reason'] == 'process_exit_nonzero', 'Invalid native guard evidence')
    for pin in pins:
        p.check_pin(pin)
    result = dict(schema='native_assertion_safe_reaudit_v1', passed=True,
        native_comparisons=25024, protocol_saved_sequences_checked=33,
        protocol_exact_error_ids_and_full_prefix_checked=True,
        python_flags=dict(optimize=sys.flags.optimize, ignore_environment=sys.flags.ignore_environment,
                          debug=__debug__), inputs=pins,
        audit=p.file_pin(output / 'audit/audit.json'), native_calls=0, image_decodes=0,
        quality_claim=False, performance_claim=False)
    (output / 'acceptance.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, native_comparisons=25024, protocol_saved_sequences=33,
                         python_flags=result['python_flags'])))


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--child':
        child(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
        return 0
    require(len(sys.argv) == 2 and re.fullmatch('[a-z][a-z0-9_]{0,80}', sys.argv[1]),
            'usage: run_native_assertion_acceptance_v1.py fresh_directory')
    out = HERE / sys.argv[1]
    out.mkdir()
    snapshot = out / 'source'
    snapshot.mkdir()
    source = snapshot / Path(__file__).name
    source.write_bytes(Path(__file__).read_bytes())
    inherited = HERE.parent / 'rgb_stratified_features_experiment'
    p = load('_safe_acceptance_provenance', inherited / 'native_provenance.py')
    guard = load('_safe_acceptance_guard', inherited / 'execution_guard.py')
    pins = [p.file_pin(path) for path in (Path(__file__), source, Path(sys.executable),
            inherited / 'native_provenance.py', inherited / 'execution_guard.py')]
    command = [sys.executable, '-E', '-B', str(source), '--child', str(HERE), str(out)]
    # Only the payload below is produced by child; snapshot/root receipts sit
    # outside the directory byte quota and are separately bounded small files.
    payload = out / 'payload'
    command[-1] = str(payload)
    observation = guard.run_guarded(command, dict(os.environ), snapshot, payload,
        out / 'execution', maximum_seconds=60, maximum_rss_bytes=536870912,
        maximum_output_bytes=67108864)
    # Child writes in payload, so explicitly bound and pin those outputs too.
    require(sum(path.stat().st_size for path in payload.rglob('*') if path.is_file()) < 1048576,
            'Supplemental audit output too large')
    result = dict(schema='native_assertion_safe_acceptance_coordinator_v1', passed=False,
                  command=command, guard=observation, inputs=pins)
    if observation['passed']:
        acceptance = json.loads((payload / 'acceptance.json').read_bytes())
        result['passed'] = acceptance['passed'] and acceptance['python_flags'] == dict(
            optimize=0, ignore_environment=1, debug=True)
        result['acceptance'] = p.file_pin(payload / 'acceptance.json')
    for pin in pins:
        p.check_pin(pin)
    (out / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], python_assertions_explicitly_active=True)))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
