"""Independent RGB empty-feature-mask training and fixed-canvas audit.

Reads only numeric evidence and serialized integer banks, without native code,
OpenCV, dataset images or the target trainer/evaluator helpers.
"""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
from pathlib import Path

from bank_reader import parse_bank
from training_numeric import inspect_object, audit_bank, require, validate_private_numeric

OBJECTS = [1, 2, 5, 8, 12, 17]
SCALES = [.75, 1., 1.5, 2.]
ANGLES = list(range(0, 360, 30))
FIELDS = ['arm', 'object_id', 'class_id', 'template_id', 'level', 'width', 'height',
          'min_x', 'min_y', 'max_x', 'max_y', 'actual_features']


def pin(data):
    return dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def check_pin(data, expected):
    actual = pin(data)
    require(all(actual[k] == expected[k] for k in actual), 'Frozen SHA/size changed')


def validate_fixed_union(rows):
    require(rows, 'No geometry layers')
    for row in rows:
        level = row['level']
        require(level in (0, 1) and row['actual_features'] > 0 and
                row['width'] > 0 and row['height'] > 0 and
                0 <= row['min_x'] <= row['max_x'] <= row['width'] and
                0 <= row['min_y'] <= row['max_y'] <= row['height'], 'Invalid layer geometry')
        if level == 0:
            require(row['width'] <= 848-64 and row['height'] <= 832-64,
                    'Fine layer exceeds fixed image minus local-search region')
        else:
            require(max(row['width'], row['max_x']+1) <= 848//2 and
                    max(row['height'], row['max_y']+1) <= 832//2,
                    'Coarse layer exceeds declared or actual feature extent')
    return dict(source_size=[720, 540], width=848, height=832, alignment=16,
                padding_ltrb=[64, 64, 64, 228], pixels=848*832,
                estimated_dynamic_bytes=848*832*512, banks=12, loaded_layers=len(rows),
                geometry_feasible=1, development_images_decoded=0, matcher_calls=0)


class Reader:
    def __init__(self, experiment):
        self.root = experiment.resolve(strict=True)
        self.pins = {}
        self.private = None

    def read(self, path):
        path = Path(path).resolve(strict=True)
        require(path.is_relative_to(self.root) and path.suffix.lower() in ('.json', '.csv', '.gz', '.txt'),
                'Only experiment numeric evidence may be opened')
        relative = path.relative_to(self.root).as_posix()
        if relative.startswith('frozen_inputs/'):
            require(self.private is not None and relative in self.private, 'Unlisted frozen input')
        data = path.read_bytes()
        if relative.startswith('frozen_inputs/'):
            validate_private_numeric(relative, data, self.private)
        current = pin(data)
        require(str(path) not in self.pins or self.pins[str(path)] == current, 'Input changed during audit')
        self.pins[str(path)] = current
        return data

    def load(self, path):
        return json.loads(self.read(path).decode('utf-8-sig'))

    def table(self, path):
        return list(csv.DictReader(self.read(path).decode('utf-8-sig').splitlines()))

    def frozen(self, record):
        data = self.read(record['path'])
        check_pin(data, record)
        return data

    def final_check(self):
        for path, expected in self.pins.items():
            check_pin(Path(path).read_bytes(), expected)


