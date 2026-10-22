"""Declare all eighteen banks only after joined training acceptance.

C0 pins are inherited from the original frozen closure, P/B pins from the
complete independent training audit. This does not discover or decode images.
"""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import native_provenance as p

OBJECTS = [1, 2, 5, 8, 12, 17]
CLOSURE = HERE.parent / 'rgb_dilated_mask_experiment' / 'INPUT_CLOSURE.json'
CLOSURE_SHA = '9f0a6fd135716495cb51cde6918a022fd6514e2177941cd453ff6eb19a83f2ff'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def inherited_pin(closure, name):
    root = Path(closure['inherited_frozen_root']).resolve()
    path = (root / name).resolve()
    p.require(path.is_relative_to(root), 'C0 pin escaped frozen root')
    return dict(path=str(path), **closure['private_files'][name])


def build(acceptance_path):
    acceptance = read(acceptance_path)
    p.require(acceptance.get('schema') == 'rgb_stratified_training_execution_acceptance_v1' and
              acceptance.get('real_training_accepted') is True and
              acceptance.get('source_runtime_accepted') is True and
              acceptance.get('numeric_audit_passed') is True and
              acceptance.get('production_promotion') is False, 'Joined complete training acceptance required')
    p.check_pin(acceptance['independent_audit'])
    p.check_pin(acceptance['training_provenance'])
    audit = read(acceptance['independent_audit']['path'])
    provenance = read(acceptance['training_provenance']['path'])
    p.require(provenance['passed'] is True and provenance['mode'] == 'train' and
              audit['numeric_training_audit_passed'] is True and audit['public_numeric_training_complete'] is True and
              audit['comparison_feasible'] is True and audit['literal_only'] is False and
              audit['output_pins_before'] == audit['output_pins_after'], 'Complete unchanged training evidence required')
    p.require(p.file_pin(CLOSURE)['sha256'] == CLOSURE_SHA, 'Inherited C0 declaration changed')
    closure = read(CLOSURE)
    p.require(closure['objects'] == OBJECTS and [row['object_id'] for row in closure['rgb_banks']] == OBJECTS,
              'C0 object order differs')
    training_pin = provenance['input_freeze']
    p.check_pin(training_pin)
    p.require(training_pin == p.file_pin(HERE / 'TRAINING_INPUT_FREEZE.json'),
              'Training freeze differs from accepted execution')
    p.require(audit['input_pins'].get(training_pin['path']) ==
              {key: training_pin[key] for key in ('bytes', 'sha256')},
              'Training freeze differs from independent numeric audit')
    training = read(training_pin['path'])
    p.check_pin(training['origin'])
    p.require(training['origin']['sha256'] == CLOSURE_SHA, 'Training origin differs from C0 closure')
    run = Path(provenance['command'][provenance['command'].index('--output') + 1]).resolve()
    banks, files, originals = [], [], []
    for index, original in enumerate(closure['rgb_banks']):
        obj = original['object_id']
        row = dict(object_id=obj, control_training=original['rgb_training'],
                   control_template_count=original['rgb_template_count'])
        for arm, prefix, native in [('C0', 'control', None),
                ('P', 'pooled', 'rgb_pooled_features'), ('B', 'stratified', 'rgb_stratified_features')]:
            if arm == 'C0':
                directory = Path(original['rgb_training']).resolve()
            else:
                directory = run / native / ('obj' + str(obj))
                count = audit['successful_templates'][arm][index]
                p.require(type(count) is int and count > 0, 'Invalid accepted P/B count')
                row[prefix+'_training'] = str(directory)
                row[prefix+'_template_count'] = count
            pins = {}
            for name, filename in [('bank', 'templates_tless_object_%s.yml.gz' % obj),
                                   ('metadata', 'template_metadata.json')]:
                path = directory / filename
                if arm == 'C0':
                    rel = path.relative_to(Path(closure['inherited_frozen_root'])).as_posix()
                    value = inherited_pin(closure, rel)
                else:
                    value = dict(path=str(path), **audit['output_pins_after'][path.relative_to(run).as_posix()])
                p.check_pin(value)
                pins[name] = value
            files.append(dict(arm=arm, object_id=obj, **pins))
        banks.append(row)
        declared = training['original_attempts'][index]
        p.require(declared['object_id'] == obj, 'Original CSV order differs')
        value = declared['pin']
        p.check_pin(value)
        p.require(audit['input_pins'][value['path']] == {key: value[key] for key in ('bytes','sha256')},
                  'Original CSV differs from independent audit input')
        originals.append(dict(object_id=obj, file=value))
    return dict(schema='rgb_stratified_geometry_inputs_v1', production_promotion=False,
        training_run=str(run), source_numeric_audit=acceptance['independent_audit'],
        source_training_freeze=training_pin,
        training_execution_acceptance=p.file_pin(acceptance_path),
        inherited_control_closure=p.file_pin(CLOSURE), banks=banks, bank_files=files,
        original_attempts=originals, source=p.file_pin(__file__), native_calls=0,
        image_decodes=0, heldout_image_reads=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training-acceptance', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    p.require(not args.output.exists(), 'Fresh geometry input declaration required')
    result=build(args.training_acceptance.resolve())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True,banks=18,output=str(args.output.resolve()),image_decodes=0,native_calls=0)))


if __name__=='__main__':
    main()
