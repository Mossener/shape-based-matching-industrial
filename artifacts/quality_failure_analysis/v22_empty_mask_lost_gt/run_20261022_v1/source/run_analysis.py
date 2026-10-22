"""Pinned V22 development numeric diagnosis, with no image/native/Git access."""
import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import struct

from diagnostic import Candidate, assign, classify, iou, maximum_capacity, nms_trace, order, size_upper

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPERIMENT = ROOT/'artifacts/silhouette_empty_mask_experiment'
NATIVE = EXPERIMENT/'run_quality_development_v1/native'
AUDIT = ROOT/'artifacts/independent_reviews/empty_mask_quality_v1/run_development_audit_20261022_v3'
AUDIT_SHA = '38f9025da7c7320f2e42eb632381f9995c6718d64eaa40d7378e205d73047e68'
OBJECTS = (1, 2, 5, 8, 12, 17)
SCENES = {1, 4, 6, 7, 8, 10, 12, 13}
ARMS = ('rgb', 'binary_empty_mask')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def rows(data):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    result = list(reader)
    require(all(None not in row and None not in row.values() for row in result), 'Malformed CSV width')
    return result


def f32(value):
    value = float(value)
    require(math.isfinite(value), 'Nonfinite number')
    return struct.unpack('<f', struct.pack('<f', value))[0]


def pose(metadata):
    return metadata['training_image_id'], f32(metadata['angle']), f32(metadata['scale'])


class Evidence:
    def __init__(self, audit):
        self.pins = {str(Path(p['path']).resolve()).casefold(): p for p in audit['input_pins']}
        self.seen = {}

    def read(self, path):
        path = Path(path).resolve(strict=True)
        require(path.is_relative_to(ROOT/'artifacts'), 'Only preserved artifact evidence is allowed')
        require(path.suffix.lower() in ('.json', '.csv', '.gz'), 'Only numeric evidence types are allowed')
        require(not any(p.casefold() in {'dataset', 'datasets', 'heldout', '磁片', 'magnet_match'}
                        for p in path.relative_to(ROOT).parts), 'Prohibited evidence path')
        pin = self.pins.get(str(path).casefold())
        require(pin is not None, 'Evidence not pinned by completed V22 audit: '+str(path))
        data = path.read_bytes()
        require(len(data) == pin['bytes'] and sha(data) == pin['sha256'], 'Pinned evidence changed')
        self.seen[path] = dict(path=path.relative_to(ROOT).as_posix(), bytes=len(data), sha256=sha(data))
        return data

    def load(self, path):
        return json.loads(self.read(path))

    def recheck(self):
        for path, pin in self.seen.items():
            data = path.read_bytes()
            require(len(data) == pin['bytes'] and sha(data) == pin['sha256'], 'Evidence changed during diagnosis')


def candidate(row, obj, metadata):
    identity = int(row['template_id'])
    require(row['class_id'] == 'tless_object_'+str(obj) and identity in metadata, 'Wrong candidate class/template')
    meta = metadata[identity]
    x, y = int(row['match_x']), int(row['match_y'])
    score = float(row['score'])
    require(score == f32(score) and 85 <= score <= 100, 'Noncanonical or below-threshold score')
    box = tuple(float(row['bbox_'+a]) for a in ('x', 'y', 'w', 'h'))
    sx, sy, width, height = meta['warped_mask_bbox']
    require(box == (x-64+sx-meta['tl_x'], y-64+sy-meta['tl_y'], width, height), 'Box metadata differs')
    actual_pose = int(row['training_image']), f32(row['angle']), f32(row['scale'])
    require(actual_pose == pose(meta), 'Candidate pose metadata differs')
    return Candidate(row['class_id'], identity, x, y, score, box, actual_pose)


