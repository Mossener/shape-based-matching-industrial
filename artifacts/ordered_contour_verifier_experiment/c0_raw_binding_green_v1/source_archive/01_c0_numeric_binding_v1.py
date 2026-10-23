"""Narrow, filesystem-free C0 numeric projection binding.

The pure projection entry point does not open files or import an evaluator.
Its eventual reader is restricted to C0 raw/manifest/own-metadata pins and the
three inherited projection CSV files. A projected GT is not an independent
reconstruction from official annotations.
"""
import math
import re
import struct

ARMS = ('rgb_control', 'rgb_pooled_features', 'rgb_stratified_features')
GT_HEADER = ('object_id,scene,image,gt_id,class_id,visibility,bbox_x,bbox_y,bbox_w,bbox_h').split(',')
PER_HEADER = ('object_id,scene,image,arm,raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,'
              'eligible_gt,ignored,all_iou_sum,eligible_iou_sum,negative_fp').split(',')
SELECTED_HEADER = ('object_id,scene,image,arm,rank,class_id,score,score_bits,template_id,training_image,'
                   'angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,'
                   'eligible_label,eligible_id').split(',')


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, minimum=None, maximum=None):
    _need(type(value) in (str, int), 'Canonical integer required')
    _need(re.fullmatch(r'(?:0|-?[1-9][0-9]*)', str(value)) is not None, 'Canonical integer required')
    result = int(value)
    _need((minimum is None or result >= minimum) and (maximum is None or result <= maximum),
          'Integer outside bounds')
    return result


def _number(value, positive=False):
    _need(type(value) in (str, int, float), 'Number required')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('Number required') from error
    _need(math.isfinite(result) and (not positive or result > 0), 'Nonfinite/nonpositive number')
    return result


def _bits(value):
    try:
        return struct.unpack('<I', struct.pack('<f', _number(value)))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError('Finite float32 value required') from error


def _score(bits):
    result = struct.unpack('<f', struct.pack('<I', bits))[0]
    _need(math.isfinite(result), 'Finite float32 score required')
    return result


def _schema(row, header):
    _need(type(row) is dict and set(row) == set(header), 'Exact projection schema required')


def _box(row):
    result = tuple(_number(row['bbox_' + axis]) for axis in ('x','y','w','h'))
    _need(result[2] > 0 and result[3] > 0, 'Positive box extents required')
    return result


def _candidate(row):
    bits = _integer(row['score_bits'], 0, 2**32 - 1)
    _need(_number(row['score']) == _score(bits) and 85 <= _score(bits) <= 100,
          'Score/float32 bits differ or outside fixed threshold')
    _number(row['scale'], True)
    return (row['class_id'], _integer(row['template_id'], 0), _integer(row['match_x']),
            _integer(row['match_y']), bits, _box(row),
            (_integer(row['training_image'], 0), _bits(row['angle']), _bits(row['scale'])))


