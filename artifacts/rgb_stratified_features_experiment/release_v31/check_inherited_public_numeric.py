"""Verify inherited numeric inputs are exact bytes already present in Git HEAD.

Explicit declared numeric inventories only; never traverses dataset images,
runtime binaries or arbitrary input/source references. No Git mutation.
"""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parents[1]


def need(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    output = HERE / 'INHERITED_PUBLIC_NUMERIC_AVAILABILITY.json'
    need(not output.exists(), 'Fresh inherited numeric availability receipt required')
    inputs_path = HERE / 'quality/QUALITY_INPUT_FREEZE.json'
    training_path = HERE / 'TRAINING_INPUT_FREEZE.json'
    prior_path = ROOT / 'artifacts/rgb_dilated_mask_experiment/PUBLISH_SELECTION_V30.json'
    inputs, training, prior = map(load, (inputs_path, training_path, prior_path))
    prior_rows = {row['path']: row for row in prior['files']}
    object_format = subprocess.check_output(['git', 'rev-parse', '--show-object-format'], cwd=ROOT).decode().strip()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '-z', 'HEAD'], cwd=ROOT)
    tracked = {}
    for row in tree.split(b'\0'):
        if row:
            metadata, name = row.split(b'\t', 1)
            mode, kind, oid = metadata.decode().split()
            if kind == 'blob':
                tracked[name.decode('utf-8')] = (mode, oid)
    declared = list(inputs['frozen_numeric_files']) + inputs['bank_input_files'] + inputs['raw_reference_files']
    declared += [inputs[key] for key in ('inherited_c0_development_stage', 'protocol',
        'inherited_quality_input_freeze', 'inherited_input_closure')]
    declared += [training['origin'], training['protocol']]
    unique = {}
    external_dataset_metadata = {}
    for value in declared:
        path = Path(value['path']).resolve()
        need(path.is_relative_to(ROOT), 'Numeric declaration escaped repository')
        if path.is_relative_to(HERE):
            continue
        need(not any(part.is_symlink() for part in (path, *path.parents)), 'Linked numeric input refused')
        need(not ({'.png', '.jpg', '.bmp', '.smd', '.exe', '.dll', '.o', '.bin'} & set(path.suffixes)),
             'Unexpected image/runtime in explicit numeric inventory')
        rel = path.relative_to(ROOT).as_posix()
        clean = dict(path=str(path), bytes=value['bytes'], sha256=value['sha256'])
        if path.is_relative_to(ROOT / 'datasets'):
            # The acquisition index is an external dataset declaration. Do
            # not read it here: it can also name sealed evaluation members.
            need(path == ROOT / 'datasets/tless_expanded/index.json',
                 'Undeclared external numeric metadata: ' + rel)
            need(rel not in external_dataset_metadata or external_dataset_metadata[rel] == clean,
                 'Conflicting external dataset metadata declaration')
            external_dataset_metadata[rel] = clean
            continue
        need(rel not in unique or unique[rel] == clean, 'Conflicting inherited numeric declaration')
        unique[rel] = clean
    rows = []
    for rel, value in sorted(unique.items()):
        need(rel in tracked and tracked[rel][0] in ('100644', '100755'), 'Inherited numeric input not published: ' + rel)
        path = Path(value['path'])
        need(path.stat().st_size == value['bytes'], 'Inherited size differs: ' + rel)
        digest = hashlib.sha256()
        blob = hashlib.new(object_format)
        blob.update(b'blob ' + str(value['bytes']).encode() + b'\0')
        count = 0
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                count += len(block)
                digest.update(block)
                blob.update(block)
        need(count == value['bytes'] and digest.hexdigest() == value['sha256'], 'Inherited bytes differ: ' + rel)
        need(blob.hexdigest() == tracked[rel][1], 'Inherited Git HEAD bytes differ: ' + rel)
        previous = prior_rows.get(rel)
        if previous:
            need((previous['bytes'], previous['sha256']) == (value['bytes'], value['sha256']),
                 'Prior public selection differs: ' + rel)
        rows.append(dict(pin=value, git_path=rel, git_blob=tracked[rel][1],
            exact_prior_V30_selection_member=previous is not None))
    result = dict(schema='v31_inherited_public_numeric_availability_v1', passed=True,
        revision=revision, git_object_format=object_format,
        sources=[pin(inputs_path), pin(training_path), pin(prior_path), pin(__file__)],
        file_count=len(rows), numeric_bytes=sum(row['pin']['bytes'] for row in rows), files=rows,
        external_dataset_metadata_pins=list(external_dataset_metadata.values()),
        all_declared_numeric_bundled=not external_dataset_metadata,
        matcher_calls=0, image_decodes=0, git_mutations=0,
        limitations=['Checks exact public Git HEAD availability of inherited numeric artifact dependencies only',
                     'The local dataset acquisition index is an external pin declaration; its bytes were not read or bundled',
                     'Dataset images remain external; current P/B banks use the accepted lossless training export'])
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, file_count=len(rows), numeric_bytes=result['numeric_bytes'])))


if __name__ == '__main__':
    main()
