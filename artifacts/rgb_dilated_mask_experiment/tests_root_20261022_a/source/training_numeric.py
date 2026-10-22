"""Independent numeric and serialized-bank audit of RGB/empty-mask training.

Does not import the evaluator, training runner or their helpers. Never opens an
image. Checks serialized records and provenance, not extraction correctness or
the intermediate features of unsuccessful extractions.
"""
import argparse
import csv
import hashlib
import itertools
import gzip

from bank_reader import parse_bank, geometry
import json
from pathlib import Path

OBJECTS = [1, 2, 5, 8, 12, 17]
GEOMETRY = ['source_crop_x', 'source_crop_y', 'source_crop_w', 'source_crop_h',
            'canvas', 'mask_x', 'mask_y', 'mask_w', 'mask_h']


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_private_numeric(relative, data, expected):
    observed = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    require(relative in expected and expected[relative] == observed,
            'Private numeric input differs from frozen closure: '+relative)


def key(row):
    return int(row['training_image']), int(row['angle']), float(row['scale'])


def inspect_object(obj, rows, old_rows, metadata, expected):
    cls = 'tless_object_' + str(obj)
    old = {key(row): row for row in old_rows}
    require(len(old) == len(old_rows) and set(old) == expected, 'Original pose coverage changed')
    require(len(rows) == len(expected) and {key(row) for row in rows} == expected,
            'Missing or duplicate new poses')
    successful = insufficient = exceptions = 0
    for row in rows:
        pose = key(row)
        require(row['class_id'] == cls and old[pose]['class_id'] == cls, 'Wrong object class')
        require([int(row[f]) for f in GEOMETRY] == [int(old[pose][f]) for f in GEOMETRY],
                'Changed official pose geometry')
        success, template_id = int(row['success']), int(row['template_id'])
        require(success in (0, 1), 'Invalid success flag')
        n0, n1 = int(row['features_l0']), int(row['features_l1'])
        if success:
            require(template_id == successful and row['error'] == '' and
                    n0 >= 1 and n1 >= 1, 'Invalid successful template')
            require(successful < len(metadata), 'Missing successful metadata')
            m = metadata[successful]
            require(m['class_id'] == cls and m['template_id'] == successful and
                    (m['training_image_id'], m['angle'], m['scale']) == pose and
                    m['tl_x'] == int(row['templ_tl_x']) and m['tl_y'] == int(row['templ_tl_y']) and
                    m['warped_mask_bbox'] == [int(row[f]) for f in ['mask_x', 'mask_y', 'mask_w', 'mask_h']],
                    'Template metadata pose/origin/box differs')
            successful += 1
        else:
            require(template_id == -1 and n0 == n1 == 0 and
                    int(row['templ_tl_x']) == int(row['templ_tl_y']) == 0,
                    'Unexpected failed-attempt serialized placeholders')
            require(row['error'] in ('insufficient_features', 'opencv_exception'),
                    'Missing or unknown failed-attempt reason')
            insufficient += row['error'] == 'insufficient_features'
            exceptions += row['error'] == 'opencv_exception'
    require(len(metadata) == successful, 'Extra successful metadata')
    return dict(object_id=obj, attempts=len(rows), successful_templates=successful,
                insufficient_features=insufficient, opencv_exception_attempts=exceptions)


def audit_bank(directory, obj, attempts, diagnostics, read):
    """Compare serialized integer features with all successful layer records."""
    successful = [row for row in attempts if int(row['success']) == 1]
    require(len(diagnostics) == 2*len(successful), 'Missing/extra feature diagnostics')
    path = directory/('templates_tless_object_'+str(obj)+'.yml.gz')
    if not successful:
        require(not path.exists(), 'Unexpected bank for zero successful templates')
        return dict(serialized_templates_checked=0, serialized_layers_checked=0)
    bank = parse_bank(gzip.decompress(read(path)).decode('utf-8'), 'tless_object_'+str(obj))
    require(len(bank) == len(successful), 'Serialized bank count differs')
    counts, minimum = [], None
    for row, layers in zip(successful, bank):
        template_id = int(row['template_id'])
        for level, layer in enumerate(layers):
            observed = geometry(layer, int(row['canvas']))
            expected = dict(class_id='tless_object_'+str(obj), training_image=int(row['training_image']),
                            angle=int(row['angle']), scale=float(row['scale']), template_id=template_id,
                            **observed)
            actual = diagnostics[2*template_id+level]
            require(set(actual) == set(expected), 'Feature CSV schema differs')
            for field, value in expected.items():
                parsed = actual[field] if field == 'class_id' else (
                    float(actual[field]) if field == 'scale' else int(actual[field]))
                require(parsed == value, 'Feature CSV differs from serialized bank: '+field)
            require(observed['actual_features'] == int(row['features_l'+str(level)]),
                    'Attempt and bank feature counts differ')
            if level == 0:
                require(layer['tl_x'] == int(row['templ_tl_x']) and layer['tl_y'] == int(row['templ_tl_y']),
                        'Attempt and bank origin differ')
            counts.append(observed['actual_features'])
            distance = observed['min_canvas_edge_distance']
            minimum = distance if minimum is None else min(minimum, distance)
    return dict(serialized_templates_checked=len(bank), serialized_layers_checked=2*len(bank),
                actual_feature_count_range=[min(counts), max(counts)], minimum_canvas_edge_distance=minimum)


