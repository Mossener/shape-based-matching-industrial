"""Losslessly package accepted numeric training evidence for GitHub file limits.

Only files named by the original successful training provenance are exported.
Large JSONL text is gzip-compressed; existing numeric gzip banks/pools remain
byte-identical. This never includes training images, caches or executables.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil

CHUNK = 1024 * 1024
MAX_STORED_FILE = 95 * 1024**2
MAX_EXPORT = 2 * 1024**3


def require(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(CHUNK), b''):
            size += len(data)
            digest.update(data)
    return dict(bytes=size, sha256=digest.hexdigest())


def relative(value):
    path = Path(value)
    require(isinstance(value, str) and path.as_posix() == value and
            not path.is_absolute() and not path.drive and
            '..' not in path.parts and value not in ('', '.'), 'invalid relative path')
    require(path.suffix in ('.json', '.jsonl', '.gz'), 'numeric evidence only')
    return path


def stream_copy(source, target, expected, encoding):
    digest = hashlib.sha256()
    size = 0
    source_context = gzip.open(source, 'rb') if encoding == 'gzip' else Path(source).open('rb')
    with source_context as stream, Path(target).open('xb') as output:
        for data in iter(lambda: stream.read(CHUNK), b''):
            size += len(data)
            require(size <= expected['bytes'], 'decoded payload exceeds original bound')
            digest.update(data)
            output.write(data)
    require(dict(bytes=size, sha256=digest.hexdigest()) == expected,
            'restored bytes differ from original')


def package(source, provenance_path, acceptance_path, output):
    source, output = source.resolve(), output.resolve()
    require(not output.exists() and not output.is_relative_to(source), 'fresh separate export required')
    provenance = json.loads(provenance_path.read_text(encoding='utf-8-sig'))
    acceptance = json.loads(acceptance_path.read_text(encoding='utf-8-sig'))
    require(provenance.get('passed') is True and provenance.get('mode') == 'train',
            'complete original training required')
    require(acceptance.get('real_training_accepted') is True and
            acceptance.get('numeric_audit_passed') is True, 'accepted complete training required')
    require(acceptance['training_provenance']['path'] == str(provenance_path.resolve()) and
            {key: acceptance['training_provenance'][key] for key in ('bytes', 'sha256')} == pin(provenance_path),
            'acceptance belongs to different provenance')
    expected = {}
    for value in provenance['files']:
        path = Path(value['path']).resolve()
        require(path.is_relative_to(source) and not path.is_symlink(), 'training member escaped source')
        name = path.relative_to(source).as_posix()
        relative(name)
        require(name not in expected, 'duplicate training member')
        expected[name] = {key: value[key] for key in ('bytes', 'sha256')}
    actual = {path.relative_to(source).as_posix() for path in source.rglob('*') if path.is_file()}
    require(actual == set(expected), 'complete training inventory differs')
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    total = 0
    for name, original in sorted(expected.items()):
        path = source / relative(name)
        require(pin(path) == original, 'original training file changed')
        encoding = 'gzip' if path.suffix != '.gz' and original['bytes'] >= 16 * 1024**2 else 'identity'
        stored = name + '.gz' if encoding == 'gzip' else name
        target = output / stored
        target.parent.mkdir(parents=True, exist_ok=True)
        with path.open('rb') as stream, target.open('xb') as destination:
            if encoding == 'gzip':
                with gzip.GzipFile(fileobj=destination, mode='wb', filename='', mtime=0) as compressed:
                    shutil.copyfileobj(stream, compressed, CHUNK)
            else:
                shutil.copyfileobj(stream, destination, CHUNK)
        saved = pin(target)
        require(saved['bytes'] <= MAX_STORED_FILE, 'stored member exceeds public file limit')
        total += saved['bytes']
        require(total <= MAX_EXPORT, 'public export exceeds budget')
        # Read back the complete stored stream without materializing a copy.
        digest = hashlib.sha256()
        count = 0
        context = gzip.open(target, 'rb') if encoding == 'gzip' else target.open('rb')
        with context as stream:
            for data in iter(lambda: stream.read(CHUNK), b''):
                count += len(data)
                require(count <= original['bytes'], 'export decoded payload exceeds original bound')
                digest.update(data)
        require(dict(bytes=count, sha256=digest.hexdigest()) == original, 'export roundtrip differs')
        require(pin(path) == original, 'training file changed during export')
        rows.append(dict(original_path=name, original=original, stored_path=stored,
                         stored=saved, encoding=encoding))
    manifest = dict(schema='rgb_stratified_lossless_training_export_v1',
        passed=True, files=rows, file_count=len(rows), stored_bytes=total,
        original_physical_bytes=sum(row['bytes'] for row in expected.values()),
        training_provenance=dict(path=str(provenance_path.resolve()), **pin(provenance_path)),
        training_acceptance=dict(path=str(acceptance_path.resolve()), **pin(acceptance_path)),
        source=dict(path=str(Path(__file__).resolve()), **pin(__file__)),
        native_calls=0, image_decodes=0, heldout_image_reads=0,
        limitation='Lossless transport of numeric evidence; no new training or quality claim')
    (output / 'EXPORT_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


def restore(export, output):
    export, output = export.resolve(), output.resolve()
    require(not output.exists() and not output.is_relative_to(export), 'fresh separate restore required')
    manifest = json.loads((export / 'EXPORT_MANIFEST.json').read_text(encoding='utf-8-sig'))
    require(manifest.get('schema') == 'rgb_stratified_lossless_training_export_v1' and
            manifest.get('passed') is True, 'complete export manifest required')
    seen = set()
    stored = set()
    for row in manifest['files']:
        name, saved = row['original_path'], row['stored_path']
        relative(name)
        relative(saved)
        require(name not in seen and saved not in stored, 'duplicate export member')
        seen.add(name)
        stored.add(saved)
        require(row['encoding'] in ('identity', 'gzip'), 'invalid encoding')
        require((export / saved).resolve().is_relative_to(export) and
                not (export / saved).is_symlink(), 'export member escaped root')
        require(pin(export / saved) == row['stored'], 'stored member bytes changed')
    require(len(seen) == manifest['file_count'] and stored | {'EXPORT_MANIFEST.json'} ==
            {p.relative_to(export).as_posix() for p in export.rglob('*') if p.is_file()},
            'export inventory differs')
    output.mkdir(parents=True, exist_ok=False)
    for row in manifest['files']:
        target = output / row['original_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        stream_copy(export / row['stored_path'], target, row['original'], row['encoding'])
    return dict(passed=True, files=len(seen), restored_original_bytes=manifest['original_physical_bytes'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    pack = commands.add_parser('package')
    pack.add_argument('--source', type=Path, required=True)
    pack.add_argument('--provenance', type=Path, required=True)
    pack.add_argument('--acceptance', type=Path, required=True)
    pack.add_argument('--output', type=Path, required=True)
    unpack = commands.add_parser('restore')
    unpack.add_argument('--export', type=Path, required=True)
    unpack.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'package':
        result = package(args.source, args.provenance, args.acceptance, args.output)
        print(json.dumps(dict(passed=True, files=result['file_count'], stored_bytes=result['stored_bytes'])))
    else:
        print(json.dumps(restore(args.export, args.output)))


if __name__ == '__main__':
    main()
