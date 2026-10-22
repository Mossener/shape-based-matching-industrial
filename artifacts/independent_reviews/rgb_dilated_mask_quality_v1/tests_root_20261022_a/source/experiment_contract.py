"""Dilation experiment bindings, independent of target executable helpers."""
import json
from pathlib import Path

OBJECTS = [1, 2, 5, 8, 12, 17]
OLD = b'        erode(mask, local_mask, Mat(), Point(-1, -1), 1, BORDER_REPLICATE);'
NEW = b'        dilate(mask, local_mask, Mat(), Point(-1, -1), 1, BORDER_REPLICATE);'
PROTOCOL_SHA = 'ee313755ba5fad4311e7f2d80ffcb0fc1277c878cf1735a0d1a92b0b99635b6f'
ORIGINAL_CORE_SHA = '85b5eb328a3b5cae3e161561e261833873d25a9f57c7457c4410dd21e52083ab'


def need(value, reason):
    if not value:
        raise ValueError(reason)


def check_core_delta(original, treatment):
    need(original.count(OLD) == 1 and treatment.count(NEW) == 1 and
         original.replace(OLD, NEW, 1) == treatment, 'Exactly one erode-to-dilate core change required')


def check_acceptance(reader, marker, training, planning):
    need(marker['schema'] == 'rgb_dilated_mask_independent_audit_acceptance_v1' and
         marker['accepted_independent_audit'] is True and marker['scope'] == 'training_and_exact_geometry',
         'Independent training/geometry acceptance differs')
    for name, path in [('training_freeze', training), ('plan_freeze', planning)]:
        need(marker[name] == reader.pin(path), 'Acceptance binds another original freeze')
    receipt = json.loads(reader.check(marker['independent_audit']).decode('utf-8-sig'))
    need(receipt.get('passed') is True, 'Independent training audit failed')
    pins = receipt.get('input_pins', {})
    if isinstance(pins, list):
        names = [str(Path(p['path']).resolve()) for p in pins]
        need(len(names) == len(set(names)), 'Duplicate independent receipt pins')
        pins = dict(zip(names, pins))
    need(isinstance(pins, dict), 'Independent receipt input pins missing')
    for name in ['training_freeze', 'plan_freeze']:
        expected = marker[name]
        observed = pins.get(expected['path'], {})
        need(all(observed.get(k) == expected[k] for k in ['sha256', 'bytes']),
             'Accepted receipt does not bind original training/plan freeze')
    return receipt


def quality_gate(pooled):
    control, treatment = (pooled[arm]['allGT'] for arm in ['rgb_control', 'rgb_dilated_mask'])
    need((control['tp'], control['fp']) == (215, 42112), 'Frozen RGB control baseline changed')
    return dict(passed=treatment['tp'] >= 215 and treatment['fp'] < 42112,
                metric='allGT', required_tp_minimum=215, required_fp_strictly_below=42112,
                observed_tp=treatment['tp'], observed_fp=treatment['fp'],
                separate_from_numeric_audit_pass=True, speed_claim=False)


