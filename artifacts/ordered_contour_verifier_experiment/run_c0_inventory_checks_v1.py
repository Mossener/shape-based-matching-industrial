"""Guarded C0 metadata tests, then separate exact-whitelist stat/hash phases.

Source modules use their workspace location to derive fixed authorized roots.
They execute there, with exact before/after pins and a pre-execution archival
copy. The archive is not described as the executed working directory.
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
    if len(sys.argv) != 3 or sys.argv[1] not in ('tests', 'estimate', 'hash') or not re.fullmatch(
            '[a-z][a-z0-9_]{0,59}', sys.argv[2]):
        raise SystemExit('usage: run_c0_inventory_checks_v1.py tests|estimate|hash fresh_name')
    mode, name = sys.argv[1:]
    out = HERE / name
    payload_name = name + '_payload'
    payload = HERE / payload_name
    if payload.exists():
        raise ValueError('Fresh payload directory required')
    out.mkdir()
    snapshot = out / 'source_archive'
    snapshot.mkdir()
    names = ['prepare_c0_payload_inventory_v1.py', 'INPUT_INVENTORY_DECISIONS_V1.json',
             'test_c0_inventory_whitelist_v1.py', 'C0_INPUT_PLAN_V1.json']
    sources = [HERE / item for item in names] + [Path(__file__), GUARD, Path(sys.executable)]
    before = [pin(source) for source in sources]
    for name in names:
        (snapshot / name).write_bytes((HERE / name).read_bytes())
    command = [sys.executable, '-E', '-B']
    if mode == 'tests':
        command += ['-m', 'unittest', '-v', 'test_c0_inventory_whitelist_v1']
    else:
        command += [str(HERE / 'prepare_c0_payload_inventory_v1.py'), mode, payload_name]
    invocation = dict(schema='c0_inventory_guard_invocation_v1', mode=mode,
        command=command, cwd=str(HERE), source_pins=before,
        source_archive_semantics='Before-execution exact copy; actual source executes in workspace, then rechecked.',
        maximum_seconds=180, maximum_observed_peak_working_set_bytes=536870912,
        maximum_output_bytes=16777216, minimum_free_disk_bytes=83886080,
        no_image_decode=True, no_decompress=True, no_native_calls=True)
    (out / 'invocation.json').write_text(json.dumps(invocation, indent=2) + '\n', encoding='utf-8')
    spec = importlib.util.spec_from_file_location('_c0_inventory_guard', GUARD)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    result = guard.run_guarded(command, dict(os.environ), HERE, payload, out / 'execution',
        maximum_seconds=180, maximum_rss_bytes=536870912, maximum_output_bytes=16777216,
        minimum_free_bytes=83886080)
    accepted = result['passed']
    observed = None
    if mode == 'tests':
        stderr = (out / 'execution/stderr.txt').read_text(encoding='utf-8')
        accepted = accepted and re.search(r'Ran 9 tests in ', stderr) is not None and stderr.rstrip().endswith('OK')
    elif accepted:
        observed = json.loads((payload / 'inventory.json').read_bytes())
        accepted = observed['file_count'] == 6094 and observed['sources_before_after_equal']
        accepted = accepted and observed['payload_hashing_complete'] == (mode == 'hash')
        accepted = accepted and observed['python_flags'] == dict(optimize=0, ignore_environment=1, debug=True)
        if mode == 'hash':
            accepted = accepted and observed['declared_pins_verified'] == 6082 and observed['newly_observed_pins'] == 12
    stable = before == [pin(source) for source in sources]
    archives_equal = all((snapshot / name).read_bytes() == (HERE / name).read_bytes() for name in names)
    accepted = accepted and stable and archives_equal
    receipt = dict(schema='c0_inventory_guard_receipt_v1', passed=bool(accepted), mode=mode,
        source_pins=before, sources_stable=stable, source_archive_equal=archives_equal,
        guard=result, inventory=pin(payload / 'inventory.json') if observed else None,
        real_pixel_input_freeze=False, no_image_decode=True, no_decompress=True,
        native_calls=0, quality_claim=False, performance_claim=False)
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=bool(accepted), mode=mode, peak_working_set_bytes=result['peak_rss_bytes'],
        elapsed_seconds=result['elapsed_seconds'], inventory=receipt['inventory'])))
    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
