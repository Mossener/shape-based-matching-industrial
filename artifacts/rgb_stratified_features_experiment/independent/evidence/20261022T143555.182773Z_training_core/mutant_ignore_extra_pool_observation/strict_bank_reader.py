"""Strict reader for this experiment's integer OpenCV class-bank YAML subset.

This is not a general YAML parser. Unknown syntax is rejected. Parsing does
not import OpenCV, native code, the trainer or the feature-diagnostic writer.
"""
import re


def need(value, message):
    if not value:
        raise ValueError(message)


def parse_bank(text, expected_class):
    lines = text.splitlines()
    need(lines[:2] == ['%YAML:1.0', '---'], 'Unexpected OpenCV YAML header')
    need(len(lines) >= 5 and lines[2] == 'class_id: '+expected_class and
         lines[3] == 'pyramid_levels: 2' and lines[4] == 'template_pyramids:', 'Wrong bank class/header')
    templates, cursor = [], 5
    fields = ('width', 'height', 'tl_x', 'tl_y', 'pyramid_level')

    def exact(value):
        nonlocal cursor
        need(cursor < len(lines) and lines[cursor] == value, 'Missing/wrong bank syntax: '+value)
        cursor += 1

    def integer(text):
        need(re.fullmatch(r'-?(0|[1-9][0-9]*)', text), 'Canonical integer required')
        value = int(text)
        need(-(1 << 31) <= value < (1 << 31), 'Serialized int outside signed 32 bits')
        return value

    while cursor < len(lines):
        exact('   -')
        exact('      template_id: '+str(len(templates)))
        exact('      templates:')
        layers = []
        for level in (0, 1):
            exact('         -')
            current = {}
            for name in fields:
                prefix = '            '+name+': '
                need(cursor < len(lines) and lines[cursor].startswith(prefix), 'Missing/out-of-order '+name)
                current[name] = integer(lines[cursor][len(prefix):])
                cursor += 1
            exact('            features:')
            current['features'] = []
            while cursor < len(lines) and lines[cursor].startswith('               - [ '):
                match = re.fullmatch(r'               - \[ (-?\d+), (-?\d+), (-?\d+) \]', lines[cursor])
                need(match, 'Unknown feature syntax')
                feature = tuple(integer(value) for value in match.groups())
                need(0 <= feature[2] <= 7, 'Invalid orientation label')
                current['features'].append(feature)
                cursor += 1
            layers.append(current)
        templates.append(layers)
    need(templates, 'No successful templates in bank')
    for layers in templates:
        need(len(layers) == 2, 'Wrong layer count')
        for level, layer in enumerate(layers):
            need(set(layer) == set(fields) | {'features'} and layer['pyramid_level'] == level and
                 layer['width'] >= 0 and layer['height'] >= 0 and
                 len(layer['features']) >= 1, 'Invalid successful layer')
    return templates


def geometry(layer, canvas):
    # V11 passes an explicit floor-half destination size to cv::pyrDown.
    side = canvas if layer['pyramid_level'] == 0 else canvas//2
    xs, ys = [p[0] for p in layer['features']], [p[1] for p in layer['features']]
    ax, ay = [x+layer['tl_x'] for x in xs], [y+layer['tl_y'] for y in ys]
    edge = min(min(ax), min(ay), side-1-max(ax), side-1-max(ay))
    need(edge >= 0, 'Serialized feature outside actual layer canvas')
    return dict(level=layer['pyramid_level'], canvas_width=side, canvas_height=side,
                tl_x=layer['tl_x'], tl_y=layer['tl_y'], width=layer['width'], height=layer['height'],
                actual_features=len(xs), min_x=min(xs), min_y=min(ys), max_x=max(xs), max_y=max(ys),
                min_absolute_x=min(ax), min_absolute_y=min(ay), max_absolute_x=max(ax), max_absolute_y=max(ay),
                min_canvas_edge_distance=edge)
