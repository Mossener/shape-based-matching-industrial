#!/usr/bin/env python3
"""Supplement frozen build provenance with all MIPP/core bytes from committed V11."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def git(*args):
    return subprocess.check_output(['git', *args])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main(args):
    revision = git('rev-parse', args.revision).decode().strip()
    head = git('rev-parse', 'HEAD').decode().strip()
    tracked = git('ls-tree', '-r', '--name-only', revision).decode().splitlines()
    names = [p for p in tracked if p.startswith('MIPP/') or ('/' not in p and p.startswith('line2Dup') and Path(p).suffix in ['.h', '.hpp', '.cpp'])]
    mipp_names = {p for p in names if p.startswith('MIPP/')}
    assert {p.as_posix() for p in Path('MIPP').rglob('*') if p.is_file()} == mipp_names, 'MIPP file set differs from committed V11'
    records = []
    frozen = json.loads(args.manifest.read_text(encoding='utf-8')) if args.manifest.exists() else None
    frozen_files = {r['path']: r for r in frozen['files']} if frozen else {}
    for name in names:
        current = Path(name).read_bytes()
        if frozen:
            record = frozen_files[name]
            assert len(current) == record['bytes'] and digest(current) == record['sha256'], 'Current input differs from frozen committed bytes: '+name
            records.append(record)
        else:
            committed = git('show', revision+':'+name)
            assert current == committed, 'Current input differs from committed bytes: '+name
            records.append({'path': name, 'bytes': len(current), 'sha256': digest(current),
                            'git_blob_oid': git('rev-parse', revision+':'+name).decode().strip(), 'byte_equal_to_committed': True})
    result = {'core_revision': revision, 'root_head_at_freeze': head, 'mipp_files': len(mipp_names),
              'root_core_files': len(records)-len(mipp_names), 'all_current_files_byte_equal_to_committed': True, 'files': records,
              'clarification': 'Supplementary dependency integrity audit; original build manifests are preserved. No matcher code or compiler flags changed.'}
    if args.manifest.exists():
        old = frozen
        assert old['core_revision'] == revision and old['files'] == records, 'Frozen dependency manifest drift'
    else:
        args.manifest.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    check = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'stage': args.stage, 'root_head_now': head,
             'manifest_sha256': digest(args.manifest.read_bytes()), 'files_verified': len(records), 'passed': True}
    args.journal.parent.mkdir(parents=True, exist_ok=True)
    with args.journal.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(check)+'\n')
    print(json.dumps(check))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default='b25df46f6ddf9c24fb43f5836f1414dc38c8caed')
    parser.add_argument('--manifest', type=Path, default=Path('artifacts/public_evaluation/dependency_integrity.json'))
    parser.add_argument('--journal', type=Path, default=Path('artifacts/public_evaluation/build/dependency_checks.jsonl'))
    parser.add_argument('--stage', required=True)
    main(parser.parse_args())
