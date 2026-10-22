"""Build/verify/measure immutable consolidation traces under the frozen protocol."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess

from capture_manifest import check_file, json_bytes, read_trace, relative_path, require, sha256
from dependency_closure import parse_depfile
from real_capture_audit import audit_real_capture

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE_NAMES = ('record.hpp', 'hash_consolidation.hpp', 'trace_io.hpp', 'replay_benchmark.cpp',
                'run_replay.py', 'summarize_replay.py', 'test_replay_summary.py',
                'capture_manifest.py', 'capture_source.py', 'dependency_closure.py',
                'real_capture_audit.py', 'REPLAY_BENCHMARK_PROTOCOL.json', 'CAPTURE_PROTOCOL.json')


def pin(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), size_bytes=path.stat().st_size, sha256=sha256(path))


def checks(items, label):
    for item in items:
        check_file(Path(item['path']), item, label)


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2)+'\n')


def checked_traces(capture_result):
    result = json_bytes(capture_result.read_bytes())
    require(result['passed'] is True and result['matcher_calls'] == 50
            and result['tiny_scenario'] == 'quality_actual85' and len(result['verified_cases']) == 25,
            'Complete fixed actual85 capture required')
    frozen = json_bytes((HERE/'CAPTURE_PROTOCOL.json').read_bytes())
    require(result['frozen_capture_protocol']['sha256'] == sha256(HERE/'CAPTURE_PROTOCOL.json'),
            'Captured frozen protocol identity differs')
    items, cases = [pin(capture_result)], []
    for item in result['verified_cases']:
        manifest = relative_path(ROOT, item['path'])
        check_file(manifest, item, 'replay capture manifest')
        protocol = manifest.parent/'protocol.json'
        audited = audit_real_capture(manifest, protocol, ROOT)
        data = json_bytes(manifest.read_bytes())
        trace = manifest.parent/data['trace']['path']
        cases.append(dict(case_id=data['case']['case_id'], scenario=data['case']['scenario'],
                          trace=str(trace), trace_sha256=audited['trace_sha256'],
                          input_count=audited['input_count'], output_count=audited['output_count'],
                          trace_bytes=trace.stat().st_size))
        items += [pin(manifest), pin(protocol), pin(trace), pin(manifest.parent/data['reference']['path'])]
    require([case['case_id'] for case in cases] == frozen['case_order'], 'Replay all25 order differs')
    return cases, items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('build', 'verify', 'measure'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capture-result', type=Path)
    parser.add_argument('--build-receipt', type=Path)
    parser.add_argument('--verification', type=Path)
    parser.add_argument('--compiler', type=Path, default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    require(args.cpu_slot_granted, 'Parent exclusive CPU slot required')
    output = args.output.resolve()
    require(output.is_relative_to(ROOT) and not output.exists(), 'Replay output must be new in repository')
    output.mkdir(parents=True)
    state = dict(passed=False, mode=args.mode, started_at=datetime.now(timezone.utc).isoformat(),
                 image_decodes=0, matcher_calls=0, performance_measurement=args.mode == 'measure',
                 limitation='Consolidation replay only; no whole-matcher latency, accuracy or memory result')
    environment = dict(os.environ)

    def invoke(command, name, cwd=output):
        process = subprocess.run(command, cwd=cwd, env=environment, capture_output=True)
        (output/(name+'_stdout.txt')).write_bytes(process.stdout)
        (output/(name+'_stderr.txt')).write_bytes(process.stderr)
        command_receipt = dict(command=command, cwd=str(cwd), exit_code=process.returncode,
                               stdout=pin(output/(name+'_stdout.txt')), stderr=pin(output/(name+'_stderr.txt')))
        state.setdefault('commands', []).append(command_receipt)
        require(process.returncode == 0, 'Replay command failed: '+name)
        return process

    try:
        if args.mode == 'build':
            source = output/'source'
            source.mkdir()
            sources = [pin(HERE/name) for name in SOURCE_NAMES]
            for name in SOURCE_NAMES:
                (source/name).write_bytes((HERE/name).read_bytes())
            helper = subprocess.check_output(['git', 'show',
                     'b25df46f6ddf9c24fb43f5836f1414dc38c8caed:line2Dup_matches.hpp'], cwd=ROOT)
            (source/'line2Dup_matches.hpp').write_bytes(helper)
            compiler = args.compiler.resolve(strict=True)
            runtimes = [compiler.parent/name for name in
                        ('libstdc++-6.dll', 'libgcc_s_seh-1.dll', 'libwinpthread-1.dll')]
            environment['PATH'] = str(compiler.parent)+os.pathsep+environment.get('PATH', '')
            prefix = [str(compiler), '-std=c++17', '-O3', '-Wall', '-Wextra', '-Werror', '-I'+str(source)]
            obj, depfile, scan = output/'core.o', output/'core.d', output/'core_scan.d'
            scan_command = prefix+['-M', '-MF', str(scan), '-MT', 'core.o', str(source/'replay_benchmark.cpp')]
            invoke(scan_command, 'scan')
            dependencies = parse_depfile(scan.read_bytes(), 'core.o', output)
            allowed = {path.resolve() for path in source.iterdir()}
            for path in dependencies:
                require(path in allowed if path.is_relative_to(ROOT) else
                        path.is_relative_to(compiler.parent.parent), 'Replay dependency outside private/compiler scope')
            dependency_pins = [pin(path) for path in dependencies]
            inputs = sources+[pin(compiler), *[pin(p) for p in runtimes], *dependency_pins]
            invoke(prefix+['-c', '-MD', '-MF', str(depfile), '-MT', 'core.o',
                          str(source/'replay_benchmark.cpp'), '-o', str(obj)], 'compile')
            require(parse_depfile(depfile.read_bytes(), 'core.o', output) == dependencies,
                    'Replay actual-MD differs from discovery')
            executable = output/'replay_benchmark.exe'
            invoke([str(compiler), str(obj), '-o', str(executable)], 'link')
            checks(inputs, 'replay build input after link')
            state.update(passed=True, executable=pin(executable), compiler=pin(compiler),
                         runtimes=[pin(p) for p in runtimes], input_pins=inputs,
                         artifacts=[pin(p) for p in (obj, scan, depfile)],
                         snapshot_pins=[pin(p) for p in source.iterdir()],
                         replay_protocol=pin(HERE/'REPLAY_BENCHMARK_PROTOCOL.json'))
        else:
            require(args.build_receipt is not None and args.capture_result is not None,
                    'Replay verification/measurement require build and capture receipts')
            build_path, capture_path = args.build_receipt.resolve(strict=True), args.capture_result.resolve(strict=True)
            require(build_path.is_relative_to(ROOT) and capture_path.is_relative_to(ROOT), 'Receipts stay in repository')
            built = json_bytes(build_path.read_bytes())
            require(built['passed'] is True and built['mode'] == 'build', 'Successful replay build required')
            require(built['replay_protocol']['sha256'] == sha256(HERE/'REPLAY_BENCHMARK_PROTOCOL.json'),
                    'Frozen replay protocol changed after build')
            inputs = [pin(build_path), *built['input_pins'], *built['artifacts'],
                      *built['snapshot_pins'], built['executable'], built['replay_protocol']]
            checks(inputs, 'replay build before trace audit')
            cases, capture_pins = checked_traces(capture_path)
            inputs += capture_pins
            if args.mode == 'measure':
                require(args.verification is not None, 'Separate successful verification required before timing')
                verify_path = args.verification.resolve(strict=True)
                verified = json_bytes(verify_path.read_bytes())
                require(verified['passed'] is True and verified['mode'] == 'verify'
                        and verified['build_receipt'] == pin(build_path)
                        and verified['capture_result'] == pin(capture_path)
                        and verified['cases'] == cases, 'Replay verification identity differs')
                inputs.append(pin(verify_path))
            trace_list = output/'traces.tsv'
            with trace_list.open('x', encoding='utf-8', newline='\n') as stream:
                for case in cases:
                    stream.write(case['case_id']+'\t'+case['scenario']+'\t'+case['trace']+'\n')
            inputs.append(pin(trace_list))
            environment['PATH'] = str(Path(built['compiler']['path']).parent)+os.pathsep+environment.get('PATH', '')
            command = [built['executable']['path'], str(trace_list), str(output/'timings.csv'), str(output/'native.json')]
            if args.mode == 'verify':
                command.append('--verify-only')
            checks(inputs, 'replay input before call')
            state.update(build_receipt=pin(build_path), capture_result=pin(capture_path), cases=cases,
                         cpu=dict(processor=platform.processor(), processor_identifier=os.environ.get('PROCESSOR_IDENTIFIER'),
                                  logical_processors=os.cpu_count(), machine=platform.machine(), os=platform.platform()),
                         exclusive_cpu_grant=True, priority='normal', cpu_pinning='none')
            invoke(command, 'replay')
            checks(inputs, 'replay input after call')
            # Full capture audit after the replay also rechecks fixed source,
            # actual dependencies, inputs, protocol, executable and runtimes.
            after_cases, _ = checked_traces(capture_path)
            require(after_cases == cases, 'Trace identities changed after replay')
            native = json_bytes((output/'native.json').read_bytes())
            require(native['passed'] is True and native['traces'] == 25 and native['replay_only'] is True
                    and native['image_decodes'] == native['matcher_calls'] == 0
                    and native['verify_only'] is (args.mode == 'verify')
                    and native['timing_rows'] == (0 if args.mode == 'verify' else 4250),
                    'Replay native result counts differ')
            checks(inputs, 'replay input final check')
            state.update(passed=True, native=pin(output/'native.json'), timings=pin(output/'timings.csv'),
                         input_pins=inputs, native_result=native)
    except Exception as error:
        state['error'] = type(error).__name__+': '+str(error)
    state['finished_at'] = datetime.now(timezone.utc).isoformat()
    write_new(output/'replay_result.json', state)
    print(json.dumps(dict(passed=state['passed'], mode=args.mode, receipt=str(output/'replay_result.json'),
                         error=state.get('error'))))
    require(state['passed'], state.get('error', 'Replay failed'))


if __name__ == '__main__':
    main()
