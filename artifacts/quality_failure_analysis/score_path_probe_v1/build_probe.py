"""Actual single-TU build provenance; run only with the root CPU slot."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from probe_contract import check, pin, require

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPERIMENT = ROOT/'artifacts/silhouette_empty_mask_experiment'
sys.path.insert(0, str(EXPERIMENT))
import freeze_private_sources as frozen
import native_provenance as provenance


def build(output, compiler, opencv, red):
    source_freeze = json.loads((EXPERIMENT/'PRIVATE_SOURCE_FREEZE.json').read_bytes())
    frozen.verify(EXPERIMENT/'private_v11', source_freeze)
    project = [EXPERIMENT/'private_v11'/name for name in source_freeze['files']]
    project += [EXPERIMENT/'frozen_helpers'/name for name in source_freeze['helpers']]
    project += [EXPERIMENT/'quality_support.hpp', HERE/'probe.cpp']
    supporting = [HERE/name for name in ('build_probe.py', 'probe_contract.py', 'prepare_probe.py', 'run_probe.py', 'runner_gates.py', 'DESIGN.md')]
    supporting += [EXPERIMENT/name for name in ('PRIVATE_SOURCE_FREEZE.json', 'freeze_private_sources.py', 'native_provenance.py')]
    project_pins = [pin(path) for path in project+supporting]
    environment = dict(os.environ)
    environment['PATH'] = str(compiler.parent)+';'+str(opencv/'build/bin')+';'+environment.get('PATH', '')
    tools, queries = provenance.compiler_tools(compiler, environment)
    libraries = [opencv/'build/lib/libopencv_world4120.dll.a', compiler.parent.parent/'lib/libz.dll.a', compiler.parent.parent/'lib/libpsapi.a']
    tool_pins = [pin(path) for path in tools+libraries]
    runtime_before = provenance.import_closure(tools+[opencv/'build/bin/libopencv_world4120.dll', compiler.parent/'zlib1.dll'], compiler, opencv, environment)
    flags = source_freeze['compile_flags']+['-I'+str(EXPERIMENT/'frozen_helpers'), '-I'+str(opencv/'build')]
    flags += ['-I'+str(opencv/'modules'/module/'include') for module in ('core', 'imgproc', 'highgui', 'imgcodecs', 'videoio')]
    if red:
        flags.append('-DSCORE_PROBE_ORACLE_RED')
    attempts = []

    def execute(label, command):
        record = dict(label=label, command=list(map(str, command)), working_directory=str(output))
        attempts.append(record)
        (output/'attempts.json').write_text(json.dumps(attempts, indent=2)+'\n')
        process = subprocess.run(record['command'], cwd=output, env=environment, capture_output=True)
        (output/(label+'.stdout')).write_bytes(process.stdout)
        (output/(label+'.stderr')).write_bytes(process.stderr)
        record['exit_code'] = process.returncode
        (output/'attempts.json').write_text(json.dumps(attempts, indent=2)+'\n')
        require(process.returncode == 0, label+' failed; diagnostics preserved')
        return process.stdout

    source = HERE/'probe.cpp'
    before = execute('dependency_before', [compiler, *flags, '-M', '-MT', 'adapter.o', source])
    (output/'adapter_before.d').write_bytes(before)
    before_pins = provenance.dependency_pins(before, 'adapter.o', output, ROOT, project)
    require(source.resolve() in [Path(p['path']) for p in before_pins] and (EXPERIMENT/'private_v11/line2Dup.cpp').resolve() in [Path(p['path']) for p in before_pins], 'Single TU must actually include frozen core')
    execute('compile', [compiler, *flags, '-c', source, '-o', output/'adapter.o', '-MD', '-MF', output/'adapter.d', '-MT', 'adapter.o'])
    actual = provenance.dependency_pins((output/'adapter.d').read_bytes(), 'adapter.o', output, ROOT, project)
    require(actual == before_pins, 'Actual compiler dependencies changed')
    executable = output/'score_probe.exe'
    execute('link', [compiler, '-fopenmp', output/'adapter.o', *libraries, '-o', executable])
    runtime_after = provenance.import_closure([executable], compiler, opencv, environment)
    for value in project_pins+tool_pins+runtime_before['files']+runtime_after['files']+actual:
        check(value)
    result = dict(passed=True, target='score_path_probe_phase1', core_revision=frozen.REV, red_negative_control=red,
        compiler=str(compiler), opencv=str(opencv), executable=pin(executable), project_sources=project_pins,
        compiler_tools_and_link_libraries=tool_pins, compiler_tool_queries=queries,
        compiler_runtime_closure=runtime_before, executable_runtime_closure=runtime_after,
        dependency_units=[dict(source=str(source), included_private_core=str(EXPERIMENT/'private_v11/line2Dup.cpp'),
            object=pin(output/'adapter.o'), dependency_file=pin(output/'adapter.d'), dependencies=actual)],
        commands=attempts, image_decodes=0, full_class_search_replays=0, public_detector_match_calls=0)
    (output/'build_manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--opencv', type=Path, default=Path('D:/opencv-4.12.0'))
    parser.add_argument('--red-negative-control', action='store_true')
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    require(args.cpu_slot_granted, 'Await root native build CPU slot')
    output = args.output.resolve()
    require(output.is_relative_to(HERE) and not output.exists(), 'Fresh contained build required')
    output.mkdir()
    try:
        result = build(output, args.compiler.resolve(strict=True), args.opencv.resolve(strict=True), args.red_negative_control)
        print(json.dumps(dict(passed=True, target=result['target'], red_negative_control=args.red_negative_control)))
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(passed=False, error=str(error), image_decodes=0), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
