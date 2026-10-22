"""Independent RGB official-mask dilation training and fixed-canvas audit.

Reads only numeric evidence and serialized integer banks, without native code,
OpenCV, dataset images or the target trainer/evaluator helpers.
"""
import argparse
import csv
import gzip
import hashlib
import itertools
import io
import json
import math
import traceback
from pathlib import Path

from bank_reader import parse_bank
from training_numeric import inspect_object, audit_bank, require, validate_private_numeric

OBJECTS = [1, 2, 5, 8, 12, 17]
SCALES = [.75, 1., 1.5, 2.]
ANGLES = list(range(0, 360, 30))
ARMS = ['rgb_control', 'rgb_dilated_mask']
OLD = b'        erode(mask, local_mask, Mat(), Point(-1, -1), 1, BORDER_REPLICATE);'
NEW = b'        dilate(mask, local_mask, Mat(), Point(-1, -1), 1, BORDER_REPLICATE);'
ORIGINAL_CORE_SHA = '85b5eb328a3b5cae3e161561e261833873d25a9f57c7457c4410dd21e52083ab'
PARENT_SOURCE_FREEZE_SHA = '7451fcb34eb445a880232116b0a1965ee51b5d0224069c133aa36c360ad1e4aa'
FIELDS = ['arm', 'object_id', 'class_id', 'template_id', 'level', 'width', 'height',
          'min_x', 'min_y', 'max_x', 'max_y', 'actual_features']
ATTEMPT_FIELDS = ('class_id,training_image,angle,scale,success,template_id,source_crop_x,source_crop_y,'
                  'source_crop_w,source_crop_h,canvas,mask_x,mask_y,mask_w,mask_h,templ_tl_x,'
                  'templ_tl_y,features_l0,features_l1,error').split(',')
FEATURE_FIELDS = ('class_id,training_image,angle,scale,template_id,level,canvas_width,canvas_height,'
                  'tl_x,tl_y,width,height,actual_features,min_x,min_y,max_x,max_y,min_absolute_x,'
                  'min_absolute_y,max_absolute_x,max_absolute_y,min_canvas_edge_distance').split(',')


def pin(data):
    return dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def check_pin(data, expected):
    actual = pin(data)
    require(all(actual[k] == expected[k] for k in actual), 'Frozen SHA/size changed')


def validate_fixed_union(rows):
    require(rows, 'No geometry layers')
    levels, banks = {}, set()
    required_width, required_height = 720+64+64, 540+64+228
    for row in rows:
        obj, arm = row['object_id'], row['arm']
        require(obj in OBJECTS and arm in ARMS and row['class_id'] == 'tless_object_'+str(obj)
                and row['template_id'] >= 0, 'Unexpected union object/arm/class/template')
        identity = (obj, arm, row['template_id'])
        level = row['level']
        pose_levels = levels.setdefault(identity, set())
        require(level not in pose_levels, 'Duplicate loaded bank layer')
        pose_levels.add(level)
        banks.add((obj, arm))
        require(level in (0, 1) and row['actual_features'] > 0 and
                row['width'] > 0 and row['height'] > 0 and
                0 <= row['min_x'] <= row['max_x'] <= row['width'] and
                0 <= row['min_y'] <= row['max_y'] <= row['height'], 'Invalid layer geometry')
        if level == 0:
            required_width = max(required_width, row['width']+64)
            required_height = max(required_height, row['height']+64)
            require(row['width'] <= 848-64 and row['height'] <= 832-64,
                    'Fine layer exceeds fixed image minus local-search region')
        else:
            required_width = max(required_width, 2*max(row['width'], row['max_x']+1))
            required_height = max(required_height, 2*max(row['height'], row['max_y']+1))
            require(max(row['width'], row['max_x']+1) <= 848//2 and
                    max(row['height'], row['max_y']+1) <= 832//2,
                    'Coarse layer exceeds declared or actual feature extent')
    require(all(value == {0, 1} for value in levels.values()), 'Incomplete loaded pose pyramid')
    require(banks == {(obj, arm) for obj in OBJECTS for arm in ARMS}, 'All twelve banks required')
    for obj, arm in banks:
        ids = sorted(tid for o, a, tid in levels if (o, a) == (obj, arm))
        require(ids == list(range(len(ids))), 'Loaded template IDs not dense')
    alignment = math.lcm(4, 2*8)
    width = (required_width+alignment-1)//alignment*alignment
    height = (required_height+alignment-1)//alignment*alignment
    require((width, height, alignment) == (848, 832, 16), 'Computed padding would enlarge fixed canvas')
    pixels, dynamic = width*height, width*height*512
    require(max(width, height) <= 2048 and pixels <= 2097152 and dynamic <= 1073741824,
            'Computed resource budget exceeded')
    return dict(source_size=[720, 540], width=848, height=832, alignment=16,
                padding_ltrb=[64, 64, 64, 228], pixels=848*832,
                estimated_dynamic_bytes=848*832*512, banks=12, loaded_layers=len(rows),
                geometry_feasible=1, development_images_decoded=0, matcher_calls=0)


