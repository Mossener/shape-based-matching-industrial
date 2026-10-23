"""Fresh native supplied-graph build and RED/GREEN coordinator, Windows only.

Build: Windows job committed-memory cap including compiler children, parent
wall/output watchdog. Test: one process, observed peak-working-set/wall/output.
Exact project sources, actual GCC dependency files, declared tool/library pins
and non-system static PE imports are retained. OS and dynamic imports are not
fully attested; this is reproducible local evidence, not execution attestation.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INHERITED = HERE.parent / 'rgb_stratified_features_experiment'
COMPILER = Path('F:/mysys2/ucrt64/bin/g++.exe')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('RED', 'GREEN'):
        raise SystemExit('usage: run_native_core_checks_v1.py RED|GREEN fresh_directory')
    phase, name = sys.argv[1:]
    if not re.fullmatch('[a-z][a-z0-9_]{0,80}', name):
        raise SystemExit('simple fresh directory name required')
    out = HERE / name
    out.mkdir()
    snapshot = out / 'source'
    snapshot.mkdir()
    sources = [HERE / name for name in ('native_ordered_match.hpp', 'native_ordered_match_test.cpp')]
    snapshots = []
    for source in sources:
        target = snapshot / source.name
        target.write_bytes(source.read_bytes())
        snapshots.append(target)
    p = load('_native_core_provenance', INHERITED / 'native_provenance.py')
    guard = load('_native_core_guard', INHERITED / 'execution_guard.py')
    env = dict(os.environ)
    env['PATH'] = str(COMPILER.parent) + ';' + env.get('PATH', '')
    tools, tool_queries = p.compiler_tools(COMPILER, env)
    gmp = COMPILER.parent.parent
    libraries = [gmp / 'lib/libgmpxx.dll.a', gmp / 'lib/libgmp.dll.a']
    runtime = p.import_closure(tools + [gmp / 'bin/libgmp-10.dll', gmp / 'bin/libgmpxx-4.dll'],
                               COMPILER, HERE / 'no_opencv_dependency', env)
    inputs = sources + [Path(__file__).resolve(), HERE / 'native_compile_child_v1.py',
                        HERE / 'NATIVE_CORE_DECISIONS_V1.json', INHERITED / 'native_provenance.py',
                        INHERITED / 'execution_guard.py', Path(sys.executable)] + libraries
    before = [p.file_pin(path) for path in inputs]
    build = out / 'build'
    build.mkdir()
    payload = build / 'payload'
    flags = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror']
    test = snapshot / 'native_ordered_match_test.cpp'
    compiler = str(COMPILER)
    commands = [
        [compiler, *flags, '-M', '-MT', 'adapter.o', '-MF', str(payload / 'declared.d'), str(test)],
        [compiler, *flags, '-MD', '-MT', 'adapter.o', '-MF', str(payload / 'actual.d'),
         '-c', str(test), '-o', str(payload / 'adapter.o')],
        [compiler, str(payload / 'adapter.o'), '-lgmpxx', '-lgmp', '-o', str(payload / 'native_test.exe')],
    ]
    reservation = dict(commands=commands, cwd=str(snapshot), output=str(payload),
                       job_memory_limit_bytes=1073741824, repository=str(ROOT),
                       allowed_project_sources=list(map(str, snapshots)),
                       provenance_source=str(INHERITED / 'native_provenance.py'))
    write(build / 'reservation.json', reservation)
    write(out / 'invocation.json', dict(phase=phase, inputs=before,
          compiler_tools_queries=tool_queries, build_runtime_before=runtime,
          declared_commands=commands, synthetic_graphs_only=True,
          build_memory='Windows job committed memory 1GiB including GCC children; helper peak working set separately observed'))
    build_guard = guard.run_guarded(
        [sys.executable, '-B', str(HERE / 'native_compile_child_v1.py'), str(build / 'reservation.json')],
        env, snapshot, payload, build / 'execution', maximum_seconds=180,
        maximum_rss_bytes=1073741824, maximum_output_bytes=134217728)
    result = dict(phase=phase, passed=False, build_guard=build_guard)
    if build_guard['passed']:
        child = json.loads((payload / 'compiler_child_result.json').read_bytes())
        result['compiler_child'] = child
        if not child['passed'] or child['peak_job_committed_memory_bytes'] > 1073741824:
            raise ValueError('Compiler job failed')
        executable = payload / 'native_test.exe'
        result['executable'] = p.file_pin(executable)
        run_runtime = p.import_closure([executable], COMPILER, HERE / 'no_opencv_dependency', env)
        result['test_runtime_before'] = run_runtime
        test_guard = guard.run_guarded([str(executable)], env, snapshot,
            out / 'test_payload', out / 'test_execution', maximum_seconds=60,
            maximum_rss_bytes=536870912, maximum_output_bytes=67108864)
        result['test_guard'] = test_guard
        stdout = (out / 'test_execution/stdout.txt').read_text(encoding='utf-8')
        summary = re.search(r'NATIVE_TEST_SUMMARY tests=(\d+) checks=(\d+) failures=(\d+) errors=(\d+)', stdout)
        if summary:
            counts = dict(zip(('tests', 'checks', 'failures', 'errors'), map(int, summary.groups())))
            result['summary'] = counts
            result['passed'] = counts['tests'] == 40 and counts['errors'] == 0
            if phase == 'RED':
                result['passed'] &= counts['failures'] > 0 and test_guard['exit_code'] == 1 and test_guard['reason'] == 'process_exit_nonzero'
            else:
                result['passed'] &= counts['failures'] == 0 and test_guard['passed'] is True
        for row in run_runtime['files']:
            p.check_pin(row)
        p.check_pin(result['executable'])
        for row in child['compiler_dependency_pins']:
            p.check_pin(row)
    for row in before + runtime['files']:
        p.check_pin(row)
    if any(source.read_bytes() != target.read_bytes() for source, target in zip(sources, snapshots)):
        raise ValueError('Executed source snapshot differs from current source')
    result['source_pins_after'] = [p.file_pin(path) for path in inputs]
    result['image_decodes'] = 0
    result['matcher_calls'] = 0
    result['production_promotion'] = False
    write(out / 'receipt.json', result)
    print(json.dumps(dict(passed=result['passed'], phase=phase, summary=result.get('summary'),
                         build_passed=build_guard['passed'])))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
