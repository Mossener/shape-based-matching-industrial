"""Fresh synthetic-Mat native pixel RED/GREEN coordinator, Windows only.

One translation unit includes the exact frozen V11 core and the snapshotted
pixel adapter/test. Three compiler commands run inside the inherited Windows
job committed-memory limit and parent wall/output watchdog. Native tests use
one guarded process. Static PE imports and actual GCC dependencies are pinned;
OS/dynamic imports and metadata preflight retain their documented limits.
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
FROZEN = INHERITED / 'control_v11'
COMPILER = Path('F:/mysys2/ucrt64/bin/g++.exe')
OPENCV = Path('D:/opencv-4.12.0')
FROZEN_MANIFEST_PIN = dict(
    bytes=4447,
    sha256='dad88a95b576f428b8a05cccb7663cfac5594847c93e31dd26a9f1e29dc5927f')
BUNDLE = ('// Synthetic Mat entry tests; exact frozen V11 core, one translation unit.\n'
          '#include "line2Dup.cpp"\n'
          '#include "native_pixel_operator.cpp"\n'
          '#include "native_pixel_operator_test.cpp"\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def source_gate(p):
    manifest_path = INHERITED / 'TRAINING_SOURCE_FREEZE.json'
    manifest_pin = p.file_pin(manifest_path)
    p.require({key: manifest_pin[key] for key in ('bytes', 'sha256')} == FROZEN_MANIFEST_PIN,
              'Frozen V11 manifest changed')
    manifest = json.loads(manifest_path.read_bytes())
    p.require(manifest['schema'] == 'rgb_stratified_exact_v11_training_source_v1'
              and manifest['git_revision'] == 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
              and manifest['sole_core_delta'] is None, 'Exact original V11 required')
    expected = manifest['files']
    actual = {path.relative_to(FROZEN).as_posix()
              for path in FROZEN.rglob('*') if path.is_file()}
    p.require(actual == set(expected), 'Frozen V11 source member set changed')
    pins = []
    for name, expected_pin in expected.items():
        path = FROZEN / name
        p.require(not path.is_symlink() and path.resolve().is_relative_to(FROZEN.resolve()),
                  'Frozen source path escapes control_v11')
        pin = p.file_pin(path)
        p.require({key: pin[key] for key in ('bytes', 'sha256')} == expected_pin,
                  'Frozen V11 source changed: ' + name)
        pins.append(pin)
    p.check_pin(manifest_pin)
    return manifest_pin, pins


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('RED', 'GREEN'):
        raise SystemExit('usage: run_native_pixel_operator_checks_v1.py RED|GREEN fresh_directory')
    phase, name = sys.argv[1:]
    if not re.fullmatch('[a-z][a-z0-9_]{0,80}', name):
        raise SystemExit('simple fresh directory name required')
    out = HERE / name
    out.mkdir()
    result = dict(phase=phase, passed=False, image_decodes=0, matcher_calls=0,
                  real_payload_reads=0, production_promotion=False)
    try:
        p = load('_native_pixel_provenance', INHERITED / 'native_provenance.py')
        guard = load('_native_pixel_guard', INHERITED / 'execution_guard.py')
        manifest_pin, frozen_pins = source_gate(p)
        frozen_sources = [Path(pin['path']) for pin in frozen_pins]
        snapshot = out / 'source'
        snapshot.mkdir()
        sources = [HERE / source_name for source_name in (
            'native_pixel_operator.hpp', 'native_pixel_operator.cpp',
            'native_pixel_operator_test.cpp')]
        snapshots = []
        for source in sources:
            target = snapshot / source.name
            target.write_bytes(source.read_bytes())
            snapshots.append(target)
        bundle = snapshot / 'bundle.cpp'
        bundle.write_bytes(BUNDLE.encode('utf-8'))
        snapshots.append(bundle)
        env = dict(os.environ)
        env['PATH'] = str(COMPILER.parent) + ';' + str(OPENCV / 'build/bin') + ';' + env.get('PATH', '')
        tools, tool_queries = p.compiler_tools(COMPILER, env)
        libraries = [OPENCV / 'build/lib/libopencv_world4120.dll.a']
        runtime = p.import_closure(tools + [Path(sys.executable), OPENCV / 'build/bin/libopencv_world4120.dll'],
                                   COMPILER, OPENCV, env)
        inputs = sources + snapshots + frozen_sources + [
            Path(__file__).resolve(), HERE / 'native_compile_child_v1.py',
            HERE / 'NATIVE_PIXEL_OPERATOR_DECISIONS_V1.json',
            INHERITED / 'TRAINING_SOURCE_FREEZE.json', INHERITED / 'native_provenance.py',
            INHERITED / 'execution_guard.py', Path(sys.executable)] + tools + libraries
        before = [p.file_pin(path) for path in inputs]
        build = out / 'build'
        build.mkdir()
        payload = build / 'payload'
        flags = ['-std=c++17', '-O3', '-mssse3', '-msse4.1', '-fopenmp', '-Wall', '-Wextra',
                 '-Wno-sign-compare', '-Wno-unused-function', '-I' + str(FROZEN),
                 '-I' + str(FROZEN / 'MIPP'), '-I' + str(OPENCV / 'build')]
        # Frozen line2Dup.h includes highgui, which includes imgcodecs/videoio
        # declarations. These include paths do not call their decode APIs.
        flags += ['-I' + str(OPENCV / 'modules' / module / 'include')
                  for module in ('core', 'imgproc', 'highgui', 'imgcodecs', 'videoio')]
        compiler = str(COMPILER)
        commands = [
            [compiler, *flags, '-M', '-MT', 'adapter.o', '-MF', str(payload / 'declared.d'), str(bundle)],
            [compiler, *flags, '-MD', '-MT', 'adapter.o', '-MF', str(payload / 'actual.d'),
             '-c', str(bundle), '-o', str(payload / 'adapter.o')],
            [compiler, '-fopenmp', str(payload / 'adapter.o'), *map(str, libraries),
             '-o', str(payload / 'native_test.exe')],
        ]
        reservation = dict(commands=commands, cwd=str(snapshot), output=str(payload),
                           job_memory_limit_bytes=1073741824, repository=str(ROOT),
                           allowed_project_sources=list(map(str, snapshots + frozen_sources)),
                           provenance_source=str(INHERITED / 'native_provenance.py'))
        write(build / 'reservation.json', reservation)
        write(out / 'invocation.json', dict(
            phase=phase, inputs=before, frozen_manifest=manifest_pin,
            frozen_core_sources=frozen_pins, compiler_tools_queries=tool_queries,
            build_runtime_before=runtime, declared_commands=commands,
            synthetic_mats_only=True, translation_units=1, compiler_commands=3,
            build_memory='Windows job committed memory 1GiB including GCC children; helper peak working set separately observed',
            limitation='Metadata/tool queries and static PE import inspection occur before the guarded compiler/test child'))
        build_guard = guard.run_guarded(
            [sys.executable, '-B', str(HERE / 'native_compile_child_v1.py'), str(build / 'reservation.json')],
            env, snapshot, payload, build / 'execution', maximum_seconds=180,
            maximum_rss_bytes=1073741824, maximum_output_bytes=134217728)
        result['build_guard'] = build_guard
        child_result_path = payload / 'compiler_child_result.json'
        child = json.loads(child_result_path.read_bytes()) if child_result_path.is_file() else None
        result['compiler_child'] = child
        runtime_after = []
        phase_passed = False
        if build_guard['passed']:
            p.require(child is not None and child['passed'] is True
                      and child['peak_job_committed_memory_bytes'] <= 1073741824,
                      'Compiler job failed')
            executable = payload / 'native_test.exe'
            result['executable'] = p.file_pin(executable)
            run_runtime = p.import_closure([executable], COMPILER, OPENCV, env)
            result['test_runtime_before'] = run_runtime
            runtime_after = run_runtime['files']
            test_guard = guard.run_guarded([str(executable)], env, snapshot,
                out / 'test_payload', out / 'test_execution', maximum_seconds=60,
                maximum_rss_bytes=536870912, maximum_output_bytes=67108864)
            result['test_guard'] = test_guard
            stdout = (out / 'test_execution/stdout.txt').read_text(encoding='utf-8')
            summaries = re.findall(
                r'^NATIVE_PIXEL_OPERATOR_TEST_SUMMARY tests=(\d+) checks=(\d+) failures=(\d+) errors=(\d+)$',
                stdout, flags=re.MULTILINE)
            if len(summaries) == 1:
                counts = dict(zip(('tests', 'checks', 'failures', 'errors'), map(int, summaries[0])))
                result['summary'] = counts
                phase_passed = counts['tests'] == 22 and counts['checks'] > 0 and counts['errors'] == 0
                if phase == 'RED':
                    phase_passed &= (counts['failures'] > 0 and test_guard['exit_code'] == 1
                                     and test_guard['reason'] == 'process_exit_nonzero')
                else:
                    phase_passed &= counts['failures'] == 0 and test_guard['passed'] is True
            else:
                result['summary_error'] = 'Exactly one complete pixel test summary required'
            p.check_pin(result['executable'])
        for row in before + runtime['files'] + runtime_after:
            p.check_pin(row)
        if child is not None:
            for row in child['compiler_dependency_pins'] or []:
                p.check_pin(row)
        if any(source.read_bytes() != target.read_bytes() for source, target in zip(sources, snapshots)):
            raise ValueError('Executed source snapshot differs from current source')
        p.require(bundle.read_bytes() == BUNDLE.encode('utf-8'), 'Executed bundle changed')
        source_gate(p)
        result['source_pins_after'] = [p.file_pin(path) for path in inputs]
        result['frozen_source_count'] = len(frozen_pins)
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
