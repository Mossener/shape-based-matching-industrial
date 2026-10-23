"""Guarded, alternating synthetic v1/compiled-scene paired measurements.

Does not modify the frozen v1 source. A generated counted copy retains its
algorithm and instruments the two actual full-scene lookup-build loops.
Complete counted-v1/v1/v2 result and work parity is checked outside timing.
Source instrumentation is operational evidence, not allocation profiling.
No elapsed-time ratio is a correctness, quality or production gate.
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


def counted_baseline(source):
    start = 'inline CandidateScore score_candidate('
    finish = '\n}  // namespace ordered_contour_native::candidate'
    if source.count(start) != 1 or source.count(finish) != 1:
        raise ValueError('Frozen baseline function boundaries differ')
    body = source[source.index(start):source.index(finish)]
    replacements = [
        (start, 'inline CandidateScore score_candidate_counted('),
        ('const Padding& padding_ltrb = {0, 0, 0, 0}) {',
         'const Padding& padding_ltrb, BaselineIndexWork& index_work) {'),
        ('    std::map<Id, const std::vector<SceneChainMember>*> members_by_pixel;\n'
         '    for (const auto& row : supplied_scene.memberships) members_by_pixel.emplace(row.pixel_id, &row.members);\n'
         '    std::map<Id, const edge::Chain*> scene_by_id;\n'
         '    for (const auto& chain : supplied_scene.chains) scene_by_id.emplace(chain.chain_id, &chain);',
         '    const auto index_started = std::chrono::steady_clock::now();\n'
         '    ++index_work.index_builds;\n'
         '    std::map<Id, const std::vector<SceneChainMember>*> members_by_pixel;\n'
         '    for (const auto& row : supplied_scene.memberships) {\n'
         '        ++index_work.membership_rows_indexed;\n'
         '        index_work.members_indexed += detail::count(row.members.size());\n'
         '        members_by_pixel.emplace(row.pixel_id, &row.members);\n'
         '    }\n'
         '    std::map<Id, const edge::Chain*> scene_by_id;\n'
         '    for (const auto& chain : supplied_scene.chains) {\n'
         '        ++index_work.chains_indexed;\n'
         '        scene_by_id.emplace(chain.chain_id, &chain);\n'
         '    }\n'
         '    index_work.index_nanoseconds += std::chrono::duration_cast<std::chrono::nanoseconds>(\n'
         '        std::chrono::steady_clock::now() - index_started).count();'),
    ]
    for original, changed in replacements:
        if body.count(original) != 1:
            raise ValueError('Frozen baseline instrumentation anchor differs')
        body = body.replace(original, changed, 1)
    prefix = ('// Generated solely from the SHA-gated frozen v1 function.\n'
              '#include "native_candidate_compatibility.hpp"\n#include <chrono>\n'
              'namespace ordered_contour_native::candidate {\n'
              'struct BaselineIndexWork {\n'
              '    Id index_builds=0, membership_rows_indexed=0, members_indexed=0, chains_indexed=0;\n'
              '    std::int64_t index_nanoseconds=0;\n};\n')
    return (prefix + body + '\n} // namespace ordered_contour_native::candidate\n').encode('utf-8')


def main():
    if len(sys.argv) != 2 or not re.fullmatch('[a-z][a-z0-9_]{0,80}', sys.argv[1]):
        raise SystemExit('usage: run_native_compiled_scene_benchmark_v2.py fresh_directory')
    out = HERE / sys.argv[1]
    out.mkdir()
    result = dict(passed=False, image_decodes=0, matcher_calls=0, real_payload_reads=0,
                  performance_scope='synthetic isolated scene-index reuse only',
                  machine_speed_ratio_gate=False, quality_claim=False, production_promotion=False)
    try:
        p = load('_compiled_scene_benchmark_provenance', INHERITED / 'native_provenance.py')
        guard = load('_compiled_scene_benchmark_guard', INHERITED / 'execution_guard.py')
        for name, expected in FROZEN.items():
            p.require(p.file_pin(HERE / name)['sha256'] == expected, 'Frozen v1 source changed')
        source_names = ['native_candidate_compiled_scene_v2.hpp', 'native_candidate_compiled_scene_v2_test.cpp',
                        'native_compiled_scene_benchmark_v2.cpp', *FROZEN]
        snapshot = out / 'source'
        snapshot.mkdir()
        sources = [HERE / name for name in source_names]
        snapshots = []
        for source in sources:
            target = snapshot / source.name
            target.write_bytes(source.read_bytes())
            snapshots.append(target)
        generated = snapshot / 'baseline_counted_v1.hpp'
        generated_bytes = counted_baseline((HERE / 'native_candidate_compatibility.hpp').read_text(encoding='utf-8'))
        generated.write_bytes(generated_bytes)
        snapshots.append(generated)
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
        compiler = str(COMPILER)
        source = snapshot / 'native_compiled_scene_benchmark_v2.cpp'
        commands = [
            [compiler, *flags, '-M', '-MT', 'adapter.o', '-MF', str(payload / 'declared.d'), str(source)],
            [compiler, *flags, '-MD', '-MT', 'adapter.o', '-MF', str(payload / 'actual.d'),
             '-c', str(source), '-o', str(payload / 'adapter.o')],
            [compiler, str(payload / 'adapter.o'), '-lgmpxx', '-lgmp', '-o', str(payload / 'native_benchmark.exe')],
        ]
        write(build / 'reservation.json', dict(commands=commands, cwd=str(snapshot), output=str(payload),
            job_memory_limit_bytes=1073741824, repository=str(ROOT), allowed_project_sources=list(map(str,snapshots)),
            provenance_source=str(INHERITED / 'native_provenance.py')))
        write(out / 'invocation.json', dict(inputs=before, compiler_tools_queries=queries, build_runtime_before=runtime,
            declared_commands=commands, synthetic_label_grids_only=True,
            measured_domain=dict(width=256,height=256,branch_components=1024,physical_scene_membership_rows=5120,
                                 scene_members=6144,scene_chains=2048,rounds=6,queries_per_round=256,
                                 complete_comparisons=1536),
            counted_baseline='SHA-gated generated copy instruments actual original scene map loops; never edits v1 source. Every counted result is compared with original v1 and v2 including work outside timing.',
            counter_semantics='membership_rows/chains count actual index insertion-loop iterations; members counts referenced member records via row.members.size(), not visits to individual member objects.',
            timing_semantics='Alternating paired order. Timed baseline calls exact frozen v1 without instrumentation; cached preparation includes index construction. Counted baseline calls and parity comparisons occur afterward outside both timed regions; scene_index_ms_untimed is only the untimed index-loop timer.',
            working_set_semantics='One process observed peak includes both paths and untimed parity; no separate per-path peak or aggregate-RSS claim.',
            machine_speed_ratio_gate=False))
        result['build_guard'] = guard.run_guarded(
            [sys.executable,'-E','-B',str(HERE / 'native_compile_child_v1.py'),str(build / 'reservation.json')],
            env,snapshot,payload,build / 'execution',maximum_seconds=180,
            maximum_rss_bytes=1073741824,maximum_output_bytes=134217728)
        p.require(result['build_guard']['passed'], 'Synthetic benchmark build failed')
        child = json.loads((payload / 'compiler_child_result.json').read_bytes())
        result['compiler_child'] = child
        p.require(child['passed'] is True and child['peak_job_committed_memory_bytes'] <= 1073741824,
                  'Compiler job failed')
        executable = payload / 'native_benchmark.exe'
        result['executable'] = p.file_pin(executable)
        run_runtime = p.import_closure([executable],COMPILER,HERE / 'no_opencv_dependency',env)
        result['test_runtime_before'] = run_runtime
        result['benchmark_guard'] = guard.run_guarded([str(executable)],env,snapshot,
            out / 'benchmark_payload',out / 'benchmark_execution',maximum_seconds=120,
            maximum_rss_bytes=536870912,maximum_output_bytes=67108864)
        p.require(result['benchmark_guard']['passed'], 'Synthetic paired benchmark failed')
        stdout = (out / 'benchmark_execution/stdout.txt').read_text(encoding='utf-8')
        lines = stdout.splitlines()
        p.require(len(lines) == 7, 'Exactly six paired measurements and one summary required')
        rows = [json.loads(line) for line in lines[:6]]
        p.require(lines[6] == 'NATIVE_COMPILED_SCENE_BENCHMARK_SUMMARY rounds=6 queries_per_round=256 complete_comparisons=1536 failures=0 errors=0',
                  'Incomplete synthetic benchmark summary')
        for index,row in enumerate(rows):
            p.require(row['round'] == index and row['order'] == ('baseline_first' if index%2==0 else 'cached_first'),
                      'Alternating round schedule changed')
            for key,multiplier in (('baseline',256),('cached',1)):
                values = row[key]
                p.require(values['index_pairs'] == multiplier and values['maps_constructed'] == 2*multiplier
                          and values['membership_rows'] == 5120*multiplier
                          and values['members'] == 6144*multiplier and values['chains'] == 2048*multiplier,
                          'Actual index construction counts changed')
        result['measurements'] = rows
        result['passed'] = True
        for pin in before + runtime['files'] + run_runtime['files'] + [result['executable']] + child['compiler_dependency_pins']:
            p.check_pin(pin)
        p.require(generated.read_bytes() == generated_bytes, 'Generated counted baseline changed')
        p.require(all(source.read_bytes()==target.read_bytes() for source,target in zip(sources,snapshots)),
                  'Executed source snapshot differs from current source')
        result['source_pins_after'] = [p.file_pin(path) for path in inputs]
    except Exception as error:
        result['passed'] = False
        result['failure'] = repr(error)
        write(out / 'receipt.json',result)
        raise
    write(out / 'receipt.json',result)
    print(json.dumps(dict(passed=result['passed'],paired_rounds=6,complete_comparisons=1536,
                          real_payload_reads=0,machine_speed_ratio_gate=False)))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
