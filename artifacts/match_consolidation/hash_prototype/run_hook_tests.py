"""Freeze and build standard-library-only, two-TU capture-hook correctness."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

CORE_REVISION = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-exit', type=int, choices=(0, 1), required=True)
    parser.add_argument('--compiler', type=Path, default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    if not args.cpu_slot_granted:
        raise ValueError('Coordinate exclusive CPU before compilation/tests')
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output/'source'
    source.mkdir()
    names = ('record.hpp', 'trace_io.hpp', 'capture_hook.hpp',
             'capture_hook_test.cpp', 'capture_hook_bridge.cpp', 'run_hook_tests.py')
    before = {name: digest(here/name) for name in names}
    for name in names:
        (source/name).write_bytes((here/name).read_bytes())
    header = subprocess.check_output(['git', 'show', CORE_REVISION+':line2Dup_matches.hpp'], cwd=root)
    blob = subprocess.check_output(['git', 'rev-parse', CORE_REVISION+':line2Dup_matches.hpp'], cwd=root).decode().strip()
    if hashlib.sha1(b'blob '+str(len(header)).encode()+b'\0'+header).hexdigest() != blob:
        raise ValueError('Exact V11 helper Git bytes differ')
    (source/'line2Dup_matches.hpp').write_bytes(header)
    snapshots = {p.name: digest(p) for p in source.iterdir() if p.is_file()}
    compiler = args.compiler.resolve(strict=True)
    env = dict(os.environ, PATH=str(compiler.parent)+os.pathsep+os.environ['PATH'])
    started = datetime.now(timezone.utc).isoformat()

    def invoke(argv, prefix):
        result = subprocess.run(argv, capture_output=True, env=env)
        (output/(prefix+'_stdout.txt')).write_bytes(result.stdout)
        (output/(prefix+'_stderr.txt')).write_bytes(result.stderr)
        return result.returncode

    version_exit = invoke([str(compiler), '--version'], 'compiler_version')
    executable = output/'capture_hook_test.exe'
    flags = ['-std=c++14', '-O2', '-Wall', '-Wextra', '-Werror', '-I'+str(source)]
    command = [str(compiler), *flags, str(source/'capture_hook_test.cpp'),
               str(source/'capture_hook_bridge.cpp'), '-o', str(executable)]
    compile_exit = invoke(command, 'compile')
    test_exit = invoke([str(executable)], 'test') if compile_exit == 0 else None
    unchanged = (before == {name: digest(here/name) for name in names} and
                 snapshots == {name: digest(source/name) for name in snapshots})
    passed = version_exit == compile_exit == 0 and test_exit == args.expected_exit and unchanged
    files = {p.name: digest(p) for p in output.iterdir() if p.is_file()}
    result = dict(status='PASS' if passed else 'FAIL', started_at=started,
                  finished_at=datetime.now(timezone.utc).isoformat(), source_sha256=before,
                  snapshot_sha256=snapshots, output_sha256=files, sources_unchanged=unchanged,
                  compiler=str(compiler), compiler_sha256=digest(compiler), command=command,
                  core_revision=CORE_REVISION, helper_git_blob=blob,
                  compile_exit=compile_exit, test_exit=test_exit, expected_test_exit=args.expected_exit,
                  image_decodes=0, dataset_files_read=0, matcher_calls=0,
                  performance_measurement=False, translation_units=2,
                  scope='Synthetic standard-library-only capture-hook correctness')
    (output/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    for name in ('compile_stderr.txt', 'test_stdout.txt', 'test_stderr.txt'):
        if (output/name).exists():
            print((output/name).read_text(errors='replace'), end='')
    if not passed:
        raise ValueError('Unexpected hook correctness result; preserve failure evidence')


if __name__ == '__main__':
    main()
