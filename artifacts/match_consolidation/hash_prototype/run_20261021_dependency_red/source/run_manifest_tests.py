"""Freeze synthetic manifest tests and preserve expected RED/GREEN evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-exit', type=int, choices=(0, 1), required=True)
    parser.add_argument('--suite', choices=('generic', 'real', 'dependencies'), default='generic')
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    if not args.cpu_slot_granted:
        raise ValueError('Coordinate the exclusive CPU slot before tests')
    here = Path(__file__).resolve().parent
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output/'source'
    snapshot.mkdir()
    names = ('capture_manifest.py', 'test_capture_manifest.py',
             'capture_source.py', 'test_capture_source.py', 'run_manifest_tests.py',
             'real_capture_audit.py', 'test_real_capture_audit.py',
             'dependency_closure.py', 'test_dependency_closure.py')
    before = {name: digest(here/name) for name in names}
    for name in names:
        (snapshot/name).write_bytes((here/name).read_bytes())
    frozen = {name: digest(snapshot/name) for name in names}
    started = datetime.now(timezone.utc).isoformat()
    modules = (['test_capture_manifest', 'test_capture_source'] if args.suite == 'generic'
               else ['test_dependency_closure'] if args.suite == 'dependencies'
               else ['test_real_capture_audit'])
    command = [sys.executable, '-m', 'unittest', '-v', *modules]
    process = subprocess.run(command, cwd=snapshot, capture_output=True,
                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    (output/'stdout.txt').write_bytes(process.stdout)
    (output/'stderr.txt').write_bytes(process.stderr)
    unchanged = (before == {name: digest(here/name) for name in names} and
                 frozen == {name: digest(snapshot/name) for name in names})
    passed = process.returncode == args.expected_exit and unchanged
    result = dict(status='PASS' if passed else 'FAIL', started_at=started,
                  finished_at=datetime.now(timezone.utc).isoformat(),
                  test_exit=process.returncode, expected_test_exit=args.expected_exit,
                  sources_unchanged=unchanged, source_sha256=before,
                  snapshot_sha256=frozen,
                  output_sha256={name: digest(output/name)
                                 for name in ('stdout.txt', 'stderr.txt')},
                  python=sys.executable, python_version=sys.version,
                  python_sha256=digest(Path(sys.executable)), command=command,
                  image_decodes=0, dataset_files_read=0, matcher_calls=0,
                  performance_measurement=False,
                  suite=args.suite, scope='Synthetic byte/manifest correctness only')
    (output/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    sys.stdout.write(process.stdout.decode('utf-8', errors='replace'))
    sys.stdout.write(process.stderr.decode('utf-8', errors='replace'))
    if not passed:
        raise ValueError('Unexpected manifest test result; preserve failure evidence')


if __name__ == '__main__':
    main()
