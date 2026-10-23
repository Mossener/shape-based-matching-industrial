"""Only nine metadata-whitelist tests for the current V2 preparer.

No estimate/hash mode and no real-input payload access. The test module and
preparer derive fixed roots from their workspace locations and execute there.
The source archive is a checked pre-execution copy, never an executed snapshot.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).absolute().parent
GUARD = HERE.parent / 'rgb_stratified_features_experiment/execution_guard.py'
SOURCE_NAMES = ('prepare_c0_payload_inventory_v2.py', 'INPUT_INVENTORY_DECISIONS_V2.json',
                'test_c0_inventory_whitelist_v2.py', 'C0_INPUT_PLAN_V1.json',
                'run_c0_inventory_whitelist_checks_v2.py')
CHILD = """import json, sys, unittest
flags = dict(optimize=sys.flags.optimize, ignore_environment=sys.flags.ignore_environment, debug=__debug__)
if flags != dict(optimize=0, ignore_environment=1, debug=True):
    raise ValueError('Expected assertions active and Python environment ignored')
suite = unittest.defaultTestLoader.loadTestsFromName('test_c0_inventory_whitelist_v2')
if suite.countTestCases() != 9:
    raise ValueError('Expected exactly nine whitelist tests')
result = unittest.TextTestRunner(verbosity=2).run(suite)
passed = result.wasSuccessful() and result.testsRun == 9 and not result.skipped
print(json.dumps(dict(passed=bool(passed), tests_run=result.testsRun, skipped=len(result.skipped),
                     failures=len(result.failures), errors=len(result.errors), python_flags=flags)), flush=True)
raise SystemExit(0 if passed else 1)
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(path):
    path = Path(path).absolute()
    size = path.stat().st_size
    require(size <= 8388608, 'Source/evidence pin file exceeds 8MiB')
    digest, count = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while True:
            block = stream.read(1048576)
            if not block:
                break
            count += len(block)
            require(count <= size and count <= 8388608, 'Source/evidence grew during pin')
            digest.update(block)
    require(count == size and path.stat().st_size == size, 'Source/evidence size changed')
    return dict(path=str(path), bytes=count, sha256=digest.hexdigest())


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def main():
    require(len(sys.argv) == 2 and re.fullmatch('[a-z][a-z0-9_]{0,80}', sys.argv[1]),
            'usage: run_c0_inventory_whitelist_checks_v2.py fresh_directory')
    out = HERE / sys.argv[1]
    require(not os.path.lexists(out), 'Fresh output directory required')
    out.mkdir()
    archive = out / 'source_archive'
    archive.mkdir()
    sources = [HERE / name for name in SOURCE_NAMES] + [GUARD, Path(sys.executable).absolute()]
    before = [pin(path) for path in sources]
    archive_pins = []
    for name in SOURCE_NAMES:
        source, target = HERE / name, archive / name
        data = source.read_bytes()
        source_pin = next(row for row in before if row['path'] == str(source))
        require(len(data) == source_pin['bytes'] and
                hashlib.sha256(data).hexdigest() == source_pin['sha256'], 'Source changed before archive')
        with target.open('xb') as stream:
            stream.write(data)
        archive_pins.append(pin(target))
    command = [sys.executable, '-E', '-B', '-c', CHILD]
    write(out / 'invocation.json', dict(schema='c0_whitelist_v2_guard_invocation_v1',
        command=command, cwd=str(HERE), source_pins_before=before, archive_pins=archive_pins,
        archive_semantics='Pre-execution exact copy; workspace sources execute and are rechecked afterward.',
        expected_tests=9, maximum_seconds=60, maximum_observed_peak_working_set_bytes=536870912,
        maximum_output_bytes=16777216, minimum_free_disk_bytes=83886080,
        input_payload_access=False, estimate_or_hash=False, native_calls=0))
    spec = importlib.util.spec_from_file_location('_whitelist_v2_guard', GUARD)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    observation = guard.run_guarded(command, dict(os.environ), HERE, out / 'payload',
        out / 'execution', maximum_seconds=60, maximum_rss_bytes=536870912,
        maximum_output_bytes=16777216, minimum_free_bytes=83886080)
    summary = None
    if observation['passed']:
        lines = (out / 'execution/stdout.txt').read_text(encoding='utf-8').splitlines()
        require(len(lines) == 1, 'Unexpected whitelist-test stdout')
        summary = json.loads(lines[0])
    after = [pin(path) for path in sources]
    archived_after = [pin(Path(row['path'])) for row in archive_pins]
    stable = before == after
    archive_stable = archive_pins == archived_after
    archive_equal = all(source['bytes'] == saved['bytes'] and source['sha256'] == saved['sha256']
                        for source, saved in zip(before[:len(SOURCE_NAMES)], archive_pins))
    expected = dict(passed=True, tests_run=9, skipped=0, failures=0, errors=0,
                    python_flags=dict(optimize=0, ignore_environment=1, debug=True))
    passed = observation['passed'] and summary == expected and stable and archive_stable and archive_equal
    write(out / 'receipt.json', dict(schema='c0_whitelist_v2_guard_receipt_v1', passed=bool(passed),
        guard=observation, summary=summary, source_pins_before=before, source_pins_after=after,
        sources_stable=stable, archive_pins=archive_pins, archive_pins_after=archived_after,
        archive_stable=archive_stable, archive_equal=archive_equal,
        actual_source_cwd=str(HERE), archive_is_executed_snapshot=False,
        real_input_payloads_opened=0, image_decodes=0, decompressions=0, native_calls=0,
        real_pixel_input_freeze=False, quality_claim=False, performance_claim=False))
    print(json.dumps(dict(passed=bool(passed), tests_run=None if summary is None else summary['tests_run'],
                         source_stable=stable, archive_equal=archive_equal)))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
