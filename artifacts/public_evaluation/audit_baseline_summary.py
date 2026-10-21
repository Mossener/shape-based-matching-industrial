#!/usr/bin/env python3
"""Cross-check the six-object summary against preserved numeric metrics."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path,
                        default=Path('artifacts/public_evaluation'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    summary_path = args.directory/'baseline_summary_all_six.json'
    summary_bytes = summary_path.read_bytes()
    summary = json.loads(summary_bytes)
    expected_objects = [1, 2, 5, 8, 12, 17]
    require(summary['objects_completed'] == expected_objects, 'Object set differs')
    require([r['object_id'] for r in summary['per_object']] == expected_objects,
            'Per-object rows differ')
    fields = ['tp', 'fp', 'fn', 'gt', 'ignored', 'matched_iou_sum']
    totals = {key: dict.fromkeys(fields, 0) for key in
              ['allGT_micro', 'visibility_ge_0_5_micro']}
    sources, groups, frame_sets = [], [], []
    negative = raw = 0
    for row in summary['per_object']:
        obj = row['object_id']
        path = args.directory/f'expanded_obj{obj}_v11/development/metrics.json'
        if not path.exists():
            path = path.with_name(path.name+'.gz')
        encoded = path.read_bytes()
        data = json.loads(gzip.decompress(encoded)
                          if path.name.endswith('.json.gz') else encoded)
        frames = data['frames']
        require(len(frames) == 400 and data['all_frames_exact_candidate_equality'],
                'Frame count/equality differs')
        frame_set = {(f['scene_id'], f['image_id']) for f in frames}
        require(len(frame_set) == 400, 'Duplicate frame')
        frame_sets.append(frame_set)
        require(data['features'] == 32 and data['coarse_threshold'] == 85 and
                data['selected_post_threshold'] == 85 and data['nms_iou'] == .3 and
                data['match_iou'] == .5, 'Fixed recipe differs')
        for agg, field, per in [
                ('allGT_micro', 'allGT_total', 'allGT'),
                ('visibility_ge_0_5_micro', 'visibility_ge_0_5_total',
                 'visibility_ge_0_5')]:
            for key, value in data[field].items():
                require(math.isclose(row[per][key], value, rel_tol=0, abs_tol=1e-12),
                        'Per-object metric differs: '+key)
            for key in fields:
                totals[agg][key] += data[field][key]
        groups.append(data['allGT_total'])
        negative += data['negative_fp']
        raw += sum(f['raw_count'] for f in frames)
        sources.append({'path': path.as_posix(), 'sha256': sha(encoded),
                        'frames': len(frames), 'object_id': obj})
    require(all(frames == frame_sets[0] for frames in frame_sets),
            'Objects were not evaluated on the same 400 images')
    for key, data in totals.items():
        data['precision'] = data['tp']/(data['tp']+data['fp'])
        data['recall'] = data['tp']/(data['tp']+data['fn'])
        data['f1'] = 2*data['tp']/(2*data['tp']+data['fp']+data['fn'])
        data['mean_tp_iou'] = data['matched_iou_sum']/data['tp']
        for metric, value in data.items():
            require(math.isclose(summary[key][metric], value,
                                 rel_tol=0, abs_tol=1e-12),
                    'Micro metric differs: '+metric)
    for metric in ['precision', 'recall', 'f1']:
        require(math.isclose(summary['object_macro'][metric],
                             sum(g[metric] for g in groups)/6,
                             rel_tol=0, abs_tol=1e-12), 'Macro metric differs')
    require(negative == summary['negative_fp'] and
            raw == summary['raw_rows_per_variant'], 'Raw/negative sum differs')
    require(summary['unique_development_images'] == 400 and
            summary['independent_object_frame_evaluations'] == 2400 and
            summary['matcher_calls'] == 4800 and
            summary['exact_candidate_equality_object_frames'] == 2400 and
            summary['one_vs_rest_per_object'] and not summary['joint_scan'],
            'Evaluation unit/call count differs')
    result = {'passed': True, 'audit_script_sha256': sha(Path(__file__).read_bytes()),
              'scope': 'Cross-check the six-object summary against all six preserved metrics files, independently of the summary construction source audits. No image or local dataset source opened.',
              'summary_sha256': sha(summary_bytes), 'objects': expected_objects,
              'unique_images': 400, 'object_frames': 2400, 'matcher_calls': 4800,
              'checked': 'Per-object/micro/macro quality, visibility, negative FP, raw counts, actual matcher/post thresholds, NMS/GT IoU, exact equality, frame identity and evaluation unit.',
              'sources': sources}
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'summary_sha256': sha(summary_bytes),
                      'negative_fp': negative, 'raw_per_variant': raw}))


if __name__ == '__main__':
    main()
