"""Independent numeric audit of an already completed coverage run.

Standard library only. Never opens RGB/mask files, decodes images, invokes the
matcher/coverage executable, imports their code, or chooses a coverage threshold.
The reported edge-support counts remain experimental inputs: without images
this audit cannot independently prove that those counts match observed edges.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import struct


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)


def frame(row):
    return int(row['scene']), int(row['image'])


def template(row):
    return row['class_id'], int(row['template_id'])


def identity(row):
    # Preserve original fields including the float32 score bits.
    return (row['class_id'], int(row['template_id']), int(row['match_x']),
            int(row['match_y']), struct.pack('<f', float(row['score'])),
            *[float(row['bbox_' + k]) for k in ('x', 'y', 'w', 'h')])


def order(row):
    return (-float(row['score']), row['class_id'], int(row['template_id']),
            int(row['match_y']), int(row['match_x']), float(row['bbox_y']),
            float(row['bbox_x']), float(row['bbox_w']), float(row['bbox_h']))


def box(row):
    return [float(row['bbox_' + k]) for k in ('x', 'y', 'w', 'h')]


def iou(a, b):
    if min(a[2:]+b[2:]) <= 0:
        return 0.0
    intersection = (max(0.0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])) *
                    max(0.0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1])))
    union = a[2]*a[3]+b[2]*b[3]-intersection
    return intersection/union if union > 0 else 0.0


def nms(candidates, threshold=None, lazy=False):
    accepted, attempts, queries, suppressed = [], 0, 0, 0
    for row in sorted(candidates, key=order):
        overlap = any((not row['class_id'] or not prev['class_id'] or
                       row['class_id'] == prev['class_id']) and
                      iou(box(row), box(prev)) > .3 for prev in accepted)
        if lazy and overlap:
            suppressed += 1
            continue
        if threshold is not None:
            attempts += 1
            if int(row['verified']):
                queries += int(row['points'])
                if float(row['balanced']) < threshold:
                    continue
        if not overlap:
            accepted.append(row)
    return accepted, attempts, suppressed, queries


def evaluate(selected, gt, eligible):
    labels, ids, used, overlap_sum = ['FP']*len(selected), [-1]*len(selected), set(), 0.0
    for ignore in (False, True) if eligible else (False,):
        for pos, row in enumerate(selected):
            if labels[pos] != 'FP':
                continue
            options = []
            for g in gt:
                gid = g['gt_id']
                if gid in used or (eligible and ((g['visib_fract'] < .5) != ignore)):
                    continue
                value = iou(box(row), g['bbox_obj'])
                if value >= .5:
                    options.append((-value, gid))
            if options:
                negative_overlap, gid = min(options)
                used.add(gid)
                labels[pos], ids[pos] = ('IGNORE' if ignore else 'TP'), gid
                if not ignore:
                    overlap_sum -= negative_overlap
    tp, ignored = labels.count('TP'), labels.count('IGNORE')
    total = sum(not eligible or g['visib_fract'] >= .5 for g in gt)
    result = dict(tp=tp, fp=len(selected)-tp-ignored, fn=total-tp,
                  gt=total, ignored=ignored, matched_iou_sum=overlap_sum)
    return result, labels, ids


def derived(counts):
    p = counts['tp']/(counts['tp']+counts['fp']) if counts['tp']+counts['fp'] else 0.0
    r = counts['tp']/counts['gt'] if counts['gt'] else 0.0
    return dict(counts, precision=p, recall=r, f1=2*p*r/(p+r) if p+r else 0.0,
                mean_tp_iou=counts['matched_iou_sum']/counts['tp'] if counts['tp'] else 0.0)


def close(a, b, where):
    require(math.isclose(float(a), float(b), rel_tol=2e-12, abs_tol=2e-12),
            f'{where}: {a} != {b}')


def audit(run):
    run = run.resolve()
    verified = read_json(run/'verified_inputs.json')
    metrics = read_json(run/'coverage_metrics.json')
    provenance = read_json(run/'execution_provenance.json')
    build = read_json(run/'build_manifest.json')
    require(provenance['exit_code'] == 0 and provenance['inputs_unchanged'] and
            provenance['sources_unchanged'], 'Runner did not complete cleanly')
    output_hashes = {}
    for name, digest in provenance['output_sha256'].items():
        require(sha(run/name) == digest.lower(), f'Output SHA differs: {name}')
        output_hashes[name] = digest.lower()
    require(sha(run/'build_manifest.json') == provenance['build_manifest_sha256'].lower(), 'Build manifest SHA')
    require(sha(run/'verified_inputs.json') == provenance['verified_inputs_sha256'].lower(), 'Verified input SHA')
    require(verified['split'] == 'development' and verified['target_objects'] in [[1], [2], [5], [8], [12], [17]], 'Scope')
    root = Path(verified['dataset_root'])
    index_path = root/'index.json'
    index_pin = next(v for v in verified['input_sha256'] if Path(v['path']) == index_path)
    require(sha(index_path) == index_pin['sha256'], 'Index hash')
    snapshot_count = 0
    for frozen in (run/'source').iterdir():
        if frozen.is_file():
            digests = [digest.lower() for path, digest in build['source_sha256'].items()
                       if Path(path).name == frozen.name]
            require(len(digests) == 1 and sha(frozen) == digests[0], f'Frozen source SHA: {frozen.name}')
            snapshot_count += 1
    selected_frames = {(v['scene_id'], v['image_id']): v for v in verified['frames']}
    index_frames = {(v['scene_id'], v['image_id']): v for v in read_json(index_path)['test']
                    if v['split'] == 'development'}
    require(set(selected_frames) <= set(index_frames), 'Frame outside development')
    candidates = collections.defaultdict(list)
    template_uses = collections.defaultdict(list)
    for row in rows(run/'all_post85_coverage.csv.gz'):
        k = frame(row)
        require(k in selected_frames and int(row['rank']) == len(candidates[k]), 'Coverage rank/frame')
        require(float(row['score']) >= 85, 'Post score threshold')
        require(int(row['verified']) in (0, 1), 'Verified flag')
        points, supported = int(row['points']), int(row['supported'])
        cells = [int(row[f'cell_points_{i}']) for i in range(16)]
        supports = [int(row[f'cell_supported_{i}']) for i in range(16)]
        require(sum(cells) == points and sum(supports) == supported, 'Cell count sum')
        require(all(0 <= s <= c for s, c in zip(supports, cells)), 'Cell support count')
        occupied = sum(c > 0 for c in cells)
        require(int(row['occupied_cells']) == occupied, 'Occupied cells')
        ratios = [s/c if c else 0.0 for s, c in zip(supports, cells)]
        for i, ratio in enumerate(ratios):
            close(row[f'cell_coverage_{i}'], ratio, 'Cell ratio')
        close(row['balanced'], sum(ratios)/occupied if occupied else 0.0, 'Balanced score')
        close(row['unweighted'], supported/points if points else 0.0, 'Unweighted score')
        require(0 <= int(row['original_in_bounds']) <= int(row['map_in_bounds']) <= points, 'In-bounds counts')
        for name in ('original_in_bounds', 'map_in_bounds'):
            close(row[name+'_fraction'], int(row[name])/points if points else 0.0, name+' fraction')
        candidates[k].append(row)
        template_uses[template(row)].append(row)
    raw_hashes = []
    for k, declared in selected_frames.items():
        require(len(candidates[k]) == declared['raw_count'], 'Raw/post85 count')
        variants = []
        for variant in ('fallback', 'fused'):
            archive = declared['archives'][variant]
            require(sha(archive['path']) == archive['sha256'], 'Raw archive SHA')
            raw = list(rows(archive['path']))
            require(len(raw) == len(candidates[k]) == archive['rows'], 'Raw row count')
            require([identity(v) for v in raw] == [identity(v) for v in candidates[k]], 'Raw/coverage original fields')
            variants.append([identity(v) for v in raw])
            raw_hashes.append(dict(path=archive['path'], sha256=archive['sha256']))
        require(variants[0] == variants[1], 'Fallback/fused mismatch')
    templates = {template(v): v for v in rows(run/'validation_templates.csv')}
    point_count, negative_offsets, audited_templates = 0, 0, set()
    for tid, group in itertools.groupby(rows(run/'validation_points.csv.gz'), template):
        points = list(group)
        require(tid in templates and tid not in audited_templates, 'Validation template identity/order')
        audited_templates.add(tid)
        t = templates[tid]
        require(len(points) == int(t['points']), 'Validation point count')
        coords, cells = [], [0]*16
        for i, point in enumerate(points):
            x, y = int(point['relative_x']), int(point['relative_y'])
            require(int(point['point_index']) == i and 0 <= int(point['label']) < 8, 'Point index/label')
            require(x == int(point['canvas_x'])-int(t['tl_x']) and
                    y == int(point['canvas_y'])-int(t['tl_y']), 'Point origin subtraction')
            coords.append((x, y))
            negative_offsets += x < 0 or y < 0
        if coords:
            xmin, xmax = min(x for x, _ in coords), max(x for x, _ in coords)
            ymin, ymax = min(y for _, y in coords), max(y for _, y in coords)
            for point, (x, y) in zip(points, coords):
                cell = 4*((4*(y-ymin))//(ymax-ymin+1)) + (4*(x-xmin))//(xmax-xmin+1)
                require(int(point['cell']) == cell, '4x4 inclusive-span cell')
                cells[cell] += 1
        require(sum(c > 0 for c in cells) == int(t['occupied_cells']), 'Template occupied count')
        for row in template_uses.get(tid, []):
            require(cells == [int(row[f'cell_points_{i}']) for i in range(16)], 'Candidate/template denominator')
            f = selected_frames[frame(row)]
            mx, my = int(row['match_x']), int(row['match_y'])
            left, top, right, bottom = f['padding']
            original = sum(left <= mx+x < left+f['width'] and top <= my+y < top+f['height'] for x, y in coords)
            bounds = sum(0 <= mx+x < left+f['width']+right and 0 <= my+y < top+f['height']+bottom for x, y in coords)
            require(original == int(row['original_in_bounds']) and bounds == int(row['map_in_bounds']), 'Query coordinate/bounds')
        point_count += len(points)
    require(audited_templates == set(templates), 'Missing validation point template')
    selected_csv = collections.defaultdict(list)
    for row in rows(run/'selected_detections.csv'):
        selected_csv[(frame(row), row['policy'])].append(row)
    frame_csv = {(frame(v), v['policy']): v for v in rows(run/'per_frame_metrics.csv')}
    policies = [('baseline', None), ('coverage_050', .5), ('coverage_065', .65), ('coverage_080', .8)]
    totals, scene_totals, retention_details, lazy_work = {}, {}, [], {}
    expected_selected_keys = set()
    for k, raw in candidates.items():
        gt = [g for g in index_frames[k]['instances'] if g['obj_id'] in verified['target_objects']]
        base, *_ = nms(raw)
        base_counts, base_labels, base_gtids = evaluate(base, gt, False)
        base_ids = {identity(r) for r, label in zip(base, base_labels) if label == 'TP'}
        base_gt = {gid for gid, label in zip(base_gtids, base_labels) if label == 'TP'}
        for policy, threshold in policies:
            expected_selected_keys.add((k, policy))
            full, _, _, _ = nms(raw, threshold)
            lazy, attempted, suppressed, queries = nms(raw, threshold, lazy=True)
            require([identity(v) for v in full] == [identity(v) for v in lazy], 'Independent full/lazy NMS')
            recorded = selected_csv[(k, policy)]
            require([identity(v) for v in full] == [identity(v) for v in recorded], 'Selected original fields/order')
            require([int(v['rank']) for v in recorded] == list(range(len(recorded))), 'Selected rank')
            all_counts, all_labels, all_ids = evaluate(full, gt, False)
            eligible_counts, eligible_labels, eligible_ids = evaluate(full, gt, True)
            require(all_labels == [v['allGT_label'] for v in recorded] and all_ids == [int(v['allGT_id']) for v in recorded], 'Independent allGT labels')
            require(eligible_labels == [v['eligible_label'] for v in recorded] and eligible_ids == [int(v['eligibleGT_id']) for v in recorded], 'Independent eligible labels')
            gt_retained = sum(label == 'TP' and gid in base_gt for label, gid in zip(all_labels, all_ids))
            detection_retained = sum(label == 'TP' and identity(v) in base_ids for v, label in zip(full, all_labels))
            per = frame_csv[(k, policy)]
            for name in ('tp', 'fp', 'fn', 'gt'):
                require(int(per[name]) == all_counts[name], 'Per-frame counts')
            for name in ('tp', 'fp', 'fn'):
                require(int(per['eligible_'+name]) == eligible_counts[name], 'Eligible per-frame counts')
            require(int(per['ignored']) == eligible_counts['ignored'], 'Ignored per-frame count')
            require(int(per['baseline_gt_retained']) == gt_retained and int(per['baseline_tp_detection_retained']) == detection_retained, 'Baseline retention')
            if threshold is not None:
                require([int(per[n]) for n in ('lazy_attempted', 'lazy_suppressed', 'lazy_point_queries')] == [attempted, suppressed, queries], 'Lazy counters')
            for container in (totals, scene_totals.setdefault(k[0], {})):
                summary = container.setdefault(policy, dict(allGT=collections.Counter(), visibility_ge_0_5=collections.Counter(), negative_frames=0, negative_frames_with_fp=0, negative_fp=0, baseline_gt_retained=0, baseline_tp_detection_retained=0))
                summary['allGT'].update(all_counts)
                summary['visibility_ge_0_5'].update(eligible_counts)
                summary['negative_frames'] += not gt
                summary['negative_frames_with_fp'] += not gt and bool(all_counts['fp'])
                summary['negative_fp'] += all_counts['fp'] if not gt else 0
                summary['baseline_gt_retained'] += gt_retained
                summary['baseline_tp_detection_retained'] += detection_retained
            work = lazy_work.setdefault(policy, collections.Counter())
            work.update(attempted=attempted if threshold is not None else 0, suppressed=suppressed if threshold is not None else 0, point_queries=queries if threshold is not None else 0)
            if base_gt:
                current_gt = {gid for gid, label in zip(all_ids, all_labels) if label == 'TP'}
                retention_details.append(dict(scene=k[0], image=k[1], policy=policy, baseline_gt=sorted(base_gt), current_gt=sorted(current_gt), lost_baseline_gt=sorted(base_gt-current_gt), new_gt=sorted(current_gt-base_gt), original_tp_detection_retained=detection_retained))
    require(set(frame_csv) == expected_selected_keys and not(set(selected_csv)-expected_selected_keys), 'Unexpected frame/policy rows')
    scene_reports = {v['scene_id']: v for v in metrics['per_scene']}
    for container, reported in [(totals, metrics)]+[(value, scene_reports[key]) for key, value in scene_totals.items()]:
        for policy, summary in container.items():
            for mode in ('allGT', 'visibility_ge_0_5'):
                summary[mode] = derived(summary[mode])
                for name, value in summary[mode].items():
                    close(value, reported[policy][mode][name], 'Metric '+policy+'/'+mode+'/'+name)
            for name in ('negative_frames', 'negative_frames_with_fp', 'negative_fp', 'baseline_gt_retained', 'baseline_tp_detection_retained'):
                require(summary[name] == reported[policy][name], 'Aggregate '+name)
    require(len(candidates) == metrics['frames'] and sum(map(len, candidates.values())) == metrics['raw_candidates'], 'Summary frame/raw count')
    full_queries = sum(int(v['points']) for group in candidates.values() for v in group if int(v['verified']))
    require(full_queries == metrics['full_point_queries'], 'Full point-query count')
    geometry = list(rows(run/'bank_geometry.csv'))
    failures = {name: sum(v[name] != '1' for v in geometry) for name in ('feature_extent_fits', 'local_interval_feasible', 'coarse_full_placement_feasible')}
    require(all(v == 0 for v in failures.values()), 'Frozen bank geometry preflight failure')
    # Recheck immutable result hashes after all streamed reads.
    for name, digest in output_hashes.items():
        require(sha(run/name) == digest, 'Output changed during audit')
    return dict(schema_version=1, verified=1, scope='Read-only independent numeric audit; cached edge-support inputs are not independently image-verified', run=str(run), protocol=metrics['protocol'], split=verified['split'], frames=len(candidates), raw_rows_per_variant=sum(map(len, candidates.values())), output_sha256=output_hashes, raw_archive_sha256=raw_hashes, frozen_source_files_checked=snapshot_count, validation_templates=len(templates), validation_points=point_count, negative_relative_point_offsets=negative_offsets, full_point_queries=full_queries, geometry_rows=len(geometry), geometry_failures=failures, independent_full_lazy_nms_policies=3, independent_frame_policy_evaluations=len(frame_csv), totals=totals, per_scene=scene_totals, retention_details=retention_details, lazy_work=lazy_work, dataset_rgb_reads=0, dataset_mask_reads=0, image_decode_calls=0, matcher_calls=0, coverage_calls=0, limitations=['Actual pixel-to-edge support and reextracted pyramid equivalence were executed by the frozen adapter; this numeric audit does not recompute either.', 'Cached full/lazy selections and lazy counters are independently reproduced; fresh per-point runtime equality is supported by frozen source assertions and clean exit, not an independent image pass.', 'No paired latency comparison is present; diagnostic timings include CSV and metric overhead.', 'Only development frames are audited. This is not an industrial deployment accuracy estimate.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite an existing audit')
    result = audit(args.run)
    result['audit_script_sha256'] = sha(__file__)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('verified', 'frames', 'raw_rows_per_variant', 'validation_templates', 'validation_points', 'full_point_queries', 'totals', 'lazy_work')}, ensure_ascii=False))
