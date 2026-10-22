"""Numeric-only Phase2 proposal and exact geometry budget; no native/image API."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

import geometry

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V1 = HERE.parent/'score_path_probe_v1'
PHASE1 = V1/'probe_phase1_v2'
RECEIPT = PHASE1/'PROBE_STAGE_FREEZE.json'
RECEIPT_SHA = 'f2be7500b13fbe1cad2bb9bc8d223b7bbf37af71919441f5b2bc2d1251e0d5ed'
PLAN_SHA = '353615a753a0be27a2665997488301259fe99989858068895870d16fe32de91c'
AUDIT = ROOT/'artifacts/independent_reviews/empty_mask_quality_v1/run_development_audit_20261022_v3/result.json'
AUDIT_SHA = '38f9025da7c7320f2e42eb632381f9995c6718d64eaa40d7378e205d73047e68'
LAYERS = ROOT/'artifacts/silhouette_empty_mask_experiment/run_plan_v1/native/loaded_layers.csv'
PHASE1_AUDIT = ROOT/'artifacts/independent_reviews/score_path_probe_v1/run_phase1_audit_20261022_v1/result.json'
PHASE1_AUDIT_SHA = '67ff1b3967e762984bf9a35e358fa2a1a9d039124de88b7fc53c98eb18eacc06'


def need(value, message):
    if not value:
        raise ValueError(message)


def read_pin(path):
    path = Path(path).resolve(strict=True)
    need(path.is_relative_to(ROOT/'artifacts') and
         (path.name == '.gitignore' or path.suffix in ('.json', '.csv', '.gz', '.stdout', '.stderr',
                                                      '.cpp', '.h', '.hpp', '.hxx', '.py', '.md')),
         'Only contained numeric/receipt/project-source files may be read by the budget preparer')
    value = path.read_bytes()
    return dict(path=str(path), bytes=len(value), sha256=hashlib.sha256(value).hexdigest())


def verify(record):
    need(read_pin(record['path']) == record, 'Numeric closure changed: '+record['path'])


def load_pinned(path, sha):
    record = read_pin(path)
    need(record['sha256'] == sha, 'Fixed numeric receipt SHA differs')
    return json.loads(Path(path).read_bytes()), record


def prepare(output):
    phase1, receipt_pin = load_pinned(RECEIPT, RECEIPT_SHA)
    need(phase1['completed'] is True and phase1['native_exit_code'] == 0 and
         phase1['actual_full_class_search_replays'] == 426 and phase1['phase2_started'] is False and
         phase1['image_before'] == phase1['image_after'] and
         len(phase1['image_before']) == 175, 'Incomplete exact Phase1 receipt')
    native_pins = phase1['files']
    expected = {Path(record['path']).resolve() for record in native_pins}
    actual = {path.resolve() for path in (PHASE1/'native').rglob('*') if path.is_file()}
    need(expected == actual and len(actual) == 1709, 'Complete Phase1 native output member set differs')
    for record in native_pins+phase1['execution_files']:
        verify(record)
    verify(phase1['build_manifest'])
    build = json.loads(Path(phase1['build_manifest']['path']).read_bytes())
    for record in build['project_sources']:
        verify(record)
    plan, plan_pin = load_pinned(V1/'PROBE_INPUTS_V1.json', PLAN_SHA)
    need(plan_pin == phase1['input_plan'], 'Phase1 input receipt differs')
    independent, independent_pin = load_pinned(PHASE1_AUDIT, PHASE1_AUDIT_SHA)
    need(independent['passed'] is True and independent['stage'] == 'score_path_probe_v1_phase1' and
         independent['phase1_freeze'] == receipt_pin and independent['input_plan'] == plan_pin and
         independent['dataset_image_bytes_opened'] == 0 and independent['phase2_started'] is False,
         'Independent Phase1 audit is not bound to the fixed completion/input receipt')
    audit, audit_pin = load_pinned(AUDIT, AUDIT_SHA)
    layer_pin = next(record for record in audit['input_pins'] if Path(record['path']).resolve() == LAYERS)
    verify(layer_pin)
    layer_rows = list(csv.DictReader(io.StringIO(LAYERS.read_text(encoding='utf-8-sig'))))
    layers = {(row['arm'], int(row['object_id']), int(row['template_id']), int(row['level'])):
              {key: int(row[key]) for key in ('width', 'height', 'actual_features', 'min_x', 'min_y', 'max_x', 'max_y')}
              for row in layer_rows}
    need(len(layers) == len(layer_rows) == 77870, 'Loaded-bank numeric geometry member set differs')
    padding_path = Path(plan['common_padding_json'])
    expected_pins = {Path(record['path']).resolve(): record for record in plan['numeric_pins']}
    verify(expected_pins[padding_path])
    padding = json.loads(padding_path.read_bytes())
    size = (padding['width'], padding['height'])
    need(size == (848, 832), 'Frozen common image dimensions differ')
    bank_meta = {}
    metadata_pins = []
    for bank in plan['banks']:
        for arm, key in [('rgb', 'rgb_training'), ('binary_empty_mask', 'binary_training')]:
            path = Path(bank[key])/'template_metadata.json'
            record = expected_pins[path]
            verify(record)
            metadata_pins.append(record)
            rows = json.loads(path.read_bytes())['templates']
            mapping = {}
            for row in rows:
                pose = (row['training_image_id'], row['angle'], row['scale'])
                need(pose not in mapping, 'Duplicate same-pose bank identity')
                mapping[pose] = row
            bank_meta[(bank['object_id'], arm)] = mapping
    jobs = {}
    identities = []
    frame_counts = Counter()
    for frame in plan['frames']:
        obj, scene, image = (frame[key] for key in ('object_id', 'scene', 'image'))
        frame_counts[obj] += 1
        for target in frame['targets']:
            gt = target['gt_id']
            identity = (obj, scene, image, gt)
            identities.append(identity)
            pose = tuple(target['rgb_tp_pose'])
            for arm in ('rgb', 'binary_empty_mask'):
                meta = bank_meta[(obj, arm)][pose]
                if arm == 'rgb':
                    need(meta['template_id'] == target['rgb_tp_template'], 'RGB anchor template identity differs')
                layer = layers[(arm, obj, meta['template_id'], 0)]
                anchor = geometry.physical_anchor(target['rgb_tp_box'], meta['warped_mask_bbox'], (meta['tl_x'], meta['tl_y']))
                if arm == 'rgb':
                    need(tuple(target['rgb_tp_match']) == anchor, 'RGB physical placement does not reconstruct the actual match')
                key = (obj, scene, image, arm, meta['template_id'])
                if key not in jobs:
                    jobs[key] = dict(key=list(key), fine_layer=layer,
                                     coarse_layer=layers[(arm, obj, meta['template_id'], 1)],
                                     targets=[], points={}, parent_keys=set(), window_keys=set())
                job = jobs[key]
                points = geometry.neighbors(*anchor)
                job['targets'].append(dict(gt_id=gt, physical_anchor=anchor, off_native_grid=anchor not in points, points=points))
                for point in points:
                    if point not in job['points']:
                        parents = geometry.parents(point, size, (layer['width'], layer['height']))
                        job['points'][point] = parents
                        job['parent_keys'].update((parent['row'], parent['col']) for parent in parents)
                        job['window_keys'].update(parent['base'] for parent in parents)
    need(len(identities) == len(set(identities)) == 215 and len(plan['frames']) == 213, 'RGB TP scope differs')
    counters = Counter()
    job_rows = []
    coarse_cells_per_job = (size[0]//16)*(size[1]//16)
    for key, job in sorted(jobs.items()):
        physical = len(job['targets'])
        point_count = len(job['points'])
        links = sum(len(parents) for parents in job['points'].values())
        windows = len(job['window_keys'])
        coarse_count = job['coarse_layer']['actual_features']
        fine_count = job['fine_layer']['actual_features']
        counters.update(jobs=1, physical_anchor_rows=physical, native_grid_points=point_count,
                        parent_point_links=links, unique_reachable_parents=len(job['parent_keys']), unique_local_windows=windows,
                        coarse_map_cells=coarse_cells_per_job, local_map_cells=256*windows,
                        coarse_feature_response_digits=coarse_cells_per_job*coarse_count,
                        local_feature_response_digits=256*windows*fine_count,
                        standalone_physical_feature_probes=physical*fine_count)
        job_rows.append(dict(key=list(key), physical_anchors=physical, native_grid_points=point_count,
                             parent_point_links=links, unique_reachable_parents=len(job['parent_keys']),
                             unique_local_windows=windows, fine_features=fine_count, coarse_features=coarse_count,
                             targets=job['targets'], point_plan=[dict(point=list(point), parents=parents)
                                                                for point, parents in sorted(job['points'].items())]))
    budget = dict(counters)
    budget.update(native_coarse_similarity_calls=counters['jobs'],
                  native_local_map_calls=counters['unique_local_windows'],
                  native_local_fused_maximum_calls=counters['unique_local_windows'],
                  full_class_search_replays=0, public_detector_match_calls=0,
                  maximum_image_decode_operations=213, permitted_unique_image_files=175,
                  image_hash_operations_per_complete_run=350,
                  maximum_peak_rss_bytes=1610612736, maximum_complete_output_bytes=1073741824,
                  maximum_wall_seconds=3600)
    result = dict(status='design_only_not_execution_authorization', phase='phase2',
                  prior_phase1_receipt=receipt_pin, prior_input_plan=plan_pin, prior_v22_audit=audit_pin,
                  independent_phase1_audit=independent_pin,
                  loaded_layers_pin=layer_pin, metadata_pins=metadata_pins, budget=budget,
                  phase1_project_source_pins=build['project_sources'],
                  proposal_source_pins=[read_pin(HERE/name) for name in ('geometry.py', 'prepare_budget.py', 'test_geometry.py',
                      'source_contract.py', 'test_source_contract.py', 'phase2.cpp', 'build_probe.py', 'DESIGN.md')],
                  runner_pin_cycle_note='run_probe.py embeds this plan hash and is pinned by each build manifest, not by this plan',
                  rgb_tp_identities=215, arm_identity_probes=430, jobs=job_rows,
                  images_opened_by_preparer=0, native_calls_by_preparer=0, matcher_calls_by_preparer=0,
                  phase1_sources_unchanged_verified=True, independent_phase1_audit_verified=True,
                  root_source_review_and_explicit_cpu_grant_still_required=True)
    for record in native_pins+phase1['execution_files']+metadata_pins+build['project_sources']+[layer_pin, receipt_pin, plan_pin, audit_pin, independent_pin]:
        verify(record)
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    need(output.is_relative_to(HERE) and not output.exists() and output.parent.is_dir(), 'Fresh sibling proposal output required')
    result = prepare(output)
    print(json.dumps(dict(passed=True, status=result['status'], budget=result['budget'],
                          image_bytes_opened=0, native_calls=0)))


if __name__ == '__main__':
    main()
