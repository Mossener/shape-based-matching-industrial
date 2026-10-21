"""Independent Python numeric audit; reads no image and invokes no matcher.

Reconstructs boxes, NMS, GT assignment, retention and timing summaries directly
from preserved gzip/CSV/JSON bytes. It imports no adapter/evaluator code.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
PROTOCOL_SHA = 'ab9207f2dd492622aed8f563997b00ca6d137d5c93fa0f2c99b67f7ec756573d'
HASHED = set()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    path = Path(path)
    HASHED.add(str(path.resolve()))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def table(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def close(a, b, reason):
    require(math.isfinite(float(a)) and math.isfinite(float(b)) and
            math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12), reason)


def f32(value):
    return struct.pack('<f', float(value))


def detection(row):
    score = float(row['score'])
    require(math.isfinite(score) and 85 <= score <= 100, 'Invalid score')
    return (row['class_id'], int(row['template_id']), int(row['match_x']),
            int(row['match_y']), f32(score),
            tuple(float(row['bbox_'+axis]) for axis in ('x', 'y', 'w', 'h')))


def score(d):
    return struct.unpack('<f', d[4])[0]


def order(d):
    x, y, w, h = d[5]
    return (-score(d), d[0], d[1], d[3], d[2], y, x, w, h)


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if min(aw, ah, bw, bh) <= 0:
        return 0.0
    intersection = max(0.0, min(ax+aw, bx+bw)-max(ax, bx)) * max(0.0, min(ay+ah, by+bh)-max(ay, by))
    return intersection / (aw*ah+bw*bh-intersection)


def nms(raw):
    kept = []
    for d in sorted(raw, key=order):
        if all(d[0] != old[0] or iou(d[5], old[5]) <= .3 for old in kept):
            kept.append(d)
    return kept


def evaluate(kept, gt, eligible):
    labels = [('FP', -1) for _ in kept]
    used = set()
    overlaps = []
    # One-to-one eligible assignments precede the low-visibility ignore pass.
    for pass_ignore in ([False, True] if eligible else [False]):
        for rank, d in enumerate(kept):
            if labels[rank][0] != 'FP':
                continue
            options = []
            for g in gt:
                if g['gt_id'] in used or (eligible and (g['visib_fract'] < .5) != pass_ignore):
                    continue
                overlap = iou(d[5], g['bbox_obj'])
                if overlap >= .5:
                    options.append((-overlap, g['gt_id']))
            if options:
                negative_overlap, identity = min(options)
                used.add(identity)
                labels[rank] = ('IGNORE' if pass_ignore else 'TP', identity)
                if not pass_ignore:
                    overlaps.append(-negative_overlap)
    counts = Counter(label for label, _ in labels)
    total_gt = sum(not eligible or g['visib_fract'] >= .5 for g in gt)
    return dict(tp=counts['TP'], fp=counts['FP'], fn=total_gt-counts['TP'],
                gt=total_gt, ignored=counts['IGNORE'], matched_iou_sum=sum(overlaps)), labels


def finish(counts):
    result = dict(counts)
    tp, fp, fn, total = (result.get(k, 0) for k in ('tp', 'fp', 'fn', 'gt'))
    result.update(precision=tp/(tp+fp) if tp+fp else 0.0,
                  recall=tp/total if total else 0.0,
                  f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0,
                  mean_tp_iou=result.get('matched_iou_sum', 0)/tp if tp else 0.0)
    return result


def check_numeric(actual, expected, prefix):
    for name, value in expected.items():
        require(name in actual, prefix+' missing '+name)
        if isinstance(value, float):
            close(actual[name], value, prefix+' '+name)
        else:
            require(actual[name] == value, prefix+' '+name)


def provenance(run, stage):
    e = load(run/'execution_provenance.json')
    require(e['exit_code'] == 0 and e['mode'] == stage, 'Unsuccessful stage')
    for field in ('sources_unchanged', 'inputs_unchanged', 'executable_unchanged', 'build_manifest_unchanged'):
        require(e[field] is True, 'Missing unchanged assertion: '+field)
    require(e['heldout_images_read'] == 0, 'Heldout image use')
    require(e['opencv_threads'] == 1 and e['openmp_threads'] == 4, 'Thread settings changed')
    for name, wanted in e['output_sha256'].items():
        require(sha(run/name) == wanted.lower(), 'Changed output: '+name)
    require(sha(run/'build_manifest.json') == e['build_manifest_sha256'].lower(), 'Changed build manifest')
    require(sha(run/'verified_inputs.json') == e['verified_inputs_sha256'].lower(), 'Changed verified inputs')
    v = load(run/'verified_inputs.json')
    require(v['verified'] == 1 and v['padding_mode'] == stage and v['target_objects'] == [8], 'Changed verification scope')
    require(v['padding_protocol_sha256'] == PROTOCOL_SHA and sha(HERE/'PROTOCOL.json') == PROTOCOL_SHA, 'Changed protocol')
    protocol = load(HERE/'PROTOCOL.json')
    require(sha(HERE/'frame_schedule.json') == protocol['frame_schedule_sha256'], 'Changed schedule')
    scheduled = load(HERE/'frame_schedule.json')['frames']
    wanted = {(f['scene_id'], f['image_id'], f['rgb']) for f in scheduled
              if stage == 'development' or f['pilot' if stage == 'pilot' else 'timing']}
    require(len(v['frames']) == len(wanted) and
            {(f['scene_id'], f['image_id'], f['rgb']) for f in v['frames']} == wanted, 'Stage schedule mismatch')
    manifest = load(run/'build_manifest.json')
    require(manifest['executable_sha256'] == e['executable_sha256'], 'Build/execution executable mismatch')
    return e, v


def raw(path, frame, variant, meta, pin=None):
    if pin is not None:
        require(sha(path) == pin.lower(), 'Changed original raw')
    compressed = Path(path).read_bytes()
    contents = gzip.decompress(compressed)
    rows = list(csv.DictReader(io.StringIO(contents.decode('utf-8'))))
    manifest = load(str(path).replace('_raw.csv.gz', '_raw_manifest.json'))
    require(manifest['raw_candidate_count'] == len(rows) and manifest['compressed_bytes'] == len(compressed) and
            manifest['uncompressed_bytes'] == len(contents) and manifest['variant'] == variant and
            (manifest['scene_id'], manifest['image_id']) == (frame['scene_id'], frame['image_id']), 'Raw manifest mismatch')
    out = []
    for rank, row in enumerate(rows):
        require((int(row['scene']), int(row['image']), row['variant'], int(row['rank'])) ==
                (frame['scene_id'], frame['image_id'], variant, rank), 'Raw frame/variant/rank mismatch')
        d = detection(row)
        m = meta[(d[0], d[1])]
        sx, sy, w, h = m['warped_mask_bbox']
        require(d[5] == (d[2]-64+sx-m['tl_x'], d[3]-64+sy-m['tl_y'], w, h), 'Box/source-origin mismatch')
        require(int(row['training_image']) == m['training_image_id'] and f32(row['angle']) == f32(m['angle']) and
                f32(row['scale']) == f32(m['scale']), 'Metadata mismatch')
        out.append(d)
    require(out == sorted(out, key=order), 'Unsorted raw candidates')
    return out


def audit_geometry(run):
    rows = table(run/'geometry.csv')
    require(len(rows) == 6912, 'Geometry count')
    keys = {(r['class_id'], int(r['template_id']), int(r['level'])) for r in rows}
    require(len(keys) == 6912, 'Duplicate geometry layer')
    old_declared = old_actual = new_actual = 0
    by_level = Counter()
    for row in rows:
        r = {k: int(v) for k, v in row.items() if k != 'class_id'}
        level = r['level']
        require(level in (0, 1) and r['T'] == (4, 8)[level], 'Geometry T/layer')
        require((r['old_width'], r['old_height'], r['new_width'], r['new_height']) ==
                (848 >> level, 672 >> level, 848 >> level, 800 >> level), 'Geometry dimensions')
        flags = []
        for width, height, complete in [(r['old_width'], r['old_height'], False),
                                         (r['old_width'], r['old_height'], True),
                                         (r['new_width'], r['new_height'], True)]:
            if level == 0:
                flag = width >= r['width']+64 and height >= r['height']+64
            else:
                flag = width >= max(r['width'], r['max_x']+1 if complete else 0) and height >= max(r['height'], r['max_y']+1 if complete else 0)
            flags.append(int(flag))
        require(flags == [r['old_declared_fit'], r['old_complete_fit'], r['new_complete_fit']], 'Geometry derived fit mismatch')
        old_declared += not flags[0]
        old_actual += not flags[1]
        new_actual += not flags[2]
        by_level[level] += not flags[1]
    require((old_declared, old_actual, new_actual) == (630, 634, 0), 'Geometry fixed counts changed')
    return dict(layers=6912, baseline_declared_infeasible=old_declared,
                baseline_complete_infeasible=old_actual, auto_complete_infeasible=new_actual,
                baseline_infeasible_by_level=dict(by_level))


def quality(run, stage):
    e, v = provenance(run, stage)
    summary = load(run/'comparison_metrics.json')
    frames = v['frames']
    require(len(frames) == (8 if stage == 'pilot' else 400), 'Frame count')
    require(summary['frames'] == len(frames) and summary['matcher_calls'] == len(frames)*(4 if stage == 'pilot' else 2), 'Calls/frame summary')
    pins = {str(Path(r['path']).resolve()): r['sha256'] for r in v['input_sha256']}
    root = Path(v['dataset_root'])
    training = Path(v['training_directory'])
    for path in (root/'index.json', training/'template_metadata.json'):
        require(sha(path) == pins[str(path.resolve())].lower(), 'Numeric source changed')
    index = load(root/'index.json')
    gt_by_frame = {(f['scene_id'], f['image_id']): [g for g in f['instances'] if g['obj_id'] == 8]
                   for f in index['test'] if f['split'] == 'development'}
    meta = {(m['class_id'], m['template_id']): m for m in load(training/'template_metadata.json')['templates']}
    require(len(meta) == 3456, 'Metadata bank size')
    per_rows = table(run/'per_frame_metrics.csv')
    per = {(int(r['scene']), int(r['image']), r['arm']): r for r in per_rows}
    require(len(per_rows) == len(per) == len(frames)*2, 'Per-frame rows/duplicates')
    selected_rows = defaultdict(list)
    for row in table(run/'selected_detections.csv'):
        selected_rows[(int(row['scene']), int(row['image']), row['arm'])].append(row)
    retention_csv = table(run/'gt_retention.csv')
    retention_rows = {(int(r['scene']), int(r['image']), int(r['gt_id'])): r for r in retention_csv}
    require(len(retention_rows) == len(retention_csv), 'Duplicate GT retention row')
    equality_csv = table(run/'candidate_equality.csv')
    equal_rows = {(int(r['scene']), int(r['image']), r['arm']): r for r in equality_csv}
    require(len(equality_csv) == len(equal_rows) == len(frames)*(2 if stage == 'pilot' else 1), 'Equality row count')
    frame_keys = {(f['scene_id'], f['image_id']) for f in frames}
    require(all(k[:2] in frame_keys and k[2] in ('baseline', 'auto') for k in selected_rows), 'Unexpected selected frame/arm')
    groups = defaultdict(lambda: dict(allGT=Counter(), visibility_ge_0_5=Counter(), other=Counter()))
    unchanged_raw_frames = 0
    all_baseline_tp = []
    for f in frames:
        key = (f['scene_id'], f['image_id'])
        gt = gt_by_frame[key]
        stem = 's%d_i%d' % key
        old = raw(Path(f['fallback_raw']), f, 'fallback', meta, f['archives']['fallback']['sha256'])
        old_fused = raw(Path(f['fused_raw']), f, 'fused', meta, f['archives']['fused']['sha256'])
        new = raw(run/'auto'/(stem+'_fallback_raw.csv.gz'), f, 'fallback', meta)
        new_fused = raw(run/'auto'/(stem+'_fused_raw.csv.gz'), f, 'fused', meta)
        require(old == old_fused and new == new_fused, 'Fallback/fused field or score-bit mismatch')
        require(len(old) == f['raw_count'], 'Verified old raw count')
        unchanged_raw_frames += old == new
        for arm in (['baseline', 'auto'] if stage == 'pilot' else ['auto']):
            eq = equal_rows[key+(arm,)]
            expected_raw = old if arm == 'baseline' else new
            require(int(eq['fallback_count']) == len(expected_raw) == int(eq['fused_count']) and
                    eq['exact_fields_and_float32_bits'] == '1', 'Equality CSV mismatch')
            require(eq['old_baseline_cache_equal'] == ('1' if arm == 'baseline' else '-1'), 'Cache equality flag mismatch')
            if arm == 'baseline':
                require(raw(run/'baseline_fresh'/(stem+'_fallback_raw.csv.gz'), f, 'fallback', meta) == old and
                        raw(run/'baseline_fresh'/(stem+'_fused_raw.csv.gz'), f, 'fused', meta) == old_fused, 'Fresh baseline differs')
        kept = {'baseline': nms(old), 'auto': nms(new)}
        assigned = {arm: evaluate(rows, gt, False) for arm, rows in kept.items()}
        baseline_gt = {identity for label, identity in assigned['baseline'][1] if label == 'TP'}
        auto_gt = {identity for label, identity in assigned['auto'][1] if label == 'TP'}
        baseline_tp = {d for d, (label, _) in zip(kept['baseline'], assigned['baseline'][1]) if label == 'TP'}
        all_baseline_tp.extend((key, d) for d in baseline_tp)
        for g in gt:
            row = retention_rows[key+(g['gt_id'],)]
            require(int(row['baseline_detected']) == int(g['gt_id'] in baseline_gt) and
                    int(row['auto_detected']) == int(g['gt_id'] in auto_gt), 'GT retention CSV mismatch')
        for arm in ('baseline', 'auto'):
            all_counts, labels = assigned[arm]
            eligible_counts, eligible_labels = evaluate(kept[arm], gt, True)
            raw_count = len(old if arm == 'baseline' else new)
            this_gt = baseline_gt if arm == 'baseline' else auto_gt
            identity_retained = sum(label == 'TP' and d in baseline_tp for d, (label, _) in zip(kept[arm], labels))
            other = dict(raw_candidates=raw_count, negative_frames=int(not gt),
                         negative_frames_with_fp=int(not gt and all_counts['fp'] > 0),
                         negative_fp=all_counts['fp'] if not gt else 0,
                         baseline_gt_retained=len(this_gt & baseline_gt),
                         baseline_tp_detection_retained=identity_retained,
                         new_gt=len(this_gt-baseline_gt), lost_baseline_gt=len(baseline_gt-this_gt))
            row = per[key+(arm,)]
            frame_expected = {k: all_counts[k] for k in ('tp', 'fp', 'fn', 'gt')}
            frame_expected.update({('ignored' if k == 'ignored' else 'eligible_'+k): eligible_counts[k] for k in ('tp', 'fp', 'fn', 'gt', 'ignored')})
            frame_expected.update({k: value for k, value in other.items() if k not in ('raw_candidates', 'negative_frames', 'negative_frames_with_fp')})
            frame_expected['raw'] = raw_count
            check_numeric({k: int(value) for k, value in row.items() if k not in ('scene', 'image', 'arm')}, frame_expected, 'Frame '+str(key)+arm)
            reported = selected_rows[key+(arm,)]
            require([detection(r) for r in reported] == kept[arm], 'Selected identities/order')
            for rank, r in enumerate(reported):
                require(int(r['rank']) == rank and (r['allGT_label'], int(r['allGT_id'])) == labels[rank] and
                        (r['eligible_label'], int(r['eligibleGT_id'])) == eligible_labels[rank], 'Selected GT labels')
            for group in ((None, arm), (key[0], arm)):
                for name, counts in [('allGT', all_counts), ('visibility_ge_0_5', eligible_counts), ('other', other)]:
                    for field, value in counts.items():
                        groups[group][name][field] += value
    require(len(retention_rows) == sum(len(gt_by_frame[(f['scene_id'], f['image_id'])]) for f in frames), 'Retention row coverage')
    scene_summaries = {s['scene_id']: s for s in summary['per_scene']}
    result_scenes = []
    result = {}
    for (scene, arm), values in groups.items():
        target = summary[arm] if scene is None else scene_summaries[scene][arm]
        computed = {name: finish(values[name]) for name in ('allGT', 'visibility_ge_0_5')}
        for name in computed:
            check_numeric(target[name], computed[name], '%s/%s/%s' % (scene, arm, name))
        check_numeric(target, values['other'], '%s/%s retention' % (scene, arm))
        computed.update(values['other'])
        if scene is None:
            result[arm] = computed
        else:
            result_scenes.append(dict(scene_id=scene, arm=arm, **computed))
    geometry = audit_geometry(run)
    preparation = load(run/'input_preparation_diagnostics.json')
    close(preparation['bank_load_ms'], summary['bank_load_ms'], 'Bank-load diagnostics')
    require(summary['decoded_frames'] == len(frames) and summary['decode_and_bank_load_excluded_from_external_call'] == 1 and
            0 < summary['peak_rss_bytes'] <= 1610612736, 'Quality diagnostic/budget assertions')
    return dict(stage=stage, frames=len(frames), matcher_calls=summary['matcher_calls'],
                source_outputs_rehashed=len(e['output_sha256']), baseline_auto_all_raw_fields_exact_frames=unchanged_raw_frames,
                input_provenance_sha256=sha(run/'verified_inputs.json'), execution_provenance_sha256=sha(run/'execution_provenance.json'),
                build_manifest_sha256=e['build_manifest_sha256'], metrics_sha256=sha(run/'comparison_metrics.json'),
                geometry=geometry, baseline=result['baseline'], auto=result['auto'], per_scene=result_scenes,
                bank_load_ms=summary['bank_load_ms'], decode_total_ms=summary['decode_total_ms'],
                peak_rss_bytes=summary['peak_rss_bytes'], all_independently_reconstructed_metrics_match=True)


def nearest(values, fraction):
    return sorted(values)[math.ceil(len(values)*fraction)-1]


def audit_timing(run, quality_run):
    e, v = provenance(run, 'timing')
    summary = load(run/'timing_metrics.json')
    q = load(quality_run/'execution_provenance.json')
    require(q['build_manifest_sha256'] == e['build_manifest_sha256'] and q['executable_sha256'] == e['executable_sha256'], 'Timing/quality build mismatch')
    rows = table(run/'timing_samples.csv')
    frames = {(f['scene_id'], f['image_id']) for f in v['frames']}
    require(len(frames) == 64 and len(rows) == 2048, 'Timing frame/sample count')
    reference_counts = {}
    for frame in v['frames']:
        key = (frame['scene_id'], frame['image_id'])
        stem = 's%d_i%d' % key
        arm_rows = {}
        for arm in ('baseline', 'auto'):
            for path in ('fallback', 'fused'):
                raw_path = Path(frame[path+'_raw']) if arm == 'baseline' else quality_run/'auto'/(stem+'_'+path+'_raw.csv.gz')
                if arm == 'baseline':
                    require(sha(raw_path) == frame['archives'][path]['sha256'], 'Changed timed baseline reference')
                ref = [detection(r) for r in csv.DictReader(io.StringIO(gzip.decompress(raw_path.read_bytes()).decode()))]
                arm_rows[(arm, path)] = ref
                reference_counts[key+(arm, path)] = (len(ref), len(nms(ref)))
        require(arm_rows[('baseline', 'fallback')] == arm_rows[('baseline', 'fused')] and
                arm_rows[('auto', 'fallback')] == arm_rows[('auto', 'fused')], 'Timing own-reference path mismatch')
    slots = set()
    samples = defaultdict(list)
    paired = defaultdict(dict)
    for row in rows:
        key = (int(row['scene']), int(row['image']))
        round_id, place = int(row['round']), int(row['order'])
        require(key in frames and 0 <= round_id < 8 and 0 <= place < 4, 'Unexpected timing slot')
        slot = key+(round_id, place)
        require(slot not in slots, 'Duplicate timing slot')
        slots.add(slot)
        variant = (place+round_id) % 4
        arm, path = ('auto' if variant >= 2 else 'baseline'), ('fused' if variant % 2 else 'fallback')
        require((row['arm'], row['path'], int(row['warmup'])) == (arm, path, int(round_id == 0)), 'Order/warmup schedule changed')
        require((int(row['raw']), int(row['selected'])) == reference_counts[key+(arm, path)], 'Timed counts differ from own arm/path reference')
        match, total = float(row['match_ms']), float(row['external_call_ms'])
        require(math.isfinite(match) and match > 0 and math.isfinite(total) and total >= match, 'Invalid clock interval')
        if round_id:
            samples[(arm, path)].append((match, total))
            paired[key+(round_id, path)][arm] = (match, total)
    variants = []
    require(len(summary['variants']) == 4 and len({(v['arm'], v['path']) for v in summary['variants']}) == 4, 'Duplicate/missing timing variant')
    for item in summary['variants']:
        key = (item['arm'], item['path'])
        times = samples[key]
        require(len(times) == 448, 'Measured samples per variant')
        computed = dict(measured_samples=len(times), match_median_ms=nearest([t[0] for t in times], .5),
                        match_p95_ms=nearest([t[0] for t in times], .95),
                        external_call_median_ms=nearest([t[1] for t in times], .5),
                        external_call_p95_ms=nearest([t[1] for t in times], .95))
        check_numeric(item, computed, 'Timing variant '+str(key))
        variants.append(dict(arm=key[0], path=key[1], **computed))
    ratios = []
    require(len(summary['paired_ratios_auto_over_baseline']) == 2 and
            {p['path'] for p in summary['paired_ratios_auto_over_baseline']} == {'fallback', 'fused'}, 'Duplicate/missing ratio path')
    for item in summary['paired_ratios_auto_over_baseline']:
        match_ratios, total_ratios = [], []
        for key, values in paired.items():
            if key[-1] == item['path']:
                require(set(values) == {'auto', 'baseline'}, 'Unpaired timing sample')
                match_ratios.append(values['auto'][0]/values['baseline'][0])
                total_ratios.append(values['auto'][1]/values['baseline'][1])
        computed = dict(samples=len(match_ratios), match_median=nearest(match_ratios, .5),
                        match_p95=nearest(match_ratios, .95), external_call_median=nearest(total_ratios, .5),
                        external_call_p95=nearest(total_ratios, .95))
        check_numeric(item, computed, 'Paired timing '+item['path'])
        ratios.append(dict(path=item['path'], **computed))
    require(summary['matcher_calls'] == 2048 and summary['frames'] == 64 and summary['decoded_frames'] == 64 and
            summary['all_timed_candidates_exact_to_own_reference'] == 1 and summary['decode_and_bank_load_excluded_from_external_call'] == 1, 'Timing completeness assertions')
    require(Counter(k[0] for k in frames) == Counter({scene: 8 for scene in (1, 4, 6, 7, 8, 10, 12, 13)}), 'Timing scene balance')
    close(load(run/'input_preparation_diagnostics.json')['bank_load_ms'], summary['bank_load_ms'], 'Timing bank-load diagnostics')
    require(0 < summary['peak_rss_bytes'] <= 1610612736, 'Timing RSS budget')
    return dict(frames=64, calls=2048, measured_samples_per_variant=448,
                variants=variants, paired_ratios_auto_over_baseline=ratios,
                source_outputs_rehashed=len(e['output_sha256']), all_timing_summaries_reconstructed=True,
                input_provenance_sha256=sha(run/'verified_inputs.json'), execution_provenance_sha256=sha(run/'execution_provenance.json'),
                build_manifest_sha256=e['build_manifest_sha256'], metrics_sha256=sha(run/'timing_metrics.json'),
                timed_counts_checked_to_own_reference=2048,
                native_each_call_full_candidate_equality_asserted=2048,
                independent_per_timed_call_full_candidate_content_reconstruction=False,
                bank_load_ms=summary['bank_load_ms'], decode_total_ms=summary['decode_total_ms'], peak_rss_bytes=summary['peak_rss_bytes'])


def selftest():
    def d(x, score_value=90, identity=0):
        return ('tless_object_8', identity, x+64, 64, f32(score_value), (x, 0.0, 10.0, 10.0))
    gt = [dict(gt_id=3, bbox_obj=[0, 0, 10, 10], visib_fract=1), dict(gt_id=4, bbox_obj=[20, 0, 10, 10], visib_fract=.4)]
    detections = [d(0), d(20, 89, 1), d(40, 88, 2)]
    a, _ = evaluate(detections, gt, False)
    b, labels = evaluate(detections, gt, True)
    require((a['tp'], a['fp'], a['fn'], a['gt']) == (2, 1, 0, 2), 'All-GT literal oracle')
    require((b['tp'], b['fp'], b['fn'], b['gt'], b['ignored']) == (1, 1, 0, 1, 1) and labels[1] == ('IGNORE', 4), 'Eligible literal oracle')
    require(nms([d(0, 89, 1), d(0, 90, 0), d(20, 88, 2)]) == [d(0, 90, 0), d(20, 88, 2)], 'NMS literal oracle')
    close(iou([0, 0, 10, 10], [5, 0, 10, 10]), 1/3, 'IoU oracle')
    require(nearest([4, 1, 3, 2], .5) == 2 and nearest([4, 1, 3, 2], .95) == 4, 'Nearest rank oracle')
    rejected = []
    for bad in [{'tp': 3}, {'tp': 2, 'fp': 0}]:
        try:
            check_numeric(bad, {'tp': 2, 'fp': 1}, 'synthetic mutation')
        except ValueError:
            rejected.append(bad)
        else:
            raise AssertionError('Numeric corruption accepted')
    return dict(passed=True, literal_oracles=5, numeric_corruptions_rejected=len(rejected), dataset_image_reads=0, image_decodes=0, matcher_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', type=Path)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--timing', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Output must be new')
    if args.self_test:
        result = selftest()
    else:
        require(args.pilot and args.development and args.timing, 'Need all three stages')
        result = dict(passed=True, auditor_sha256=sha(Path(__file__)), protocol_sha256=PROTOCOL_SHA,
                      pilot=quality(args.pilot, 'pilot'), development=quality(args.development, 'development'),
                      timing=audit_timing(args.timing, args.development),
                      dataset_image_reads=0, image_decodes=0, matcher_calls=0,
                      heldout_images_read=0, reserved_objects_matched=[],
                      limitations='Numeric reconstruction audits retained outputs and clock samples. It cannot independently prove native timed calls, physical SIMD tail-read safety, or industrial accuracy.')
        result['distinct_files_hashed'] = len(HASHED)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('passed', 'image_decodes', 'matcher_calls')}))


if __name__ == '__main__':
    main()
