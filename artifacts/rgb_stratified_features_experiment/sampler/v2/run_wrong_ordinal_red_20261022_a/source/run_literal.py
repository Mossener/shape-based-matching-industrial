"""Capture protocol-signed-int64 sampler literal evidence; no matcher/images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True,
                        choices=['signed-limit-v1-red', 'wrong-ordinal-red', 'green'])
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--compiler', type=Path, default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    if not args.cpu_slot_granted:
        raise ValueError('Coordinated pure literal CPU slot is required')
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(HERE):
        raise ValueError('Fresh contained literal output is required')
    output.mkdir(parents=True)
    source = output / 'source'
    source.mkdir()
    header_origin = (HERE.parent if args.mode == 'signed-limit-v1-red' else HERE) / 'stratified_sampler.hpp'
    origins = [HERE / 'sampler_literal_tests.cpp', HERE / 'run_literal.py', header_origin]
    before = [pin(path) for path in origins]
    for origin in origins:
        (source / origin.name).write_bytes(origin.read_bytes())
    mutation = None
    if args.mode == 'signed-limit-v1-red':
        # Text seam identifies the exact unmodified v1 function exercised by the RED.
        header = source / 'stratified_sampler.hpp'
        header_bytes = header.read_bytes()
        begin = header_bytes.index(b'inline std::uint64_t squared_distance(')
        end = header_bytes.index(b'\n}\n', begin) + 2
        function_bytes = header_bytes[begin:end]
        seam = dict(kind='unmodified-v1-squared-distance-text-seam', header=pin(header),
                    start_line=header_bytes[:begin].count(b'\n') + 1,
                    end_line=header_bytes[:end].count(b'\n') + 1,
                    function_utf8=function_bytes.decode('utf-8'), function_bytes=len(function_bytes),
                    function_sha256=hashlib.sha256(function_bytes).hexdigest(),
                    expected_failure='full int32 axial distance above INT64_MAX accepted')
        (output / 'v1_source_seam.json').write_text(json.dumps(seam, indent=2) + '\n',
                                                   encoding='utf-8', newline='\n')
    elif args.mode == 'wrong-ordinal-red':
        header = source / 'stratified_sampler.hpp'
        data = header.read_bytes()
        old = b'return left.ordinal < right.ordinal;'
        new = b'return left.ordinal > right.ordinal;'
        if data.count(old) != 1:
            raise ValueError('Unique ordinal tie mutation target differs')
        mutation = dict(kind='reverse-ordinal-tie-only', replacements=1, before=pin(header))
        header.write_bytes(data.replace(old, new))
        mutation['after'] = pin(header)
    compiler = args.compiler.resolve(strict=True)
    env = dict(os.environ)
    env['PATH'] = str(compiler.parent) + ';' + env.get('PATH', '')
    version = subprocess.run([str(compiler), '--version'], capture_output=True, env=env, timeout=30)
    (output / 'compiler_version.stdout').write_bytes(version.stdout)
    (output / 'compiler_version.stderr').write_bytes(version.stderr)
    executable = output / 'sampler_literal_tests.exe'
    command = [str(compiler), '-std=c++14', '-O2', '-Wall', '-Wextra', '-Werror', '-pedantic',
               '-static', '-static-libgcc', '-static-libstdc++', str(source / 'sampler_literal_tests.cpp'),
               '-o', str(executable)]
    compiled = subprocess.run(command, capture_output=True, env=env, cwd=source, timeout=120)
    (output / 'compile.stdout').write_bytes(compiled.stdout)
    (output / 'compile.stderr').write_bytes(compiled.stderr)
    execution = None
    if compiled.returncode == 0:
        execution = subprocess.run([str(executable)], capture_output=True, env=env, cwd=source, timeout=30)
        (output / 'run.stdout').write_bytes(execution.stdout)
        (output / 'run.stderr').write_bytes(execution.stderr)
    unchanged = before == [pin(path) for path in origins]
    expected_message = {'signed-limit-v1-red': b'full int32 axial distance above INT64_MAX accepted',
                        'wrong-ordinal-red': b'literal selected ordinal differs'}
    expected = (compiled.returncode == 0 and execution is not None and
                (execution.returncode == 0 if args.mode == 'green' else
                 execution.returncode == 1 and expected_message[args.mode] in execution.stderr))
    result = dict(passed=bool(expected and unchanged and version.returncode == 0), mode=args.mode,
                  protocol_distance='checked signed int64 squared Euclidean, reject sum > 2^63-1',
                  compile_command=command, compile_exit=compiled.returncode,
                  run_exit=None if execution is None else execution.returncode,
                  compiler=pin(compiler), source_pins=before,
                  source_unchanged_during_execution=unchanged, mutation=mutation,
                  image_bytes_opened=0, image_decodes=0, matcher_calls=0,
                  scope='Pure literal C++14 sampler correctness; no quality/performance claim',
                  toolchain_closure='Compiler executable/version pinned; not complete transitive toolchain closure')
    result['files'] = [pin(path) for path in sorted(output.rglob('*')) if path.is_file()]
    (output / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n',
                                       encoding='utf-8', newline='\n')
    print(json.dumps({k: result[k] for k in ['passed', 'mode', 'compile_exit', 'run_exit',
                                          'source_unchanged_during_execution']}))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
