"""Build reviewed empty-mask adapter or synthetic RED/GREEN; no images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

import freeze_private_sources as frozen
import native_provenance as provenance
import prepare_input_closure as inputs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', choices=['adapter','source-test-green','source-test-red'], default='adapter')
    parser.add_argument('--cpu-slot-granted', action='store_true')
    parser.add_argument('--compiler', type=Path, default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--opencv', type=Path, default=Path('D:/opencv-4.12.0'))
    args = parser.parse_args()
    provenance.require(args.cpu_slot_granted, 'Await coordinated actual-build CPU slot')
    out, compiler, opencv = args.output.resolve(), args.compiler.resolve(strict=True), args.opencv.resolve(strict=True)
    provenance.require(out.is_relative_to(HERE) and not out.exists(), 'Build directory must be fresh inside experiment')
    out.mkdir()
    attempts = []
    try:
        manifest = json.loads((HERE/'PRIVATE_SOURCE_FREEZE.json').read_text())
        frozen.verify(HERE/'private_v11', manifest)
        inputs.verify()
        env = dict(os.environ)
        env['PATH'] = str(compiler.parent)+';'+str(opencv/'build/bin')+';'+env.get('PATH', '')
        tools, queries = provenance.compiler_tools(compiler, env)
        runtime_before = provenance.import_closure(tools+[opencv/'build/bin/libopencv_world4120.dll', compiler.parent/'zlib1.dll'], compiler, opencv, env)
        libraries = [opencv/'build/lib/libopencv_world4120.dll.a', compiler.parent.parent/'lib/libz.dll.a', compiler.parent.parent/'lib/libpsapi.a']
        tool_pins = [provenance.file_pin(p) for p in tools+libraries]
        project = [HERE/'private_v11'/n for n in manifest['files']]+[HERE/'frozen_helpers'/n for n in manifest['helpers']]
        adapter = HERE/('silhouette_eval.cpp' if args.target=='adapter' else 'empty_mask_source_test.cpp')
        project += [adapter, HERE/'silhouette_source.hpp',HERE/'empty_mask_policy.hpp']
        if args.target=='source-test-red':
            project.append(HERE/'synthetic_fixtures/empty_mask_policy_red.hpp')
        supporting = [HERE/n for n in ('build_adapter.py', 'native_provenance.py', 'freeze_private_sources.py',
                                       'prepare_input_closure.py', 'PRIVATE_SOURCE_FREEZE.json', 'INPUT_CLOSURE.json', 'PROTOCOL.json',
                                       'IMPLEMENTATION_ORIGIN.json')]
        project_pins = [provenance.file_pin(p) for p in project+supporting]
        flags = manifest['compile_flags']+['-I'+str(opencv/'build')]
        flags += ['-I'+str(opencv/'modules'/module/'include') for module in ('core', 'imgproc', 'highgui', 'imgcodecs', 'videoio')]
        if args.target=='source-test-red':
            flags.append('-DEMPTY_MASK_POLICY_RED_TEST')
        units = []

        def run(label, command):
            record = dict(label=label, command=list(map(str, command)), working_directory=str(out))
            attempts.append(record)
            (out/'attempts.json').write_text(json.dumps(attempts, indent=2)+'\n')
            process = subprocess.run(record['command'], cwd=out, env=env, capture_output=True)
            (out/(label+'.stdout')).write_bytes(process.stdout);(out/(label+'.stderr')).write_bytes(process.stderr)
            record['exit_code'] = process.returncode
            (out/'attempts.json').write_text(json.dumps(attempts, indent=2)+'\n')
            provenance.require(process.returncode == 0, label+' failed; compiler diagnostics preserved')
            return process.stdout

        for name, source in [('core', HERE/'private_v11/line2Dup.cpp'), ('adapter', adapter)]:
            target = name+'.o'
            before_data = run(name+'_dependency_before', [compiler, *flags, '-M', '-MT', target, source])
            (out/(name+'_before.d')).write_bytes(before_data)
            before = provenance.dependency_pins(before_data, target, out, ROOT, project)
            provenance.require(source.resolve() in [Path(p['path']) for p in before], 'Precompile dependency file omits actual translation unit')
            run(name+'_compile', [compiler, *flags, '-c', source, '-o', out/target, '-MD', '-MF', out/(name+'.d'), '-MT', target])
            actual_data = (out/(name+'.d')).read_bytes()
            actual = provenance.dependency_pins(actual_data, target, out, ROOT, project)
            provenance.require(actual == before, 'Actual compiler dependencies differ from precompile bytes/list')
            units.append(dict(source=str(source), target=target, object=provenance.file_pin(out/target),
                              dependency_file=provenance.file_pin(out/(name+'.d')), dependencies=actual))
        exe = out/('silhouette_eval.exe' if args.target=='adapter' else 'empty_mask_source_test.exe')
        run('link', [compiler, '-fopenmp', out/'core.o', out/'adapter.o', *libraries, '-o', exe])
        actual_runtime = provenance.import_closure([exe], compiler, opencv, env)
        for pin in tool_pins+project_pins+runtime_before['files']:
            provenance.check_pin(pin)
        for unit in units:
            provenance.check_pin(unit['object']);provenance.check_pin(unit['dependency_file'])
            for pin in unit['dependencies']:
                provenance.check_pin(pin)
        for pin in actual_runtime['files']:
            provenance.check_pin(pin)
        inputs.verify()
        result = dict(passed=True, target=args.target, core_revision=frozen.REV, actual_private_core=str(HERE/'private_v11/line2Dup.cpp'),
                      executable=provenance.file_pin(exe), compiler=str(compiler), opencv=str(opencv),
                      compiler_tools_and_link_libraries=tool_pins, compiler_tool_queries=queries,
                      compiler_runtime_closure=runtime_before, executable_runtime_closure=actual_runtime,
                      project_sources=project_pins, dependency_units=units, commands=attempts,
                      image_files_opened=0, image_decodes=0, matcher_calls=0,
                      scope='Independent empty-feature-mask training/planner or synthetic policy oracle; actual private V11 and actual two-TU GCC -MD dependencies; no quality/default promotion')
        (out/'build_manifest.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(dict(passed=True, compiler_commands=len(attempts), image_decodes=0, matcher_calls=0)))
    except Exception as error:
        (out/'failure.json').write_text(json.dumps(dict(incomplete=True, reason=str(error), attempts=attempts, image_decodes=0, matcher_calls=0), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
