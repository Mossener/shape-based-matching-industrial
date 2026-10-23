"""Metadata-only C0 selection. Does not open images, raw tables or banks.

This is a plan of declared inputs, not an execution freeze or payload audit.
Only the selected 2,400 small fallback manifests are read and checked against
their actual V31 stage pins; source image/bank/raw pins remain declarations.
"""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
QUALITY = ROOT / 'artifacts/rgb_stratified_features_experiment/quality'


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    destination = HERE / 'C0_INPUT_PLAN_V1.json'
    if destination.exists():
        raise ValueError('fresh plan required')
    paths = [QUALITY / 'QUALITY_INPUT_FREEZE.json',
             QUALITY / 'run_development_v1/QUALITY_STAGE_FREEZE.json',
             ROOT / 'artifacts/rgb_dilated_mask_experiment/INPUT_CLOSURE.json',
             ROOT / 'artifacts/rgb_stratified_features_experiment/GEOMETRY_INPUT_FREEZE.json']
    before = [pin(path) for path in paths]
    quality, stage, closure, geometry = [json.loads(path.read_bytes()) for path in paths]
    assert before[1]['sha256'] == '6070b474d29b112c822d7f6a94a2ec920e454d104c511c42c29bf78a1d77b47a'
    assert stage['completed'] and stage['post_verification_passed']
    assert not stage['heldout_images_allowed']
    objects = [1, 2, 5, 8, 12, 17]
    assert quality['objects'] == objects == closure['objects']
    frames = quality['development']
    assert frames == closure['development'] and len(frames) == 400
    frame_ids = {(row['scene_id'], row['image_id']) for row in frames}
    assert len(frame_ids) == 400
    assert not ({11, 14, 15, 16, 17, 18, 19, 20} & {s for s, _ in frame_ids})
    assert len(closure['training']) == 432
    all_files = {str(Path(item['path']).resolve()): item for item in stage['files']}
    assert len(all_files) == len(stage['files'])
    records, observed_pins, totals = [], [], {}
    pattern = re.compile(r's(\d+)_i(\d+)_fallback_raw_manifest\.json')
    for obj in objects:
        directory = QUALITY / f'run_development_v1/native/obj{obj}/rgb_control'
        chosen = [item for item in stage['files']
                  if Path(item['path']).parent == directory and pattern.fullmatch(Path(item['path']).name)]
        assert len(chosen) == 400
        counts, zero, seen = 0, 0, set()
        for declared in sorted(chosen, key=lambda row: row['path']):
            path = Path(declared['path'])
            actual = pin(path)
            assert actual == declared
            observed_pins.append(actual)
            manifest = json.loads(path.read_bytes())
            match = pattern.fullmatch(path.name)
            identity = (int(match[1]), int(match[2]))
            assert identity == (manifest['scene_id'], manifest['image_id'])
            assert identity in frame_ids and identity not in seen
            seen.add(identity)
            assert manifest['variant'] == 'fallback'
            assert manifest['class_id'] == f'tless_object_{obj}'
            assert manifest['class_ids'] == [manifest['class_id']]
            raw = path.with_name(path.name.replace('_raw_manifest.json', '_raw.csv.gz'))
            assert Path(manifest['path']).resolve() == raw.resolve()
            raw_pin = all_files[str(raw.resolve())]
            assert raw_pin['bytes'] == manifest['compressed_bytes']
            count = manifest['raw_candidate_count']
            assert type(count) is int and count >= 0
            counts += count
            zero += count == 0
            records.append(dict(object_id=obj, scene_id=identity[0], image_id=identity[1],
                                candidate_count_declared=count, raw_declared=raw_pin,
                                manifest_observed=actual))
        assert seen == frame_ids
        totals[str(obj)] = dict(manifests=400, candidates_declared=counts, zero_combinations=zero)
    assert sum(row['candidates_declared'] for row in totals.values()) == 457279
    assert sum(row['zero_combinations'] for row in totals.values()) == 390
    banks = [row for row in geometry['bank_files'] if row['arm'] == 'C0']
    assert [row['object_id'] for row in banks] == objects
    assert before == [pin(path) for path in paths]
    assert observed_pins == [pin(Path(row['path'])) for row in observed_pins]
    result = dict(schema='ordered_contour_c0_input_plan_v1', status='metadata_selection_only',
                  source_pins_observed=before, preparer_observed=pin(Path(__file__)),
                  sole_stage=before[1], arm='rgb_control', path='fallback',
                  query_width=848, query_height=848, padding_ltrb=[64, 64, 64, 244],
                  candidate_scope='complete post-score85 pre-NMS consolidated C0 return',
                  objects=objects, dataset_root=quality['dataset_root'],
                  development_declared=frames, training_declared=closure['training'],
                  own_banks_declared=banks, attempts_declared=geometry['original_attempts'],
                  candidates=records, totals=totals,
                  counts=dict(object_frame_combinations=2400, raw_candidates_declared=457279,
                              zero_combinations=390, training_members_declared=432,
                              training_attempts_expected=20736, successful_templates_expected=18199),
                  raw_payloads_opened=0, bank_payloads_opened=0, image_files_opened=0,
                  image_decodes=0, dataset_indexes_opened=0, native_calls=0,
                  real_input_freeze=False, real_pixel_execution=False, production_promotion=False,
                  limitations=['raw rows and compressed bytes not audited here',
                               'bank, training attempts and image pins are inherited declarations',
                               'source, native build, resource and all-attempt replay acceptance still required'])
    destination.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(plan=pin(destination), counts=result['counts'])))


if __name__ == '__main__':
    main()
