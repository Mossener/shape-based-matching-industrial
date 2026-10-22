"""Capture a small isolated sampler literal RED/GREEN build; no matcher/images."""
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
    parser.add_argument('--mode', required=True, choices=['missing-header-red', 'wrong-ordinal-red', 'green'])
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
    source = output / 'source'; source.mkdir()
    names = ['sampler_literal_tests.cpp', 'run_literal.py']
    if args.mode != 'missing-header-red':
        names += ['stratified_sampler.hpp']
    before = [pin(HERE / name) for name in names]
    for name in names:
        (source / name).write_bytes((HERE / name).read_bytes())
    mutation = None
    if args.mode == 'wrong-ordinal-red':
        path = source / 'stratified_sampler.hpp'
        data = path.read_bytes()
        old = b'return left.ordinal < right.ordinal;'
        new = b'return left.ordinal > right.ordinal;'
        if data.count(old) != 1:
            raise ValueError('Unique ordinal tie mutation target differs')
        mutation = dict(kind='reverse-ordinal-tie-only', replacements=1, before=pin(path))
        path.write_bytes(data.replace(old, new)); mutation['after'] = pin(path)
    compiler = args.compiler.resolve(strict=True)
    env = dict(os.environ); env['PATH'] = str(compiler.parent) + ';' + env.get('PATH', '')
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
    unchanged = before == [pin(HERE / name) for name in names]
    expected = (compiled.returncode != 0 and b'stratified_sampler.hpp' in compiled.stderr
                if args.mode == 'missing-header-red' else
                compiled.returncode == 0 and execution is not None and execution.returncode == 1
                and b'literal selected ordinal differs' in execution.stderr
                if args.mode == 'wrong-ordinal-red' else
                compiled.returncode == 0 and execution is not None and execution.returncode == 0)
    result = dict(passed=bool(expected and unchanged and version.returncode == 0), mode=args.mode,
                  compile_command=command, compile_exit=compiled.returncode,
                  run_exit=None if execution is None else execution.returncode,
                  compiler=pin(compiler), source_pins=before,
                  source_unchanged_during_execution=unchanged, mutation=mutation,
                  image_bytes_opened=0, image_decodes=0, matcher_calls=0,
                  scope='Pure literal standard-library C++14 sampler correctness; no quality/performance claim')
    result['files'] = [pin(path) for path in sorted(output.rglob('*')) if path.is_file()]
    (output / 'receipt.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: result[k] for k in ['passed', 'mode', 'compile_exit', 'run_exit', 'source_unchanged_during_execution']}))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