def check_core_pair(original, treatment, pin_original=True):
    require(original.count(OLD) == 1 and original.count(NEW) == 0, 'Unique original seam required')
    if pin_original:
        require(pin(original)['sha256'] == ORIGINAL_CORE_SHA, 'Frozen original core differs')
    require(treatment == original.replace(OLD, NEW, 1), 'Unauthorized core delta')


def validate_protocol(protocol):
    require(protocol['objects'] == OBJECTS and protocol['experiment'] ==
            'RGB_grayscale_source_official_mask_per_layer_dilation', 'Experiment policy differs')
    factor = protocol['change_surface']
    require(factor['core_changes'] == 1 and factor['core_old'] == OLD.decode() and
            factor['core_new'] == NEW.decode() and
            factor['third_addTemplate_argument'] == 'warped_official_mask', 'Treatment factor differs')
    training = protocol['training']
    required = dict(attempts_total=20736, views_per_object=72, attempts_per_object=3456,
                    scales=SCALES, angles_degrees=ANGLES, pyramid_T=[4, 8],
                    weak_threshold=20, strong_threshold=40, requested_features=[32, 16], border=16)
    require(all(training[k] == v for k, v in required.items()), 'Training schedule differs')
    gate = protocol['geometry_gate']
    fixed = dict(required_width=848, required_height=832, source_width=720, source_height=540,
                 padding_ltrb=[64, 64, 64, 228], alignment=16, exact_size_required=True)
    require(all(gate[k] == v for k, v in fixed.items()), 'Fixed canvas protocol differs')
    limits = dict(axis=2048, pixels=2097152, bytes_per_pixel=512,
                  estimated_dynamic_bytes=1073741824, peak_rss_bytes=1610612736)
    require(all(gate['limits'][k] == v for k, v in limits.items()), 'Resource protocol differs')


def audit_source_seam(exp, reader, closure):
    """Compare original/control/treatment bytes directly; no generator import."""
    inherited = Path(closure['inherited_frozen_root']).resolve(strict=True)
    manifest_bytes = reader.read(exp/'PRIVATE_SOURCE_FREEZE.json')
    require(pin(manifest_bytes)['sha256'] == closure['private_source_freeze_sha256'],
            'Source freeze binding differs')
    manifest = json.loads(manifest_bytes)
    parent_bytes = reader.read_source(inherited/'PRIVATE_SOURCE_FREEZE.json')
    require(pin(parent_bytes)['sha256'] == PARENT_SOURCE_FREEZE_SHA, 'Parent source freeze changed')
    parent = json.loads(parent_bytes)
    require(manifest['parent_source_freeze_sha256'] == PARENT_SOURCE_FREEZE_SHA and
            manifest['git_revision'] == parent['git_revision'] ==
            'b25df46f6ddf9c24fb43f5836f1414dc38c8caed', 'Wrong original source revision')
    require(len(parent['files']) == 23 and set(manifest['files']) == set(parent['files']),
            'Core source membership differs')
    changes = []
    for name, expected in parent['files'].items():
        member = Path(name)
        require(not member.is_absolute() and '..' not in member.parts, 'Unsafe source member')
        original = reader.read_source(inherited/'private_v11'/name)
        control = reader.read_source(exp/'control_v11'/name)
        treatment = reader.read_source(exp/'private_v11'/name)
        check_pin(original, expected);check_pin(treatment, manifest['files'][name])
        require(control == original, 'Control source differs: '+name)
        if name == 'line2Dup.cpp':
            check_core_pair(original, treatment)
        else:
            require(treatment == original, 'Extra private source change: '+name)
        if original != treatment:
            changes.append(name)
    require(changes == ['line2Dup.cpp'], 'Exactly one core delta required')
    for directory in ['control_v11', 'private_v11']:
        require({p.relative_to(exp/directory).as_posix() for p in (exp/directory).rglob('*') if p.is_file()}
                == set(parent['files']), 'Source tree member set differs')
    require(set(manifest['helpers']) == set(parent['helpers']), 'Helper membership differs')
    for name, expected in parent['helpers'].items():
        original = reader.read_source(inherited/'frozen_helpers'/name)
        current = reader.read_source(exp/'frozen_helpers'/name)
        check_pin(original, expected)
        require(current == original and manifest['helpers'][name] == expected, 'Official helper changed')
    return dict(passed=True, source_files=23, changed_files=changes,
                original_core_sha256=ORIGINAL_CORE_SHA,
                treatment_core_sha256=manifest['files']['line2Dup.cpp']['sha256'],
                factor='per-actual-layer erode-to-dilate, official mask retained')


