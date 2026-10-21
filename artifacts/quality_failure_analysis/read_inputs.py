"""Read numeric development evidence only; no image reader dependencies."""
import csv
import io
import math


RAW_FIELDS = ('scene,image,variant,class_id,rank,score,template_id,training_image,'
              'angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h').split(',')


def development_frames(index):
    result = {}
    for frame in index['test']:
        if frame['split'] != 'development':
            continue
        key = (frame['scene_id'], frame['image_id'])
        if key in result:
            raise ValueError('Duplicate development frame')
        result[key] = frame
    return result


def parse_raw(data, key, object_id):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8')))
    if reader.fieldnames != RAW_FIELDS:
        raise ValueError('Raw schema differs')
    result = []
    for row in reader:
        if (int(row['scene']), int(row['image'])) != key or (
            row['variant'] != 'fallback' or
            row['class_id'] != f'tless_object_{object_id}' or
            int(row['rank']) != len(result)):
            raise ValueError('Raw frame/variant/class/rank differs')
        score = float(row['score'])
        box = tuple(float(row['bbox_'+v]) for v in ('x', 'y', 'w', 'h'))
        if not math.isfinite(score) or score < 85 or not all(map(math.isfinite, box)):
            raise ValueError('Invalid raw score/box')
        result.append(dict(box=box, score=score, template_id=int(row['template_id'])))
    return result
