"""Independent numeric and serialized-bank audit of binary/empty-mask training.

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Evidence output must be fresh')
    exp, run = args.experiment.resolve(strict=True), args.run.resolve(strict=True)
    require(run.is_relative_to(exp), 'Training run must be inside experiment')
    pins = {}

    def read(path):
        path = Path(path).resolve(strict=True)
        require(path.is_relative_to(exp) and path.suffix not in ('.png', '.jpg', '.bmp'),
                'Audit path must be experiment numeric evidence')
        data = path.read_bytes()
        pins[str(path)] = dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
        return data

    def load(path):
        return json.loads(read(path).decode('utf-8-sig'))

    def table(path):
        return list(csv.DictReader(read(path).decode('utf-8-sig').splitlines()))

    closure = load(exp/'INPUT_CLOSURE.json')
    protocol = load(exp/'PROTOCOL.json')
    freeze = load(run/'BANK_FREEZE.json')
    summary = load(run/'native/training_summary.json')
    require(closure['protocol_sha256'] == pins[str((exp/'PROTOCOL.json').resolve())]['sha256'],
            'Closure protocol SHA differs')
    for field, path in [('protocol', exp/'PROTOCOL.json'), ('input_closure', exp/'INPUT_CLOSURE.json')]:
        pin = freeze[field]
        require(Path(pin['path']).resolve() == path.resolve() and
                pin['sha256'] == pins[str(path.resolve())]['sha256'] and
                pin['bytes'] == pins[str(path.resolve())]['bytes'], 'Bank freeze input/protocol binding differs')
    require(closure['objects'] == protocol['objects'] == OBJECTS, 'Six-object scope changed')
    require(protocol['scales'] == [.75, 1., 1.5, 2.] and protocol['angles'] == list(range(0, 360, 30)),
            'Frozen pose policy changed')
    require(protocol['changed_factor_vs_source_only'].startswith('addTemplate feature-selection mask becomes empty cv::Mat()'),
            'Unexpected experiment factor')
    banks = {b['object_id']: b for b in closure['rgb_banks']}
    require(set(banks) == set(OBJECTS) and len(closure['rgb_banks']) == 6, 'RGB bank scope changed')
    results = []
    for obj in OBJECTS:
        views = [r['image_id'] for r in closure['training'] if r['object_id'] == obj]
        require(len(views) == len(set(views)) == 72, 'Training view coverage changed')
        expected = set(itertools.product(views, protocol['angles'], protocol['scales']))
        directory = run/'native'/('obj'+str(obj))
        meta = load(directory/'template_metadata.json')['templates']
        attempts = table(directory/'template_attempts.csv')
        result = inspect_object(obj, attempts,
                                table(Path(banks[obj]['rgb_training'])/'template_attempts.csv'), meta, expected)
        inspect_object(obj, attempts,
                       table(Path(banks[obj]['source_only_training'])/'template_attempts.csv'), meta, expected)
        result.update(audit_bank(directory, obj, attempts, table(directory/'feature_geometry.csv'), read))
        config = load(directory/'training_config.json')
        require(config['features'] == 32 and config['pyramid_T'] == [4, 8] and
                config['scales'] == protocol['scales'] and config['angle_step'] == 30 and
                config['weak_threshold'] == 20 and config['strong_threshold'] == 40 and
                config['training_border'] == 16 and config['input_padding'] == 64 and
                config['coarse_threshold'] == config['selected_post_threshold'] == 85 and
                config['target_objects'] == [obj] and config['attempts'] == 3456 and
                config['template_count'] == result['successful_templates'] and
                config['opencv_exception_attempts'] == result['opencv_exception_attempts'] and
                config['all_original_pose_geometries_equal'] == 1 and
                config['all_source_only_pose_geometries_equal'] == 1 and
                config['training_source'] == 'clone of binary official warped object mask' and
                config['feature_selection_mask'] == 'empty cv::Mat()', 'Training config/summary differs')
        require((directory/('templates_tless_object_'+str(obj)+'.yml.gz')).exists() ==
                (result['successful_templates'] > 0), 'Unexpected/missing serialized bank')
        results.append(result)
    require(summary['attempts'] == sum(r['attempts'] for r in results) == 20736 and
            summary['training_attempts_complete'] == 1 and summary['matcher_calls'] == 0,
            'Total attempt/call summary differs')
    zero = sum(r['successful_templates'] == 0 for r in results)
    exceptions = sum(r['opencv_exception_attempts'] for r in results)
    feasible = zero == 0 and exceptions == 0
    require(summary['zero_success_objects'] == zero and summary['opencv_exception_attempts'] == exceptions and
            summary['comparison_feasible'] == int(feasible) and summary['incomplete_comparison'] == int(not feasible),
            'Incomplete-comparison summary differs')
    require(len(summary['objects']) == 6 and [r['object_id'] for r in summary['objects']] == OBJECTS,
            'Summary object order/scope differs')
    for actual, reported in zip(results, summary['objects']):
        for field in ['object_id', 'attempts', 'successful_templates', 'opencv_exception_attempts']:
            require(actual[field] == reported[field], 'Per-object summary differs')
    require(freeze['comparison_feasible'] is feasible and freeze['training_attempts_complete'] is True and
            freeze['native_exit_zero'] is feasible and freeze['summary'] == summary and freeze['matcher_calls'] == 0,
            'Bank freeze status differs')
    listed = set()
    native = (run/'native').resolve(strict=True)
    for pin in freeze['files']:
        path = Path(pin['path']).resolve(strict=True)
        require(path.is_relative_to(native) and path not in listed, 'Unsafe/duplicate native artifact pin')
        listed.add(path)
        data = read(path)
        require(pin['sha256'] == hashlib.sha256(data).hexdigest() and pin['bytes'] == len(data),
                'Frozen bank artifact differs')
    require(listed == {p.resolve() for p in native.rglob('*') if p.is_file() and p.name != '.gitignore'},
            'Bank freeze omits/adds artifacts')
    for name, expected_pin in pins.items():
        data = Path(name).read_bytes()
        require(dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)) == expected_pin,
                'Numeric evidence changed during audit')
    result = dict(passed=True, objects=results, attempts=20736, comparison_feasible=feasible,
                  zero_success_objects=zero, opencv_exception_attempts=exceptions, input_pins=pins,
                  audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  image_files_opened=0, image_decodes=0, matcher_calls=0,
                  limitation='Serialized numeric records/provenance only; does not re-extract features, '
                  'audit unsuccessful partial features or demonstrate accuracy/speed improvement; '
                  'serialized banks independently agree with successful per-layer diagnostics')
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'input_pins'}))


if __name__ == '__main__':
    main()