def read_raw(evidence, obj, arm, scene, image, metadata):
    stem = NATIVE/f'obj{obj}'/arm/f's{scene}_i{image}_fallback_raw'
    encoded = evidence.read(str(stem)+'.csv.gz')
    manifest = evidence.load(str(stem)+'_manifest.json')
    plain = gzip.decompress(encoded)
    table = rows(plain)
    require((manifest['scene_id'], manifest['image_id'], manifest['variant'],
             manifest['compressed_bytes'], manifest['uncompressed_bytes'], manifest['raw_candidate_count']) ==
            (scene, image, 'fallback', len(encoded), len(plain), len(table)), 'Raw manifest differs')
    result = []
    for rank, row in enumerate(table):
        require((int(row['scene']), int(row['image']), row['variant'], int(row['rank'])) ==
                (scene, image, 'fallback', rank), 'Raw frame/rank differs')
        result.append(candidate(row, obj, metadata))
    require(result == sorted(result, key=order), 'Raw canonical ordering differs')
    return result


def capacity(raw, kept, truths):
    graph = [[g for g, truth in enumerate(truths) if iou(c.box, truth['box']) >= .5] for c in raw]
    return maximum_capacity(graph, len(truths)), maximum_capacity([graph[r] for r in kept], len(truths))


def best_candidate(raw, box):
    return min(range(len(raw)), key=lambda r: (-iou(raw[r].box, box), order(raw[r]))) if raw else None


def describe(raw, rank, box):
    if rank is None:
        return None
    value = asdict(raw[rank])
    value.update(raw_rank=rank, gt_iou=iou(raw[rank].box, box),
                 best_translation_size_iou=size_upper(raw[rank].box[2:], box[2:]))
    return value


def summarize(entries):
    return dict(gt=len(entries), status=dict(sorted(Counter(r['status'] for r in entries).items())),
                binary_categories=dict(sorted(Counter(r['binary_category'] for r in entries).items())),
                lost_categories=dict(sorted(Counter(r['binary_category'] for r in entries if r['status'] == 'lost').items())),
                lost_rgb_pose_present_in_binary_bank=sum(r['status'] == 'lost' and r['rgb_tp_pose_in_binary_bank'] for r in entries),
                lost_without_binary_bank_size_compatibility=sum(r['status'] == 'lost' and r['binary_bank_best_size_iou'] < .5 for r in entries),
                lost_with_binary_same_rgb_pose_raw_hit=sum(r['status'] == 'lost' and r['binary_same_rgb_pose_raw_hit_count'] > 0 for r in entries),
                lost_with_binary_same_rgb_pose_any_raw=sum(r['status'] == 'lost' and r['binary_same_rgb_pose_raw_count'] > 0 for r in entries))


def write_table(path, records):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        for row in records:
            writer.writerow({key: json.dumps(value, separators=(',', ':')) if isinstance(value, (list, tuple, dict)) else value
                             for key, value in row.items()})


