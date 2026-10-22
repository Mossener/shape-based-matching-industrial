"""Prepare a Phase1 numeric-only allowlist; image bytes are never opened here."""
import argparse
from collections import defaultdict
import csv
import io
import json
from pathlib import Path

from probe_contract import OBJECTS, SCENES, check, pin, require, scope

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPERIMENT = ROOT/'artifacts/silhouette_empty_mask_experiment'
AUDIT = ROOT/'artifacts/independent_reviews/empty_mask_quality_v1/run_development_audit_20261022_v3/result.json'
AUDIT_SHA = '38f9025da7c7320f2e42eb632381f9995c6718d64eaa40d7378e205d73047e68'
NATIVE = EXPERIMENT/'run_quality_development_v1/native'


def table(data):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    result = list(reader)
    require(all(None not in r and None not in r.values() for r in result), 'Malformed numeric table')
    return result


def prepare(output):
    audit_pin = pin(AUDIT)
    require(audit_pin['sha256'] == AUDIT_SHA, 'Completed V22 audit changed')
    audit = json.loads(AUDIT.read_bytes())
    require(audit['passed'] is True and audit['stage'] == 'development', 'Completed development audit required')
    pins = {str(Path(r['path']).resolve()).casefold(): r for r in audit['input_pins']}
    seen = {}

    def numeric(path):
        path = Path(path).resolve(strict=True)
        require(path.is_relative_to(ROOT/'artifacts') and path.suffix in ('.json', '.csv', '.gz'), 'Only preserved numeric artifacts allowed')
        expected = pins.get(str(path).casefold())
        require(expected is not None, 'Artifact absent from completed audit closure')
        check(expected)
        seen[str(path)] = expected
        return path.read_bytes()

    inputs = json.loads(numeric(EXPERIMENT/'QUALITY_INPUT_FREEZE.json'))
    require(tuple(inputs['objects']) == OBJECTS, 'Wrong object scope')
    schedule = {(r['scene_id'], r['image_id']): r for r in inputs['development']}
    require(len(schedule) == 400 and {s for s, _ in schedule} == set(SCENES), 'Wrong development scope')
    native_gt = {(int(r['object_id']), int(r['scene']), int(r['image']), int(r['gt_id'])): r
                 for r in table(numeric(NATIVE/'ground_truth.csv'))}
    targets = defaultdict(list)
    identities = []
    for row in table(numeric(NATIVE/'selected_detections.csv')):
        if row['arm'] != 'rgb' or row['allGT_label'] != 'TP':
            continue
        identity = tuple(int(row[field]) for field in ('object_id', 'scene', 'image', 'allGT_id'))
        truth = native_gt[identity]
        identities.append(identity)
        targets[identity[:3]].append(dict(gt_id=identity[3], bbox=[float(truth['bbox_'+a]) for a in ('x', 'y', 'w', 'h')],
            rgb_tp_box=[float(row['bbox_'+a]) for a in ('x', 'y', 'w', 'h')],
            rgb_tp_template=int(row['template_id']), rgb_tp_pose=[int(row['training_image']), float(row['angle']), float(row['scale'])],
            rgb_tp_match=[int(row['match_x']), int(row['match_y'])], rgb_tp_score_bits=int(row['score_bits'])))
    counts = scope(identities)
    require(counts == dict(identities=215, object_frames=213, image_frames=175, full_class_search_replays=426), 'Fixed anchor/call scope differs')
    frames, image_pins = [], {}
    dataset_root = Path(inputs['dataset_root']).resolve()
    for (obj, scene, image), selected in sorted(targets.items()):
        declared = schedule[(scene, image)]
        relative = Path(declared['rgb'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe frozen image path')
        image_path = (dataset_root/relative).resolve()
        require(image_path.is_relative_to(dataset_root) and relative.parts[:2] == ('test_primesense', f'{scene:06d}'), 'Image outside allowed scene')
        image_pin = dict(path=str(image_path), sha256=declared['rgb_sha256'], bytes=declared['rgb_bytes'])
        if str(image_path) in image_pins:
            require(image_pins[str(image_path)] == image_pin, 'Inconsistent repeated image pin')
        image_pins[str(image_path)] = image_pin
        frame = dict(object_id=obj, scene=scene, image=image, rgb_relative=relative.as_posix(),
                     image_path=str(image_path), targets=sorted(selected, key=lambda r: r['gt_id']))
        for arm, field in [('rgb', 'rgb_raw'), ('binary_empty_mask', 'binary_raw')]:
            archive = NATIVE/f'obj{obj}'/arm/f's{scene}_i{image}_fallback_raw.csv.gz'
            numeric(archive)
            numeric(NATIVE/f'obj{obj}'/arm/f's{scene}_i{image}_fallback_raw_manifest.json')
            frame[field] = str(archive)
        frames.append(frame)
    banks = []
    for bank in inputs['rgb_banks']:
        for field in ('rgb_training', 'binary_training'):
            directory = Path(bank[field])
            numeric(directory/'template_metadata.json')
            numeric(directory/f'templates_tless_object_{bank["object_id"]}.yml.gz')
        banks.append({field: bank[field] for field in ('object_id', 'rgb_training', 'binary_training', 'rgb_template_count')})
    numeric(inputs['common_padding_json'])
    for record in seen.values():
        check(record)
    check(audit_pin)
    result = dict(version='score_path_probe_v1', stage='phase1', rgb_tp_identities=215, object_frames=213,
        image_frames=175, full_class_search_replays=426, public_detector_match_calls=0,
        rgb_reference_raw_rows=71178, binary_reference_raw_rows=156638,
        common_padding_json=inputs['common_padding_json'], banks=banks, frames=frames,
        audit=audit_pin, numeric_pins=list(seen.values()), permitted_image_pins=list(image_pins.values()),
        images_opened_by_preparer=0, matcher_calls=0, heldout_access=False, phase2_authorized=False)
    require(len(image_pins) == 175, 'Unexpected permitted image closure')
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(HERE) and not output.exists() and output.parent.is_dir(), 'Fresh contained input plan required')
    result = prepare(output)
    print(json.dumps(dict(passed=True, rgb_tp_identities=result['rgb_tp_identities'], full_class_search_replays=426,
                          permitted_image_files=175, image_bytes_opened=0)))


if __name__ == '__main__':
    main()
