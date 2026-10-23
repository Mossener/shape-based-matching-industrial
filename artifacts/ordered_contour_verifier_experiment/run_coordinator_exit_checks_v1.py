"""Explicit coordinator-exit regression successor; original coordinators remain immutable.

The watchdog is reused from the published V31 experiment. Source snapshots are
the actual child working directory, and are checked again after execution.
An expected RED exit is evidence of missing behavior, never a GREEN success.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
GUARD = HERE.parent / 'rgb_stratified_features_experiment/execution_guard.py'


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: run_coordinator_exit_checks_v1.py coordinator_exit RED|GREEN fresh_directory_name')
    suite, phase, name = sys.argv[1:]
    if suite != 'coordinator_exit' or phase not in ('RED', 'GREEN'):
        raise SystemExit('unknown suite or phase')
    if not re.fullmatch('[a-z][a-z0-9_]{0,80}', name):
        raise SystemExit('output must be one simple fresh directory name')
    sources = ['run_native_oracle_checks_v1.py', 'test_native_coordinator_exit_v1.py']
    module = 'test_native_coordinator_exit_v1'
    output = HERE / name
    output.mkdir()
    snapshot = output / 'source'
    snapshot.mkdir()
    for source in sources:
        (snapshot / source).write_bytes((HERE / source).read_bytes())
    before = [pin(HERE / source) for source in sources]
    inputs = before + [pin(GUARD), pin(Path(__file__).resolve()), pin(Path(sys.executable))]
    command = [sys.executable, '-B', '-m', 'unittest', '-v', module]
    reservation = dict(schema='ordered_coordinator_exit_checks_v1', suite=suite, phase=phase,
                       source_pins=inputs, command=command, cwd=str(snapshot),
                       maximum_seconds=60, maximum_rss_bytes=536870912,
                       maximum_output_bytes=67108864,
                       monitoring='50ms observed process peak working set and directory sizes; not an OS allocation sandbox',
                       image_decodes=0, native_calls=0, production_promotion=False)
    (output / 'invocation.json').write_text(json.dumps(reservation, indent=2) + '\n', encoding='utf-8')
    spec = importlib.util.spec_from_file_location('_chain_checks_execution_guard', GUARD)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    execution = output / 'execution'
    result = guard.run_guarded(command, dict(os.environ), snapshot,
                              output / 'payload', execution,
                              maximum_seconds=60, maximum_rss_bytes=536870912,
                              maximum_output_bytes=67108864,
                              maximum_execution_bytes=67108864)
    stderr = (execution / 'stderr.txt').read_text(encoding='utf-8')
    count = re.search(r'Ran (\d+) tests? in ', stderr)
    failures = re.search(r'FAILED \(failures=(\d+)\)\s*$', stderr)
    stable = before == [pin(HERE / source) for source in sources]
    snapshots_equal = all((snapshot / source).read_bytes() == (HERE / source).read_bytes()
                          for source in sources)
    accepted = stable and snapshots_equal and count is not None
    if phase == 'RED':
        accepted = accepted and result['exit_code'] == 1 and result['reason'] == 'process_exit_nonzero'
        accepted = accepted and failures is not None and int(failures[1]) > 0
    else:
        accepted = accepted and result['passed'] is True and result['exit_code'] == 0
        accepted = accepted and stderr.rstrip().endswith('OK')
    receipt = dict(schema='ordered_coordinator_exit_checks_receipt_v1', phase=phase,
                   expected_phase_observed=bool(accepted),
                   unittest_methods=int(count[1]) if count else None,
                   assertion_failures=int(failures[1]) if failures else 0,
                   sources_unchanged=stable, executed_snapshots_equal=snapshots_equal,
                   snapshot_pins=[pin(snapshot / source) for source in sources],
                   invocation=pin(output / 'invocation.json'), guard=result,
                   outputs=[pin(execution / item) for item in ('stdout.txt', 'stderr.txt')],
                   scope='Mocked coordinator phases only; no compiler, solver, image, accuracy or performance evidence')
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(expected_phase_observed=bool(accepted), phase=phase,
                          tests=receipt['unittest_methods'], assertion_failures=receipt['assertion_failures'],
                          peak_rss_bytes=result['peak_rss_bytes'], reason=result['reason'])))
    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
