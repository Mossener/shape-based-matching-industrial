#!/usr/bin/env python3
"""Audit recorded single-object development outputs without decoding any dataset image."""
import argparse
from collections import Counter
import csv
from datetime import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import statistics
import struct


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iou(a, b):
    area = max(0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])) * max(0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    union = a[2]*a[3]+b[2]*b[3]-area
    return area/union if union > 0 else 0.0


def order(d):
    return (-d['score'], d['class_id'], d['template_id'], d['match_y'], d['match_x'], d['box'][1], d['box'][0], d['box'][2], d['box'][3])


def nms(rows, threshold):
    kept = []
    for row in sorted(rows, key=order):
        if not any(row['class_id'] == previous['class_id'] and iou(row['box'], previous['box']) > threshold for previous in kept):
            kept.append(row)
    return kept


def evaluate(rows, truths, eligible):
    remaining = {g['gt_id']: g for g in truths}
    labels, ids, matched = [], [], []
    for row in rows:
        options = [(iou(row['box'], g['bbox_obj']), -gid, gid) for gid, g in remaining.items()
                   if row['class_id'] == g['class_id'] and (not eligible or g['visibility'] >= 0.5)]
        best = max(options, default=(0, 0, -1))
        if best[0] >= 0.5:
            remaining.pop(best[2]); labels.append('TP'); ids.append(best[2]); matched.append(best[0])
        else:
            labels.append('FP'); ids.append(-1)
    if eligible:
        for pos, row in enumerate(rows):
            if labels[pos] != 'FP':
                continue
            options = [(iou(row['box'], g['bbox_obj']), -gid, gid) for gid, g in remaining.items()
                       if row['class_id'] == g['class_id'] and g['visibility'] < 0.5]
            best = max(options, default=(0, 0, -1))
            if best[0] >= 0.5:
                remaining.pop(best[2]); labels[pos] = 'IGNORE'; ids[pos] = best[2]
    gt = sum(not eligible or g['visibility'] >= 0.5 for g in truths)
    counts = Counter(labels)
    return {'tp': counts['TP'], 'fp': counts['FP'], 'ignored': counts['IGNORE'], 'fn': gt-counts['TP'], 'gt': gt,
            'matched_iou_sum': sum(matched), 'labels': labels, 'ids': ids}


def self_test():
    def detection(class_id, score=90, template_id=0):
        return {'class_id': class_id, 'score': score, 'template_id': template_id, 'match_x': 0, 'match_y': 0, 'box': (0, 0, 10, 10)}
    def truth(class_id, gid=0, visibility=1):
        return {'class_id': class_id, 'gt_id': gid, 'bbox_obj': [0, 0, 10, 10], 'visibility': visibility}
    assert iou((0, 0, 4, 4), (2, 0, 4, 4)) == 1/3
    assert iou((0, 0, 4, 4), (4, 0, 4, 4)) == 0
    assert len(nms([detection('tless_object_1'), detection('tless_object_2')], 0.3)) == 2
    assert len(nms([detection('tless_object_2', 90), detection('tless_object_2', 89)], 0.3)) == 1
    r = evaluate([detection('tless_object_1')], [truth('tless_object_2')], False)
    assert (r['tp'], r['fp'], r['fn']) == (0, 1, 1)
    r = evaluate([detection('tless_object_2')], [truth('tless_object_2')], False)
    assert (r['tp'], r['fp'], r['fn']) == (1, 0, 0)
    r = evaluate([detection('tless_object_2', 90), detection('tless_object_2', 89)], [truth('tless_object_2', visibility=0.1)], True)
    assert (r['tp'], r['fp'], r['fn'], r['ignored'], r['ids']) == (0, 1, 0, 1, [0, -1])
    r = evaluate([detection('tless_object_2')], [truth('tless_object_2', 9), truth('tless_object_2', 4)], False)
    assert r['ids'] == [4] and r['fn'] == 1
    r = evaluate([detection('tless_object_2')], [], False)
    assert (r['tp'], r['fp'], r['fn']) == (0, 1, 0)
    return 9


def main(args):
    literal_checks = self_test()
    protocol = load(args.protocol)
    index = load(args.dataset/'index.json')
    legacy_tiny = index.get('schema_version', 1) < 2
    training = load(args.training/'training_config.json')
    metadata = load(args.training/'template_metadata.json')['templates']
    attempts = list(csv.DictReader((args.training/'template_attempts.csv').open(newline='')))
    metrics = load(args.pilot/'metrics.json')
    is_pilot = args.stage == 'pilot'
    config = load(args.pilot/('pilot_config.json' if is_pilot else 'frozen_config.json'))
    provenance = load(args.pilot/'execution_provenance.json')
    objects = training.get('target_objects', [1] if legacy_tiny else [])
    assert len(objects) == 1 and objects[0] in protocol['development_objects']
    object_id = objects[0]
    class_id = f'tless_object_{object_id}'
    if legacy_tiny:
        assert object_id == index['target_object_id'] == 1
        for m in metadata:
            m.setdefault('class_id', class_id)
        for a in attempts:
            a.setdefault('class_id', class_id)
    expected = ([(f['scene_id'], f['image_id']) for f in protocol['pilot_frames']] if is_pilot else
                [(f['scene_id'], f['image_id']) for f in index['test'] if f['split'] == 'development'])
    observed = [(f['scene_id'], f['image_id']) for f in metrics['frames']]
    assert observed == expected and len(observed) == (8 if is_pilot else 16 if legacy_tiny else 400)
    assert config['evaluation_stage'] == ('pilot' if is_pilot else 'development_full') and config['target_objects'] == objects
    assert config['coarse_threshold'] == config['selected_post_threshold'] == 85
    assert config['nms_iou'] == 0.3 and config['match_iou'] == 0.5
    assert provenance['exit_code'] == 0
    assert provenance['build_manifest']['core_git_revision'] == protocol['core_revision']
    assert len(attempts) == 3456 and len(set(int(a['training_image']) for a in attempts)) == 72
    assert {a['class_id'] for a in attempts} == {class_id}
    assert sum(a['success'] == '1' for a in attempts) == len(metadata)
    assert [a['template_id'] for a in metadata] == list(range(len(metadata)))
    meta = {(m['class_id'], m['template_id']): m for m in metadata}
    development = {(r['scene_id'], r['image_id']): r for r in index['test'] if r['split'] == 'development'}
    assert all(key in development for key in observed)
    if is_pilot:
        assert all(next(r['image_id'] for r in index['test'] if r['scene_id'] == scene and r['split'] == 'development') == image for scene, image in expected)
    archive_hashes = {Path(a['path']).name: a['sha256'].lower() for a in provenance['raw_archives']}
    archive_summary, per_frame = [], []
    totals = {False: Counter(), True: Counter()}
    for frame in metrics['frames']:
        scene, image = frame['scene_id'], frame['image_id']
        truth = development[(scene, image)]
        assert frame['split'] == 'development' and frame['rgb'] == truth['rgb']
        expected_gt = [g for g in truth['instances'] if g['obj_id'] == object_id]
        assert len(expected_gt) == len(frame['ground_truth'])
        for a, b in zip(expected_gt, frame['ground_truth']):
            assert a['gt_id'] == b['gt_id'] and a['bbox_obj'] == b['bbox_obj'] and a['visib_fract'] == b['visibility']
        variants = {}
        for variant in ['fallback', 'fused']:
            path = args.pilot/f's{scene}_i{image}_{variant}_raw.csv.gz'
            data = gzip.decompress(path.read_bytes())
            rows = list(csv.DictReader(io.StringIO(data.decode('utf-8'))))
            manifest = load(path.with_name(path.name.replace('.csv.gz', '_manifest.json')))
            assert len(rows) == frame['raw_count'] == manifest['raw_candidate_count']
            assert len(data) == manifest['uncompressed_bytes'] and path.stat().st_size == manifest['compressed_bytes']
            assert sha(path) == archive_hashes[path.name]
            converted = []
            for rank, r in enumerate(rows):
                assert (int(r['scene']), int(r['image']), r['variant'], int(r['rank'])) == (scene, image, variant, rank)
                score = float(r['score'])
                bits = struct.pack('<f', score)
                assert struct.unpack('<f', bits)[0] == score
                m = meta[(r['class_id'], int(r['template_id']))]
                assert (int(r['training_image']), float(r['angle']), float(r['scale'])) == (m['training_image_id'], m['angle'], m['scale'])
                box = tuple(float(r['bbox_'+k]) for k in ['x', 'y', 'w', 'h'])
                expected_box = (int(r['match_x'])-config['input_padding']+m['warped_mask_bbox'][0]-m['tl_x'],
                                int(r['match_y'])-config['input_padding']+m['warped_mask_bbox'][1]-m['tl_y'], *m['warped_mask_bbox'][2:])
                assert box == expected_box
                converted.append({'class_id': r['class_id'], 'template_id': int(r['template_id']), 'score': score,
                                  'bits': bits.hex(), 'match_x': int(r['match_x']), 'match_y': int(r['match_y']), 'box': box})
            variants[variant] = converted
            archive_summary.append({'file': path.name, 'rows': len(rows), 'compressed_bytes': path.stat().st_size,
                                    'uncompressed_bytes': len(data), 'sha256': sha(path)})
        keys = lambda rows: Counter((r['class_id'], r['template_id'], r['bits'], r['match_x'], r['match_y'], r['box']) for r in rows)
        assert keys(variants['fallback']) == keys(variants['fused'])
        selected = nms([r for r in variants['fallback'] if r['score'] >= 85], 0.3)
        assert len(selected) == frame['selected_count'] == len(frame['detections'])
        for a, b in zip(selected, frame['detections']):
            assert a['class_id'] == b['class_id'] and a['template_id'] == b['template_id'] and a['score'] == b['score'] and a['box'] == tuple(b['bbox_obj'])
        for eligible, name in [(False, 'allGT'), (True, 'visibility_ge_0_5')]:
            result = evaluate(selected, frame['ground_truth'], eligible)
            for key in ['tp', 'fp', 'fn', 'gt', 'ignored']:
                assert result[key] == frame[name][key]
                totals[eligible][key] += result[key]
            assert abs(result['matched_iou_sum']-frame[name]['matched_iou_sum']) < 1e-12
            totals[eligible]['matched_iou_sum'] += result['matched_iou_sum']
            prefix = 'eligible' if eligible else 'allGT'
            assert result['labels'] == [d[prefix+'_label'] for d in frame['detections']]
            id_key = 'eligibleGT_id' if eligible else 'allGT_id'
            assert result['ids'] == [d[id_key] for d in frame['detections']]
        per_frame.append({k: frame[k] for k in ['scene_id', 'image_id', 'raw_count', 'selected_count', 'fallback_match_ms', 'fused_match_ms']})
    for eligible, name in [(False, 'allGT_total'), (True, 'visibility_ge_0_5_total')]:
        for key, value in totals[eligible].items():
            assert abs(value-metrics[name][key]) < 1e-12
    negatives = [f for f in metrics['frames'] if not f['ground_truth']]
    assert len(negatives) == metrics['negative_frames']
    assert sum(f['allGT']['fp'] for f in negatives) == metrics['negative_fp']
    times = {v: [f[v+'_match_ms'] for f in metrics['frames']] for v in ['fallback', 'fused']}
    paired = sum(times['fallback'])+sum(times['fused'])
    result = {'passed': True, 'checked_utc': datetime.now().astimezone().isoformat(),
              'audit_script_sha256': sha(Path(__file__)), 'independent_literal_checks': literal_checks,
              'stage': args.stage,
              'warning': ('Development diagnostic pilot only. One positive image; ' if is_pilot else 'Fixed development baseline only; ') + 'no accuracy improvement claim. Fixed fallback-first single calls are not a speed benchmark.',
              'training': {'attempts': len(attempts), 'successful_templates': len(metadata), 'source_views': 72, 'objects': objects},
              'pilot_frames': per_frame, 'allGT': metrics['allGT_total'], 'visibility_ge_0_5': metrics['visibility_ge_0_5_total'],
              'negative_frames': len(negatives), 'negative_frames_with_fp': sum(bool(f['allGT']['fp']) for f in negatives), 'negative_fp': metrics['negative_fp'],
              'exact_candidate_equality_frames': len(observed), 'raw_rows_per_variant': sum(f['raw_count'] for f in metrics['frames']),
              'archive_summary': archive_summary,
              'timing': {v: {'mean_ms': statistics.mean(t), 'min_ms': min(t), 'max_ms': max(t)} for v, t in times.items()},
              'full_4800_calls_extrapolation_seconds': paired/(2*len(observed))*4800/1000,
              'no_rgb_decoded_by_this_audit': True, 'heldout_matching_run': False, 'object_25_29_training_or_matching_run': False,
              'input_sha256': {str(path): sha(path) for path in [args.protocol, args.dataset/'index.json', args.training/'training_config.json', args.training/'template_metadata.json', args.training/'template_attempts.csv', args.training/f'templates_tless_object_{object_id}.yml.gz', args.pilot/'metrics.json', args.pilot/'execution_provenance.json']}}
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['passed', 'stage', 'training', 'allGT', 'negative_frames', 'negative_fp', 'exact_candidate_equality_frames', 'raw_rows_per_variant', 'timing', 'full_4800_calls_extrapolation_seconds']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=Path('datasets/tless_expanded'))
    parser.add_argument('--training', type=Path, default=Path('datasets/tless_expanded_obj1_f32_train'))
    parser.add_argument('--pilot', type=Path, default=Path('datasets/tless_expanded_obj1_f32_pilot'))
    parser.add_argument('--protocol', type=Path, default=Path('artifacts/public_evaluation/expanded_baseline_protocol.json'))
    parser.add_argument('--stage', choices=['pilot', 'development_full'], default='pilot')
    parser.add_argument('--output', type=Path, default=Path('artifacts/public_evaluation/expanded_obj1_pilot_audit.json'))
    main(parser.parse_args())
