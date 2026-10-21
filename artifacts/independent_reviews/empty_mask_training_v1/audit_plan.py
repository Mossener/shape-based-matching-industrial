"""Independently reconstruct full twelve-bank geometry and common padding.

Uses only serialized numeric evidence and the independent integer bank reader.
No OpenCV, evaluator, training helpers or images are loaded.
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from bank_reader import parse_bank, need

OBJECTS = [1, 2, 5, 8, 12, 17]
FIELDS = ['arm', 'object_id', 'class_id', 'template_id', 'level', 'width', 'height',
          'min_x', 'min_y', 'max_x', 'max_y', 'actual_features']


def dimensions(rows):
    need(rows, 'Empty bank union')
    width, height = 848, 672
    for row in rows:
        need(row['level'] in (0, 1) and row['width'] > 0 and row['height'] > 0 and
             0 <= row['min_x'] <= row['max_x'] <= row['width'] and
             0 <= row['min_y'] <= row['max_y'] <= row['height'], 'Invalid layer geometry')
        if row['level'] == 0:
            w, h = row['width']+64, row['height']+64
        else:
            w = 2*max(row['width'], row['max_x']+1)
            h = 2*max(row['height'], row['max_y']+1)
        width, height = max(width, w), max(height, h)
    width, height = ((width+15)//16)*16, ((height+15)//16)*16
    need(width <= 2048 and height <= 2048 and width*height <= 2097152 and
         width*height*512 <= 1073741824, 'Plan exceeds declared resource budget')
    return dict(source_size=[720, 540], width=width, height=height, alignment=16,
                padding_ltrb=[64, 64, width-784, height-604], pixels=width*height,
                estimated_dynamic_bytes=width*height*512, banks=12, loaded_layers=len(rows),
                geometry_feasible=1, development_images_decoded=0, matcher_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', type=Path, required=True)
    parser.add_argument('--training-run', type=Path, required=True)
    parser.add_argument('--plan-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    exp = args.experiment.resolve(strict=True)
    training, plan = args.training_run.resolve(strict=True), args.plan_run.resolve(strict=True)
    need(training.is_relative_to(exp) and plan.is_relative_to(exp) and not args.output.exists(),
         'Unsafe evidence paths or existing output')
    pins = {}
    source_pins = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in [Path(__file__), Path(__file__).with_name('bank_reader.py')]}

    def read(path):
        path = Path(path).resolve(strict=True)
        need(path.is_relative_to(exp) and path.suffix in ('.json', '.csv', '.gz'),
             'Only experiment numeric evidence may be read')
        data = path.read_bytes()
        pins[str(path)] = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
        return data

    def load(path):
        return json.loads(read(path).decode('utf-8-sig'))

    def checked_file(item):
        path = Path(item['path']).resolve(strict=True)
        read(path)
        need(pins[str(path)] == {k: item[k] for k in ('sha256', 'bytes')}, 'Frozen file changed')

    closure = load(exp/'INPUT_CLOSURE.json')
    need(closure['objects'] == OBJECTS and [b['object_id'] for b in closure['rgb_banks']] == OBJECTS,
         'Six-object bank order changed')
    freeze = load(plan/'COMMON_PADDING_FREEZE.json')
    need(freeze['passed'] is True and freeze['development_images_decoded'] == freeze['matcher_calls'] == 0,
         'Numeric planner stage did not pass')
    checked_file(freeze['bank_freeze'])
    need(Path(freeze['bank_freeze']['path']).resolve() == training/'BANK_FREEZE.json', 'Wrong training freeze')
    bank_freeze = load(training/'BANK_FREEZE.json')
    checked_file(bank_freeze['input_closure'])
    need(Path(bank_freeze['input_closure']['path']).resolve() == exp/'INPUT_CLOSURE.json',
         'Planner closure is not the exact frozen training closure')
    need(bank_freeze['comparison_feasible'] is True and bank_freeze['training_attempts_complete'] is True,
         'Incomplete training bank')
    frozen_banks = {str(Path(p['path']).resolve()): p for p in bank_freeze['files']}
    rows = []
    for item in closure['rgb_banks']:
        obj, cls = item['object_id'], 'tless_object_'+str(item['object_id'])
        for arm, directory in [('rgb', Path(item['rgb_training'])),
                               ('binary_empty_mask', training/'native'/('obj'+str(obj)))]:
            path = (directory/('templates_'+cls+'.yml.gz')).resolve(strict=True)
            data = read(path)
            expected_pin = (closure['private_files'].get(path.relative_to(exp).as_posix()) if arm == 'rgb'
                            else frozen_banks.get(str(path)))
            need(expected_pin and pins[str(path)] == {k: expected_pin[k] for k in ('sha256', 'bytes')},
                 'Bank differs from frozen private/training input')
            bank = parse_bank(gzip.decompress(data).decode('utf-8'), cls)
            count = (item['rgb_template_count'] if arm == 'rgb' else
                     next(o['successful_templates'] for o in bank_freeze['summary']['objects'] if o['object_id'] == obj))
            need(len(bank) == count, 'Bank count differs')
            for template_id, layers in enumerate(bank):
                for level, layer in enumerate(layers):
                    xs, ys = zip(*[(f[0], f[1]) for f in layer['features']])
                    rows.append(dict(arm=arm, object_id=obj, class_id=cls, template_id=template_id,
                                     level=level, width=layer['width'], height=layer['height'],
                                     min_x=min(xs), min_y=min(ys), max_x=max(xs), max_y=max(ys),
                                     actual_features=len(xs)))
    reader = csv.DictReader(read(plan/'native/loaded_layers.csv').decode().splitlines())
    need(reader.fieldnames == FIELDS, 'Layer CSV schema differs')
    observed = list(reader)
    need(len(rows) == len(observed), 'Layer CSV count differs')
    for expected, actual in zip(rows, observed):
        need(set(actual) == set(expected) and all(actual[k] == str(v) for k, v in expected.items()),
             'Layer CSV differs from serialized bank')
    expected = dimensions(rows)
    need(load(plan/'native/common_padding_plan.json') == expected, 'Computed common plan differs')
    listed = set()
    for item in freeze['files']:
        path = Path(item['path']).resolve(strict=True)
        need(path.is_relative_to(plan/'native') and path not in listed, 'Unsafe/duplicate plan artifact')
        listed.add(path)
        checked_file(item)
    need(listed == {p.resolve() for p in (plan/'native').iterdir() if p.is_file() and p.name != '.gitignore'},
         'Planner freeze inventory differs')
    for name, pin in pins.items():
        data = Path(name).read_bytes()
        need(pin == dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)), 'Numeric evidence changed')
    for name, pin in source_pins.items():
        need(hashlib.sha256(Path(name).read_bytes()).hexdigest() == pin, 'Audit source changed')
    result = dict(passed=True, plan=expected, input_pins=pins, image_files_opened=0,
                  image_decodes=0, matcher_calls=0,
                  audit_source_pins=source_pins,
                  limitation='Numeric geometry only; no SIMD memory-safety, accuracy or speed proof')
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, plan=expected)))


if __name__ == '__main__':
    main()
