"""Independent strict numeric serialization contracts; no target imports."""
import csv
import gzip
import io
import math
import re
import struct

from numeric import order

RAW_HEADER = 'scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h'.split(',')
SELECTED_HEADER = 'object_id,scene,image,arm,rank,class_id,score,score_bits,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,eligible_label,eligible_id'.split(',')
PER_HEADER = 'object_id,scene,image,arm,raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,eligible_gt,ignored,all_iou_sum,eligible_iou_sum,negative_fp'.split(',')
EQUALITY_HEADER = 'object_id,scene,image,arm,fallback_count,fused_count,exact_order_fields_score_bits,reference_exact,fallback_match_ms,fused_match_ms,fallback_external_ms,fused_external_ms'.split(',')
RETENTION_HEADER = 'object_id,scene,image,metric,gt_id,rgb_detected,binary_detected,same_pose_if_both'.split(',')
GT_HEADER = 'object_id,scene,image,gt_id,class_id,visibility,bbox_x,bbox_y,bbox_w,bbox_h'.split(',')


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def integer(value):
    text = str(value)
    need(re.fullmatch(r'-?(0|[1-9][0-9]*)', text) is not None, 'Noncanonical integer')
    result = int(text)
    need(-2147483648 <= result <= 4294967295, 'Integer outside serialized ranges')
    return result


def number(value):
    result = float(value)
    need(math.isfinite(result), 'Non-finite numeric value')
    return result


def bits(value):
    try:
        result = struct.pack('<f', number(value))
    except (OverflowError, struct.error) as error:
        raise ValueError('Non-binary32 numeric value') from error
    need(math.isfinite(struct.unpack('<f', result)[0]), 'Non-finite binary32')
    return result


def table(encoded, header=None):
    reader = csv.DictReader(io.StringIO(encoded.decode('utf-8-sig'), newline=''))
    if header is not None:
        need(reader.fieldnames == header, 'CSV schema differs')
    rows = []
    for row in reader:
        need(None not in row and None not in row.values(), 'CSV width differs')
        rows.append(row)
    return rows


def candidate(row, obj, metadata):
    cls = 'tless_object_'+str(obj)
    identity = integer(row['template_id'])
    need(row['class_id'] == cls and identity in metadata, 'Raw class/template metadata identity')
    meta = metadata[identity]
    need(meta['class_id'] == cls and meta['template_id'] == identity, 'Metadata key mismatch')
    x, y = integer(row['match_x']), integer(row['match_y'])
    value = number(row['score'])
    need(85 <= value <= 100, 'Raw score outside frozen threshold/range')
    score = bits(value)
    box = tuple(number(row['bbox_'+axis]) for axis in ('x', 'y', 'w', 'h'))
    sx, sy, width, height = meta['warped_mask_bbox']
    need(min(width, height) > 0 and box == (x-64+sx-meta['tl_x'], y-64+sy-meta['tl_y'], width, height),
         'Raw metadata/source-origin box differs')
    pose = (integer(row['training_image']), struct.unpack('<f', bits(row['angle']))[0],
            struct.unpack('<f', bits(row['scale']))[0])
    need(pose == (meta['training_image_id'], struct.unpack('<f', bits(meta['angle']))[0],
                  struct.unpack('<f', bits(meta['scale']))[0]), 'Raw training/pose metadata differs')
    return cls, identity, x, y, score, box, pose


def parse_raw(encoded, manifest, frame, variant, obj, metadata):
    contents = gzip.decompress(encoded)
    rows = table(contents, RAW_HEADER)
    need((manifest['scene_id'], manifest['image_id'], manifest['variant'], manifest['raw_candidate_count'],
          manifest['compressed_bytes'], manifest['uncompressed_bytes']) ==
         (*frame, variant, len(rows), len(encoded), len(contents)), 'Raw manifest identity/size/count differs')
    result = []
    for rank, row in enumerate(rows):
        need((integer(row['scene']), integer(row['image']), row['variant'], integer(row['rank'])) ==
             (*frame, variant, rank), 'Raw frame/path/rank differs')
        result.append(candidate(row, obj, metadata))
    need(result == sorted(result, key=order), 'Raw canonical order differs')
    return result


def exact_stream(left, right):
    need(left == right, 'Full ordered candidate fields/float32 score bits differ')


def check_selected(rows, frame, obj, arm, metadata, kept, labels, eligible_labels):
    need(len(rows) == len(kept) == len(labels) == len(eligible_labels), 'Selected row coverage differs')
    decoded = []
    for rank, row in enumerate(rows):
        need((integer(row['object_id']), integer(row['scene']), integer(row['image']), row['arm'], integer(row['rank'])) ==
             (obj, *frame, arm, rank), 'Selected frame/arm/rank differs')
        item = candidate(row, obj, metadata)
        need(integer(row['score_bits']) == struct.unpack('<I', item[4])[0], 'Selected float32 bits differ')
        need((row['allGT_label'], integer(row['allGT_id'])) == labels[rank] and
             (row['eligible_label'], integer(row['eligible_id'])) == eligible_labels[rank], 'Selected GT label/identity differs')
        decoded.append(item)
    exact_stream(decoded, kept)


def check_retention(rows, expected):
    result = {}
    for row in rows:
        key = (integer(row['object_id']), integer(row['scene']), integer(row['image']), row['metric'], integer(row['gt_id']))
        need(key not in result, 'Duplicate retention identity')
        result[key] = tuple(integer(row[name]) for name in ('rgb_detected', 'binary_detected', 'same_pose_if_both'))
    need(result == expected, 'Retention identity/coverage/pose differs')


def finish(counts):
    result = dict(counts)
    tp, fp, fn, total = (result.get(name, 0) for name in ('tp', 'fp', 'fn', 'gt'))
    result.update(precision=tp/(tp+fp) if tp+fp else 0., recall=tp/total if total else 0.,
                  f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
                  mean_tp_iou=result.get('matched_iou_sum', 0)/tp if tp else 0.)
    return result


def check_numeric(actual, expected, where):
    for field, value in expected.items():
        need(field in actual, where+' missing '+field)
        if isinstance(value, dict):
            check_numeric(actual[field], value, where+'/'+field)
        elif isinstance(value, float):
            need(math.isfinite(float(actual[field])) and math.isclose(actual[field], value, rel_tol=1e-12, abs_tol=1e-12),
                 where+' numeric mismatch '+field)
        else:
            need(actual[field] == value, where+' numeric mismatch '+field)
