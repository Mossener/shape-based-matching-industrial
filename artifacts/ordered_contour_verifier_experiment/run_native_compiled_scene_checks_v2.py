"""Guarded synthetic compiled-scene v2 literal/full-v1-parity RED/GREEN.

Three single-TU compiler commands use the inherited 1GiB Windows job limit.
The foreground test process has a 60s/512MiB/64MiB watchdog. Exact frozen v1
sources, GCC dependencies and non-system static PE imports are pinned. OS and
dynamic imports, tool queries and metadata preflight keep inherited limits.
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
FROZEN = {
    'native_candidate_compatibility.hpp': '76ce2bffb0b452d7c5d56d2b4492221402af38f05b677cde89378c8d0361e89e',
    'native_edge_chains.hpp': 'bc39ca22c1c1f80273d8ddbafa57941f9b07a66ac11f10f46e58e9db2ca7ffbf',
    'native_ordered_match.hpp': '1236a5555c781f639be34beef95ea187d5e57de6d629df1c96805029bc8b85a3',
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def source_gate(p):
    pins = [p.file_pin(HERE / name) for name in FROZEN]
    for pin in pins:
        p.require(pin['sha256'] == FROZEN[Path(pin['path']).name], 'Frozen native v1 source changed')
    return pins


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('RED', 'GREEN'):
        raise SystemExit('usage: run_native_compiled_scene_checks_v2.py RED|GREEN fresh_directory')
    phase, name = sys.argv[1:]
    if not re.fullmatch('[a-z][a-z0-9_]{0,80}', name):
        raise SystemExit('simple fresh directory name required')
    out = HERE / name
    out.mkdir()
    result = dict(phase=phase, passed=False, image_decodes=0, matcher_calls=0,
                  real_payload_reads=0, performance_measured=False, production_promotion=False)
    try:
        p = load('_native_compiled_scene_provenance', INHERITED / 'native_provenance.py')
        guard = load('_native_compiled_scene_guard', INHERITED / 'execution_guard.py')
        frozen_pins = source_gate(p)
        snapshot = out / 'source'
        snapshot.mkdir()
        sources = [HERE / source_name for source_name in (
            'native_candidate_compiled_scene_v2.hpp', 'native_candidate_compiled_scene_v2_test.cpp',
            *FROZEN)]
        snapshots = []
        for source in sources:
            target = snapshot / source.name
            target.write_bytes(source.read_bytes())
            snapshots.append(target)
        env = dict(os.environ)
        env['PATH'] = str(COMPILER.parent) + ';' + env.get('PATH', '')
        tools, queries = p.compiler_tools(COMPILER, env)
        gmp = COMPILER.parent.parent
        libraries = [gmp / 'lib/libgmpxx.dll.a', gmp / 'lib/libgmp.dll.a']
        runtime = p.import_closure(tools + [gmp / 'bin/libgmp-10.dll', gmp / 'bin/libgmpxx-4.dll'],
                                   COMPILER, HERE / 'no_opencv_dependency', env)
        inputs = sources + snapshots + [Path(__file__).resolve(), HERE / 'native_compile_child_v1.py',
            HERE / 'NATIVE_COMPILED_SCENE_DECISIONS_V2.json', INHERITED / 'native_provenance.py',
            INHERITED / 'execution_guard.py', Path(sys.executable)] + tools + libraries
        before = [p.file_pin(path) for path in inputs]
        build = out / 'build'
        build.mkdir()
        payload = build / 'payload'
        flags = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror']
        test = snapshot / 'native_candidate_compiled_scene_v2_test.cpp'
        compiler = str(COMPILER)
        commands = [
            [compiler, *flags, '-M', '-MT', 'adapter.o', '-MF', str(payload / 'declared.d'), str(test)],
            [compiler, *flags, '-MD', '-MT', 'adapter.o', '-MF', str(payload / 'actual.d'),
             '-c', str(test), '-o', str(payload / 'adapter.o')],
            [compiler, str(payload / 'adapter.o'), '-lgmpxx', '-lgmp', '-o', str(payload / 'native_test.exe')],
        ]
        write(build / 'reservation.json', dict(
            commands=commands, cwd=str(snapshot), output=str(payload), job_memory_limit_bytes=1073741824,
            repository=str(ROOT), allowed_project_sources=list(map(str, snapshots)),
            provenance_source=str(INHERITED / 'native_provenance.py')))
        write(out / 'invocation.json', dict(phase=phase, inputs=before, frozen_v1=frozen_pins,
            compiler_tools_queries=queries, build_runtime_before=runtime, declared_commands=commands,
            synthetic_label_grids_only=True, expected_tests=28, exhaustive_candidate_comparisons=6144,
            solver_work_compared=True, independent_oracle=False,
            build_memory='Windows job committed memory 1GiB including GCC children; helper peak working set separately observed'))
        build_guard = guard.run_guarded(
            [sys.executable, '-E', '-B', str(HERE / 'native_compile_child_v1.py'), str(build / 'reservation.json')],
            env, snapshot, payload, build / 'execution', maximum_seconds=180,
            maximum_rss_bytes=1073741824, maximum_output_bytes=134217728)
        result['build_guard'] = build_guard
        child_path = payload / 'compiler_child_result.json'
        child = json.loads(child_path.read_bytes()) if child_path.is_file() else None
        result['compiler_child'] = child
        run_pins = []
        phase_passed = False
        if build_guard['passed']:
            p.require(child is not None and child['passed'] is True
                      and child['peak_job_committed_memory_bytes'] <= 1073741824, 'Compiler job failed')
            executable = payload / 'native_test.exe'
            result['executable'] = p.file_pin(executable)
            run_runtime = p.import_closure([executable], COMPILER, HERE / 'no_opencv_dependency', env)
            result['test_runtime_before'] = run_runtime
            run_pins = run_runtime['files']
            test_guard = guard.run_guarded([str(executable)], env, snapshot,
                out / 'test_payload', out / 'test_execution', maximum_seconds=60,
                maximum_rss_bytes=536870912, maximum_output_bytes=67108864)
            result['test_guard'] = test_guard
            stdout = (out / 'test_execution/stdout.txt').read_text(encoding='utf-8')
            summaries = re.findall(
                r'^NATIVE_COMPILED_SCENE_TEST_SUMMARY tests=(\d+) checks=(\d+) failures=(\d+) errors=(\d+)$',
                stdout, flags=re.MULTILINE)
            if len(summaries) == 1:
                counts = dict(zip(('tests', 'checks', 'failures', 'errors'), map(int, summaries[0])))
                result['summary'] = counts
                phase_passed = counts['tests'] == 28 and counts['checks'] > 0 and counts['errors'] == 0
                if phase == 'RED':
                    phase_passed &= (counts['failures'] > 0 and test_guard['exit_code'] == 1
                                     and test_guard['reason'] == 'process_exit_nonzero')
                else:
                    phase_passed &= counts['failures'] == 0 and test_guard['passed'] is True
            else:
                result['summary_error'] = 'Exactly one complete compiled-scene test summary required'
            p.check_pin(result['executable'])
        for pin in before + runtime['files'] + run_pins:
            p.check_pin(pin)
        if child is not None:
            for pin in child['compiler_dependency_pins'] or []:
                p.check_pin(pin)
        if any(source.read_bytes() != target.read_bytes() for source, target in zip(sources, snapshots)):
            raise ValueError('Executed source snapshot differs from current source')
        source_gate(p)
        result['source_pins_after'] = [p.file_pin(path) for path in inputs]
        result['passed'] = bool(phase_passed)
    except Exception as error:
        result['passed'] = False
        result['failure'] = repr(error)
        write(out / 'receipt.json', result)
        raise
    write(out / 'receipt.json', result)
    print(json.dumps(dict(passed=result['passed'], phase=phase, summary=result.get('summary'),
                         build_passed=result.get('build_guard', {}).get('passed', False))))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