def verify_experiment(reader, experiment, inputs):
    exp = Path(experiment).resolve()
    closure = reader.json(exp/'INPUT_CLOSURE.json')
    need(reader.pin(exp/'INPUT_CLOSURE.json')['sha256'] == inputs['inherited_input_closure_sha256'],
         'Quality input closure binding differs')
    need(closure['version'] == 'rgb_dilated_mask_input_closure_v1' and closure['objects'] == OBJECTS and
         inputs['objects'] == OBJECTS and inputs['development'] == closure['development'] and
         inputs['dataset_root'] == closure['dataset_root'], 'Quality scope/declarations differ')
    reader.check(dict(path=str(Path(inputs['dataset_root'])/'index.json'),
                      **closure['private_files']['frozen_inputs/dataset_index.json']))
    protocol = reader.json(exp/'PROTOCOL.json')
    need(reader.pin(exp/'PROTOCOL.json')['sha256'] == closure['protocol_sha256'] ==
         inputs['protocol_sha256'] == PROTOCOL_SHA, 'Dilation protocol differs')
    need(protocol['change_surface']['core_changes'] == 1 and
         protocol['change_surface']['core_old'] == OLD.decode() and
         protocol['change_surface']['core_new'] == NEW.decode() and
         protocol['change_surface']['third_addTemplate_argument'] == 'warped_official_mask',
         'Official mask/factor differs')
    policy = protocol['quality']
    need([policy[k] for k in ['threshold','post_threshold','nms_iou','gt_iou','eligible_visibility']] ==
         [85,85,.3,.5,.5], 'Evaluation policy changed')
    need(protocol['quality']['primary_hypothesis'] == 'treatment TP >= 215 AND treatment FP < 42112',
         'Fixed quality gate changed')
    training, planning = exp/'run_training_v1/BANK_FREEZE.json', exp/'run_plan_v1/COMMON_PADDING_FREEZE.json'
    marker_path = exp/'AUDIT_ACCEPTANCE.json'
    marker = reader.json(marker_path)
    check_acceptance(reader, marker, training, planning)
    required_numeric = {str(p.resolve()) for p in [training, planning, marker_path,
        exp/'run_training_v1/training_audit.json', exp/'run_plan_v1/plan_audit.json',
        Path(marker['independent_audit']['path'])]}
    need(required_numeric.issubset({str(Path(p['path']).resolve()) for p in inputs['frozen_numeric_files']}),
         'Accepted training/plan/receipt not included in quality numeric pins')
    inherited = Path(closure['inherited_frozen_root']).resolve()
    need(inherited == exp.parent/'rgb_empty_mask_experiment', 'Unexpected inherited RGB root')
    need([b['object_id'] for b in inputs['rgb_banks']] == OBJECTS and
         inputs['common_padding_json'] == str(exp/'run_plan_v1/common_padding_plan.json'),
         'Bank ordering or common-plan path changed')
    for bank in inputs['rgb_banks']:
        obj = bank['object_id']
        control = inherited/'frozen_inputs'/f'obj{obj}'/'rgb_training'
        need(Path(bank['rgb_training']).resolve() == control and
             Path(bank['treatment_training']).resolve() == exp/'run_training_v1'/f'obj{obj}',
             'Control/treatment bank directory differs')
        for name in ['template_metadata.json',f'templates_tless_object_{obj}.yml.gz']:
            path = control/name
            expected = closure['private_files'][path.relative_to(inherited).as_posix()]
            reader.check(dict(path=str(path), **expected))
    seam = verify_source_seam(reader, exp, closure)
    return dict(passed=True, accepted_marker=reader.pin(marker_path),
                independent_training_receipt=marker['independent_audit'],
                **seam)


def verify_source_seam(reader, experiment, closure):
    exp=Path(experiment).resolve()
    inherited=Path(closure['inherited_frozen_root']).resolve()
    manifest_path = exp/'PRIVATE_SOURCE_FREEZE.json'
    manifest = reader.json(manifest_path)
    need(reader.pin(manifest_path)['sha256'] == closure['private_source_freeze_sha256'], 'Core freeze differs')
    parent_path = inherited/'PRIVATE_SOURCE_FREEZE.json'
    parent = reader.json(parent_path)
    need(reader.pin(parent_path)['sha256'] == manifest['parent_source_freeze_sha256'] and
         len(parent['files']) == 23 and set(parent['files']) == set(manifest['files']), 'Source origin differs')
    changed = []
    for name, expected in parent['files'].items():
        member = Path(name)
        need(not member.is_absolute() and '..' not in member.parts, 'Unsafe source member')
        original = reader.check(dict(path=str(inherited/'private_v11'/name), **expected))
        control = reader.read(exp/'control_v11'/name)
        treatment = reader.check(dict(path=str(exp/'private_v11'/name), **manifest['files'][name]))
        need(control == original, 'Control source changed')
        if name == 'line2Dup.cpp':
            need(expected['sha256'] == ORIGINAL_CORE_SHA, 'Original core differs')
            check_core_delta(original, treatment)
        else:
            need(treatment == original, 'Additional core source change')
        if treatment != original:
            changed.append(name)
    need(changed == ['line2Dup.cpp'] and manifest['helpers'] == parent['helpers'], 'Source/helper factors differ')
    for name, expected in parent['helpers'].items():
        original = reader.check(dict(path=str(inherited/'frozen_helpers'/name), **expected))
        need(reader.read(exp/'frozen_helpers'/name) == original, 'Evaluation helper differs')
    return dict(source_members=23, changed_core_files=changed, factor='per-layer official-mask erode-to-dilate')