def bind_projection(objects, frames, gt_rows, per_rows, selected_rows):
    """Bind exact tables to every object/frame, including zero/negative rows.

    Inputs are dictionaries from CSV parsing, with exact documented headers.
    Every known arm must have one per-frame row for every object/frame; GT is
    shared. Unknown identities/arms, malformed values, incomplete coverage,
    duplicate identities/ranks, or inconsistent labels/counts raise ValueError.
    Returned mappings contain only rgb_control and preserve full candidates,
    score float32 bits, pose bits, boxes, assignment labels and GT identities.

    This verifies the projection's structure, identity and count conservation.
    The separate raw replay recomputes NMS and numeric GT assignment, including
    exact selected rows, labels and IoU sums. Projection GT remains inherited.
    """
    _need(type(objects) in (tuple, list) and len(objects) > 0, 'Nonempty object schedule required')
    _need(all(type(obj) is int and obj > 0 for obj in objects) and len(set(objects)) == len(objects),
          'Distinct integer objects required')
    _need(type(frames) in (tuple, list) and len(frames) > 0, 'Nonempty frame schedule required')
    _need(all(type(frame) in (tuple,list) and len(frame) == 2 and
              all(type(value) is int for value in frame) and frame[0] > 0 and frame[1] >= 0
              for frame in frames), 'Integer frame pairs required')
    frames = tuple(tuple(frame) for frame in frames)
    _need(len(set(frames)) == len(frames), 'Distinct frames required')
    _need(all(type(rows) in (tuple,list) for rows in (gt_rows,per_rows,selected_rows)), 'Table rows required')
    expected = {(obj,*frame) for obj in objects for frame in frames}
    full = {(*key,arm) for key in expected for arm in ARMS}
    truth = {key: [] for key in expected}
    identities, physical_gt = set(), set()

    def identity(row, with_arm=False):
        key = tuple(_integer(row[name], 0) for name in ('object_id','scene','image'))
        _need(key in expected, 'Unknown object/frame identity')
        if with_arm:
            _need(row['arm'] in ARMS, 'Unknown projection arm')
            return (*key,row['arm'])
        return key

    for row in gt_rows:
        _schema(row, GT_HEADER)
        key = identity(row)
        gid = _integer(row['gt_id'], 0)
        _need((*key,gid) not in identities and (*key[1:],gid) not in physical_gt, 'Duplicate GT identity')
        identities.add((*key,gid)); physical_gt.add((*key[1:],gid))
        _need(row['class_id'] == f'tless_object_{key[0]}', 'GT class/object differs')
        visibility = _number(row['visibility'])
        _need(0 <= visibility <= 1, 'Visibility outside [0,1]')
        truth[key].append(dict(gt_id=gid, class_id=row['class_id'], obj_id=key[0],
                               bbox_obj=_box(row), visib_fract=visibility))
    for records in truth.values():
        records.sort(key=lambda record: record['gt_id'])

    per = {}
    for row in per_rows:
        _schema(row, PER_HEADER)
        key = identity(row, True)
        _need(key not in per, 'Duplicate per-frame identity')
        per[key] = {name: (_number(row[name]) if name.endswith('_iou_sum') else _integer(row[name],0))
                    for name in PER_HEADER[4:]}
    _need(set(per) == full, 'Incomplete per-frame coverage including zero combinations')
    selected = {key: [] for key in full}
    all_labels = {key: [] for key in full}
    eligible_labels = {key: [] for key in full}
    for row in selected_rows:
        _schema(row, SELECTED_HEADER)
        key = identity(row, True)
        _need(_integer(row['rank'],0) == len(selected[key]), 'Selected ranks duplicate, gapped or reordered')
        _need(row['class_id'] == f'tless_object_{key[0]}', 'Selected class/object differs')
        selected[key].append(_candidate(row))
        by_id = {record['gt_id']:record for record in truth[key[:3]]}
        for prefix, target in (('allGT',all_labels),('eligible',eligible_labels)):
            label, gid = row[prefix+'_label'], _integer(row[prefix+'_id'], -1)
            allowed = ('TP','FP') if prefix == 'allGT' else ('TP','FP','IGNORE')
            _need(label in allowed, 'Unknown assignment label')
            _need((label == 'FP' and gid == -1) or (label != 'FP' and gid in by_id),
                  'Assignment GT identity differs')
            if prefix == 'eligible' and label != 'FP':
                _need((by_id[gid]['visib_fract'] >= .5) == (label == 'TP'),
                      'Eligible/ignored visibility differs')
            _need(label == 'FP' or all(old_gid != gid for _,old_gid in target[key]),
                  'GT assigned more than once')
            target[key].append((label,gid))

    for key in full:
        counts, records = per[key], truth[key[:3]]
        labels, eligible = all_labels[key], eligible_labels[key]
        tp = sum(label == 'TP' for label,_ in labels)
        etp = sum(label == 'TP' for label,_ in eligible)
        ignored = sum(label == 'IGNORE' for label,_ in eligible)
        gt, egt = len(records), sum(record['visib_fract'] >= .5 for record in records)
        _need(counts['raw'] >= counts['selected'] == len(selected[key]), 'Raw/selected count differs')
        expected_counts = dict(tp=tp, fp=len(labels)-tp, fn=gt-tp, gt=gt,
            eligible_tp=etp, eligible_fp=len(eligible)-etp-ignored, eligible_fn=egt-etp,
            eligible_gt=egt, ignored=ignored, negative_fp=len(labels)-tp if not records else 0)
        _need(all(counts[name] == value for name,value in expected_counts.items()),
              'Projection label/count conservation differs')
        _need(.5*tp <= counts['all_iou_sum'] <= tp and
              .5*etp <= counts['eligible_iou_sum'] <= etp, 'Projected IoU sum outside assignment bounds')

    def control(mapping):
        return {key:mapping[(*key,ARMS[0])] for key in sorted(expected)}

    control_all, control_eligible = control(all_labels), control(eligible_labels)
    return dict(truth={key:truth[key] for key in sorted(expected)}, per=control(per),
                selected=control(selected), all_labels=control_all, eligible_labels=control_eligible,
                retained_gt_ids=tuple(sorted((*key,gid) for key,labels in control_all.items()
                                             for label,gid in labels if label == 'TP')),
                eligible_retained_gt_ids=tuple(sorted((*key,gid) for key,labels in control_eligible.items()
                                                      for label,gid in labels if label == 'TP')),
                gt_projection_independently_reconstructed=False)
