"""Create the frozen six-object numeric/input closure without opening images.

Expected training/test image hashes come from the frozen download manifest.
They are not retroactively attributed to the original training runner, whose
record pins only its index, download manifest and build. Actual byte checks are
an explicit later phase and require the coordinated CPU slot.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OBJECTS = [1, 2, 5, 8, 12, 17]
MANIFEST_SHA = 'b97154a31063e14043b91da95dc8d7ce93a42f9c42394e7e8edd7ae9d9e2108c'
SOURCE_READS = {}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(value):
    text = str(value).replace('\\', '/')
    path = PurePosixPath(text)
    require(text and not path.is_absolute() and '..' not in path.parts and ':' not in text and str(path) == text,
            'Unsafe dataset relative path')
    return text


def read(path, expected=None):
    path = Path(path).resolve()
    data = path.read_bytes()
    sha = digest(data)
    require(expected is None or sha == expected.lower(), 'Frozen input SHA changed: '+str(path))
    old = SOURCE_READS.get(str(path))
    require(old is None or old['sha256'] == sha, 'Input changed during closure: '+str(path))
    SOURCE_READS[str(path)] = dict(sha256=sha, bytes=len(data))
    return data


def load(path, expected=None):
    return json.loads(read(path, expected).decode('utf-8-sig'))


def unpack_copy(name, encoded, original_sha):
    # Original banks remain compressed byte-for-byte. The two preservation-only
    # gzip wrappers are removed to recover the original native JSON/CSV bytes.
    if name in ('template_metadata.json.gz', 'template_attempts.csv.gz'):
        original = gzip.decompress(encoded)
        name = name[:-3]
    else:
        original = encoded
    require(digest(original) == original_sha, 'Copied training original SHA changed: '+name)
    return name, original


def file_lookup(manifest):
    files = {relative(item['local_path']): item for item in manifest['files']}
    require(len(files) == len(manifest['files']), 'Duplicate downloaded member')
    for item in files.values():
        require(item['bytes'] > 0 and re.fullmatch('[0-9a-fA-F]{64}', item['sha256']), 'Malformed downloaded member hash/size')
    return files


def training_records(index, manifest):
    require(index['development_objects'] == OBJECTS and index['strict_object_generalization'] == [25, 29], 'Dataset object partition changed')
    files = file_lookup(manifest)
    records, seen = [], set()
    for frame in index['training']:
        obj = frame['target_obj_id']
        if obj not in OBJECTS:
            continue
        key = (obj, frame['image_id'])
        require(key not in seen and len(frame['instances']) == 1 and frame['instances'][0]['obj_id'] == obj, 'Duplicate/invalid training view')
        seen.add(key)
        rgb, mask = relative(frame['rgb']), relative(frame['instances'][0]['mask'])
        require(rgb in files and mask in files, 'Training image absent from frozen download manifest')
        records.append(dict(object_id=obj, image_id=frame['image_id'], rgb=rgb, mask=mask,
                            rgb_sha256=files[rgb]['sha256'], rgb_bytes=files[rgb]['bytes'],
                            mask_sha256=files[mask]['sha256'], mask_bytes=files[mask]['bytes']))
    require(Counter(r['object_id'] for r in records) == dict.fromkeys(OBJECTS, 72), 'Training view coverage changed')
    require(len({r[k] for r in records for k in ('rgb', 'mask')}) == 864, 'Training input paths are not unique')
    return sorted(records, key=lambda r: (r['object_id'], r['image_id']))


def development_records(index, manifest, schedule):
    files = file_lookup(manifest)
    planned = {(r['scene_id'], r['image_id']): r for r in schedule['frames']}
    require(len(planned) == len(schedule['frames']) == 400, 'Frame schedule coverage changed')
    records, seen = [], set()
    for frame in index['test']:
        if frame['split'] != 'development':
            continue
        key = (frame['scene_id'], frame['image_id'])
        require(key in planned and key not in seen and (frame['width'], frame['height']) == (720, 540), 'Development frame scope/dimensions changed')
        seen.add(key)
        rgb = relative(frame['rgb'])
        require(rgb in files, 'Development image absent from frozen download manifest')
        records.append(dict(scene_id=key[0], image_id=key[1], rgb=rgb, rgb_sha256=files[rgb]['sha256'], rgb_bytes=files[rgb]['bytes'],
                            pilot=bool(planned[key]['pilot']), timing=bool(planned[key]['timing'])))
    require(seen == set(planned) and len(records) == 400 and sum(r['pilot'] for r in records) == 8 and sum(r['timing'] for r in records) == 64,
            'Development schedule split changed')
    return sorted(records, key=lambda r: (r['scene_id'], r['image_id']))


def create():
    destination = HERE/'frozen_inputs'
    require(not destination.exists() and not (HERE/'INPUT_CLOSURE.json').exists(), 'Input closure must be new')
    protocol = load(HERE/'PROTOCOL.json')
    for item in protocol['input_pin_sources']:
        read(ROOT/item['path'], item['sha256'])
    source_freeze = load(HERE/'PRIVATE_SOURCE_FREEZE.json')
    require(source_freeze['git_revision'] == protocol['core_revision'] and source_freeze['file_count'] == 23, 'Private source freeze missing')
    index = load(ROOT/'datasets/tless_expanded/index.json')
    download = load(ROOT/'artifacts/public_datasets/tless_expanded_manifest.json', MANIFEST_SHA)
    schedule = load(ROOT/'artifacts/obj8_padding_experiment/frame_schedule.json')
    training = training_records(index, download)
    frames = development_records(index, download, schedule)
    pilot_keys = {(r['scene_id'], r['image_id']) for r in frames if r['pilot']}
    require(pilot_keys == set(map(tuple, protocol['pilot_frames'])), 'Pilot frame identities changed')
    destination.mkdir()
    private_records, banks = {}, []

    def write(relative_name, data):
        path = destination/relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        require(not path.exists(), 'Duplicate private input write')
        path.write_bytes(data)
        private_records[path.relative_to(HERE).as_posix()] = dict(sha256=digest(data), bytes=len(data))
        return str(path)

    # Store the exact source index as evidence, although the native helper uses
    # the original dataset root so the existing paths keep their meaning.
    write('dataset_index.json', read(ROOT/'datasets/tless_expanded/index.json'))
    for obj in OBJECTS:
        old_dir = ROOT/f'artifacts/public_evaluation/expanded_obj{obj}_v11/development'
        old = load(old_dir/'preservation_manifest.json')
        require(old['object_id'] == obj and old['stage'] == 'development' and old['raw_archives'] == 800, 'Original preservation scope changed')
        write(f'obj{obj}/original_preservation_manifest.json', read(old_dir/'preservation_manifest.json'))
        training_dir = destination/f'obj{obj}/rgb_training'
        copied = []
        for item in old['files']:
            original_path = str(item['copy']).replace('\\', '/')
            if f'/expanded_obj{obj}_v11/training/' not in '/'+original_path:
                continue
            data = read(ROOT/original_path, item['copy_sha256'])
            require(len(data) == item['bytes'], 'Copied training file size changed')
            name, data = unpack_copy(Path(original_path).name, data, item['source_sha256'])
            write(f'obj{obj}/rgb_training/'+name, data)
            copied.append(name)
        require(set(copied) == {'training_config.json', 'execution_provenance.json', 'template_metadata.json', 'template_attempts.csv', f'templates_tless_object_{obj}.yml.gz'}, 'Incomplete original RGB training copy')
        attempts = read(training_dir/'template_attempts.csv').decode().splitlines()
        require(len(attempts) == 3457, 'Original training attempt count changed')
        config = load(training_dir/'training_config.json')
        require(config['features'] == 32 and config['scales'] == [.75, 1., 1.5, 2.] and config['angle_step'] == 30 and config['pyramid_T'] == [4, 8], 'Original bank recipe changed')
        require(config['coarse_threshold'] == config['selected_post_threshold'] == 85 and config['target_objects'] == [obj], 'Original bank object/threshold changed')
        bank = dict(object_id=obj, class_id='tless_object_'+str(obj), rgb_training=str(training_dir),
                    rgb_template_count=config['template_count'], original_pilot_raw=str(destination/f'obj{obj}/original_pilot_raw'))
        # Expand the complete original tar to verify retained byte provenance,
        # but only copy the 16 fixed-pilot candidate paths and their manifests.
        archive_item = next(i for i in old['files'] if str(i['copy']).replace('\\', '/').endswith('/raw_numeric.tar.gz'))
        archive_data = read(ROOT/str(archive_item['copy']).replace('\\', '/'), archive_item['copy_sha256'])
        require(len(archive_data) == archive_item['bytes'], 'Original raw tar size changed')
        members = {r['name']: r for r in old['raw_archive_members']}
        require(len(members) == len(old['raw_archive_members']) == 1600, 'Original raw member scope changed')
        seen, copies = set(), 0
        with tarfile.open(fileobj=io.BytesIO(archive_data), mode='r:gz') as archive:
            for member in archive:
                require(member.isfile() and member.name == PurePosixPath(member.name).name and member.name in members and member.name not in seen, 'Unsafe/duplicate original raw member')
                seen.add(member.name)
                data = archive.extractfile(member).read()
                pin = members[member.name]
                require(len(data) == pin['bytes'] == member.size and digest(data) == pin['sha256'], 'Original raw member SHA changed')
                matched = re.fullmatch(r's(\d+)_i(\d+)_(fallback|fused)_raw(?:\.csv\.gz|_manifest\.json)', member.name)
                require(matched is not None, 'Unexpected original raw member name')
                if tuple(map(int, matched.groups()[:2])) in pilot_keys:
                    write(f'obj{obj}/original_pilot_raw/'+member.name, data)
                    copies += 1
        require(seen == set(members) and copies == 32, 'Original pilot reference coverage changed')
        banks.append(bank)
    for name, pin in SOURCE_READS.items():
        require(digest(Path(name).read_bytes()) == pin['sha256'], 'Numeric source changed while preparing closure')
    result = dict(version='silhouette_input_closure_v1', dataset_root=str(ROOT/'datasets/tless_expanded'), objects=OBJECTS,
                  training=training, development=frames, rgb_banks=banks, private_files=private_records,
                  source_sha256=SOURCE_READS, private_source_freeze_sha256=digest((HERE/'PRIVATE_SOURCE_FREEZE.json').read_bytes()),
                  protocol_sha256=digest((HERE/'PROTOCOL.json').read_bytes()), preparer_sha256=digest(Path(__file__).read_bytes()),
                  image_hash_origin='Expected member SHA/size from fixed download manifest; not invented historical runner member attestations',
                  images_opened=0, image_decodes=0, matcher_calls=0)
    (HERE/'INPUT_CLOSURE.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def verify(images=None):
    closure = load(HERE/'INPUT_CLOSURE.json')
    require(digest((HERE/'PROTOCOL.json').read_bytes()) == closure['protocol_sha256'], 'Protocol changed after input freeze')
    require(digest((HERE/'PRIVATE_SOURCE_FREEZE.json').read_bytes()) == closure['private_source_freeze_sha256'], 'Private source manifest changed')
    for name, pin in closure['private_files'].items():
        data = read(HERE/name, pin['sha256'])
        require(len(data) == pin['bytes'], 'Private input byte count changed')
    # Original index remains a runtime dependency. Numeric cache/build source
    # paths otherwise do not need to remain mutable runtime dependencies.
    original_index = ROOT/'datasets/tless_expanded/index.json'
    read(original_index, closure['source_sha256'][str(original_index)]['sha256'])
    members = []
    if images == 'training':
        members = [(r[k], r[k+'_sha256'], r[k+'_bytes']) for r in closure['training'] for k in ('rgb', 'mask')]
    elif images == 'development':
        members = [(r['rgb'], r['rgb_sha256'], r['rgb_bytes']) for r in closure['development']]
    require(images in (None, 'training', 'development'), 'Unknown image verification phase')
    for name, sha, size in members:
        data = (ROOT/'datasets/tless_expanded'/relative(name)).read_bytes()
        require(len(data) == size and digest(data) == sha, 'Dataset image SHA/size changed: '+name)
    return dict(passed=True, image_files_opened=len(members), image_decodes=0, matcher_calls=0,
                image_phase=images, protocol_sha256=closure['protocol_sha256'], private_file_count=len(closure['private_files']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create', action='store_true')
    group.add_argument('--verify', action='store_true')
    parser.add_argument('--verify-images', choices=['training', 'development'])
    parser.add_argument('--cpu-slot-granted', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Output must be new')
    require(not args.verify_images or args.verify and args.cpu_slot_granted, 'Image byte access requires coordinated CPU slot')
    try:
        result = create() if args.create else verify(args.verify_images)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(dict(passed=True, image_files_opened=result.get('image_files_opened', result.get('images_opened', 0)), image_decodes=0, matcher_calls=0)))
    except Exception as error:
        args.output.write_text(json.dumps(dict(incomplete=True, reason=str(error), missing_frames_are_not_negatives=True), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
