"""Independent numeric audit of the RGB empty-mask quality stage.

Only frozen numeric artifacts and the dataset index are read.  Image suffixes
are rejected by Reader; this audit does not import, execute, or link the
native matcher/evaluator.
"""
from collections import Counter, defaultdict
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import struct
import sys

from numeric import candidate_order, evaluate, finish, float_bits, nms, overlap, score

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXPERIMENT = ROOT / 'artifacts/rgb_empty_mask_experiment'
OBJECTS = [1, 2, 5, 8, 12, 17]
ARMS = ('rgb_control', 'rgb_empty_mask')
PATHS = ('fallback', 'fused')
RAW_HEADER = ('scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,'
              'match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h').split(',')
SELECTED_HEADER = ('object_id,scene,image,arm,rank,class_id,score,score_bits,template_id,training_image,'
                   'angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,'
                   'eligible_label,eligible_id').split(',')
PER_HEADER = ('object_id,scene,image,arm,raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,'
              'eligible_gt,ignored,all_iou_sum,eligible_iou_sum,negative_fp').split(',')
EQ_HEADER = ('object_id,scene,image,arm,fallback_count,fused_count,exact_order_fields_score_bits,'
             'reference_exact,fallback_match_ms,fused_match_ms,fallback_external_ms,fused_external_ms').split(',')
