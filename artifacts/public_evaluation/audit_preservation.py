#!/usr/bin/env python3
"""Independently audit published numeric packages; never open original datasets."""
import argparse
from copy import deepcopy
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def audit(manifest_path, root):
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode('utf-8-sig'))
    package = manifest_path.parent.parent.resolve()
    seen = set()
    archives = []
    copied_bytes = 0
    for item in manifest['files']:
        relative = PurePosixPath(item['copy'].replace('\\', '/'))
        require(not relative.is_absolute() and '..' not in relative.parts,
                'Unsafe copy path')
        path = (root / str(relative)).resolve()
        require(package in path.parents, 'Copy outside its numeric package')
        require(path not in seen, 'Duplicate copy entry')
        seen.add(path)
        require(path.name.endswith(('.json', '.csv', '.json.gz', '.csv.gz',
                                    '.yml.gz', '.tar.gz')), 'Nonnumeric file')
        data = path.read_bytes()
        require(len(data) == item['bytes'], 'Copy byte count differs')
        require(sha(data) == item['copy_sha256'], 'Copy SHA differs')
        copied_bytes += len(data)
        if 'source_sha256' in item:
            original_name = PurePosixPath(item['source'].replace('\\', '/')).name
            source_bytes = (gzip.decompress(data)
                            if path.name == original_name + '.gz' else data)
            require(sha(source_bytes) == item['source_sha256'],
                    'Restored original bytes differ from source SHA')
        else:
            require(path.name == 'raw_numeric.tar.gz', 'Unknown archive')
            archives.append((path, item, data))
    require(len(archives) == 1, 'Expected one raw archive')
    expected = {}
    pattern = re.compile(r's\d+_i\d+_(fallback|fused)_raw(?:\.csv\.gz|_manifest\.json)\Z')
    for item in manifest['raw_archive_members']:
        require(pattern.fullmatch(item['name']) is not None, 'Unsafe/nonnumeric tar name')
        require(item['name'] not in expected, 'Duplicate expected member')
        expected[item['name']] = item
    archive_path, archive_info, archive_bytes = archives[0]
    require(len(expected) == archive_info['members'], 'Member count differs')
    require(len(expected) == 2 * manifest['raw_archives'], 'Raw pair count differs')
    observed = set()
    uncompressed_bytes = 0
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:gz') as archive:
        for member in archive:
            require(member.isfile(), 'Tar entry is not a regular file')
            require(member.name in expected, 'Unexpected tar member')
            require(member.name not in observed, 'Duplicate tar member')
            observed.add(member.name)
            data = archive.extractfile(member).read()
            item = expected[member.name]
            require(member.size == len(data) == item['bytes'], 'Tar byte count differs')
            require(sha(data) == item['sha256'], 'Tar member SHA differs')
            uncompressed_bytes += len(data)
    require(observed == set(expected), 'Missing tar member')
    require(sum(name.endswith('.csv.gz') for name in observed) == manifest['raw_archives'],
            'Raw CSV count differs')
    for name in observed:
        if name.endswith('.csv.gz'):
            require(name[:-len('.csv.gz')] + '_manifest.json' in observed,
                    'Missing paired raw manifest')
        else:
            require(name[:-len('_manifest.json')] + '.csv.gz' in observed,
                    'Missing paired raw CSV')
    return {'manifest': manifest_path.as_posix(), 'manifest_sha256': sha(manifest_bytes),
            'object_id': manifest['object_id'], 'stage': manifest['stage'],
            'copied_files': len(seen), 'copied_bytes': copied_bytes,
            'raw_archives': manifest['raw_archives'], 'tar_members': len(observed),
            'tar_member_bytes': uncompressed_bytes, 'tar_sha256': sha(archive_bytes)}


