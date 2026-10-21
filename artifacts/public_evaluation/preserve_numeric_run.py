#!/usr/bin/env python3
"""Preserve a recorded run's numeric evidence and bank, without copying RGB."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(destination, data):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        assert destination.read_bytes() == data, 'Refusing to overwrite changed preserved evidence: '+str(destination)
    else:
        destination.write_bytes(data)


def compressed(data):
    return gzip.compress(data, compresslevel=6, mtime=0)


def preserve(args):
    training = json.loads((args.training/'training_config.json').read_text(encoding='utf-8-sig'))
    object_id = training.get('target_objects', [1])[0]
    paths = []
    for name in ['training_config.json', 'execution_provenance.json', 'template_attempts.csv', 'template_metadata.json', f'templates_tless_object_{object_id}.yml.gz']:
        source = args.training/name
        data = source.read_bytes()
        dest = args.output/'training'/name
        if source.suffix in ['.json', '.csv'] and len(data) > 262144:
            dest = dest.with_name(dest.name+'.gz'); data = compressed(data)
        put(dest, data)
        paths.append({'source': str(source), 'copy': str(dest), 'source_sha256': sha(source.read_bytes()), 'copy_sha256': sha(data), 'bytes': len(data)})
    run_dir = args.output/args.stage
    raw = sorted(args.run.glob('*_raw.csv.gz'))
    raw_members = []
    for source in sorted(args.run.iterdir()):
        if not source.is_file() or source.name == '.gitignore' or '_raw' in source.name:
            continue
        assert source.suffix in ['.json', '.csv'], 'Unexpected nonnumeric file'
        data = source.read_bytes(); dest = run_dir/source.name
        if len(data) > 262144:
            dest = dest.with_name(dest.name+'.gz'); data = compressed(data)
        put(dest, data)
        paths.append({'source': str(source), 'copy': str(dest), 'source_sha256': sha(source.read_bytes()), 'copy_sha256': sha(data), 'bytes': len(data)})
    buffer = io.BytesIO()
    with tarfile.open(mode='w', fileobj=buffer) as archive:
        for source in raw:
            for member in [source, source.with_name(source.name.replace('.csv.gz', '_manifest.json'))]:
                data = member.read_bytes(); info = tarfile.TarInfo(member.name); info.size = len(data); info.mtime=0; info.mode=0o644
                archive.addfile(info, io.BytesIO(data))
                raw_members.append({'name': member.name, 'bytes': len(data), 'sha256': sha(data)})
    data = compressed(buffer.getvalue())
    assert len(data) < 50*1024*1024, 'Numeric archive exceeds public artifact size limit; keep raw local'
    archive_path = run_dir/'raw_numeric.tar.gz'; put(archive_path, data)
    paths.append({'copy': str(archive_path), 'copy_sha256': sha(data), 'bytes': len(data), 'members': len(raw_members)})
    manifest = {'warning': 'Numeric evidence only. No original or derived RGB/failure PNG is copied. Raw local files are untouched. Source absolute paths in copied provenance retain their execution context.',
                'object_id': object_id, 'stage': args.stage, 'source_run': str(args.run), 'raw_archives': len(raw), 'raw_archive_members': raw_members, 'files': paths}
    put(run_dir/'preservation_manifest.json', (json.dumps(manifest, indent=2)+'\n').encode())
    print(json.dumps({'object_id': object_id, 'stage': args.stage, 'raw_archives': len(raw), 'raw_numeric_tar_bytes': len(data), 'output': str(run_dir)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=['pilot', 'development'], required=True)
    preserve(parser.parse_args())
