"""Synthetic source-freeze tests for the silhouette experiment.

These tests intentionally run before the freezer exists.  They catch a future
implementation that merely hashes the mutable workspace or compiles the root
core while claiming a V11 frozen source.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REV = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
CORE = [
    'line2Dup.cpp', 'line2Dup.h', 'line2Dup_local.hpp',
    'line2Dup_matches.hpp', 'line2Dup_response.hpp',
    'line2Dup_search.hpp', 'line2Dup_spread.hpp',
]


def require(value, message):
    if not value:
        raise AssertionError(message)


def git_files():
    result = subprocess.run(['git', 'ls-tree', '-r', '--name-only', REV, '--', 'MIPP'],
                            cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout.splitlines()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'output must be fresh')
    args.output.mkdir(parents=True)
    expected = CORE + git_files()
    freezer = HERE / 'freeze_private_sources.py'
    require(freezer.exists(), 'source freezer is missing')
    result = subprocess.run(['py', '-3.10', str(freezer), '--verify', '--output', str(args.output/'verify.json')],
                            cwd=ROOT, capture_output=True, text=True)
    require(result.returncode == 0, 'private source verification failed: '+result.stderr)
    manifest = json.loads((args.output/'verify.json').read_text())
    private = HERE / 'private_v11'
    require(manifest['git_revision'] == REV and manifest['file_count'] == len(expected), 'wrong source freeze scope')
    require(sorted(manifest['files']) == sorted(expected), 'private source manifest is incomplete')
    for rel in expected:
        path = private / ('MIPP' / Path(rel).relative_to('MIPP') if rel.startswith('MIPP/') else rel)
        root = subprocess.run(['git', 'show', REV+':'+rel], cwd=ROOT, check=True, capture_output=True).stdout
        require(path.read_bytes() == root, 'private byte differs from frozen git blob: '+rel)
    compile_flags = manifest['compile_flags']
    require(any(flag.startswith('-I') and 'private_v11' in flag for flag in compile_flags), 'compile does not include private core')
    require(any(flag.startswith('-I') and flag.endswith('private_v11\\MIPP') for flag in compile_flags), 'compile does not include private MIPP')
    require('artifacts/public_evaluation/build/core_source_b25df46f6ddf' not in ' '.join(compile_flags), 'compile uses mutable public build core')
    (args.output/'results.json').write_text(json.dumps({'passed': True, 'file_count': len(expected),
        'private_sha256': manifest['private_sha256'], 'image_decodes': 0, 'matcher_calls': 0}, indent=2)+'\n')
    print(json.dumps({'passed': True, 'file_count': len(expected)}))


if __name__ == '__main__':
    main()
