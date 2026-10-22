"""Read frozen complete binary pre lists; distinguish same-pose and other-pose support."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

from classify import HERE, ROOT, V2, check, need, pin, rows

PHASE1 = HERE.parent/'score_path_probe_v1/probe_phase1_v2/PROBE_STAGE_FREEZE.json'
PHASE1_SHA = 'f2be7500b13fbe1cad2bb9bc8d223b7bbf37af71919441f5b2bc2d1251e0d5ed'
CLASSIFICATION = HERE/'run_20261022_v2/result.json'
CLASSIFICATION_SHA = 'b96383b4bcf32f809cefa46725154c06424992ca72edf1e2b7d655d69f4b5872'
PAIRED_FREEZE = HERE/'report_20261022_v1/REPORT_FREEZE.json'


def iou(a, b):
    intersection = max(0., min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0]))*max(
        0., min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    union = a[2]*a[3]+b[2]*b[3]-intersection
    return intersection/union if union > 0 else 0.


def run(output):
    phase1_pin = pin(PHASE1);need(phase1_pin['sha256'] == PHASE1_SHA, 'Wrong Phase1 completion')
    phase1 = json.loads(PHASE1.read_bytes());check(phase1['input_plan'])
    plan = json.loads(Path(phase1['input_plan']['path']).read_bytes())
    classification_pin = pin(CLASSIFICATION)
    need(classification_pin['sha256'] == CLASSIFICATION_SHA, 'Wrong fixed classification')
    classification = json.loads(CLASSIFICATION.read_bytes())
    for value in classification['input_pins']+classification['source_pins']+classification['output_pins']:
        check(value)
    paired_freeze = json.loads(PAIRED_FREEZE.read_bytes())
    for value in paired_freeze['output_pins']:
        check(value)
    paired = list(rows(HERE/'report_20261022_v1/paired_215.csv'))
    paired_by_id = {tuple(int(row[key]) for key in ('object_id', 'scene', 'image', 'gt_id')): row for row in paired}
    need(len(paired_by_id) == len(paired) == 215, 'Paired scope differs')
    native_pin = {value['path']: value for value in phase1['files']}
    source_pins, counter, poses = [], Counter(), {}
    stats = {}
    for frame in plan['frames']:
        frame_id = tuple(frame[key] for key in ('object_id', 'scene', 'image'))
        obj, scene, image = frame_id
        pre = PHASE1.parent/'native'/('obj%d' % obj)/'binary_empty_mask'/('s%d_i%d_pre_raw.csv.gz' % (scene, image))
        expected_pin = native_pin[str(pre)];check(expected_pin);source_pins.append(expected_pin)
        targets = {}
        for target in frame['targets']:
            identity = (*frame_id, target['gt_id']);paired_row = paired_by_id[identity]
            targets[target['gt_id']] = dict(identity=identity, box=target['bbox'],
                template=int(paired_row['binary_template_id']), pose=tuple(target['rgb_tp_pose']),
                same_pose_hit_pre_rows=0, other_pose_hit_pre_rows=0, same_pose_pre_rows=0,
                same_pose_hit_positions=set(), other_pose_hit_templates=set(),
                same_pose_best_pre_iou=0., other_pose_best_pre_iou=0.)
        for raw in rows(pre):
            need(int(raw['scene']) == scene and int(raw['image']) == image and raw['variant'] == 'pre' and
                 raw['class_id'] == 'tless_object_%d' % obj, 'Complete pre row identity differs')
            template = int(raw['template_id']);pose = (int(raw['training_image']), float(raw['angle']), float(raw['scale']))
            previous = poses.setdefault((obj, template), pose);need(previous == pose, 'Inconsistent template/pose mapping')
            box = [float(raw[key]) for key in ('bbox_x', 'bbox_y', 'bbox_w', 'bbox_h')]
            for target in targets.values():
                overlap = iou(box, target['box']);same = template == target['template']
                need(same == (pose == target['pose']), 'Different template shares fixed same-pose identity')
                if same:
                    target['same_pose_pre_rows'] += 1
                    target['same_pose_best_pre_iou'] = max(target['same_pose_best_pre_iou'], overlap)
                    if overlap >= .5:
                        target['same_pose_hit_pre_rows'] += 1
                        target['same_pose_hit_positions'].add((int(raw['match_x']), int(raw['match_y'])))
                else:
                    target['other_pose_best_pre_iou'] = max(target['other_pose_best_pre_iou'], overlap)
                    if overlap >= .5:
                        target['other_pose_hit_pre_rows'] += 1;target['other_pose_hit_templates'].add(template)
            counter['binary_complete_pre_rows_scanned'] += 1
        for target in targets.values():
            stats[target['identity']] = target
    need(len(stats) == 215 and len(source_pins) == 213, 'Complete pre target/frame scope differs')
    nms_path = V2/'probe_phase2_v1/native/fullclass_nms_assignment.csv.gz'
    nms_pin = next(value for value in classification['input_pins'] if Path(value['path']) == nms_path)
    check(nms_pin);assigned = {}
    for raw in rows(nms_path):
        if raw['arm'] != 'binary_empty_mask' or raw['allGT_label'] != 'TP':
            continue
        identity = tuple(int(raw[key]) for key in ('object_id', 'scene', 'image', 'allGT_id'))
        if identity in stats:
            need(identity not in assigned, 'Repeated GT assignment');assigned[identity] = int(raw['template'])
    output_rows = []
    for identity, original in sorted(paired_by_id.items()):
        target = stats[identity];row = dict(original)
        for key in ('same_pose_hit_pre_rows', 'other_pose_hit_pre_rows', 'same_pose_pre_rows',
                    'same_pose_best_pre_iou', 'other_pose_best_pre_iou'):
            row['binary_complete_'+key] = target[key]
        row['binary_complete_same_pose_hit_positions'] = len(target['same_pose_hit_positions'])
        row['binary_complete_other_pose_hit_templates'] = len(target['other_pose_hit_templates'])
        selected = assigned.get(identity)
        need((selected is not None) == (original['v22_status'] == 'retained'), 'Global V22 assignment mismatch')
        row['binary_selected_tp_template'] = selected
        row['binary_selected_tp_pose_relation'] = ('not_assigned' if selected is None else
            'same_rgb_pose' if selected == target['template'] else 'other_pose')
        if selected is not None:
            need((identity[0], selected) in poses, 'Selected representative absent from complete pre')
            need((poses[(identity[0], selected)] == target['pose']) == (selected == target['template']),
                 'Selected template/pose relation differs')
        output_rows.append(row)
    groups = {}
    for state in ('all', 'lost', 'retained'):
        selected = [row for row in output_rows if state == 'all' or row['v22_status'] == state]
        groups[state] = dict(identities=len(selected),
            complete_same_pose_pre_gt_support=sum(row['binary_complete_same_pose_hit_pre_rows'] > 0 for row in selected),
            complete_other_pose_pre_gt_support=sum(row['binary_complete_other_pose_hit_pre_rows'] > 0 for row in selected),
            other_pose_support_without_same_pose_support=sum(row['binary_complete_other_pose_hit_pre_rows'] > 0 and
                 row['binary_complete_same_pose_hit_pre_rows'] == 0 for row in selected),
            selected_tp_pose_relations=dict(Counter(row['binary_selected_tp_pose_relation'] for row in selected)),
            traced_neighbor_paths=dict(Counter(row['binary_native_neighbor_path'] for row in selected)))
    with (output/'paired_215.csv').open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(output_rows[0]));writer.writeheader();writer.writerows(output_rows)
    all_inputs = [phase1_pin, phase1['input_plan'], classification_pin, pin(PAIRED_FREEZE), nms_pin]+source_pins
    for value in all_inputs:
        check(value)
    result = dict(completed=True, numeric_complete_pre_support_only=True, source=pin(HERE/'complete_pre_support.py'),
                  input_pins=all_inputs, output_pins=[pin(output/'paired_215.csv')], groups=groups,
                  complete_binary_pre_frames=213, counts=dict(counter),
                  dataset_image_bytes_opened=0, native_calls=0, matcher_calls=0,
                  independent_phase2_audit_required=True, accuracy_improvement_claim=False,
                  interpretation='Other-pose rescue is the actual selected TP template pose relation; pre-support is separately complete, before representative/NMS.')
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(completed=True, groups=groups, counts=dict(counter))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args();output = args.output.resolve()
    need(output.is_relative_to(HERE) and not output.exists() and output.parent.is_dir(), 'Fresh contained output required')
    output.mkdir();run(output)