def self_test():
    rejected = []
    with tempfile.TemporaryDirectory(prefix='numeric-package-audit-') as directory:
        root = Path(directory)
        stage = root/'artifacts'/'fixture'/'development'
        stage.mkdir(parents=True)
        copied = gzip.compress(b'{"numeric": 1}\n', mtime=0)
        (stage/'metrics.json.gz').write_bytes(copied)
        raw = [('s1_i2_fallback_raw.csv.gz', gzip.compress(b'rank,score\n0,85\n', mtime=0)),
               ('s1_i2_fallback_raw_manifest.json', b'{"raw_candidate_count":1}\n')]

        def make_tar(rows):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w:gz') as archive:
                for name, data in rows:
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            return stream.getvalue()

        archive_bytes = make_tar(raw)
        archive_path = stage/'raw_numeric.tar.gz'
        archive_path.write_bytes(archive_bytes)
        manifest = {'object_id': 1, 'stage': 'development', 'raw_archives': 1,
                    'raw_archive_members': [dict(name=n, bytes=len(d), sha256=sha(d)) for n,d in raw],
                    'files': [dict(source='local/metrics.json', copy='artifacts/fixture/development/metrics.json.gz',
                                   source_sha256=sha(gzip.decompress(copied)), copy_sha256=sha(copied), bytes=len(copied)),
                              dict(copy='artifacts/fixture/development/raw_numeric.tar.gz', copy_sha256=sha(archive_bytes),
                                   bytes=len(archive_bytes), members=2)]}
        manifest_path = stage/'preservation_manifest.json'

        def check(value):
            manifest_path.write_text(json.dumps(value), encoding='utf-8')
            return audit(manifest_path, root)

        check(manifest)

        def reject(name, mutate, replacement=None):
            changed = deepcopy(manifest)
            if replacement is not None:
                archive_path.write_bytes(replacement)
                changed['files'][1]['bytes'] = len(replacement)
                changed['files'][1]['copy_sha256'] = sha(replacement)
            mutate(changed)
            try:
                check(changed)
            except (ValueError, FileNotFoundError):
                rejected.append(name)
            else:
                raise RuntimeError('Mutation not rejected: ' + name)
            finally:
                archive_path.write_bytes(archive_bytes)

        reject('copy_sha', lambda m: m['files'][0].update(copy_sha256='0'*64))
        reject('source_sha', lambda m: m['files'][0].update(source_sha256='0'*64))
        reject('copy_size', lambda m: m['files'][0].update(bytes=1))
        reject('parent_path', lambda m: m['files'][0].update(copy='../secret.json'))
        reject('outside_package', lambda m: m['files'][0].update(copy='other/value.json'))
        reject('duplicate_copy', lambda m: m['files'].append(deepcopy(m['files'][0])))
        reject('raw_count', lambda m: m.update(raw_archives=2))
        reject('missing_tar_member', lambda m: None, make_tar(raw[:1]))
        reject('duplicate_tar_member', lambda m: None, make_tar(raw + raw[:1]))
        reject('unexpected_tar_member', lambda m: None, make_tar(raw+[('image.png', b'x')]))
        reject('member_sha', lambda m: m['raw_archive_members'][0].update(sha256='0'*64))
        reject('member_bytes', lambda m: m['raw_archive_members'][0].update(bytes=1))
        reject('duplicate_expected', lambda m: m['raw_archive_members'].append(deepcopy(m['raw_archive_members'][0])))
        reject('unsafe_tar_name', lambda m: m['raw_archive_members'][0].update(name='../image.png'))
        only_manifests = [('s1_i2_fallback_raw_manifest.json', b'{}'),
                          ('s1_i2_fused_raw_manifest.json', b'{}')]
        reject('manifest_only_pair',
               lambda m: m.update(raw_archive_members=[dict(name=n, bytes=len(d), sha256=sha(d))
                                                       for n,d in only_manifests]),
               make_tar(only_manifests))
        check(manifest)
    return {'green_fixture_checks': 2, 'rejected_mutations': rejected,
            'original_or_derived_images_opened': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--manifest', type=Path, action='append', default=[])
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(args.self_test or args.manifest, 'Supply a manifest or --self-test')
    result = {'passed': True, 'audit_script_sha256': sha(Path(__file__).read_bytes()),
              'scope': 'Only published numeric copies and tar bytes; no original source path is opened.',
              'self_test': self_test() if args.self_test else None,
              'packages': [audit(path, args.root.resolve()) for path in args.manifest]}
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
