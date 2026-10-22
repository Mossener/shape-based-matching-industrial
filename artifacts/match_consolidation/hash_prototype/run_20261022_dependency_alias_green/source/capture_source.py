"""Create a new exact-V11 private source snapshot with one capture call seam."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

CORE_REVISION = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
CORE_FILES = ('line2Dup.cpp', 'line2Dup.h', 'line2Dup_local.hpp',
              'line2Dup_search.hpp', 'line2Dup_response.hpp',
              'line2Dup_spread.hpp', 'line2Dup_matches.hpp')


def instrument_core(source):
    include = b'#include "line2Dup_matches.hpp"'
    call = b'    detail::consolidateMatches(matches);'
    if (not isinstance(source, bytes) or source.count(include) != 1
            or source.count(call) != 1 or b'capture_hook.hpp' in source
            or b'capture_trace::' in source):
        raise ValueError('Need one pristine V11 helper include and consolidation call')
    newline = b'\r\n' if b'\r\n' in source else b'\n'
    return source.replace(include, include+newline+b'#include "capture_hook.hpp"').replace(
        call, b'    capture_trace::consolidate(matches);')


def make_snapshot(repo_root, destination, load_git=None):
    root = Path(repo_root).resolve(strict=True)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Snapshot destination must be new')
    if not destination.is_relative_to(root):
        raise ValueError('Snapshot destination must stay within the repository')
    if load_git is None:
        def load_git(*arguments):
            return subprocess.check_output(['git', *arguments], cwd=root)
    resolved = load_git('rev-parse', '--verify', CORE_REVISION).decode('ascii').strip()
    if resolved != CORE_REVISION:
        raise ValueError('Need exact fixed V11 revision')
    entries = {}
    for entry in load_git('ls-tree', '-r', '-z', CORE_REVISION).split(b'\x00'):
        if not entry:
            continue
        properties, raw_name = entry.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        selected = (name.startswith('MIPP/') or
                    ('/' not in name and name.startswith('line2Dup') and
                     PurePosixPath(name).suffix in ('.cpp', '.h', '.hpp')))
        if not selected:
            continue
        parts = properties.decode('ascii').split(' ')
        if (len(parts) != 3 or parts[0] not in ('100644', '100755') or parts[1] != 'blob'
                or not re.fullmatch('[0-9a-f]{40}', parts[2]) or name in entries
                or '\\' in name or ':' in name or '\x00' in name or
                any(p in ('', '.', '..') for p in name.split('/')) or
                PurePosixPath(name).is_absolute()):
            raise ValueError('Unsafe or duplicate source inventory entry')
        entries[name] = parts[2]
    if ({name for name in entries if not name.startswith('MIPP/')} != set(CORE_FILES)
            or sum(name.startswith('MIPP/') for name in entries) != 16):
        raise ValueError('Exact seven-core/sixteen-MIPP inventory required')
    originals = {}
    for name, blob in entries.items():
        data = load_git('show', CORE_REVISION+':'+name)
        actual_blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\x00'+data).hexdigest()
        if actual_blob != blob:
            raise ValueError('Git payload differs from tree blob: '+name)
        originals[name] = data
    captured = dict(originals)
    captured['line2Dup.cpp'] = instrument_core(originals['line2Dup.cpp'])
    destination.mkdir(parents=True, exist_ok=False)
    for kind, files in (('original', originals), ('captured', captured)):
        for name, data in files.items():
            path = destination/kind/name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
            if path.read_bytes() != data:
                raise ValueError('Snapshot bytes differ after write: '+name)
    manifest = dict(core_revision=CORE_REVISION, mipp_file_count=16,
                    recipe='Exact Git stdout bytes; one core call redirected and one include added',
                    helper_unchanged=True, files={
                        name: dict(git_blob=entries[name], original_bytes=len(originals[name]),
                                   captured_bytes=len(captured[name]),
                                   original_sha256=hashlib.sha256(originals[name]).hexdigest(),
                                   captured_sha256=hashlib.sha256(captured[name]).hexdigest())
                        for name in sorted(entries)})
    with (destination/'source_manifest.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(manifest, indent=2)+'\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = make_snapshot(args.repo_root, args.output)
    print(json.dumps(dict(passed=True, core_revision=manifest['core_revision'],
                          files=len(manifest['files']), matcher_calls=0, image_decodes=0,
                          performance_measurement=False)))


if __name__ == '__main__':
    main()
