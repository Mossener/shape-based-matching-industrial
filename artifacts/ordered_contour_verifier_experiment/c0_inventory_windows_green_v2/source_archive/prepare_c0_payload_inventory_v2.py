"""Prepare an exact C0 byte inventory, never a pixel-execution acceptance.

Source delivered without execution. Run estimate/hash separately, each under
the coordinator's external one-process wall/working-set/output guard. Estimate
stats only the exact accepted whitelist; hash reads its bytes without decoding,
decompression, CSV/JSON payload interpretation, native calls or dataset scans.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[1]
DATASET = ROOT / 'datasets/tless_expanded'
BANK_ROOT = ROOT / 'artifacts/rgb_empty_mask_experiment/frozen_inputs'
STAGE_ROOT = ROOT / 'artifacts/rgb_stratified_features_experiment/quality/run_development_v1'
PLAN_PATH = HERE / 'C0_INPUT_PLAN_V1.json'
DECISIONS_PATH = HERE / 'INPUT_INVENTORY_DECISIONS_V2.json'
PLAN_HASH = '62610add5d6e40c219a3f9929edb1aa2f87c831d8a678ec4848cf282eb8236c0'
OBJECTS = (1, 2, 5, 8, 12, 17)
SCENES = (1, 4, 6, 7, 8, 10, 12, 13)
COUNTS = dict(training_rgb=432, training_mask=432, development_rgb=400,
              own_bank=6, own_metadata=6, own_attempts=6,
              training_config_new=6, training_provenance_new=6,
              candidate_raw=2400, candidate_manifest=2400)
MAX_TOTAL = 536870912
MAX_FILE = 67108864
MAX_OUTPUT = 16777216
MIN_FREE = 67108864
CHUNK = 1048576


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'Expected nonnegative builtin integer')
    return value


def canonical(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'Absolute traversal-free path required')
    require(path == Path(os.path.abspath(path)), 'Noncanonical path')
    return path


def safe_stat(path, *, directory=False):
    """Inspect every component without following symlinks/junctions/reparse points."""
    path = canonical(path)
    for part in tuple(reversed(path.parents)) + (path,):
        info = os.lstat(part)
        require(not stat.S_ISLNK(info.st_mode) and
                not (getattr(info, 'st_file_attributes', 0) &
                     getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024)),
                'Reparse/symlink component forbidden: ' + str(part))
        is_directory = part != path or directory
        require(stat.S_ISDIR(info.st_mode) if is_directory else stat.S_ISREG(info.st_mode),
                'Unexpected path type: ' + str(part))
    require(path.resolve(strict=True) == path, 'Resolved path differs: ' + str(path))
    return info


def stamp(info):
    # Windows path-stat and handle-stat can give st_ctime different meanings.
    # Explicit birth time is shared by both APIs and must be available here.
    require(hasattr(info, 'st_birthtime_ns'), 'Explicit Windows birth time is required')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_birthtime_ns)


def inspect_file(path, limit=MAX_FILE, *, capture=False, expected_stamp=None):
    """Bounded single-handle read; optional metadata bytes share the hashed read."""
    path = canonical(path)
    before = safe_stat(path)
    if expected_stamp is not None:
        require(stamp(before) == expected_stamp, 'Input changed since preflight: ' + str(path))
    require(before.st_size <= limit, 'File exceeds byte policy: ' + str(path))
    digest, consumed = hashlib.sha256(), 0
    chunks = [] if capture else None
    with path.open('rb') as stream:
        require(stamp(os.fstat(stream.fileno())) == stamp(before), 'Opened file changed')
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            consumed += len(block)
            require(consumed <= before.st_size and consumed <= limit, 'Input grew during hashing')
            digest.update(block)
            if capture:
                chunks.append(block)
        require(stamp(os.fstat(stream.fileno())) == stamp(before), 'File changed while hashing')
    require(consumed == before.st_size and stamp(safe_stat(path)) == stamp(before),
            'File changed after hashing')
    return (dict(path=str(path), bytes=consumed, sha256=digest.hexdigest()),
            b''.join(chunks) if capture else None)


def hash_file(path, limit=MAX_FILE, *, expected_stamp=None):
    return inspect_file(path, limit, expected_stamp=expected_stamp)[0]


def pin_equal(actual, declared):
    require(set(declared) == {'path', 'bytes', 'sha256'}, 'Unexpected pin fields')
    require(actual == declared, 'Declared pin mismatch: ' + str(declared['path']))


def read_json(path, declared=None):
    observed, data = inspect_file(path, capture=True)
    if declared is not None:
        pin_equal(observed, declared)
    return json.loads(data), observed


def write_json(path, value):
    safe_stat(path.parent, directory=True)
    data = (json.dumps(value, indent=2) + '\n').encode('utf-8')
    require(len(data) < MAX_OUTPUT, 'Inventory output too large')
    with path.open('xb') as stream:
        stream.write(data)


def build_whitelist(plan):
    require(plan['schema'] == 'ordered_contour_c0_input_plan_v1' and
            plan['status'] == 'metadata_selection_only', 'Unexpected plan schema/status')
    require(plan['objects'] == list(OBJECTS) and plan['arm'] == 'rgb_control' and
            plan['path'] == 'fallback', 'C0 selection differs')
    require(plan['query_width'] == plan['query_height'] == 848 and
            plan['padding_ltrb'] == [64, 64, 64, 244], 'Actual V31 grid differs')
    require(canonical(plan['dataset_root']) == DATASET, 'Dataset root differs')
    records, selected_paths, role_counts = [], set(), {role: 0 for role in COUNTS}

    def add(role, path, declared, identity):
        path = canonical(path)
        require(path.is_relative_to(DATASET) or path.is_relative_to(BANK_ROOT) or
                path.is_relative_to(STAGE_ROOT / 'native'), 'Input escapes authorized roots')
        require(path.name != 'index.json', 'Dataset indexes forbidden')
        key = os.path.normcase(str(path))
        require(key not in selected_paths, 'Duplicate whitelist path')
        selected_paths.add(key)
        if declared is not None:
            require(canonical(declared['path']) == path, 'Declared role path differs')
            integer(declared['bytes'])
            require(bool(re.fullmatch('[0-9a-f]{64}', declared['sha256'])), 'Invalid declared SHA')
        records.append(dict(role=role, identity=identity, path=str(path), declared=declared,
                            pin_origin='accepted_plan' if declared is not None else 'new_observation_required'))
        role_counts[role] += 1

    train_keys = set()
    require(len(plan['training_declared']) == 432, 'Training member count differs')
    for row in plan['training_declared']:
        obj, image = integer(row['object_id']), integer(row['image_id'])
        require(obj in OBJECTS and (obj, image) not in train_keys, 'Training identity differs/duplicates')
        train_keys.add((obj, image))
        relative = dict(rgb=f'train_primesense/{obj:06d}/rgb/{image:06d}.png',
                        mask=f'train_primesense/{obj:06d}/mask/{image:06d}_000000.png')
        for kind in ('rgb', 'mask'):
            require(row[kind] == relative[kind], 'Unexpected training path')
            path = DATASET / relative[kind]
            declared = dict(path=str(path), bytes=row[kind + '_bytes'], sha256=row[kind + '_sha256'])
            add('training_' + kind, path, declared, dict(object_id=obj, image_id=image))
    require(all(sum(obj == key[0] for key in train_keys) == 72 for obj in OBJECTS),
            'Expected exactly 72 training members per object')

    frame_keys = set()
    require(len(plan['development_declared']) == 400, 'Development count differs')
    for row in plan['development_declared']:
        scene, image = integer(row['scene_id']), integer(row['image_id'])
        require(scene in SCENES and (scene, image) not in frame_keys, 'Development identity differs/duplicates')
        frame_keys.add((scene, image))
        relative = f'test_primesense/{scene:06d}/rgb/{image:06d}.png'
        require(row['rgb'] == relative, 'Unexpected development path')
        path = DATASET / relative
        add('development_rgb', path,
            dict(path=str(path), bytes=row['rgb_bytes'], sha256=row['rgb_sha256']),
            dict(scene_id=scene, image_id=image))
    require(all(sum(scene == key[0] for key in frame_keys) == 50 for scene in SCENES),
            'Expected exactly 50 frames per development scene')

    require([row['object_id'] for row in plan['own_banks_declared']] == list(OBJECTS), 'Bank object order differs')
    require([row['object_id'] for row in plan['attempts_declared']] == list(OBJECTS), 'Attempt object order differs')
    for bank, attempts in zip(plan['own_banks_declared'], plan['attempts_declared']):
        obj = bank['object_id']
        require(bank['arm'] == 'C0', 'Foreign bank arm')
        directory = BANK_ROOT / f'obj{obj}/rgb_training'
        for role, name, declared in (
                ('own_bank', f'templates_tless_object_{obj}.yml.gz', bank['bank']),
                ('own_metadata', 'template_metadata.json', bank['metadata']),
                ('own_attempts', 'template_attempts.csv', attempts['file']),
                ('training_config_new', 'training_config.json', None),
                ('training_provenance_new', 'execution_provenance.json', None)):
            add(role, directory / name, declared, dict(object_id=obj))

    candidate_keys, counts, zero = set(), 0, 0
    require(len(plan['candidates']) == 2400, 'Candidate combination count differs')
    for row in plan['candidates']:
        obj, scene, image = (integer(row[key]) for key in ('object_id', 'scene_id', 'image_id'))
        key = (obj, scene, image)
        require(obj in OBJECTS and (scene, image) in frame_keys and key not in candidate_keys,
                'Candidate identity differs/duplicates')
        candidate_keys.add(key)
        count = integer(row['candidate_count_declared'])
        counts += count
        zero += count == 0
        directory = STAGE_ROOT / f'native/obj{obj}/rgb_control'
        for role, suffix, pin_key in (
                ('candidate_raw', '_fallback_raw.csv.gz', 'raw_declared'),
                ('candidate_manifest', '_fallback_raw_manifest.json', 'manifest_observed')):
            add(role, directory / f's{scene}_i{image}{suffix}', row[pin_key],
                dict(object_id=obj, scene_id=scene, image_id=image))
    require(candidate_keys == {(obj, scene, image) for obj in OBJECTS for scene, image in frame_keys},
            'Incomplete C0 object/frame product')
    require(counts == 457279 and zero == 390 and role_counts == COUNTS and len(records) == 6094,
            'Whitelist totals differ')
    declared = [row['declared'] for row in records if row['declared'] is not None]
    require(len(declared) == 6082 and sum(row['bytes'] for row in declared) == 333585840,
            'Declared count/byte total differs')
    return records


def gt_declarations(stage):
    """Carry existing stage pins only; never open GT/result payloads here."""
    by_path = {row['path']: row for row in stage['files']}
    paths = [STAGE_ROOT / 'native' / name for name in
             ('ground_truth.csv', 'per_frame_metrics.csv', 'selected_detections.csv',
              'gt_retention.csv', 'stage_summary.json')]
    paths += [STAGE_ROOT / f'native/obj{obj}/metrics.json' for obj in OBJECTS]
    require(all(str(path) in by_path for path in paths), 'Missing frozen GT/result declaration')
    selected = [by_path[str(path)] for path in paths]
    return dict(status='declarations_only_not_opened', files=selected,
                payloads_opened=0, independently_reconstructed=False,
                json_scope='Six metrics JSON files and stage_summary contain aggregates, not full per-frame GT/NMS identities',
                forbidden_existing_audit_dependency='independent_quality/quality_audit.py gt_schedule reads dataset index; not called here',
                follow_up='Accept exact frozen GT/result schemas and complete per-frame C0 identity/NMS/GT binding; no dataset index may be guessed or opened by this inventory')


def main():
    require(os.name == 'nt', 'This path-confined preparer is Windows-only')
    require(len(sys.argv) == 3 and sys.argv[1] in ('estimate', 'hash') and
            re.fullmatch('[a-z][a-z0-9_]{0,80}', sys.argv[2]),
            'usage: prepare_c0_payload_inventory_v2.py estimate|hash fresh_directory')
    mode, name = sys.argv[1:]
    safe_stat(HERE, directory=True)
    out = HERE / name
    require(not os.path.lexists(out), 'Fresh output directory required')
    plan, plan_pin = read_json(PLAN_PATH)
    require(plan_pin['bytes'] == 2215868 and plan_pin['sha256'] == PLAN_HASH, 'Accepted plan pin differs')
    decisions, decisions_pin = read_json(DECISIONS_PATH)
    require(decisions['expected_files'] == COUNTS and decisions['declared_pin_bytes'] == 333585840,
            'Decisions disagree with source')
    stage_path = STAGE_ROOT / 'QUALITY_STAGE_FREEZE.json'
    require(canonical(plan['sole_stage']['path']) == stage_path, 'Foreign stage path')
    stage, stage_pin = read_json(stage_path, plan['sole_stage'])
    require(stage['completed'] and stage['post_verification_passed'] and
            not stage['heldout_images_allowed'], 'Stage acceptance differs')
    preparer = HERE / 'prepare_c0_input_plan_v1.py'
    require(canonical(plan['preparer_observed']['path']) == preparer, 'Foreign plan preparer path')
    preparer_pin = hash_file(preparer)
    pin_equal(preparer_pin, plan['preparer_observed'])
    source_pins = [hash_file(Path(__file__).absolute()), decisions_pin, plan_pin, stage_pin, preparer_pin]
    records = build_whitelist(plan)
    stage_pins = {row['path']: row for row in stage['files']}
    require(len(stage_pins) == len(stage['files']), 'Duplicate stage file paths')
    for row in records:
        if row['role'] in ('candidate_raw', 'candidate_manifest'):
            require(stage_pins.get(row['path']) == row['declared'], 'Candidate stage pin differs')
    declarations = gt_declarations(stage)

    snapshots, role_bytes, total = {}, {role: 0 for role in COUNTS}, 0
    for row in records:
        info = safe_stat(row['path'])
        limit = 1048576 if row['role'] == 'training_config_new' else (
            16777216 if row['role'] == 'training_provenance_new' else MAX_FILE)
        require(info.st_size <= limit, 'Input exceeds role byte ceiling')
        if row['declared'] is not None:
            require(info.st_size == row['declared']['bytes'], 'Pre-hash declared size mismatch: ' + row['path'])
        snapshots[row['path']] = stamp(info)
        row['preflight_bytes'] = info.st_size
        row['maximum_bytes'] = limit
        role_bytes[row['role']] += info.st_size
        total += info.st_size
    require(total <= MAX_TOTAL, 'Inventory input-byte ceiling exceeded')
    free = shutil.disk_usage(HERE).free
    require(free >= MIN_FREE + MAX_OUTPUT, 'Insufficient output disk headroom')
    estimate = dict(schema='c0_payload_inventory_estimate_v1', mode=mode,
                    exact_selected_files=len(records), role_counts=COUNTS, role_bytes=role_bytes,
                    total_input_bytes=total, declared_pin_files=6082, declared_pin_bytes=333585840,
                    newly_observed_pin_files=12, maximum_output_bytes=MAX_OUTPUT,
                    free_disk_bytes=free, minimum_free_disk_bytes=MIN_FREE,
                    disk_headroom_required_bytes=MIN_FREE + MAX_OUTPUT,
                    sources=source_pins, gt_result_declarations=declarations,
                    payload_content_bytes_read=0, payload_hashing_complete=False,
                    real_pixel_execution=False, production_promotion=False,
                    external_process_guard_required=True)
    out.mkdir()
    safe_stat(out, directory=True)
    write_json(out / 'estimate.json', estimate)
    print(json.dumps(dict(phase='pre_hash_estimate', files=len(records), input_bytes=total,
                          free_disk_bytes=free, mode=mode)), flush=True)
    if mode == 'hash':
        for row in records:
            actual = hash_file(row['path'], row['maximum_bytes'],
                               expected_stamp=snapshots[row['path']])
            if row['declared'] is not None:
                pin_equal(actual, row['declared'])
            row['observed'] = actual
        for row in records:
            require(stamp(safe_stat(row['path'])) == snapshots[row['path']],
                    'Input changed after inventory hashing: ' + row['path'])
    for pin in source_pins:
        pin_equal(hash_file(pin['path']), pin)
    result = dict(schema='c0_payload_inventory_v1', status='byte_inventory_only', mode=mode,
                  payload_hashing_complete=mode == 'hash', sources_before_after_equal=True,
                  source_pins=source_pins, python_executable=hash_file(Path(sys.executable).absolute()),
                  python_flags=dict(optimize=sys.flags.optimize, ignore_environment=sys.flags.ignore_environment,
                                    debug=__debug__),
                  files=records, file_count=len(records), total_input_bytes=total,
                  declared_pins_verified=6082 if mode == 'hash' else 0,
                  newly_observed_pins=12 if mode == 'hash' else 0,
                  gt_result_declarations=declarations,
                  image_decodes=0, image_header_parses=0, decompressions=0, dataset_indexes_opened=0,
                  native_calls=0, gradients_created=0, edge_scores_created=0,
                  real_pixel_input_freeze=False, real_pixel_execution=False,
                  quality_claim=False, performance_claim=False, production_promotion=False,
                  limitations=['Byte inventory only; no raw rows, bank fields, attempts or pixel semantics audited',
                               'New config/provenance hashes are observations, not inherited accepted pins',
                               'GT/result payloads are still declarations; complete C0 per-frame binding remains open',
                               'No OS filesystem lock/attestation; explicit path/stamp checks and external process guard required'])
    write_json(out / 'inventory.json', result)
    require(sum(path.stat().st_size for path in out.iterdir()) < MAX_OUTPUT, 'Combined output ceiling exceeded')
    print(json.dumps(dict(inventory=hash_file(out / 'inventory.json'), mode=mode,
                          declared_pins_verified=result['declared_pins_verified'],
                          real_pixel_input_freeze=False)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