class Reader:
    def __init__(self, experiment):
        self.root = experiment.resolve(strict=True)
        self.pins = {}
        self.private = None
        self.inherited = None
        self.inherited_pins = {}

    def allow_inherited(self, root, pins):
        self.inherited = Path(root).resolve(strict=True)
        self.inherited_pins = pins

    def _record(self, path, data):
        current = pin(data)
        require(str(path) not in self.pins or self.pins[str(path)] == current, 'Input changed during audit')
        self.pins[str(path)] = current
        return data

    def read_source(self, path):
        path = Path(path).resolve(strict=True)
        require(path.suffix in ('.json', '.py', '.cpp', '.hpp', '.h', '.hxx'), 'Non-source input')
        require(path.is_relative_to(self.root) or
                (self.inherited is not None and path.is_relative_to(self.inherited) and
                 (path == self.inherited/'PRIVATE_SOURCE_FREEZE.json' or
                  path.is_relative_to(self.inherited/'private_v11') or
                  path.is_relative_to(self.inherited/'frozen_helpers'))), 'Source outside approved roots')
        return self._record(path, path.read_bytes())

    def read(self, path):
        path = Path(path).resolve(strict=True)
        require(path.suffix.lower() in ('.json', '.csv', '.gz', '.txt'),
                'Only experiment numeric evidence may be opened')
        if not path.is_relative_to(self.root):
            require(self.inherited is not None and path.is_relative_to(self.inherited),
                    'Numeric input outside approved roots')
            relative = path.relative_to(self.inherited).as_posix()
            require(relative in self.inherited_pins, 'Unlisted inherited numeric input')
            data = path.read_bytes()
            check_pin(data, self.inherited_pins[relative])
            return self._record(path, data)
        relative = path.relative_to(self.root).as_posix()
        if relative.startswith('frozen_inputs/'):
            require(self.private is not None and relative in self.private, 'Unlisted frozen input')
        data = path.read_bytes()
        if relative.startswith('frozen_inputs/'):
            validate_private_numeric(relative, data, self.private)
        return self._record(path, data)

    def load(self, path):
        return json.loads(self.read(path).decode('utf-8-sig'))

    def table(self, path):
        table = csv.DictReader(io.StringIO(self.read(path).decode('utf-8-sig'), newline=''))
        result = list(table)
        require(table.fieldnames is not None and len(table.fieldnames) == len(set(table.fieldnames)) and
                all(None not in row and None not in row.values() for row in result), 'CSV row width/schema differs')
        expected = {'template_attempts.csv': ATTEMPT_FIELDS, 'feature_geometry.csv': FEATURE_FIELDS,
                    'loaded_layers.csv': FIELDS}.get(Path(path).name)
        require(expected is None or table.fieldnames == expected, 'Unexpected numeric CSV columns')
        return result

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
    require(closure['objects'] == protocol['objects'] == OBJECTS,
            'Object scope differs')
    require(len(closure['training']) == 432 and
            all(row['object_id'] in OBJECTS for row in closure['training']) and
            len({(row['object_id'], row['image_id']) for row in closure['training']}) == 432,
            'Full training declaration scope differs')
    require(len(closure['development']) == 400 and
            len({(row['scene_id'], row['image_id']) for row in closure['development']}) == 400 and
            {row['scene_id'] for row in closure['development']} == {1,4,6,7,8,10,12,13},
            'Development declaration scope differs')
    require(closure['version'] == 'rgb_dilated_mask_input_closure_v1', 'Wrong input closure')
    require(closure['protocol_sha256'] == pin(read.read(exp/'PROTOCOL.json'))['sha256'],
            'Protocol binding differs')
    validate_protocol(protocol)
    inherited = Path(closure['inherited_frozen_root']).resolve(strict=True)
    require(inherited == exp.parent/'rgb_empty_mask_experiment', 'Unexpected inherited root')
    inherited_pin = closure['inherited_closure_origin']
    require(Path(inherited_pin['path']).resolve() == inherited/'INPUT_CLOSURE.json',
            'Inherited closure path differs')
    inherited_numeric = dict(closure['private_files'])
    inherited_numeric['INPUT_CLOSURE.json'] = {k:inherited_pin[k] for k in ('sha256','bytes')}
    read.allow_inherited(inherited, inherited_numeric)
    read.frozen(inherited_pin)
    source_seam = audit_source_seam(exp, read, closure)
    train, plan = exp/'run_training_v1', exp/'run_plan_v1'
    freeze = read.load(train/'BANK_FREEZE.json')
    summary = read.load(train/'training_summary.json')
    plan_freeze = read.load(plan/'COMMON_PADDING_FREEZE.json')
    require(freeze['native_exit_zero'] is True and freeze['comparison_feasible'] is True and
            freeze['training_attempts_complete'] is True and freeze['attempts'] == 20736 and
            freeze['objects'] == OBJECTS and freeze['matcher_calls'] == 0 and
            freeze['summary'] == summary, 'Training completion differs')
    require(set(freeze['successful_templates']) == {str(obj) for obj in OBJECTS} and
            all(0 < value <= 3456 for value in freeze['successful_templates'].values()),
            'Incomplete/zero-success successful-template declarations')
    require(freeze['training_source'] == 'frozen grayscale RGB warp' and
            freeze['feature_selection_mask'] == 'official warped mask; per-layer 3x3 dilation', 'Freeze treatment policy differs')
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
    if 'independent_training_audit' in freeze:
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
        require(Path(b['rgb_training']).resolve() == inherited/'frozen_inputs'/('obj'+str(obj))/'rgb_training', 'Unexpected RGB bank path')
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
        require(sum(success(x) for x in control) == b['rgb_template_count'] == protocol['training']['rgb_control_successful_template_counts'][str(obj)], 'Control count differs')
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
                config['feature_selection_mask'] == 'official warped mask; per-layer 3x3 dilation', 'Training config differs')
        reported = next(x for x in summary['objects'] if x['object_id'] == obj)
        require(all(result[k] == reported[k] for k in ('object_id','attempts','successful_templates','opencv_exception_attempts')) and
                Path(reported['directory']).resolve() == directory, 'Per-object summary differs')
        for arm, location, count in [('rgb_control',Path(b['rgb_training']), b['rgb_template_count']),
                                     ('rgb_dilated_mask',directory,result['successful_templates'])]:
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
    require(0 < summary['peak_rss_bytes'] <= 1610612736, 'Peak working-set numeric ceiling exceeded')
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
    require(plan_paths == {p.resolve() for p in plan.rglob('*') if p.is_file() and
            p.name not in ('.gitignore','COMMON_PADDING_FREEZE.json')}, 'Plan member set differs')
    read.final_check()
    require(sources == {p.name:pin(p.read_bytes()) for p in Path(__file__).parent.iterdir()
            if p.is_file() and (p.suffix == '.py' or p.name == 'ORIGIN.json')}, 'Audit sources changed')
    return dict(passed=True,version='rgb_dilated_mask_independent_training_geometry_audit_v1',
        source_seam=source_seam,objects=results,training_attempts=20736,
        serialized_treatment_layers=sum(x['serialized_layers_checked'] for x in results),plan=computed,
        input_pins=read.pins,audit_source_pins=sources,image_files_opened=0,image_decodes=0,matcher_calls=0,
        reported_training_freeze_image_decodes=freeze['image_decodes'],
        counter_note='432 RGB training views plus 432 official mask inputs imply 864 native decode operations; audit itself reads no image bytes or pixels.',
        limitation='Numeric serialized evidence only; does not independently re-extract pixels, observe failed partial features, establish SIMD safety or prove quality/speed gains.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    output=args.output.resolve()
    require(output.is_relative_to(Path(__file__).resolve().parent) and not output.exists(),
            'Fresh output directory inside independent audit required')
    output.mkdir()
    snapshot=output/'source';snapshot.mkdir()
    for path in Path(__file__).parent.iterdir():
        if path.is_file() and (path.suffix=='.py' or path.name=='ORIGIN.json'):
            (snapshot/path.name).write_bytes(path.read_bytes())
    try:
        result=audit(args.experiment)
        (output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k not in ('input_pins','audit_source_pins')}))
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),
             image_files_opened=0,image_decodes=0,matcher_calls=0),indent=2)+'\n',encoding='utf-8')
        (output/'traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise


if __name__=='__main__':
    main()