GT_HEADER = ('object_id,scene,image,gt_id,class_id,visibility,bbox_x,bbox_y,bbox_w,bbox_h').split(',')
RETENTION_HEADER = ('object_id,scene,image,metric,gt_id,rgb_control_detected,rgb_empty_mask_detected,'
                    'same_pose_if_both').split(',')


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Reader:
    """Numeric-only reader; image byte access is a hard error."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.seen = {}

    def allowed(self, path):
        path = Path(path).resolve(strict=True)
        need(path.is_relative_to(self.root), 'Audit path escaped repository root')
        need(path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp'},
             'Image byte access refused')
        datasets = self.root / 'datasets'
        need(not path.is_relative_to(datasets) or path == datasets / 'tless_expanded/index.json',
             'Dataset access outside numeric index refused')
        return path

    def read(self, path):
        path = self.allowed(path)
        data = path.read_bytes()
        pin = {'path': str(path), 'sha256': digest(data), 'bytes': len(data)}
        need(self.seen.setdefault(str(path), pin) == pin, 'Numeric file changed during audit')
        return data

    def json(self, path):
        return json.loads(self.read(path).decode('utf-8-sig'))

    def pin(self, path):
        self.read(path)
        return dict(self.seen[str(Path(path).resolve())])

    def check(self, pin):
        data = self.read(pin['path'])
        need(len(data) == int(pin['bytes']) and digest(data) == pin['sha256'],
             'Frozen numeric SHA/bytes differ: ' + str(pin['path']))
        return data

    def recheck(self):
        for pin in list(self.seen.values()):
            self.check(pin)


def table(data, header):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    need(reader.fieldnames == header, 'CSV schema differs')
    rows = list(reader)
    for row in rows:
        need(None not in row and None not in row.values(), 'CSV width differs')
    return rows


def integer(value):
    text = str(value)
    need(text == str(int(text)), 'Noncanonical integer')
    return int(text)


def number(value):
    result = float(value)
    need(result == result and abs(result) != float('inf'), 'Nonfinite number')
    return result


def metadata(reader, directory, object_id, expected):
    records = reader.json(Path(directory) / 'template_metadata.json')['templates']
    cls = f'tless_object_{object_id}'
    need(len(records) == expected, f'Metadata count differs for object {object_id}')
    result = {}
    for index, item in enumerate(records):
        need(item['template_id'] == index and item['class_id'] == cls and index not in result,
             'Template id/class/order differs')
        need(len(item['warped_mask_bbox']) == 4 and min(item['warped_mask_bbox'][2:]) > 0,
             'Template official box metadata differs')
        result[index] = item
    return result


def parse_candidate(row, object_id, meta):
    cls = f'tless_object_{object_id}'
    template = integer(row['template_id'])
    need(row['class_id'] == cls and template in meta, 'Raw class/template identity differs')
    m = meta[template]
    raw_score = number(row['score'])
    bits = float_bits(raw_score)
    need(85 <= score(bits) <= 100, 'Raw score outside threshold')
    x, y = integer(row['match_x']), integer(row['match_y'])
    box = tuple(number(row[f'bbox_{axis}']) for axis in ('x', 'y', 'w', 'h'))
    sx, sy, width, height = (number(v) for v in m['warped_mask_bbox'])
    expected_box = (x - 64 + sx - m['tl_x'], y - 64 + sy - m['tl_y'], width, height)
    need(box == expected_box, 'Official box/source-origin conversion differs')
    angle_bits, scale_bits = float_bits(number(row['angle'])), float_bits(number(row['scale']))
    need(integer(row['training_image']) == m['training_image_id'] and
         score(angle_bits) == score(float_bits(m['angle'])) and
         score(scale_bits) == score(float_bits(m['scale'])), 'Raw pose metadata differs')
    return cls, template, x, y, bits, box, (m['training_image_id'], angle_bits, scale_bits)


def parse_raw(reader, path, frame, variant, object_id, meta):
    encoded = reader.read(path)
    manifest_path = Path(str(path).replace('.csv.gz', '_manifest.json'))
    manifest = reader.json(manifest_path)
    contents = gzip.decompress(encoded)
    rows = table(contents, RAW_HEADER)
    need((manifest['scene_id'], manifest['image_id'], manifest['variant'], manifest['raw_candidate_count'],
          manifest['compressed_bytes'], manifest['uncompressed_bytes']) ==
         (*frame, variant, len(rows), len(encoded), len(contents)), 'Raw manifest differs')
    result = []
    for rank, row in enumerate(rows):
        need((integer(row['scene']), integer(row['image']), row['variant'], integer(row['rank'])) ==
             (*frame, variant, rank), 'Raw frame/path/rank differs')
        result.append(parse_candidate(row, object_id, meta))
    need(result == sorted(result, key=candidate_order), 'Raw canonical order differs')
    return result


def same_rows(left, right):
    return left == right


def check_path_equality(left, right):
    need(same_rows(left, right), 'Fallback/fused raw streams differ')


def check_coverage(per, selected, equality_keys, expected_keys):
    need(set(per) == expected_keys and set(equality_keys) == expected_keys and
         len(equality_keys) == len(expected_keys) and set(selected).issubset(expected_keys),
         'Per-frame/selected/equality coverage differs')
    for key in expected_keys:
        selected.setdefault(key, [])


def check_gt_row(row, truth):
    need(row['class_id'] == truth['class_id'] and number(row['visibility']) == truth['visib_fract'] and
         tuple(number(row[f'bbox_{a}']) for a in ('x', 'y', 'w', 'h')) == tuple(truth['bbox_obj']),
         'Ground-truth projection value differs')


def check_selected(rows, kept, key, all_labels, eligible_labels):
    need(len(rows) == len(kept) == len(all_labels) == len(eligible_labels), 'Selected row count differs')
    for rank, (row, candidate) in enumerate(zip(rows, kept)):
        need((integer(row['object_id']), integer(row['scene']), integer(row['image']), row['arm']) == key and
             integer(row['rank']) == rank and row['class_id'] == candidate[0] and
             integer(row['template_id']) == candidate[1] and integer(row['score_bits']) == candidate[4] and
             number(row['score']) == score(candidate[4]) and
             integer(row['match_x']) == candidate[2] and integer(row['match_y']) == candidate[3] and
             integer(row['training_image']) == candidate[6][0] and
             float_bits(number(row['angle'])) == candidate[6][1] and
             float_bits(number(row['scale'])) == candidate[6][2] and
             tuple(number(row[f'bbox_{a}']) for a in ('x', 'y', 'w', 'h')) == candidate[5] and
             (row['allGT_label'], integer(row['allGT_id'])) == all_labels[rank] and
             (row['eligible_label'], integer(row['eligible_id'])) == eligible_labels[rank],
             'Selected candidate/label differs')


def frame_counts(result):
    all_counts, eligible = result['allGT'], result['eligible']
    return dict(raw=len(result['raw']), selected=len(result['kept']),
                tp=all_counts['tp'], fp=all_counts['fp'], fn=all_counts['fn'], gt=all_counts['gt'],
                eligible_tp=eligible['tp'], eligible_fp=eligible['fp'], eligible_fn=eligible['fn'],
                eligible_gt=eligible['gt'], ignored=eligible['ignored'],
                all_iou_sum=all_counts['matched_iou_sum'], eligible_iou_sum=eligible['matched_iou_sum'],
                negative_fp=result['negative_fp'])


def rows_by(rows, key):
    result = {}
    for row in rows:
        identity = key(row)
        need(identity not in result, 'Duplicate numeric row identity')
        result[identity] = row
    return result


def add_totals(destination, result):
    for metric in ('allGT', 'eligible'):
        count = destination.setdefault(metric, Counter())
        count.update({k: result[metric][k] for k in ('tp', 'fp', 'fn', 'gt', 'ignored')})
        count['matched_iou_sum'] += result[metric]['matched_iou_sum']
    for key in ('raw_candidates', 'negative_frames', 'negative_frames_with_fp', 'negative_fp'):
        destination[key] = destination.get(key, 0) + result[key]


def finished(total):
    return {**{metric: finish(total[metric]) for metric in ('allGT', 'eligible')},
            **{k: total.get(k, 0) for k in ('raw_candidates', 'negative_frames',
                                             'negative_frames_with_fp', 'negative_fp')}}


def same_numeric(left, right):
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(same_numeric(left[key], right[key]) for key in left)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= 1e-11 * max(1.0, abs(float(left)), abs(float(right)))
    return left == right


def gt_schedule(reader, inputs):
    index = reader.json(Path(inputs['dataset_root']) / 'index.json')
    development = {(row['scene_id'], row['image_id']): row for row in index['test']
                   if row['split'] == 'development'}
    scheduled = {(row['scene_id'], row['image_id']) for row in inputs['development']}
    need(len(scheduled) == len(inputs['development']) == 400, 'Frozen development schedule differs')
    need(set(development) >= scheduled, 'Frozen schedule frame absent from numeric index')
    frames = {}
    for frame in scheduled:
        source = development[frame]
        frozen = next(row for row in inputs['development'] if (row['scene_id'], row['image_id']) == frame)
        need(source['rgb'] == frozen['rgb'] and source['width'] == 720 and source['height'] == 540,
             'Development source geometry/path differs')
        frames[frame] = [dict(gt_id=g['gt_id'], class_id=g['class_id'], obj_id=g['obj_id'],
                              bbox_obj=tuple(g['bbox_obj']), visib_fract=float(g['visib_fract']))
                         for g in source['instances']]
    return frames


def stage_gate(reader, stage_path):
    stage = reader.json(stage_path)
    need(stage['completed'] is True and stage['stage'] == 'development' and
         stage['native_exit_code'] == 0 and stage['actual_matcher_calls'] == 9600,
         'Development stage freeze incomplete')
    need(stage['missing_frames_are_not_negatives'] is True and stage['heldout_images_allowed'] is False,
         'Stage safety flags differ')
    summary = stage['summary']
    need(summary['passed'] == 1 and summary['stage'] == 'development' and
         summary['objects'] == OBJECTS and summary['unique_frames'] == 400 and
         summary['object_frame_combinations'] == 2400 and summary['matcher_calls'] == 9600,
         'Development stage summary scope differs')
    # Freeze inventory is the authoritative list.  Reading it also pins every
    # raw archive and prevents an audit from silently using an unregistered file.
    for pin in stage['files'] + stage['execution_files']:
        reader.check(pin)
    native = Path(stage_path).parent / 'native'
    actual = {str(path.resolve()) for path in native.rglob('*') if path.is_file() and path.name != '.gitignore'}
    declared = {pin['path'] for pin in stage['files']}
    need(actual == declared, 'Frozen native output inventory differs')
    return stage, summary


def audit(stage_path, output):
    reader = Reader(ROOT)
    stage, summary = stage_gate(reader, stage_path)
    need(Path(stage['quality_inputs']['path']).resolve() == EXPERIMENT / 'QUALITY_INPUT_FREEZE.json',
         'Stage references a different quality input freeze')
    inputs = json.loads(reader.check(stage['quality_inputs']).decode('utf-8-sig'))
    need(inputs['objects'] == OBJECTS and inputs['version'] == 'rgb_empty_mask_quality_inputs_v1' and
         inputs['total_matcher_call_budget'] == 22176 and inputs['dataset_image_reads'] == 0 and
         inputs['image_decodes'] == 0 and inputs['matcher_calls'] == 0,
         'Frozen RGB input scope differs')
    for pin in inputs['frozen_numeric_files']:
        reader.check(pin)
    training = reader.json(EXPERIMENT / 'run_training_v1/BANK_FREEZE.json')
    need(training['native_exit_zero'] is True and training['comparison_feasible'] is True and
         training['training_attempts_complete'] is True and training['objects'] == OBJECTS and
         training['attempts'] == 20736, 'Training bank freeze incomplete')
    for pin in training['files']:
        reader.check(pin)
    planning = reader.json(EXPERIMENT / 'run_plan_v1/COMMON_PADDING_FREEZE.json')
    need(planning['passed'] is True and planning['bank_freeze']['sha256'] ==
         reader.pin(EXPERIMENT / 'run_training_v1/BANK_FREEZE.json')['sha256'],
         'Planning/training freeze binding differs')
    for pin in planning['files']:
        reader.check(pin)
    common = reader.json(EXPERIMENT / 'run_plan_v1/common_padding_plan.json')
    need(common == {**common, 'width': 848} and common['height'] == 832, 'Padding plan malformed')
    need(common['source_size'] == [720, 540] and common['padding_ltrb'] == [64, 64, 64, 228] and
         common['banks'] == 12 and common['geometry_feasible'] == 1,
         'Required 848x832 common geometry differs')
    frames = gt_schedule(reader, inputs)
    native = Path(stage_path).parent / 'native'
    per = rows_by(table(reader.read(native / 'per_frame_metrics.csv'), PER_HEADER),
                  lambda r: (integer(r['object_id']), integer(r['scene']), integer(r['image']), r['arm']))
    selected = defaultdict(list)
    for row in table(reader.read(native / 'selected_detections.csv'), SELECTED_HEADER):
        selected[(integer(row['object_id']), integer(row['scene']), integer(row['image']), row['arm'])].append(row)
    gt_csv = table(reader.read(native / 'ground_truth.csv'), GT_HEADER)
    gt_rows = rows_by(gt_csv, lambda r: tuple(integer(r[x]) for x in ('object_id', 'scene', 'image', 'gt_id')))
    equality = table(reader.read(native / 'candidate_equality.csv'), EQ_HEADER)
    expected_keys = {(obj, scene, image, arm) for obj in OBJECTS for scene, image in frames for arm in ARMS}
    check_coverage(per, selected, equality_row_key(equality), expected_keys)
    eq_map = rows_by(equality, lambda r: (integer(r['object_id']), integer(r['scene']), integer(r['image']), r['arm']))
    banks = {}
    template_counts = {}
    for bank in inputs['rgb_banks']:
        obj = int(bank['object_id'])
        need(obj in OBJECTS and bank['class_id'] == f'tless_object_{obj}', 'Bank identity differs')
        need(int(bank['treatment_template_count']) == int(training['successful_templates'][str(obj)]),
             'Treatment count does not derive from accepted training freeze')
        banks[obj] = {
            'rgb_control': metadata(reader, bank['rgb_training'], obj, int(bank['rgb_template_count'])),
            'rgb_empty_mask': metadata(reader, bank['treatment_training'], obj, int(bank['treatment_template_count'])),
        }
        template_counts[obj] = {arm: len(meta) for arm, meta in banks[obj].items()}
    totals = {arm: {} for arm in ARMS}
    per_frame_out = []
    retention_expected = {}
    for obj in OBJECTS:
        totals[obj] = {arm: {} for arm in ARMS}
        for frame, truths in sorted(frames.items()):
            gt_for_obj = [g for g in truths if g['obj_id'] == obj]
            expected_gt = {(obj, *frame, g['gt_id']) for g in gt_for_obj}
            actual_gt = {key for key in gt_rows if key[:3] == (obj, *frame)}
            need(actual_gt == expected_gt, 'Ground-truth projection coverage differs')
            for key in expected_gt:
                row = gt_rows[key]
                truth = next(g for g in gt_for_obj if g['gt_id'] == key[3])
                check_gt_row(row, truth)
            results = {}
            for arm in ARMS:
                raw = parse_raw(reader, native / f'obj{obj}' / arm / f's{frame[0]}_i{frame[1]}_fallback_raw.csv.gz',
                                frame, 'fallback', obj, banks[obj][arm])
                fused = parse_raw(reader, native / f'obj{obj}' / arm / f's{frame[0]}_i{frame[1]}_fused_raw.csv.gz',
                                  frame, 'fused', obj, banks[obj][arm])
                check_path_equality(raw, fused)
                kept = nms(raw)
                all_counts, all_labels = evaluate(kept, gt_for_obj, False)
                eligible, eligible_labels = evaluate(kept, gt_for_obj, True)
                results[arm] = dict(raw=raw, kept=kept, allGT=all_counts, eligible=eligible,
                                    all_labels=all_labels, eligible_labels=eligible_labels,
                                    raw_candidates=len(raw), negative_frames=int(not gt_for_obj),
                                    negative_frames_with_fp=int(not gt_for_obj and all_counts['fp'] > 0),
                                    negative_fp=all_counts['fp'] if not gt_for_obj else 0)
                key = (obj, *frame, arm)
                p = per[key]
                counts = frame_counts(results[arm])
                for field, value in counts.items():
                    expected = float(value) if field.endswith('_sum') else value
                    need(number(p[field]) == expected, f'Per-frame metric differs: {key}/{field}')
                check_selected(selected[key], kept, key, results[arm]['all_labels'], results[arm]['eligible_labels'])
                eq = eq_map[key]
                need(integer(eq['fallback_count']) == integer(eq['fused_count']) == len(raw) and
                     integer(eq['exact_order_fields_score_bits']) == integer(eq['reference_exact']) == 1,
                     'Candidate equality declaration differs')
                per_frame_out.append(dict(object_id=obj, scene=frame[0], image=frame[1], arm=arm, **counts))
                add_totals(totals[obj][arm], results[arm])
            for metric, labels_name in (('allGT', 'all_labels'), ('eligible', 'eligible_labels')):
                for truth in gt_for_obj:
                    if metric == 'eligible' and truth['visib_fract'] < .5:
                        continue
                    identity = truth['gt_id']
                    detected = []
                    poses = []
                    for arm in ARMS:
                        match = next((results[arm]['kept'][i] for i, value in enumerate(results[arm][labels_name])
                                      if value == ('TP', identity)), None)
                        detected.append(int(match is not None))
                        poses.append(match[6] if match else None)
                    retention_expected[(obj, *frame, metric, identity)] = (*detected,
                        int(poses[0] == poses[1]) if all(detected) else -1)
    retention = table(reader.read(native / 'gt_retention.csv'), RETENTION_HEADER)
    actual_retention = rows_by(retention, lambda r: (integer(r['object_id']), integer(r['scene']), integer(r['image']),
                                                      r['metric'], integer(r['gt_id'])))
    need({key: tuple(integer(actual_retention[key][field]) for field in ('rgb_control_detected',
          'rgb_empty_mask_detected', 'same_pose_if_both')) for key in actual_retention} == retention_expected,
         'GT retention identity/pose differs')
    pooled = {arm: {} for arm in ARMS}
    for arm in ARMS:
        pooled_total = {}
        for obj in OBJECTS:
            add = totals[obj][arm]
            for metric in ('allGT', 'eligible'):
                target = pooled_total.setdefault(metric, Counter())
                target.update({k: add[metric][k] for k in ('tp', 'fp', 'fn', 'gt', 'ignored')})
                target['matched_iou_sum'] += add[metric]['matched_iou_sum']
            for key in ('raw_candidates', 'negative_frames', 'negative_frames_with_fp', 'negative_fp'):
                pooled_total[key] = pooled_total.get(key, 0) + add.get(key, 0)
        pooled[arm] = finished(pooled_total)
        expected_summary = dict(pooled[arm])
        expected_summary['visibility_ge_0_5'] = expected_summary.pop('eligible')
        need(same_numeric(summary[arm], expected_summary), f'Pooled summary differs for {arm}: {summary[arm]} != {expected_summary}')
    reader.recheck()
    output.mkdir(parents=False)
    (output / 'per_frame_audit.json').write_text(json.dumps(per_frame_out, indent=2) + '\n', encoding='utf-8')
    result = dict(passed=True, stage='development', unique_frames=400, object_frame_pairs=2400,
                  arms=list(ARMS), matcher_calls=0, image_decodes=0, dataset_image_bytes_opened=0,
                  heldout_frames_processed=0, reserved_objects_processed=0,
                  independent_of_target_evaluator_imports=True, common_geometry=common,
                  template_counts=template_counts,
                  stage_freeze_sha256=reader.pin(stage_path)['sha256'],
                  quality_input_sha256=reader.pin(EXPERIMENT / 'QUALITY_INPUT_FREEZE.json')['sha256'],
                  pooled=pooled, raw_and_selected_numeric_equality=True,
                  source_sha256={name: digest((HERE / name).read_bytes()) for name in ('audit.py', 'numeric.py')},
                  input_pins=list(reader.seen.values()))
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def equality_row_key(rows):
    return [(integer(r['object_id']), integer(r['scene']), integer(r['image']), r['arm']) for r in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage-freeze', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage = args.stage_freeze.resolve()
    output = args.output.resolve()
    need(stage.is_relative_to(EXPERIMENT) and stage.name == 'QUALITY_STAGE_FREEZE.json',
         'Stage freeze must belong to RGB experiment')
    need(output.is_relative_to(HERE) and not output.exists(), 'Fresh contained output required')
    try:
        result = audit(stage, output)
    except Exception as error:
        output.mkdir(parents=False, exist_ok=True)
        (output / 'failure.json').write_text(json.dumps(dict(passed=False, reason=str(error), matcher_calls=0,
            image_decodes=0, missing_frames_are_not_negatives=True), indent=2) + '\n', encoding='utf-8')
        raise
    print(json.dumps(dict(passed=result['passed'], stage=result['stage'], matcher_calls=0,
                          object_frame_pairs=result['object_frame_pairs'])))


if __name__ == '__main__':
    main()
