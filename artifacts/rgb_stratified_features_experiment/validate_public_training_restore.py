"""Materialize the accepted training export, then independently hash all originals.

Transport verification only: no image decoding, training or matcher invocation.
The second inventory/hash pass uses the accepted original provenance, rather
than trusting the exporter's restore return value or its manifest's originals.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

import execution_guard

HERE = Path(__file__).resolve().parent
EXPORT = HERE / 'public_training_export_v1'
RESTORED = HERE / 'public_training_restore_validation_v1'
EVIDENCE = HERE / 'PUBLIC_EXPORT_RESTORE_CHECK'
EXECUTION = HERE / 'PUBLIC_EXPORT_RESTORE_CHECK_execution'
ACCEPTANCE = HERE / 'PUBLIC_EXPORT_ACCEPTANCE.json'
EXPORT_PIN = dict(bytes=22826,
    sha256='9094d4f4fde321b1c1099bd9f762cc3de9522e8e8894a026555812376323d10f')


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    count = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            count += len(block)
            digest.update(block)
    return dict(path=str(path), bytes=count, sha256=digest.hexdigest())


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    need(sys.argv[1:] == ['--cpu-slot-granted'], 'One coordinated transport slot required')
    need(all(not path.exists() for path in (RESTORED, EVIDENCE, EXECUTION, ACCEPTANCE)),
         'Fresh restore, execution and acceptance paths required; preserve failed attempts')
    manifest_pin = pin(EXPORT / 'EXPORT_MANIFEST.json')
    need({key: manifest_pin[key] for key in EXPORT_PIN} == EXPORT_PIN,
         'Root-accepted export manifest differs')
    manifest = load(manifest_pin['path'])
    training_acceptance = load(manifest['training_acceptance']['path'])
    need(pin(manifest['training_acceptance']['path']) == manifest['training_acceptance'] and
         training_acceptance['real_training_accepted'] is True and
         training_acceptance['numeric_audit_passed'] is True,
         'Complete accepted original training required')
    provenance_pin = training_acceptance['training_provenance']
    need(provenance_pin == manifest['training_provenance'] and
         pin(provenance_pin['path']) == provenance_pin, 'Original provenance binding differs')
    provenance = load(provenance_pin['path'])
    need(provenance['passed'] is True and provenance['mode'] == 'train', 'Original training failed')
    original_root = HERE / 'run_training_v1'
    expected = {}
    for row in provenance['files']:
        path = Path(row['path']).resolve()
        need(path.is_relative_to(original_root), 'Original member escaped accepted training root')
        name = path.relative_to(original_root).as_posix()
        need(name not in expected, 'Duplicate original member')
        expected[name] = {key: row[key] for key in ('bytes', 'sha256')}
    exported = {row['original_path']: row['original'] for row in manifest['files']}
    need(len(exported) == len(manifest['files']) == len(expected) == 46 and exported == expected,
         'Export original mapping differs from accepted provenance')
    sources = [pin(path) for path in (Path(__file__), HERE / 'preserve_training_evidence.py',
                                    HERE / 'execution_guard.py', Path(sys.executable))]
    need(sources[1] == manifest['source'], 'Exporter source changed after package')
    command = [sys.executable, '-B', str(HERE / 'preserve_training_evidence.py'),
               'restore', '--export', str(EXPORT), '--output', str(RESTORED)]
    EVIDENCE.mkdir()
    save(EVIDENCE / 'invocation.json', dict(command=command, sources=sources,
        export_manifest=manifest_pin, provenance=provenance_pin,
        restore_root=str(RESTORED), native_calls=0, image_decodes=0))
    result = dict(schema='rgb_stratified_independent_export_restore_check_v1', passed=False,
        export_manifest=manifest_pin, training_provenance=provenance_pin, sources=sources,
        native_calls=0, image_decodes=0, heldout_image_reads=0, production_promotion=False)
    try:
        guard = execution_guard.run_guarded(command, dict(os.environ), HERE, RESTORED, EXECUTION,
            maximum_seconds=5400, maximum_rss_bytes=1073741824,
            maximum_output_bytes=2147483648, minimum_free_bytes=2147483648,
            maximum_execution_bytes=67108864)
        result['guard'] = guard
        need(guard['passed'] is True and guard['exit_code'] == 0, 'Fresh restore execution failed')
        actual = set()
        for path in RESTORED.rglob('*'):
            need(not path.is_symlink() and path.resolve().is_relative_to(RESTORED),
                 'Restored inventory contains an escaped or linked path')
            if path.is_file():
                actual.add(path.relative_to(RESTORED).as_posix())
        need(actual == set(expected), 'Independent restored original-name inventory differs')
        rows = []
        for name in sorted(expected):
            value = pin(RESTORED / name)
            need({key: value[key] for key in ('bytes', 'sha256')} == expected[name],
                 'Independent original-byte readback differs: ' + name)
            rows.append(dict(original_path=name, expected=expected[name], restored=value, passed=True))
        need(pin(manifest_pin['path']) == manifest_pin and
             pin(provenance_pin['path']) == provenance_pin and
             pin(manifest['training_acceptance']['path']) == manifest['training_acceptance'] and
             all(pin(row['path']) == row for row in sources), 'Input/source changed during restore')
        result.update(passed=True, files=len(rows),
            restored_original_bytes=sum(row['restored']['bytes'] for row in rows), rows=rows,
            limitations=['Independent inventory/hash readback uses the accepted original provenance',
                         'Exporter decoder is reused; this is no new numeric training audit',
                         'Complete transitive Python runtime is not attested'])
    except BaseException as error:
        result.update(incomplete=True, reason=repr(error))
    check_path = EVIDENCE / 'result.json'
    save(check_path, result)
    execution_files = [pin(EXECUTION / name) for name in (
        'guard_reservation.json', 'guard_latest.json', 'guard_telemetry.jsonl',
        'guard_receipt.json', 'stdout.txt', 'stderr.txt') if (EXECUTION / name).exists()]
    save(ACCEPTANCE, dict(schema='rgb_stratified_public_export_acceptance_v1',
        passed=result['passed'], independently_restored=result['passed'], export_manifest=manifest_pin,
        training_provenance=provenance_pin, restore_check=pin(check_path),
        invocation=pin(EVIDENCE / 'invocation.json'), execution_files=execution_files,
        source=sources[0], native_calls=0, image_decodes=0, production_promotion=False))
    print(json.dumps(dict(passed=result['passed'], files=result.get('files'),
                         restored_original_bytes=result.get('restored_original_bytes'))))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