def run(output):
    audit_bytes = (AUDIT/'result.json').read_bytes()
    require(sha(audit_bytes) == AUDIT_SHA, 'Completed V22 audit pin differs')
    audit = json.loads(audit_bytes)
    require(audit['passed'] is True and audit['stage'] == 'development' and
            audit['unique_frames'] == 400 and audit['object_frame_pairs'] == 2400, 'Audit scope differs')
    evidence = Evidence(audit)
    inputs = evidence.load(EXPERIMENT/'QUALITY_INPUT_FREEZE.json')
    require(tuple(inputs['objects']) == OBJECTS, 'Fixed object set differs')
    schedule = {(r['scene_id'], r['image_id']) for r in inputs['development']}
    require(len(schedule) == len(inputs['development']) == 400 and {s for s, _ in schedule} == SCENES,
            'Fixed development schedule differs')
    truth_groups = defaultdict(list)
    for row in rows(evidence.read(NATIVE/'ground_truth.csv')):
        obj, scene, image, identity = (int(row[field]) for field in ('object_id', 'scene', 'image', 'gt_id'))
        require(obj in OBJECTS and (scene, image) in schedule, 'GT outside fixed development scope')
        truth_groups[(obj, scene, image)].append(dict(gt_id=identity,
            box=tuple(float(row['bbox_'+a]) for a in ('x', 'y', 'w', 'h')), visibility=float(row['visibility'])))
    require(sum(map(len, truth_groups.values())) == 400 and len(truth_groups) == 350, 'GT scope differs')
    selected_groups = defaultdict(list)
    selected_totals = defaultdict(Counter)
    for row in rows(evidence.read(NATIVE/'selected_detections.csv')):
        obj, scene, image = (int(row[field]) for field in ('object_id', 'scene', 'image'))
        arm = row['arm']
        require(obj in OBJECTS and arm in ARMS and (scene, image) in schedule, 'Selected row outside fixed scope')
        key = obj, scene, image, arm
        require(int(row['rank']) == len(selected_groups[key]), 'Selected rank differs')
        selected_groups[key].append(row)
        selected_totals[arm][row['allGT_label']] += 1
    for arm in ARMS:
        expected = audit['quality']['micro'][arm]['allGT']
        require(selected_totals[arm] == Counter(TP=expected['tp'], FP=expected['fp']), 'All selected totals differ')
    per = {}
    for row in rows(evidence.read(NATIVE/'per_frame_metrics.csv')):
        key = int(row['object_id']), int(row['scene']), int(row['image']), row['arm']
        require(key not in per and key[0] in OBJECTS and key[3] in ARMS and key[1:3] in schedule, 'Per-frame scope differs')
        per[key] = row
    require(len(per) == 4800, 'Complete object/frame/arm scope differs')
    for arm in ARMS:
        expected = audit['quality']['micro'][arm]
        require(sum(int(row['raw']) for key, row in per.items() if key[3] == arm) == expected['raw_candidates'],
                'Full development raw count differs')

    output_rows, detail_rows, frame_rows, bank_rows = [], [], [], []
    loaded_raw = Counter()
    for obj in OBJECTS:
        bank = next(b for b in inputs['rgb_banks'] if b['object_id'] == obj)
        metadata, pose_maps, dimensions = {}, {}, {}
        for arm, directory in [('rgb', bank['rgb_training']), ('binary_empty_mask', bank['binary_training'])]:
            table = evidence.load(Path(directory)/'template_metadata.json')['templates']
            metadata[arm] = {m['template_id']: m for m in table}
            require(len(metadata[arm]) == len(table) and all(m['class_id'] == bank['class_id'] for m in table), 'Bank metadata differs')
            pose_maps[arm] = {pose(m): m for m in table}
            require(len(pose_maps[arm]) == len(table), 'Duplicate training pose in bank')
            dimensions[arm] = {tuple(m['warped_mask_bbox'][2:]) for m in table}
        bank_rows.append(dict(object_id=obj, rgb_templates=len(metadata['rgb']), binary_templates=len(metadata['binary_empty_mask']),
            rgb_training_poses_missing_from_binary=len(pose_maps['rgb'].keys()-pose_maps['binary_empty_mask'].keys()),
            unique_rgb_box_sizes=len(dimensions['rgb']), unique_binary_box_sizes=len(dimensions['binary_empty_mask'])))
        for key in sorted(key for key in truth_groups if key[0] == obj):
            _, scene, image = key
            truths = truth_groups[key]
            require(len({g['gt_id'] for g in truths}) == len(truths), 'Duplicate GT identity')
            values = {}
            for arm in ARMS:
                raw = read_raw(evidence, obj, arm, scene, image, metadata[arm])
                loaded_raw[arm] += len(raw)
                kept, blockers = nms_trace(raw)
                labels = assign(raw, kept, truths)
                selected = selected_groups[(*key, arm)]
                require([raw[r] for r in kept] == [candidate(row, obj, metadata[arm]) for row in selected], 'Complete independent NMS differs')
                require(labels == [(r['allGT_label'], int(r['allGT_id'])) for r in selected], 'Independent GT assignment differs')
                require(all(int(r['score_bits']) == struct.unpack('<I', struct.pack('<f', raw[k].score))[0]
                            for k, r in zip(kept, selected)), 'Selected score bits differ')
                require((len(raw), len(kept), sum(label == 'TP' for label, _ in labels)) ==
                        tuple(int(per[(*key, arm)][field]) for field in ('raw', 'selected', 'tp')), 'Positive-frame metrics differ')
                raw_capacity, selected_capacity = capacity(raw, kept, truths)
                detected = {identity: rank for rank, (label, identity) in zip(kept, labels) if label == 'TP'}
                values[arm] = dict(raw=raw, kept=kept, blockers=blockers, labels=labels, detected=detected)
                frame_rows.append(dict(object_id=obj, scene=scene, image=image, arm=arm, gt=len(truths), raw=len(raw),
                    selected=len(kept), actual_tp=len(detected), raw_capacity=raw_capacity, selected_capacity=selected_capacity,
                    raw_capacity_deficit=len(truths)-raw_capacity, raw_to_selected_capacity_loss=raw_capacity-selected_capacity,
                    assignment_capacity_loss=selected_capacity-len(detected)))
            for truth in truths:
                identity, box = truth['gt_id'], truth['box']
                before, after = values['rgb'], values['binary_empty_mask']
                old_rank = before['detected'].get(identity)
                new_rank = after['detected'].get(identity)
                old = before['raw'][old_rank] if old_rank is not None else None
                status = ('retained' if old_rank is not None and new_rank is not None else
                          'lost' if old_rank is not None else 'new' if new_rank is not None else 'neither')
                diagnostic = classify(identity, truths, after['raw'], after['kept'], after['blockers'], after['labels'])
                hits = diagnostic['overlapping_raw_ranks']
                old_pose = old.pose if old is not None else None
                same_pose_raw = [r for r, c in enumerate(after['raw']) if old_pose is not None and c.pose == old_pose]
                same_pose_hits = [r for r in same_pose_raw if r in hits]
                old_pose_meta = pose_maps['binary_empty_mask'].get(old_pose)
                best = best_candidate(after['raw'], box)
                entry = dict(object_id=obj, scene=scene, image=image, gt_id=identity, visibility=truth['visibility'],
                    bbox=box, status=status, binary_category=diagnostic['category'], rgb_raw=len(before['raw']),
                    binary_raw=len(after['raw']), binary_raw_hit_count=len(hits),
                    binary_selected_hit_count=len(diagnostic['overlapping_kept_raw_ranks']),
                    binary_best_raw_iou=iou(after['raw'][best].box, box) if best is not None else 0.,
                    binary_best_hit_score=max((after['raw'][r].score for r in hits), default=None),
                    rgb_tp_score=old.score if old else None, rgb_tp_pose=old_pose,
                    rgb_tp_pose_in_binary_bank=old_pose in pose_maps['binary_empty_mask'] if old else False,
                    binary_same_rgb_pose_raw_count=len(same_pose_raw), binary_same_rgb_pose_raw_hit_count=len(same_pose_hits),
                    binary_rgb_pose_size_iou=size_upper(old_pose_meta['warped_mask_bbox'][2:], box[2:]) if old_pose_meta else None,
                    rgb_bank_best_size_iou=max(size_upper(s, box[2:]) for s in dimensions['rgb']),
                    binary_bank_best_size_iou=max(size_upper(s, box[2:]) for s in dimensions['binary_empty_mask']))
                output_rows.append(entry)
                if status == 'lost':
                    blockers = []
                    selected_labels = dict(zip(after['kept'], after['labels']))
                    for rank in diagnostic['blocker_raw_ranks']:
                        described = describe(after['raw'], rank, box)
                        described['selected_label'], described['selected_gt_id'] = selected_labels[rank]
                        described['suppresses_overlapping_gt_raw_ranks'] = [r for r in hits if after['blockers'].get(r) == rank]
                        blockers.append(described)
                    detail_rows.append(dict(**entry, rgb_tp=describe(before['raw'], old_rank, box),
                        binary_best_iou_raw=describe(after['raw'], best, box),
                        binary_top_three_gt_overlapping_raw=[describe(after['raw'], r, box) for r in hits[:3]],
                        suppression_blockers=blockers))
        print(json.dumps(dict(object_id=obj, positive_frames=sum(k[0] == obj for k in truth_groups), status='numeric_diagnosed')), flush=True)

    changes_path = AUDIT/'gt_identity_changes.csv'
    changes_bytes = changes_path.read_bytes()
    changes = {(int(r['object_id']), int(r['scene']), int(r['image']), int(r['gt_id'])): r['status']
               for r in rows(changes_bytes) if r['comparison'] == 'training_policy' and r['metric'] == 'allGT'}
    recomputed = {(r['object_id'], r['scene'], r['image'], r['gt_id']): r['status'] for r in output_rows if r['status'] != 'neither'}
    require(changes == recomputed and len(output_rows) == 400 and len(detail_rows) == 67, 'Cross-arm GT identity totals differ')
    require(Counter(r['status'] for r in output_rows) == Counter(retained=148, lost=67, new=59, neither=126), 'Fixed identity closure differs')
    source_files = [HERE/'diagnostic.py', HERE/'run_analysis.py', HERE/'test_diagnostic.py', HERE/'PROTOCOL.json']
    source_pins = []
    (output/'source').mkdir()
    for path in source_files:
        data = path.read_bytes()
        source_pins.append(dict(path=path.relative_to(ROOT).as_posix(), bytes=len(data), sha256=sha(data)))
        (output/'source'/path.name).write_bytes(data)
    evidence.recheck()
    require(sha((AUDIT/'result.json').read_bytes()) == AUDIT_SHA and changes_path.read_bytes() == changes_bytes, 'Audit outputs changed during diagnosis')
    summary = dict(passed=True, protocol='v22_empty_mask_lost_gt_v1', matcher_calls=0, image_decodes=0,
        dataset_files_opened=0, native_builds_or_runs=0, git_commands=0, heldout_frames_processed=0,
        reserved_objects_processed=0, development_frames=400, object_frame_pairs=2400,
        positive_object_frames_replayed=350, gt_identities=400, raw_rows_loaded_on_positive_frames=dict(loaded_raw),
        all_scope_selected_counts={a: dict(v) for a, v in selected_totals.items()},
        micro=summarize(output_rows),
        per_object=[dict(object_id=obj, **summarize([r for r in output_rows if r['object_id'] == obj])) for obj in OBJECTS],
        per_scene=[dict(scene=scene, **summarize([r for r in output_rows if r['scene'] == scene])) for scene in sorted(SCENES)],
        capacity={arm: {field: sum(r[field] for r in frame_rows if r['arm'] == arm) for field in
            ('gt', 'actual_tp', 'raw_capacity', 'selected_capacity', 'raw_capacity_deficit', 'raw_to_selected_capacity_loss', 'assignment_capacity_loss')}
            for arm in ARMS},
        bank_coverage=bank_rows, minimum_binary_bank_best_size_iou=min(r['binary_bank_best_size_iou'] for r in output_rows),
        examples=[next(r for r in detail_rows if r['binary_category'] == category) for category in sorted({r['binary_category'] for r in detail_rows})],
        example_selection='First object/scene/image/gt identity in each observed lost category; no score/IoU cherry picking',
        approved_audit=dict(path=(AUDIT/'result.json').relative_to(ROOT).as_posix(), sha256=AUDIT_SHA),
        approved_gt_changes=dict(path=changes_path.relative_to(ROOT).as_posix(), sha256=sha(changes_bytes)),
        source_pins=source_pins, input_pins=list(evidence.seen.values()),
        limitation='Saved raw rows are truncated at fixed matcher score 85. No row cannot distinguish below-threshold score, coarse proposal pruning, descriptor mismatch, or placement failure. Pose labels are training identities, not GT 3D pose. Box-size bounds are translation-only. Background raw candidates were not replayed, so no new false-positive claim. Numeric diagnostics do not establish a recovered detector or generalization.')
    write_table(output/'per_gt.csv', output_rows)
    write_table(output/'per_positive_frame.csv', frame_rows)
    (output/'lost_gt_details.json').write_text(json.dumps(detail_rows, indent=2)+'\n', encoding='utf-8')
    (output/'result.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    require(args.cpu_slot_granted, 'Root must coordinate the numeric CPU slot with native timing')
    output = args.output.resolve()
    require(output.is_relative_to(HERE) and not output.exists(), 'Fresh contained output required')
    output.mkdir(parents=True)
    try:
        result = run(output)
        print(json.dumps(dict(passed=True, micro=result['micro'], capacity=result['capacity'])))
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(passed=False, error=str(error), partial_results_not_accuracy_evidence=True), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
