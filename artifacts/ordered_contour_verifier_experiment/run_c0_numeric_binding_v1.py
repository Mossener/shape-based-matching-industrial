"""Guard only fixed synthetic projection tests; never open real payloads.

Archive is a before-execution copy, not the executed working directory.
The existing 50ms child watchdog bounds observed working set/wall/output;
it does not provide OS allocation isolation. All failed output is preserved.
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
    if len(sys.argv) != 3 or sys.argv[1] not in ('RED', 'GREEN') or not re.fullmatch(
            '[a-z][a-z0-9_]{0,59}', sys.argv[2]):
        raise SystemExit('usage: run_c0_numeric_binding_v1.py RED|GREEN fresh_name')
    mode, name = sys.argv[1:]
    out, payload = HERE / name, HERE / (name + '_unused_payload')
    if out.exists() or payload.exists():
        raise ValueError('Fresh output paths required')
    out.mkdir()
    archive = out / 'source_archive'
    archive.mkdir()
    names = ['c0_numeric_binding_v1.py', 'test_c0_numeric_binding_v1.py',
             'DECISIONS_c0_numeric_binding_v1.json']
    sources = [HERE / item for item in names] + [Path(__file__), GUARD, Path(sys.executable)]
    before = [pin(path) for path in sources]
    for item in names:
        (archive / item).write_bytes((HERE / item).read_bytes())
    command = [sys.executable, '-E', '-B', '-m', 'unittest', '-v', 'test_c0_numeric_binding_v1']
    invocation = dict(schema='c0_numeric_binding_guard_invocation_v1', mode=mode,
        command=command, cwd=str(HERE), source_pins=before,
        source_archive_semantics='Exact before-execution copies; actual source executes in workspace and is rechecked.',
        maximum_seconds=60, maximum_observed_peak_working_set_bytes=268435456,
        maximum_output_bytes=8388608, minimum_free_disk_bytes=83886080,
        input_scope='Only fixed in-memory synthetic projection dictionaries; no plan, inventory or real payload reads.')
    (out / 'invocation.json').write_text(json.dumps(invocation, indent=2) + '\n', encoding='utf-8')
    spec = importlib.util.spec_from_file_location('_c0_numeric_binding_guard', GUARD)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    result = guard.run_guarded(command, dict(os.environ), HERE, payload, out / 'execution',
        maximum_seconds=60, maximum_rss_bytes=268435456, maximum_output_bytes=8388608,
        minimum_free_bytes=83886080)
    stderr = (out / 'execution/stderr.txt').read_text(encoding='utf-8')
    count = re.search(r'Ran 28 tests in ', stderr)
    failures = re.search(r'FAILED \(failures=([1-9][0-9]*)\)\s*$', stderr)
    if mode == 'RED':
        accepted = (result['exit_code'] == 1 and result['reason'] == 'process_exit_nonzero'
                    and count is not None and failures is not None)
    else:
        accepted = result['passed'] and count is not None and stderr.rstrip().endswith('OK')
    stable = before == [pin(path) for path in sources]
    archive_equal = all((archive / item).read_bytes() == (HERE / item).read_bytes() for item in names)
    accepted = bool(accepted and stable and archive_equal)
    receipt = dict(schema='c0_numeric_binding_guard_receipt_v1', mode=mode, passed=accepted,
        source_pins=before, sources_stable=stable, source_archive_equal=archive_equal,
        expected_test_methods=28, observed_failure_count=int(failures[1]) if failures else 0,
        guard=result, real_payload_reads=0, image_reads=0, dataset_index_reads=0,
        native_calls=0, quality_claim=False, performance_claim=False,
        production_promotion=False)
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=accepted, mode=mode, peak_working_set_bytes=result['peak_rss_bytes'],
                         elapsed_seconds=result['elapsed_seconds'])))
    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
