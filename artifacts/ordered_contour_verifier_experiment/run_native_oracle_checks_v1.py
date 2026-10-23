"""Sequential guarded fixture generation, native build/run and exact audit.

The compiler job has a committed-memory cap including children; the individual
generator, native driver and auditor have observed working-set/wall/output
watchdogs. This is not an OS RSS sandbox or a matching speed benchmark.
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
    if len(sys.argv) != 2 or not re.fullmatch('[a-z][a-z0-9_]{0,80}', sys.argv[1]):
        raise SystemExit('usage: run_native_oracle_checks_v1.py fresh_directory')
    out = HERE / sys.argv[1]
    out.mkdir()
    snapshot = out / 'source'
    snapshot.mkdir()
    names = ['native_ordered_match.hpp', 'native_ordered_match_batch_v1.cpp',
             'native_oracle_fixtures_v1.py', 'independent_tiny_oracle.py',
             'weighted_ordered_match.py', 'NATIVE_BATCH_PROTOCOL_V1.json']
    for name in names:
        (snapshot / name).write_bytes((HERE / name).read_bytes())
    p = load('_native_oracle_provenance', INHERITED / 'native_provenance.py')
    guard = load('_native_oracle_guard', INHERITED / 'execution_guard.py')
    env = dict(os.environ)
    env['PATH'] = str(COMPILER.parent) + ';' + env.get('PATH', '')
    tools, queries = p.compiler_tools(COMPILER, env)
    gmp = COMPILER.parent.parent
    libraries = [gmp / 'lib/libgmpxx.dll.a', gmp / 'lib/libgmp.dll.a']
    build_runtime = p.import_closure(tools + [gmp / 'bin/libgmp-10.dll', gmp / 'bin/libgmpxx-4.dll'],
                                   COMPILER, HERE / 'no_opencv_dependency', env)
    inputs = [HERE / name for name in names] + [Path(__file__).resolve(),
        HERE / 'native_compile_child_v1.py', INHERITED / 'native_provenance.py',
        INHERITED / 'execution_guard.py', Path(sys.executable)] + libraries
    before = [p.file_pin(path) for path in inputs]
    result = dict(schema='native_ordered_oracle_checks_v1', passed=False,
                  image_decodes=0, matcher_calls=0, quality_claim=False, performance_claim=False,
                  production_promotion=False)
    write(out / 'invocation.json', dict(source_pins=before, compiler_tools_queries=queries,
        build_runtime_before=build_runtime, synthetic_graphs_only=True,
        per_child_limits=dict(seconds=60, observed_peak_working_set_bytes=536870912,
                              combined_output_bytes=67108864),
        compiler_limits=dict(seconds=180, job_committed_memory_bytes=1073741824,
                             helper_peak_working_set_bytes=1073741824, output_bytes=134217728),
        memory_semantics='Observed per-process working set; compiler job committed memory includes GCC children. No aggregate RSS claim.',
        provenance_semantics='Actual GCC dependencies and declared non-system static PE imports; OS/dynamic imports are not fully attested.'))
    runtime = None
    child = None
    try:
        fixture_command = [sys.executable, '-B', str(snapshot / 'native_oracle_fixtures_v1.py'),
                           'generate', str(out / 'fixtures')]
        result['generation_guard'] = guard.run_guarded(fixture_command, env, snapshot,
            out / 'fixtures', out / 'generation_execution', maximum_seconds=60,
            maximum_rss_bytes=536870912, maximum_output_bytes=67108864)
        if not result['generation_guard']['passed']:
            return 1
        generation = json.loads((out / 'fixtures/generation.json').read_bytes())
        if generation['comparisons'] != 25024:
            raise ValueError('Incomplete fixture domain')
        fixture_pins = [p.file_pin(out / 'fixtures' / name)
                        for name in ('generation.json', 'requests.txt', 'expected.jsonl')]
        result['fixture_pins'] = fixture_pins
        build = out / 'build'
        build.mkdir()
        payload = build / 'payload'
        flags = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror']
        test = snapshot / 'native_ordered_match_batch_v1.cpp'
        commands = [
            [str(COMPILER), *flags, '-M', '-MT', 'adapter.o', '-MF', str(payload / 'declared.d'), str(test)],
            [str(COMPILER), *flags, '-MD', '-MT', 'adapter.o', '-MF', str(payload / 'actual.d'),
             '-c', str(test), '-o', str(payload / 'adapter.o')],
            [str(COMPILER), str(payload / 'adapter.o'), '-lgmpxx', '-lgmp', '-o', str(payload / 'native_batch.exe')]]
        write(build / 'reservation.json', dict(commands=commands, cwd=str(snapshot), output=str(payload),
            job_memory_limit_bytes=1073741824, repository=str(ROOT),
            allowed_project_sources=[str(snapshot / name) for name in names[:2]],
            provenance_source=str(INHERITED / 'native_provenance.py')))
        result['build_guard'] = guard.run_guarded([sys.executable, '-B',
            str(HERE / 'native_compile_child_v1.py'), str(build / 'reservation.json')],
            env, snapshot, payload, build / 'execution', maximum_seconds=180,
            maximum_rss_bytes=1073741824, maximum_output_bytes=134217728)
        if not result['build_guard']['passed']:
            return 1
        child = json.loads((payload / 'compiler_child_result.json').read_bytes())
        result['compiler_child'] = child
        if not child['passed'] or child['peak_job_committed_memory_bytes'] > 1073741824:
            raise ValueError('Compiler job failed')
        executable = payload / 'native_batch.exe'
        result['executable'] = p.file_pin(executable)
        runtime = p.import_closure([executable], COMPILER, HERE / 'no_opencv_dependency', env)
        result['native_runtime_before'] = runtime
        result['native_guard'] = guard.run_guarded([str(executable), str(out / 'fixtures/requests.txt')],
            env, snapshot, out / 'native_payload', out / 'native_execution', maximum_seconds=60,
            maximum_rss_bytes=536870912, maximum_output_bytes=67108864)
        if not result['native_guard']['passed']:
            return 1
        responses = out / 'native_execution/stdout.txt'
        response_pin = p.file_pin(responses)
        result['audit_guard'] = guard.run_guarded([sys.executable, '-B',
            str(snapshot / 'native_oracle_fixtures_v1.py'), 'audit', str(out / 'fixtures'),
            str(responses), str(out / 'audit')], env, snapshot, out / 'audit', out / 'audit_execution',
            maximum_seconds=60, maximum_rss_bytes=536870912, maximum_output_bytes=67108864)
        if not result['audit_guard']['passed']:
            return 1
        audit = json.loads((out / 'audit/audit.json').read_bytes())
        result['audit'] = audit
        for row in fixture_pins + [response_pin, result['executable']]:
            p.check_pin(row)
        result['passed'] = audit['passed'] and audit['comparisons'] == 25024
    except Exception as error:
        result['exception'] = repr(error)
        raise
    finally:
        try:
            for row in before + build_runtime['files']:
                p.check_pin(row)
            if runtime:
                for row in runtime['files']:
                    p.check_pin(row)
            if child:
                for row in child['compiler_dependency_pins']:
                    p.check_pin(row)
            if any((HERE / name).read_bytes() != (snapshot / name).read_bytes() for name in names):
                raise ValueError('Source snapshots differ after execution')
            result['sources_stable'] = True
        except Exception as error:
            result['sources_stable'] = False
            result['passed'] = False
            result['stability_exception'] = repr(error)
        write(out / 'receipt.json', result)
        print(json.dumps(dict(passed=result['passed'], sources_stable=result['sources_stable'],
            comparisons=result.get('audit', {}).get('comparisons'), exception=result.get('exception'))))
    # A final pin mismatch must affect both the receipt and the exit status.
    # Returning inside try would freeze a successful return before finally.
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
