"""Independent pinned numeric-byte reader; no image/native process access."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

from checked import need

OBJECTS = [1, 2, 5, 8, 12, 17]
CALLS = dict(selftest=0, old_gate=96, pilot=192, development=9600)
PREVIOUS = dict(selftest=None, old_gate=None, pilot='old_gate', development='pilot')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_relative(value):
    text = str(value).replace('\\', '/')
    path = PurePosixPath(text)
    need(text and not path.is_absolute() and '..' not in path.parts and ':' not in text and str(path) == text,
         'Unsafe relative numeric path')
    return text


def members(encoded, expected):
    wanted = {row['name']: row for row in expected}
    need(len(wanted) == len(expected), 'Duplicate declared tar member')
    result = {}
    with tarfile.open(fileobj=io.BytesIO(encoded), mode='r:gz') as archive:
        for member in archive:
            name = member.name
            need(member.isfile() and name == PurePosixPath(name).name and '\\' not in name and ':' not in name and
                 name in wanted and name not in result, 'Unsafe/unexpected/duplicate tar member')
            payload = archive.extractfile(member).read()
            pin = wanted[name]
            need(len(payload) == member.size == pin['bytes'] and digest(payload) == pin['sha256'], 'Tar member SHA/bytes differ')
            result[name] = payload
    need(set(result) == set(wanted), 'Incomplete tar member set')
    return result


class Reader:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.seen = {}

    def allowed(self, path):
        path = Path(path).resolve(strict=True)
        # This audit may inspect numeric index metadata but never image bytes,
        # including outside the dataset folder or via a symlink/reparse point.
        need(path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp'}, 'Image byte access refused')
        need(not path.is_relative_to(self.root/'datasets') or path == self.root/'datasets/tless_expanded/index.json',
             'Dataset access outside numeric index refused')
        return path

    def read(self, path):
        path = self.allowed(path)
        data = path.read_bytes()
        pin = dict(path=str(path), sha256=digest(data), bytes=len(data))
        need(self.seen.setdefault(str(path), pin) == pin, 'Numeric file changed during audit')
        return data

    def json(self, path):
        return json.loads(self.read(path).decode('utf-8-sig'))

    def pin(self, path):
        self.read(path)
        return dict(self.seen[str(Path(path).resolve())])

    def check(self, pin):
        data = self.read(pin['path'])
        need(len(data) == pin['bytes'] and digest(data) == pin['sha256'], 'Frozen numeric SHA/bytes differ: '+pin['path'])
        return data

    def recheck(self):
        for pin in list(self.seen.values()):
            self.check(pin)


def stage_gate(reader, path, expected, build_pin, input_pin, experiment, seen=None):
    path = Path(path).resolve(strict=True)
    need(path.is_relative_to(experiment) and path.name == 'QUALITY_STAGE_FREEZE.json', 'Stage freeze outside experiment')
    seen = set() if seen is None else seen
    if str(path) in seen:
        return reader.json(path)
    seen.add(str(path))
    manifest = reader.json(path)
    need(manifest['completed'] is True and manifest['stage'] == expected and manifest['native_exit_code'] == 0 and
         manifest['actual_matcher_calls'] == manifest['maximum_matcher_calls'] == CALLS[expected] and
         manifest['build_manifest'] == build_pin and manifest['quality_inputs'] == input_pin and
         manifest['post_verification_passed'] is True and manifest['missing_frames_are_not_negatives'] is True and
         manifest['heldout_images_allowed'] is False, 'Unsuccessful/wrong stage closure')
    for field in ('files', 'execution_files'):
        pins = manifest[field]
        need(len({p['path'] for p in pins}) == len(pins), 'Duplicate stage pin')
        for pin in pins:
            reader.check(pin)
    native = path.parent/'native'
    need({str(p.resolve()) for p in native.rglob('*') if p.is_file() and p.name != '.gitignore'} ==
         {pin['path'] for pin in manifest['files']}, 'Complete native output inventory differs')
    need({str(p.resolve()) for p in path.parent.iterdir() if p.is_file() and p != path} ==
         {pin['path'] for pin in manifest['execution_files']}, 'Execution output inventory differs')
    execution = reader.json(path.parent/'execution_provenance.json')
    need(execution['mode'] == expected and execution['native_exit_code'] == 0 and
         execution['maximum_matcher_calls'] == CALLS[expected] and execution['build_manifest'] == build_pin and
         execution['quality_inputs'] == input_pin and execution['selftest'] == manifest['selftest'] and
         execution['previous_stage'] == manifest['previous_stage'] and execution['reservation'] == manifest['reservation'],
         'Execution/freeze stage binding differs')
    for pin in execution['script_pins']:
        reader.check(pin)
    summary_name = 'selftest_result.json' if expected == 'selftest' else 'stage_summary.json'
    summary = reader.json(native/summary_name)
    need(manifest['summary'] == summary and summary['passed'] == 1 and summary['matcher_calls'] == CALLS[expected],
         'Stage summary differs')
    if expected == 'selftest':
        need(manifest['selftest'] is None and manifest['previous_stage'] is None and manifest['reservation'] is None,
             'Synthetic selftest has matching-stage dependency')
    else:
        reader.check(manifest['selftest'])
        stage_gate(reader, manifest['selftest']['path'], 'selftest', build_pin, input_pin, experiment, seen)
        reservation = json.loads(reader.check(manifest['reservation']))
        need(reservation['stage'] == expected and reservation['run'] == str(path.parent) and
             reservation['maximum_calls'] == CALLS[expected] and reservation['previous_stage'] == PREVIOUS[expected] and
             reservation['previous_freeze'] == manifest['previous_stage'] and reservation['total_protocol_maximum'] == 22176,
             'Stage reservation differs')
        if PREVIOUS[expected]:
            reader.check(manifest['previous_stage'])
            stage_gate(reader, manifest['previous_stage']['path'], PREVIOUS[expected], build_pin, input_pin, experiment, seen)
        else:
            need(manifest['previous_stage'] is None, 'Unexpected old-gate previous stage')
    return manifest


def build_gate(reader, pin, experiment):
    build = json.loads(reader.check(pin))
    need(build['passed'] is True and build['target'] == 'quality' and
         build['core_revision'] == 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed' and
         build['actual_private_core'] == str(experiment/'private_v11/line2Dup.cpp') and
         Path(build['executable']['path']).name == 'quality_eval.exe', 'Quality build identity differs')
    need(len(build['commands']) == 5 and all(row['exit_code'] == 0 for row in build['commands']) and
         all('-DEMPTY_MASK_POLICY_RED_TEST' not in row['command'] for row in build['commands']), 'Quality build commands differ')
    need([row['source'] for row in build['dependency_units']] ==
         [str(experiment/'private_v11/line2Dup.cpp'), str(experiment/'quality_eval.cpp')], 'Quality build translation units differ')
    pins = (build['project_sources']+build['compiler_tools_and_link_libraries']+
            build['compiler_runtime_closure']['files']+build['executable_runtime_closure']['files']+[build['executable']])
    for unit in build['dependency_units']:
        pins += unit['dependencies']+[unit['object'], unit['dependency_file']]
        need(unit['source'] in [p['path'] for p in unit['dependencies']], 'Actual dependency list omits translation unit')
    for item in pins:
        reader.check(item)
    return build


def quality_gate(reader, stage, origin, experiment, kind):
    stage = Path(stage).resolve(strict=True)
    head = reader.json(stage)
    input_pin = head['quality_inputs']
    need(input_pin['sha256'] == origin['new_quality_inputs_sha256'], 'Reviewed quality input pin differs')
    inputs = json.loads(reader.check(input_pin))
    need(inputs['objects'] == OBJECTS and inputs['total_matcher_call_budget'] == 22176 and
         inputs['version'] == 'empty_mask_quality_inputs_v1' and inputs['dataset_image_reads'] == inputs['matcher_calls'] == 0,
         'Fixed numeric input scope differs')
    for pin in inputs['frozen_numeric_files']+[inputs['preparer'], inputs['stage_contract']]:
        reader.check(pin)
    closure_path = experiment/'INPUT_CLOSURE.json'
    need(reader.pin(closure_path)['sha256'] == inputs['inherited_input_closure_sha256'], 'Input inheritance binding differs')
    closure = reader.json(closure_path)
    need(closure['objects'] == inputs['objects'] and closure['development'] == inputs['development'] and
         closure['dataset_root'] == inputs['dataset_root'], 'Inherited numeric scope differs')
    for pin in closure['inherited_numeric_files']:
        reader.check(pin)
    for name, old_pin in closure['private_files'].items():
        reader.check(dict(path=str((experiment/safe_relative(name)).resolve()), **old_pin))
    need({p.relative_to(experiment).as_posix() for p in (experiment/'frozen_inputs').rglob('*') if p.is_file()} ==
         set(closure['private_files']), 'Inherited private numeric inventory differs')
    need([row['object_id'] for row in inputs['rgb_banks']] == OBJECTS, 'RGB bank order differs')
    for old, new in zip(closure['rgb_banks'], inputs['rgb_banks']):
        need(all(new[name] == value for name, value in old.items()), 'RGB bank inheritance differs')
    build_gate(reader, head['build_manifest'], experiment)
    need(kind in ('pilot', 'development'), 'Only fixed pilot or development audit allowed')
    stage_gate(reader, stage, kind, head['build_manifest'], input_pin, experiment)
    return inputs, closure, head
