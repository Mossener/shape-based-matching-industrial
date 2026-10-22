"""Prepare/check the one-line treatment from the pinned V27 source snapshot.

Only C++/Python source and JSON declarations are read. No bank/image reads.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT/'artifacts/rgb_empty_mask_experiment'
REV = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
BASE_FREEZE_SHA = '7451fcb34eb445a880232116b0a1965ee51b5d0224069c133aa36c360ad1e4aa'
OLD = b'        erode(mask, local_mask, Mat(), Point(-1, -1), 1, BORDER_REPLICATE);'
NEW = b'        dilate(mask, local_mask, Mat(), Point(-1, -1), 1, BORDER_REPLICATE);'
CORE_SHA = '85b5eb328a3b5cae3e161561e261833873d25a9f57c7457c4410dd21e52083ab'


def require(value, message):
    if not value: raise ValueError(message)


def digest(data): return hashlib.sha256(data).hexdigest()
def record(data): return dict(sha256=digest(data), bytes=len(data))


def transform_core(data):
    require(data.count(OLD)==1 and data.count(NEW)==0, 'Expected unique erode seam and no preexisting dilate seam')
    return data.replace(OLD, NEW, 1)


def private_flags(private):
    return ['-std=c++17','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wextra',
            '-Wno-sign-compare','-Wno-unused-function','-I'+str(private),'-I'+str(private/'MIPP')]


def source_bytes():
    data = (BASE/'PRIVATE_SOURCE_FREEZE.json').read_bytes()
    require(digest(data)==BASE_FREEZE_SHA, 'V27 source-freeze origin changed')
    manifest = json.loads(data)
    require(manifest['git_revision']==REV and len(manifest['files'])==23, 'V27 private origin scope changed')
    files = {}
    for name, pin in manifest['files'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe source member')
        value = (BASE/'private_v11'/name).read_bytes()
        require(record(value)==pin, 'V27 source bytes changed: '+name)
        files[name] = value
    require(digest(files['line2Dup.cpp'])==CORE_SHA, 'Original V11 core changed')
    helpers = {}
    for name, pin in manifest['helpers'].items():
        value = (BASE/'frozen_helpers'/name).read_bytes()
        require(record(value)=={k:pin[k] for k in ('sha256','bytes')}, 'Official helper changed: '+name)
        helpers[name] = value
    require(b'detector.addTemplate(warped,classId,warped_mask)' in helpers['tless_eval.cpp'], 'Official RGB mask interface changed')
    return manifest, files, helpers


def verify(private, manifest):
    origin, files, helpers = source_bytes()
    require(manifest['git_revision']==REV and manifest['parent_source_freeze_sha256']==BASE_FREEZE_SHA, 'Wrong private source origin')
    require(set(manifest['files'])==set(files), 'Private file membership changed')
    require({p.relative_to(private).as_posix() for p in private.rglob('*') if p.is_file()}==set(files), 'Unexpected private source member')
    changes=[]
    for name, data in files.items():
        expected=transform_core(data) if name=='line2Dup.cpp' else data
        actual=(private/name).read_bytes()
        require(actual==expected and record(actual)==manifest['files'][name], 'Unauthorized private delta: '+name)
        if actual!=data: changes.append(name)
        require((HERE/'control_v11'/name).read_bytes()==data, 'Literal-test control source changed: '+name)
    require(changes==['line2Dup.cpp'], 'Exactly one changed core source required')
    require({p.relative_to(HERE/'control_v11').as_posix() for p in (HERE/'control_v11').rglob('*') if p.is_file()}==set(files), 'Control source membership changed')
    require(set(manifest['helpers'])==set(helpers), 'Helper membership changed')
    require({p.name for p in (HERE/'frozen_helpers').iterdir() if p.is_file()}==set(helpers), 'Unexpected helper member')
    for name,data in helpers.items():
        require((HERE/'frozen_helpers'/name).read_bytes()==data, 'Helper bytes differ: '+name)
        require(manifest['helpers'][name]==origin['helpers'][name], 'Helper origin differs')
    require(manifest['compile_flags']==private_flags(private), 'Private include flags changed')
    require(manifest['core_translation_unit']==str(private/'line2Dup.cpp'), 'Actual core TU differs')
    return dict(manifest, passed=True, changed_files=changes, image_files_opened=0, image_decodes=0, matcher_calls=0)


def create():
    require(not (HERE/'PRIVATE_SOURCE_FREEZE.json').exists(), 'Source snapshot already exists')
    for directory in ('private_v11','control_v11','frozen_helpers'):
        require(not (HERE/directory).exists(), 'Source output must be fresh: '+directory)
    origin, files, helpers = source_bytes()
    for name,data in files.items():
        for directory,value in [('control_v11',data),('private_v11',transform_core(data) if name=='line2Dup.cpp' else data)]:
            path=HERE/directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
    (HERE/'frozen_helpers').mkdir()
    for name,data in helpers.items(): (HERE/'frozen_helpers'/name).write_bytes(data)
    manifest=dict(git_revision=REV, file_count=23,
        files={n:record((HERE/'private_v11'/n).read_bytes()) for n in files},
        helpers=origin['helpers'], original_files=origin['files'],
        parent_source_freeze_sha256=BASE_FREEZE_SHA,
        core_translation_unit=str(HERE/'private_v11/line2Dup.cpp'),
        compile_flags=private_flags(HERE/'private_v11'),
        adapter_include='frozen_helpers/tless_eval.cpp',
        source_policy='Pinned V27 original V11 bytes; exact one-line erode-to-dilate transform; official RGB mask retained',
        sole_core_delta=dict(old=OLD.decode(),new=NEW.decode(),function='ColorGradientPyramid::extractTemplate',occurrences=1),
        image_files_opened=0,image_decodes=0,matcher_calls=0)
    (HERE/'PRIVATE_SOURCE_FREEZE.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return verify(HERE/'private_v11',manifest)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create',action='store_true')
    args=parser.parse_args()
    result=create() if args.create else verify(HERE/'private_v11',json.loads((HERE/'PRIVATE_SOURCE_FREEZE.json').read_text()))
    print(json.dumps(dict(passed=result['passed'],changed_files=result['changed_files'],native_calls=0,image_decodes=0)))
