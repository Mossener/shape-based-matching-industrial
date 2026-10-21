#!/usr/bin/env python3
"""Freeze/verify exact V11 Git bytes without touching production sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMMIT = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
CORE = ('line2Dup.cpp', 'line2Dup.h', 'line2Dup_local.hpp',
        'line2Dup_search.hpp', 'line2Dup_response.hpp',
        'line2Dup_spread.hpp', 'line2Dup_matches.hpp')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def put_exact(path, data, create):
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise ValueError('Refusing to overwrite differing bytes: '+str(path))
    elif create:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    else:
        raise FileNotFoundError(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['freeze', 'verify', 'prepare-candidate'],
                        required=True)
    args = parser.parse_args()
    commit = git('rev-parse', COMMIT).decode().strip()
    mipp = git('ls-tree', '-r', '--name-only', commit, '--', 'MIPP').decode().splitlines()
    if len(mipp) != 16:
        raise ValueError('Unexpected MIPP inventory')
    entries = {}
    originals = {}
    for name in sorted(list(CORE)+mipp):
        data = git('show', f'{commit}:{name}')
        originals[name] = data
        entries[name] = {'sha256': hashlib.sha256(data).hexdigest(),
                         'bytes': len(data),
                         'git_blob': git('rev-parse', f'{commit}:{name}').decode().strip()}
        put_exact(HERE/'baseline'/name, data, args.mode == 'freeze')
    manifest = {'commit': commit,
                'method': 'git show exact stdout bytes; no encoding or newline conversion',
                'core_files': list(CORE), 'mipp_files': 16, 'files': entries}
    encoded = (json.dumps(manifest, indent=2)+'\n').encode()
    put_exact(HERE/'baseline/manifest.json', encoded, args.mode == 'freeze')
    observed = {p.relative_to(HERE/'baseline').as_posix()
                for p in (HERE/'baseline').rglob('*') if p.is_file()}
    if observed != set(entries)|{'manifest.json'}:
        raise ValueError('Unexpected or missing baseline file')
    if args.mode == 'prepare-candidate':
        for name in CORE:
            put_exact(HERE/'candidate'/name, originals[name], True)
        prepared = {'baseline_commit': commit,
                    'baseline_manifest_sha256': hashlib.sha256(encoded).hexdigest(),
                    'method': 'Exact copies of the seven V11 core Git blobs; cache stub is separate',
                    'files': {name: entries[name] for name in CORE}}
        put_exact(HERE/'candidate_initial_manifest.json',
                  (json.dumps(prepared, indent=2)+'\n').encode(), True)
    print(json.dumps({'passed': True, 'mode': args.mode, 'commit': commit,
                      'files': len(entries),
                      'baseline_manifest_sha256': hashlib.sha256(encoded).hexdigest()}))


if __name__ == '__main__':
    main()
