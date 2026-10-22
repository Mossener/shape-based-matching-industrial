"""Independent fixed pilot/development numeric audit. No images or matcher."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path
import struct

from analysis_core import compare, frame_result, legacy_selected
from checked import (EQUALITY_HEADER, GT_HEADER, PER_HEADER, RETENTION_HEADER, SELECTED_HEADER,
                     check_numeric, check_retention, check_selected, exact_stream, finish,
                     integer, need, number, parse_raw, table)
from evidence import OBJECTS, Reader, digest, members, quality_gate, safe_relative

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPERIMENT = ROOT/'artifacts/silhouette_empty_mask_experiment'
ARMS = ('v15_rgb', 'rgb', 'binary_empty_mask')
METRICS = ('allGT', 'visibility_ge_0_5')
OTHER = ('raw_candidates', 'negative_frames', 'negative_frames_with_fp', 'negative_fp')
PAIRS = [('padding', 'v15_rgb', 'rgb'), ('training_policy', 'rgb', 'binary_empty_mask'),
         ('overall', 'v15_rgb', 'binary_empty_mask')]
LEGACY_HEADER = 'scene,image,rank,class_id,score,template_id,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,eligible_label,eligibleGT_id'.split(',')


def metadata(reader, directory, obj, expected):
    records = reader.json(Path(directory)/'template_metadata.json')['templates']
    need(len(records) == expected and all(m['template_id'] == i and m['class_id'] == 'tless_object_'+str(obj)
         for i, m in enumerate(records)), 'Template metadata count/order/class differs')
    return {m['template_id']: m for m in records}


def unique(rows, key):
    result = {key(row): row for row in rows}
    need(len(result) == len(rows), 'Duplicate numeric row identity')
    return result


def key4(row):
    return integer(row['object_id']), integer(row['scene']), integer(row['image']), row['arm']


def add(destination, result):
    for metric in METRICS:
        target = destination.setdefault(metric, Counter())
        target.update(result[metric])
    for field in OTHER:
        destination[field] = destination.get(field, 0)+result[field]


def finished(values):
    return {**{name: finish(values[name]) for name in METRICS}, **{name: values[name] for name in OTHER}}


def report_groups(groups):
    pooled, objects, scenes = {}, [], []
    for arm in ARMS:
        pooled[arm] = finished(groups[(None, None, arm)])
    for obj in OBJECTS:
        values = dict(object_id=obj, **{arm: finished(groups[(obj, None, arm)]) for arm in ARMS})
        values['per_scene'] = [dict(scene_id=scene, **{arm: finished(groups[(obj, scene, arm)]) for arm in ARMS})
                               for scene in sorted({s for o, s, _ in groups if o == obj and s is not None})]
        objects.append(values)
    for scene in sorted({s for o, s, _ in groups if o is None and s is not None}):
        scenes.append(dict(scene_id=scene, **{arm: finished(groups[(None, scene, arm)]) for arm in ARMS}))
    macro = {arm: {metric: {field: sum(item[arm][metric][field] for item in objects)/len(objects)
                            for field in ('precision', 'recall', 'f1', 'mean_tp_iou')}
                   for metric in METRICS} for arm in ARMS}
    return dict(micro=pooled, per_object=objects, per_scene=scenes, equal_object_macro=macro)


def copied(reader, manifest, path):
    relative = Path(path).resolve().relative_to(ROOT).as_posix()
    records = [r for r in manifest['files'] if safe_relative(r['copy']) == relative]
    need(len(records) == 1, 'Preserved numeric copy absent/duplicate')
    record = records[0]
    data = reader.check(dict(path=str(Path(path).resolve()), sha256=record['copy_sha256'], bytes=record['bytes']))
    plain = gzip.decompress(data) if str(path).endswith('.gz') and not str(path).endswith('.tar.gz') else data
    if 'source_sha256' in record:
        need(digest(plain) == record['source_sha256'], 'Preserved decoded numeric/source SHA differs')
    return plain, record


def manifest_copy(manifest, stem):
    """Resolve a retained copy by manifest identity, including compression."""
    records = [record for record in manifest['files']
               if Path(safe_relative(record['copy'])).name.startswith(stem)]
    need(len(records) == 1, 'Preserved numeric copy absent/duplicate: '+stem)
    return ROOT/safe_relative(records[0]['copy'])


def legacy_object(reader, obj, baseline, rgb_meta, frame_keys, all_frame_keys):
    entry = next(item for item in baseline['per_object'] if item['object_id'] == obj)
    sources = entry['sources']
    for field in ('audit', 'training_provenance_copy', 'development_provenance_copy'):
        need(reader.pin(ROOT/safe_relative(sources[field]))['sha256'] == sources[field+'_sha256'],
             'Retained baseline source pin differs: '+field)
    audit = reader.json(ROOT/safe_relative(sources['audit']))
    need(audit['passed'] is True and audit['stage'] == 'development_full' and audit['heldout_matching_run'] is False,
         'Retained baseline audit scope differs')
    directory = ROOT/f'artifacts/public_evaluation/expanded_obj{obj}_v11/development'
    manifest = reader.json(directory/'preservation_manifest.json')
    need(manifest['object_id'] == obj and manifest['stage'] == 'development' and manifest['raw_archives'] == 800,
         'Retained baseline preservation scope differs')
    meta_bytes, _ = copied(reader, manifest, directory.parent/'training/template_metadata.json.gz')
    meta_records = json.loads(meta_bytes)['templates']
    need(meta_records == [rgb_meta[i] for i in range(len(rgb_meta))], 'Inherited RGB metadata differs from retained V15')
    # Bind metadata and metrics to the earlier independently pinned audit;
    # copied CSV scores alone have only six significant digits.
    normalized_pins = {safe_relative(k): value for k, value in audit['input_sha256'].items()}
    for raw_bytes, relative in [(meta_bytes, f'datasets/tless_expanded_obj{obj}_f32_train/template_metadata.json')]:
        need(digest(raw_bytes) == normalized_pins[relative], 'Earlier audit metadata binding differs')
    bank_path = directory.parent/f'training/templates_tless_object_{obj}.yml.gz'
    bank_bytes = reader.read(bank_path)
    copied_bank_pin = next(r for r in manifest['files'] if safe_relative(r['copy']) == bank_path.relative_to(ROOT).as_posix())
    need(digest(bank_bytes) == copied_bank_pin['copy_sha256'] == normalized_pins[f'datasets/tless_expanded_obj{obj}_f32_train/templates_tless_object_{obj}.yml.gz'],
         'Retained RGB template bank pin differs')
    metrics_bytes, _ = copied(reader, manifest, directory/'metrics.json.gz')
    need(digest(metrics_bytes) == normalized_pins[f'datasets/tless_expanded_obj{obj}_f32_development/metrics.json'],
         'Earlier audit/full metrics binding differs')
    metrics = json.loads(metrics_bytes)
    metric_frames = unique(metrics['frames'], lambda row: (row['scene_id'], row['image_id']))
    need(set(metric_frames) == all_frame_keys, 'Retained metrics development frame coverage differs')
    config_bytes, _ = copied(reader, manifest, directory/'frozen_config.json')
    config = json.loads(config_bytes)
    check_numeric(config, dict(features=32, angle_step=30, scales=[.75, 1., 1.5, 2.], pyramid_T=[4, 8],
                              weak_threshold=20, strong_threshold=40, training_border=16, input_padding=64,
                              coarse_threshold=85., selected_post_threshold=85., nms_iou=.3, match_iou=.5,
                              eligible_visibility=.5, target_objects=[obj], template_count=len(rgb_meta)), 'Retained config')
    # The retained V15 development copy is plain CSV; only the metrics and
    # provenance members are gzip-compressed. Keep the path bound to the
    # preservation manifest instead of assuming one compression convention.
    selected_bytes, _ = copied(reader, manifest, manifest_copy(manifest, 'selected_detections.csv'))
    selected = defaultdict(list)
    for row in table(selected_bytes, LEGACY_HEADER):
        key = integer(row['scene']), integer(row['image'])
        need(key in all_frame_keys and integer(row['rank']) == len(selected[key]), 'Legacy selected frame/rank differs')
        selected[key].append(row)
    archive_path = directory/'raw_numeric.tar.gz'
    archive_bytes = reader.read(archive_path)
    need(len(archive_bytes) == sources['development_raw_tar_bytes'] and
         digest(archive_bytes) == sources['development_raw_tar_sha256'], 'Pinned retained raw tar differs')
    need(len(manifest['raw_archive_members']) == 1600, 'Retained raw member count differs')
    payloads = members(archive_bytes, manifest['raw_archive_members'])
    expected_names = {f's{scene}_i{image}_{variant}_raw{suffix}' for scene, image in all_frame_keys
                      for variant in ('fallback', 'fused') for suffix in ('.csv.gz', '_manifest.json')}
    need(set(payloads) == expected_names, 'Retained tar schedule/path inventory differs')
    audit_raw = {r['file']: r for r in audit['archive_summary']}
    need(len(audit_raw) == len(audit['archive_summary']) == 800, 'Earlier audit raw inventory differs')
    for name, pin in audit_raw.items():
        need(name in payloads and digest(payloads[name]) == pin['sha256'], 'Earlier audit raw SHA differs')
    result = {}
    for frame in frame_keys:
        paths = {}
        for variant in ('fallback', 'fused'):
            stem = 's%d_i%d_%s_raw' % (*frame, variant)
            paths[variant] = parse_raw(payloads[stem+'.csv.gz'], json.loads(payloads[stem+'_manifest.json']), frame, variant, obj, rgb_meta)
        exact_stream(paths['fallback'], paths['fused'])
        record = metric_frames[frame]
        need(record['raw_count'] == record['fused_raw_count'] == len(paths['fallback']) and
             record['exact_candidate_equality'] == 1 and record['split'] == 'development', 'Legacy metric raw/equality differs')
        result[frame] = dict(raw=paths['fallback'], metric=record, selected=selected[frame])
    return result, entry


def numeric_gt(reader, inputs):
    index = reader.json(Path(inputs['dataset_root'])/'index.json')
    frames = unique([row for row in index['test'] if row['split'] == 'development'],
                    lambda row: (row['scene_id'], row['image_id']))
    scheduled = {(row['scene_id'], row['image_id']) for row in inputs['development']}
    need(len(frames) == len(inputs['development']) == len(scheduled) == 400 and set(frames) == scheduled,
         'Fixed development numeric GT coverage differs')
    for key, frame in frames.items():
        identities = set()
        for gt in frame['instances']:
            need(gt['gt_id'] not in identities and len(gt['bbox_obj']) == 4 and
                 min(gt['bbox_obj'][2:]) > 0 and 0 <= number(gt['visib_fract']) <= 1,
                 'Numeric GT identity/geometry differs')
            identities.add(gt['gt_id'])
    return frames


def frame_counts(result):
    all_counts, eligible = result['allGT'], result['visibility_ge_0_5']
    return dict(raw=len(result['raw']), selected=len(result['kept']),
                **{name: all_counts[name] for name in ('tp', 'fp', 'fn', 'gt')},
                **{'eligible_'+name: eligible[name] for name in ('tp', 'fp', 'fn', 'gt')},
                ignored=eligible['ignored'], all_iou_sum=all_counts['matched_iou_sum'],
                eligible_iou_sum=eligible['matched_iou_sum'], negative_fp=result['negative_fp'])


def serial(candidate):
    if candidate is None:
        return None
    value = list(candidate)
    value[4] = dict(float32_bits=struct.unpack('<I', candidate[4])[0], score=struct.unpack('<f', candidate[4])[0])
    return value


def first_difference(left, right):
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else None
        b = right[index] if index < len(right) else None
        if a != b:
            return dict(rank=index, before=serial(a), after=serial(b))
    return None


def run(stage, kind, output):
    reader = Reader(ROOT)
    source_pins = [reader.pin(path) for path in sorted(HERE.glob('*.py'))+sorted(HERE.glob('*.md'))+[HERE/'ORIGIN.json']]
    origin = reader.json(HERE/'ORIGIN.json')
    for pin in origin['adapted_sources']:
        need(reader.pin(ROOT/safe_relative(pin['path']))['sha256'] == pin['sha256'], 'Independent algorithm origin source changed')
    inputs, closure, stage_freeze = quality_gate(reader, stage, origin, EXPERIMENT, kind)
    native = Path(stage).resolve().parent/'native'
    frames = numeric_gt(reader, inputs)
    chosen = [(row['scene_id'], row['image_id']) for row in inputs['development'] if kind == 'development' or row['pilot']]
    need(len(chosen) == (400 if kind == 'development' else 8), 'Fixed stage frame selection differs')
    baseline_path = ROOT/'artifacts/public_evaluation/baseline_summary_all_six.json'
    need(reader.pin(baseline_path)['sha256'] == origin['retained_baseline_summary_sha256'], 'Retained baseline summary changed')
    baseline = reader.json(baseline_path)
    need(baseline['objects_completed'] == OBJECTS and baseline['unique_development_images'] == 400 and
         baseline['independent_object_frame_evaluations'] == 2400, 'Retained baseline scope differs')
    raw_names = {str((native/f'obj{obj}'/arm/('s%d_i%d_%s_raw%s' % (*frame, variant, suffix))).resolve())
                 for obj in OBJECTS for frame in chosen for arm in ARMS[1:] for variant in ('fallback', 'fused')
                 for suffix in ('.csv.gz', '_manifest.json')}
    observed_raw = {str(p.resolve()) for p in native.rglob('*_raw*') if p.is_file()}
    need(observed_raw == raw_names, 'Native complete raw archive schedule/path inventory differs')
    per = unique(table(reader.read(native/'per_frame_metrics.csv'), PER_HEADER), key4)
    equality = unique(table(reader.read(native/'candidate_equality.csv'), EQUALITY_HEADER), key4)
    wanted = {(obj, *frame, arm) for obj in OBJECTS for frame in chosen for arm in ARMS[1:]}
    need(set(per) == set(equality) == wanted, 'Native per-frame/equality coverage differs')
    selected = defaultdict(list)
    for row in table(reader.read(native/'selected_detections.csv'), SELECTED_HEADER):
        key = key4(row)
        need(key in wanted, 'Unexpected selected frame/arm')
        selected[key].append(row)
    gt_rows = table(reader.read(native/'ground_truth.csv'), GT_HEADER)
    gt_projection = unique(gt_rows, lambda row: tuple(integer(row[field]) for field in ('object_id', 'scene', 'image', 'gt_id')))
    expected_gt = {(obj, *frame, g['gt_id']): g for obj in OBJECTS for frame in chosen
                   for g in frames[frame]['instances'] if g['obj_id'] == obj}
    need(set(gt_projection) == set(expected_gt), 'Native ground-truth projection coverage differs')
    for key, truth in expected_gt.items():
        row = gt_projection[key]
        need(row['class_id'] == 'tless_object_'+str(key[0]) and number(row['visibility']) == truth['visib_fract'] and
             tuple(number(row['bbox_'+a]) for a in ('x', 'y', 'w', 'h')) == tuple(truth['bbox_obj']), 'Native GT projection value differs')
    groups = defaultdict(dict)
    comparisons, equality_totals = defaultdict(Counter), defaultdict(Counter)
    retention_expected, frame_rows, changes, equalities, first_differences = {}, [], [], [], {}
    for bank in inputs['rgb_banks']:
        obj = bank['object_id']
        meta = {'rgb': metadata(reader, bank['rgb_training'], obj, bank['rgb_template_count']),
                'binary_empty_mask': metadata(reader, bank['binary_training'], obj, 3456)}
        legacy, baseline_entry = legacy_object(reader, obj, baseline, meta['rgb'], chosen, set(frames))
        # Exact compressed bank identity, independently pinned in inherited closure.
        old_bank = ROOT/f'artifacts/public_evaluation/expanded_obj{obj}_v11/training/templates_tless_object_{obj}.yml.gz'
        new_bank = Path(bank['rgb_training'])/f'templates_tless_object_{obj}.yml.gz'
        need(reader.pin(old_bank)['sha256'] == reader.pin(new_bank)['sha256'], 'Padding comparison changed RGB bank')
        for frame in chosen:
            gt = [g for g in frames[frame]['instances'] if g['obj_id'] == obj]
            results = {'v15_rgb': frame_result(legacy[frame]['raw'], gt)}
            prior = legacy[frame]['metric']
            old = results['v15_rgb']
            need(prior['selected_count'] == len(old['kept']), 'Legacy selected count differs')
            legacy_selected(legacy[frame]['selected'], prior['detections'], old['kept'], old['all_labels'], old['eligible_labels'])
            for metric in METRICS:
                check_numeric(prior[metric], finish(old[metric]), 'Legacy independent frame '+str((obj, frame, metric)))
            old_gt = {(g['gt_id'], g['class_id'], g['visibility'], tuple(g['bbox_obj'])) for g in prior['ground_truth']}
            need(old_gt == {(g['gt_id'], 'tless_object_'+str(obj), g['visib_fract'], tuple(g['bbox_obj'])) for g in gt},
                 'Legacy numeric GT differs')
            for arm in ARMS[1:]:
                paths = {}
                for variant in ('fallback', 'fused'):
                    stem = native/f'obj{obj}'/arm/('s%d_i%d_%s_raw' % (*frame, variant))
                    paths[variant] = parse_raw(reader.read(str(stem)+'.csv.gz'), reader.json(str(stem)+'_manifest.json'),
                                               frame, variant, obj, meta[arm])
                exact_stream(paths['fallback'], paths['fused'])
                value = frame_result(paths['fallback'], gt)
                results[arm] = value
                key = (obj, *frame, arm)
                eq = equality[key]
                need(integer(eq['fallback_count']) == integer(eq['fused_count']) == len(paths['fallback']) and
                     eq['exact_order_fields_score_bits'] == eq['reference_exact'] == '1', 'Native equality assertion differs')
                for field in ('fallback_match_ms', 'fused_match_ms', 'fallback_external_ms', 'fused_external_ms'):
                    need(number(eq[field]) >= 0, 'Invalid descriptive single-pass timing')
                typed_per = {field: number(per[key][field]) if field.endswith('_sum') else integer(per[key][field])
                             for field in frame_counts(value)}
                check_numeric(typed_per, frame_counts(value), 'Native independent frame '+str(key))
                check_selected(selected[key], frame, obj, arm, meta[arm], value['kept'], value['all_labels'], value['eligible_labels'])
            for arm, result in results.items():
                frame_rows.append(dict(object_id=obj, scene=frame[0], image=frame[1], arm=arm, **frame_counts(result)))
                for group in ((None, None, arm), (obj, None, arm), (obj, frame[0], arm), (None, frame[0], arm)):
                    add(groups[group], result)
            for name, before, after in PAIRS:
                detail = compare(results[before], results[after])
                equality_row = dict(comparison=name, object_id=obj, scene=frame[0], image=frame[1],
                                    raw_equal=detail['raw_equal'], selected_equal=detail['selected_equal'],
                                    before_raw=len(results[before]['raw']), after_raw=len(results[after]['raw']),
                                    before_selected=len(results[before]['kept']), after_selected=len(results[after]['kept']))
                equalities.append(equality_row)
                equality_counts = dict(frames=1, raw_equal_frames=detail['raw_equal'], raw_changed_frames=1-detail['raw_equal'],
                                       selected_equal_frames=detail['selected_equal'], selected_changed_frames=1-detail['selected_equal'],
                                       **{field: equality_row[field] for field in ('before_raw', 'after_raw', 'before_selected', 'after_selected')})
                for scope in ((name, None, None), (name, obj, None), (name, obj, frame[0]), (name, None, frame[0])):
                    equality_totals[scope].update(equality_counts)
                if name not in first_differences and not detail['raw_equal']:
                    first_differences[name] = dict(object_id=obj, scene=frame[0], image=frame[1],
                                                  raw=first_difference(results[before]['raw'], results[after]['raw']),
                                                  selected=first_difference(results[before]['kept'], results[after]['kept']))
                for metric in METRICS:
                    ids = detail[metric]
                    for scope in ((name, None, None, metric), (name, obj, None, metric),
                                  (name, obj, frame[0], metric), (name, None, frame[0], metric)):
                        comparisons[scope].update({field: len(values) for field, values in ids.items()})
                    for status in ('retained', 'new', 'lost'):
                        for identity in ids[status]:
                            changes.append(dict(comparison=name, metric=metric, object_id=obj, scene=frame[0], image=frame[1],
                                                gt_id=identity, status=status, same_pose_if_both=int(identity in ids['same_pose']) if status == 'retained' else -1,
                                                exact_detection_retained=int(identity in ids['exact_detection_retained'])))
                if name == 'training_policy':
                    for metric, label_name in [('allGT', 'all_labels'), ('eligible', 'eligible_labels')]:
                        detected = [{identity: detection for detection, (label, identity) in zip(results[arm]['kept'], results[arm][label_name])
                                     if label == 'TP'} for arm in ('rgb', 'binary_empty_mask')]
                        for truth in gt:
                            if metric == 'eligible' and truth['visib_fract'] < .5:
                                continue
                            identity = truth['gt_id']
                            both = identity in detected[0] and identity in detected[1]
                            retention_expected[(obj, *frame, metric, identity)] = (int(identity in detected[0]), int(identity in detected[1]),
                                int(detected[0][identity][6] == detected[1][identity][6]) if both else -1)
        summary = reader.json(native/f'obj{obj}'/'metrics.json')
        need(summary['object_id'] == obj, 'Native object summary identity differs')
        for arm in ARMS[1:]:
            check_numeric(summary[arm], finished(groups[(obj, None, arm)]), 'Native object totals')
        scene_map = unique(summary['per_scene'], lambda row: row['scene_id'])
        need(set(scene_map) == {s for o, s, _ in groups if o == obj and s is not None}, 'Native object scene coverage differs')
        for scene, item in scene_map.items():
            for arm in ARMS[1:]:
                check_numeric(item[arm], finished(groups[(obj, scene, arm)]), 'Native object/scene totals')
        if kind == 'development':
            for metric in METRICS:
                check_numeric(baseline_entry[metric], finished(groups[(obj, None, 'v15_rgb')])[metric], 'Pinned V15 object totals')
            old_totals = finished(groups[(obj, None, 'v15_rgb')])
            check_numeric(baseline_entry, {name: old_totals[name] for name in OTHER if name != 'raw_candidates'}, 'Pinned V15 object negatives')
            need(baseline_entry['raw_rows_per_variant'] == old_totals['raw_candidates'], 'Pinned V15 raw count differs')
        print(json.dumps(dict(object_id=obj, stage=kind, frames=len(chosen), status='independent_numeric_match')), flush=True)
    check_retention(table(reader.read(native/'gt_retention.csv'), RETENTION_HEADER), retention_expected)
    report = report_groups(groups)
    summary = reader.json(native/'stage_summary.json')
    check_numeric(summary, dict(passed=1, stage=kind, objects=OBJECTS, unique_frames=len(chosen),
                               object_frame_combinations=6*len(chosen), matcher_calls=stage_freeze['actual_matcher_calls'],
                               exact_same_arm_paths=1, complete_raw_archives=1, decode_and_bank_load_excluded_from_external_call=1,
                               paired_performance_benchmark=0), 'Native stage summary')
    for arm in ARMS[1:]:
        check_numeric(summary[arm], report['micro'][arm], 'Native pooled totals')
    raw_bytes = sum(reader.seen[name]['bytes'] for name in raw_names)
    need(summary['raw_output_bytes'] == raw_bytes and 0 < raw_bytes <= 1073741824 and
         0 < number(summary['peak_rss_bytes']) <= 1610612736 and number(summary['decode_total_ms']) >= 0,
         'Native raw-byte/resource diagnostics differ')
    stage_scenes = unique(summary['per_scene'], lambda row: row['scene_id'])
    need(set(stage_scenes) == {frame[0] for frame in chosen}, 'Native pooled scene coverage differs')
    for item in report['per_scene']:
        for arm in ARMS[1:]:
            check_numeric(stage_scenes[item['scene_id']][arm], item[arm], 'Native pooled scene totals')
    if kind == 'development':
        for metric, field in [('allGT', 'allGT_micro'), ('visibility_ge_0_5', 'visibility_ge_0_5_micro')]:
            check_numeric(baseline[field], report['micro']['v15_rgb'][metric], 'Pinned V15 pooled totals')
        check_numeric(baseline['object_macro'], {field: report['equal_object_macro']['v15_rgb']['allGT'][field]
                                               for field in ('precision', 'recall', 'f1')}, 'Pinned V15 macro')
    reader.recheck()
    comparisons_report = [dict(comparison=name, object_id=obj, scene_id=scene, metric=metric, **counts)
                          for (name, obj, scene, metric), counts in comparisons.items()]
    result = dict(passed=True, stage=kind, unique_frames=len(chosen), object_frame_pairs=6*len(chosen),
                  matcher_calls=0, dataset_image_bytes_opened=0, image_decodes=0, heldout_frames_processed=0,
                  reserved_objects_processed=0, independent_of_target_evaluator_imports=True,
                  quality=report, comparisons=comparisons_report, first_raw_differences=first_differences,
                  equality_totals=[dict(comparison=name, object_id=obj, scene_id=scene, **counts)
                                   for (name, obj, scene), counts in equality_totals.items()],
                  single_pass_timings_are_not_speed_evidence=True,
                  cross_training_pose_identity='object/training_image/angle/scale; numeric template IDs are arm-local',
                  source_pins=source_pins, input_pins=list(reader.seen.values()))
    for name, rows in [('per_frame.csv', frame_rows), ('gt_identity_changes.csv', changes), ('cross_arm_equality.csv', equalities)]:
        with (output/name).open('w', encoding='utf-8', newline='') as stream:
            # A zero-TP result legitimately leaves the identity-change table
            # header-only. Fixed frame/equality scopes are always nonempty.
            headers = list(rows[0]) if rows else ['comparison', 'metric', 'object_id', 'scene', 'image', 'gt_id', 'status', 'same_pose_if_both', 'exact_detection_retained']
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader(); writer.writerows(rows)
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-freeze', type=Path, required=True)
    parser.add_argument('--stage-kind', choices=['pilot', 'development'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    need(args.cpu_slot_granted, 'Independent archive audit awaits coordinated CPU slot')
    output = args.output.resolve()
    need(output.is_relative_to(HERE) and not output.exists(), 'Fresh contained independent output required')
    output.mkdir()
    for path in sorted(HERE.glob('*.py'))+sorted(HERE.glob('*.md'))+[HERE/'ORIGIN.json']:
        (output/'source').mkdir(exist_ok=True)
        (output/'source'/path.name).write_bytes(path.read_bytes())
    try:
        result = run(args.stage_freeze, args.stage_kind, output)
        print(json.dumps(dict(passed=True, stage=args.stage_kind, object_frame_pairs=result['object_frame_pairs'], matcher_calls=0)))
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(incomplete=True, reason=str(error), matcher_calls=0,
            missing_frames_are_not_negatives=True, no_accuracy_claim_from_partial_evidence=True), indent=2)+'\n', encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