def audit(experiment):
    exp = experiment.resolve(strict=True)
    read = Reader(exp)
    sources = {p.name: pin(p.read_bytes()) for p in Path(__file__).parent.iterdir()
               if p.is_file() and (p.suffix == '.py' or p.name == 'ORIGIN.json')}
    closure = read.load(exp/'INPUT_CLOSURE.json')
    read.private = closure['private_files']
    protocol = read.load(exp/'PROTOCOL.json')
    quality = read.load(exp/'QUALITY_INPUT_FREEZE.json')
    require(closure['objects'] == protocol['objects'] == quality['objects'] == OBJECTS,
            'Object scope differs')
    require(closure['protocol_sha256'] == quality['protocol_sha256'] ==
            pin(read.read(exp/'PROTOCOL.json'))['sha256'], 'Protocol binding differs')
    require(quality['inherited_input_closure_sha256'] ==
            pin(read.read(exp/'INPUT_CLOSURE.json'))['sha256'], 'Input closure binding differs')
    require(protocol['experiment'] == 'A_rgb_grayscale_source_empty_feature_selection_mask' and
            protocol['training']['attempts_total'] == 20736 and
            protocol['training']['scales'] == SCALES and
            protocol['training']['angles_degrees'] == ANGLES and
            protocol['geometry_gate']['required_width'] == 848 and
            protocol['geometry_gate']['required_height'] == 832,
            'Unexpected RGB experiment policy')
    for record in quality['frozen_numeric_files']:
        read.frozen(record)
    train, plan = exp/'run_training_v1', exp/'run_plan_v1'
    freeze = read.load(train/'BANK_FREEZE.json')
    summary = read.load(train/'training_summary.json')
    plan_freeze = read.load(plan/'COMMON_PADDING_FREEZE.json')
    require(freeze['native_exit_zero'] is True and freeze['comparison_feasible'] is True and
            freeze['training_attempts_complete'] is True and freeze['attempts'] == 20736 and
            freeze['objects'] == OBJECTS and freeze['matcher_calls'] == 0 and
            freeze['summary'] == summary, 'Training completion differs')
    require(plan_freeze['passed'] is True and plan_freeze['image_decodes'] ==
            plan_freeze['matcher_calls'] == 0, 'Planner completion differs')
    require(Path(plan_freeze['bank_freeze']['path']).resolve() == train/'BANK_FREEZE.json',
            'Planner binds another bank freeze')
    require(hashlib.sha256(read.read(train/'BANK_FREEZE.json')).hexdigest() ==
            plan_freeze['bank_freeze']['sha256'], 'Planner bank freeze SHA differs')
    training_paths = set()
    for record in freeze['files']:
        path = Path(record['path']).resolve()
        require(path.is_relative_to(train) and path not in training_paths, 'Unsafe/duplicate training member')
        training_paths.add(path); read.frozen(record)
    read.frozen(freeze['independent_training_audit'])
    require(training_paths == {p.resolve() for p in train.rglob('*') if p.is_file() and
            p.name not in ('.gitignore', 'BANK_FREEZE.json', 'training_audit.json')},
            'Training member set differs')
    banks = closure['rgb_banks']
    require([b['object_id'] for b in banks] == OBJECTS and len(banks) == 6,
            'RGB control bank scope differs')
    results, geometry_rows = [], []
    for b in banks:
        obj, cls = b['object_id'], 'tless_object_'+str(b['object_id'])
        directory = train/('obj'+str(obj))
        views = [x['image_id'] for x in closure['training'] if x['object_id'] == obj]
        require(len(views) == len(set(views)) == 72, 'Training view coverage differs')
        expected = set(itertools.product(views, ANGLES, SCALES))
        attempts = read.table(directory/'template_attempts.csv')
        control = read.table(Path(b['rgb_training'])/'template_attempts.csv')
        metadata = read.load(directory/'template_metadata.json')['templates']
        result = inspect_object(obj, attempts, control, metadata, expected)
        result.update(audit_bank(directory, obj, attempts, read.table(directory/'feature_geometry.csv'), read.read))
        require(result['successful_templates'] == freeze['successful_templates'][str(obj)] and
                result['opencv_exception_attempts'] == 0, 'Successful count/exception differs')
        original = {tuple([int(x['training_image']),int(x['angle']),float(x['scale'])]):x for x in control}
        success = lambda row: int(row['success']) == 1
        require(sum(success(x) for x in control) == b['rgb_template_count'], 'Control count differs')
        result['control_successful_templates'] = b['rgb_template_count']
        result['control_failed_treatment_successful'] = sum(success(x) and not success(original[(int(x['training_image']),int(x['angle']),float(x['scale']))]) for x in attempts)
        config = read.load(directory/'training_config.json')
        require(config['features'] == 32 and config['pyramid_T'] == [4,8] and
                config['scales'] == SCALES and config['angle_step'] == 30 and
                config['weak_threshold'] == 20 and config['strong_threshold'] == 40 and
                config['training_border'] == 16 and config['input_padding'] == 64 and
                config['coarse_threshold'] == config['selected_post_threshold'] == 85 and
                config['target_objects'] == [obj] and config['attempts'] == 3456 and
                config['template_count'] == result['successful_templates'] and
                config['opencv_exception_attempts'] == 0 and
                config['all_original_pose_geometries_equal'] == 1 and
                config['training_source'] == 'frozen grayscale RGB warp' and
                config['feature_selection_mask'] == 'empty cv::Mat()', 'Training config differs')
        reported = next(x for x in summary['objects'] if x['object_id'] == obj)
        require(all(result[k] == reported[k] for k in ('object_id','attempts','successful_templates','opencv_exception_attempts')) and
                Path(reported['directory']).resolve() == directory, 'Per-object summary differs')
        for arm, location, count in [('rgb_control',Path(b['rgb_training']), b['rgb_template_count']),
                                     ('rgb_empty_mask',directory,result['successful_templates'])]:
            bank = parse_bank(gzip.decompress(read.read(location/('templates_'+cls+'.yml.gz'))).decode(),cls)
            require(len(bank) == count, 'Plan bank count differs')
            for tid,layers in enumerate(bank):
                for level,layer in enumerate(layers):
                    xs,ys=zip(*[(f[0],f[1]) for f in layer['features']])
                    geometry_rows.append(dict(arm=arm,object_id=obj,class_id=cls,template_id=tid,level=level,
                        width=layer['width'],height=layer['height'],min_x=min(xs),min_y=min(ys),
                        max_x=max(xs),max_y=max(ys),actual_features=len(xs)))
        results.append(result)
    require(summary['attempts'] == sum(x['attempts'] for x in results) == 20736 and
            summary['zero_success_objects'] == summary['opencv_exception_attempts'] == summary['matcher_calls'] == 0 and
            summary['training_attempts_complete'] == summary['comparison_feasible'] == 1 and
            summary['incomplete_comparison'] == 0 and [x['object_id'] for x in summary['objects']] == OBJECTS,
            'Pooled training summary differs')
    observed = read.table(plan/'loaded_layers.csv')
    require(len(observed) == len(geometry_rows), 'Loaded layer count differs')
    for actual,expected in zip(observed,geometry_rows):
        require(list(actual) == FIELDS and all(actual[k] == str(v) for k,v in expected.items()),
                'Loaded layer CSV differs from serialized bank')
    computed = validate_fixed_union(geometry_rows)
    require(read.load(plan/'common_padding_plan.json') == plan_freeze['plan'] == computed,
            'Fixed-canvas plan differs')
    plan_paths=set()
    for record in plan_freeze['files']:
        path=Path(record['path']).resolve()
        require(path.is_relative_to(plan) and path not in plan_paths, 'Unsafe/duplicate plan member')
        plan_paths.add(path);read.frozen(record)
    require(plan_paths == {p.resolve() for p in plan.iterdir() if p.is_file() and
            p.name not in ('.gitignore','COMMON_PADDING_FREEZE.json')}, 'Plan member set differs')
    read.final_check()
    require(sources == {p.name:pin(p.read_bytes()) for p in Path(__file__).parent.iterdir()
            if p.is_file() and (p.suffix == '.py' or p.name == 'ORIGIN.json')}, 'Audit sources changed')
    return dict(passed=True,objects=results,training_attempts=20736,
        serialized_treatment_layers=sum(x['serialized_layers_checked'] for x in results),plan=computed,
        input_pins=read.pins,audit_source_pins=sources,image_files_opened=0,image_decodes=0,matcher_calls=0,
        historical_training_freeze_image_decodes=freeze['image_decodes'],
        historical_counter_note='BANK_FREEZE stores 432 RGB training views; native training source calls imread on both RGB and mask (864 decode calls). Audit itself reads no images.',
        limitation='Numeric serialized evidence only; does not independently re-extract pixels, observe failed partial features, establish SIMD safety or prove quality/speed gains.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    require(not args.output.exists(),'Output must be fresh')
    result=audit(args.experiment)
    with args.output.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('input_pins','audit_source_pins')}))


if __name__=='__main__':
    main()
