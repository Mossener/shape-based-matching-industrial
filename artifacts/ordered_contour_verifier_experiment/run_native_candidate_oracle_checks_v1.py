"""Guarded independent candidate generation, native build/run and exact audit.

Only synthetic supplied labels are used. The compiler job bounds committed
memory including GCC children; each generation/native/audit process is watched
for working set, wall time and output. Metadata/import preflight is outside
those child watchdogs. This is not an aggregate RSS sandbox or speed benchmark.
Expected results never use optimized Python; solver counters are not audited.
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


def require(value, message):
    if not value:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def main():
    if len(sys.argv) != 2 or not re.fullmatch('[a-z][a-z0-9_]{0,80}', sys.argv[1]):
        raise SystemExit('usage: run_native_candidate_oracle_checks_v1.py fresh_directory')
    out = HERE / sys.argv[1]
    out.mkdir()
    snapshot = out / 'source'
    snapshot.mkdir()
    native_names = ['native_candidate_compatibility.hpp', 'native_edge_chains.hpp',
                    'native_ordered_match.hpp', 'native_candidate_batch_v1.cpp']
    names = native_names + ['NATIVE_CANDIDATE_BATCH_PROTOCOL_V1.json',
        'native_candidate_oracle_fixtures_v1.py', 'independent_candidate_oracle.py',
        'independent_edge_oracle.py', 'independent_tiny_oracle.py']
    for name in names:
        (snapshot / name).write_bytes((HERE / name).read_bytes())
    p = load('_native_candidate_oracle_provenance', INHERITED / 'native_provenance.py')
    guard = load('_native_candidate_oracle_guard', INHERITED / 'execution_guard.py')
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
    result = dict(schema='native_candidate_oracle_checks_v1', passed=False,
                  image_decodes=0, matcher_calls=0, quality_claim=False, performance_claim=False,
                  production_promotion=False, optimized_python_expectations_used=False,
                  work_counters_independently_verified=False)
    write(out / 'invocation.json', dict(source_pins=before, compiler_tools_queries=queries,
        build_runtime_before=build_runtime, synthetic_label_grids_only=True,
        per_child_limits=dict(seconds=60, observed_peak_working_set_bytes=536870912,
                              combined_output_bytes=67108864),
        compiler_limits=dict(seconds=180, job_committed_memory_bytes=1073741824,
                             helper_peak_working_set_bytes=1073741824, output_bytes=134217728),
        oracle_domain=dict(scene_occupancies=512, direction_profiles=2, templates=3,
                           transforms=2, candidate_comparisons=6144, skipped_cases=0),
        expectation_dependencies='Independent candidate/edge/tiny references only; tiny brute_force imports no optimized carriers.',
        counters='Solver work is omitted and is not independently verified here.',
        memory_semantics='Observed per-process working set; compiler job committed memory includes GCC children. No aggregate RSS claim.',
        provenance_semantics='Actual GCC dependencies and declared non-system static PE imports; OS/dynamic imports are not fully attested.'))
    runtime, child = None, None
    fixture_pins = []
    response_pin = None
    try:
        fixture_script = str(snapshot / 'native_candidate_oracle_fixtures_v1.py')
        result['generation_guard'] = guard.run_guarded(
            [sys.executable, '-E', '-B', fixture_script, 'generate', str(out / 'fixtures')],
            env, snapshot, out / 'fixtures', out / 'generation_execution', maximum_seconds=60,
            maximum_rss_bytes=536870912, maximum_output_bytes=67108864)
        require(result['generation_guard']['passed'], 'Independent fixture generation failed')
        generation = json.loads((out / 'fixtures/generation.json').read_bytes())
        require(generation['comparisons'] == 6144 and
                generation['domain_counts']['skipped_cases'] == 0, 'Incomplete fixture domain')
        result['generation'] = generation
        fixture_pins = [p.file_pin(out / 'fixtures' / name)
                        for name in ('generation.json', 'requests.txt', 'expected.jsonl')]
        result['fixture_pins'] = fixture_pins
        build = out / 'build'
        build.mkdir()
        payload = build / 'payload'
        flags = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror']
        driver = snapshot / 'native_candidate_batch_v1.cpp'
        commands = [
            [str(COMPILER), *flags, '-M', '-MT', 'adapter.o', '-MF', str(payload / 'declared.d'), str(driver)],
            [str(COMPILER), *flags, '-MD', '-MT', 'adapter.o', '-MF', str(payload / 'actual.d'),
             '-c', str(driver), '-o', str(payload / 'adapter.o')],
            [str(COMPILER), str(payload / 'adapter.o'), '-lgmpxx', '-lgmp', '-o', str(payload / 'native_batch.exe')]]
        write(build / 'reservation.json', dict(commands=commands, cwd=str(snapshot), output=str(payload),
            job_memory_limit_bytes=1073741824, repository=str(ROOT),
            allowed_project_sources=[str(snapshot / name) for name in native_names],
            provenance_source=str(INHERITED / 'native_provenance.py')))
        result['declared_commands'] = commands
        result['build_guard'] = guard.run_guarded([sys.executable, '-E', '-B',
            str(HERE / 'native_compile_child_v1.py'), str(build / 'reservation.json')],
            env, snapshot, payload, build / 'execution', maximum_seconds=180,
            maximum_rss_bytes=1073741824, maximum_output_bytes=134217728)
        require(result['build_guard']['passed'], 'Native candidate driver build failed')
        child = json.loads((payload / 'compiler_child_result.json').read_bytes())
        result['compiler_child'] = child
        require(child['passed'] and child['peak_job_committed_memory_bytes'] <= 1073741824,
                'Compiler job failed or exceeded committed-memory limit')
        executable = payload / 'native_batch.exe'
        result['executable'] = p.file_pin(executable)
        runtime = p.import_closure([executable], COMPILER, HERE / 'no_opencv_dependency', env)
        result['native_runtime_before'] = runtime
        result['native_guard'] = guard.run_guarded([str(executable), str(out / 'fixtures/requests.txt')],
            env, snapshot, out / 'native_payload', out / 'native_execution', maximum_seconds=60,
            maximum_rss_bytes=536870912, maximum_output_bytes=67108864)
        require(result['native_guard']['passed'], 'Native candidate fixture execution failed')
        responses = out / 'native_execution/stdout.txt'
        response_pin = p.file_pin(responses)
        result['response_pin'] = response_pin
        result['audit_guard'] = guard.run_guarded([sys.executable, '-E', '-B', fixture_script,
            'audit', str(out / 'fixtures'), str(responses), str(out / 'audit')],
            env, snapshot, out / 'audit', out / 'audit_execution', maximum_seconds=60,
            maximum_rss_bytes=536870912, maximum_output_bytes=67108864)
        require(result['audit_guard']['passed'], 'Exact independent candidate audit failed')
        audit = json.loads((out / 'audit/audit.json').read_bytes())
        result['audit'] = audit
        result['passed'] = (audit['passed'] is True and audit['comparisons'] == 6144 and
                            audit['zero_skips'] is True and
                            audit['work_counters_independently_verified'] is False)
    except Exception as error:
        result['passed'] = False
        result['exception'] = repr(error)
    finally:
        try:
            for row in before + build_runtime['files'] + fixture_pins:
                p.check_pin(row)
            if response_pin is not None:
                p.check_pin(response_pin)
            if 'executable' in result:
                p.check_pin(result['executable'])
            if runtime is not None:
                for row in runtime['files']:
                    p.check_pin(row)
            if child is not None:
                for row in child['compiler_dependency_pins']:
                    p.check_pin(row)
            require(all((HERE / name).read_bytes() == (snapshot / name).read_bytes() for name in names),
                    'Source snapshots differ after execution')
            result['sources_stable'] = True
        except Exception as error:
            result['sources_stable'] = False
            result['passed'] = False
            result['stability_exception'] = repr(error)
        write(out / 'receipt.json', result)
        print(json.dumps(dict(passed=result['passed'], sources_stable=result['sources_stable'],
            comparisons=result.get('audit', {}).get('comparisons'), exception=result.get('exception'),
            stability_exception=result.get('stability_exception'))))
    # Decide the exit only after final pins: a late mismatch must fail both
    # the retained receipt and the process, including otherwise successful runs.
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    require(__debug__ and sys.flags.optimize == 0 and sys.flags.ignore_environment == 1,
            'Use -E -B with active assertions')
    raise SystemExit(main())
