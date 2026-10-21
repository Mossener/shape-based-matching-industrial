"""Inherit frozen numeric inputs for the empty-feature-mask successor.

Copies only the parent's numeric input allowlist and source-only training
evidence. No training/development image bytes are opened by create/verify unless
an explicit image phase is requested after the coordinated native CPU slot.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT/'artifacts/silhouette_template_experiment'
OBJECTS = [1,2,5,8,12,17]
PROTOCOL_SHA = 'e4260feb88abc00532b096b1fdb602a4c5a785ec060788aa54ba821eacd4245b'


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(value):
    text = str(value).replace('\\','/')
    path = PurePosixPath(text)
    require(text and not path.is_absolute() and '..' not in path.parts and ':' not in text and str(path)==text,
            'Unsafe relative input path')
    return text


def rebase_private(name):
    name = relative(name)
    require(name.startswith('frozen_inputs/'), 'Parent private copy outside numeric frozen_inputs scope')
    return HERE/name


def pin(path):
    path = Path(path).resolve(strict=True);data = path.read_bytes()
    return dict(path=str(path),sha256=digest(data),bytes=len(data))


def check(path, expected):
    actual = pin(path)
    require(actual['sha256']==expected['sha256'] and actual['bytes']==expected['bytes'],
            'Frozen inherited input SHA/size changed: '+str(path))
    return actual


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate_parent_scope(parent):
    require(parent['version']=='silhouette_input_closure_v1' and parent['objects']==OBJECTS, 'Parent source-only scope changed')
    training = parent['training'];development = parent['development']
    require(Counter(row['object_id'] for row in training)==dict.fromkeys(OBJECTS,72), 'Parent training coverage changed')
    require(len({(r['object_id'],r['image_id']) for r in training})==432 and
            len({relative(r[k]) for r in training for k in ('rgb','mask')})==864, 'Duplicate parent training records')
    require(len(development)==400 and len({(r['scene_id'],r['image_id']) for r in development})==400 and
            sum(bool(r['pilot']) for r in development)==8 and sum(bool(r['timing']) for r in development)==64,
            'Parent development schedule coverage changed')
    require([r['object_id'] for r in parent['rgb_banks']]==OBJECTS, 'Parent RGB bank scope/order changed')
    for row in training:
        for key in ('rgb','mask'):
            require(len(row[key+'_sha256'])==64 and row[key+'_bytes']>0,'Invalid inherited training member pin')
    for row in development:
        relative(row['rgb']);require(len(row['rgb_sha256'])==64 and row['rgb_bytes']>0,'Invalid inherited development member pin')


def create():
    require(not (HERE/'INPUT_CLOSURE.json').exists() and not (HERE/'frozen_inputs').exists(), 'Successor closure must be fresh')
    require(digest((HERE/'PROTOCOL.json').read_bytes())==PROTOCOL_SHA, 'Reviewed successor protocol changed')
    protocol = load(HERE/'PROTOCOL.json')
    inherited = []
    for item in protocol['input_pins']:
        path = ROOT/relative(item['path']);record = pin(path)
        require(record['sha256']==item['sha256'],'Reviewed parent input pin changed: '+str(path));inherited.append(record)
    parent = load(PARENT/'INPUT_CLOSURE.json');validate_parent_scope(parent)
    require(parent['dataset_root']==str(ROOT/'datasets/tless_expanded'), 'Parent dataset origin changed')
    private = {}
    for name, expected in parent['private_files'].items():
        destination = rebase_private(name)
        old = check(PARENT/relative(name),expected);inherited.append(old)
        data = Path(old['path']).read_bytes()
        require(digest(data)==old['sha256'],'Parent changed during numeric copy')
        destination.parent.mkdir(parents=True,exist_ok=True);require(not destination.exists(),'Duplicate inherited numeric copy')
        destination.write_bytes(data);private[destination.relative_to(HERE).as_posix()] = dict(sha256=old['sha256'],bytes=len(data))
    # The full old closure records original compressed banks, original cache
    # and decoded preservation-only metadata/attempt files. Recheck their
    # numeric bytes; these paths do not include dataset image members.
    for name, expected in parent['source_sha256'].items():
        path = Path(name).resolve(strict=True)
        require(not path.is_relative_to(ROOT/'datasets') or path==ROOT/'datasets/tless_expanded/index.json',
                'Parent source closure unexpectedly includes a dataset image')
        inherited.append(check(path,expected))
    bank_freeze = load(PARENT/'run_source_only_training_v1/BANK_FREEZE.json')
    require(bank_freeze['training_attempts_complete'] is True and bank_freeze['comparison_feasible'] is False and
            bank_freeze['summary']['attempts']==20736 and bank_freeze['summary']['zero_success_objects']==6 and
            bank_freeze['summary']['opencv_exception_attempts']==0, 'Parent source-only feasibility evidence changed')
    source_only = []
    for record in bank_freeze['files']:
        path=Path(record['path']).resolve(strict=True)
        base=PARENT/'run_source_only_training_v1/native'
        require(path.is_relative_to(base),'Source-only evidence copy outside native scope')
        actual=check(path,record);inherited.append(actual)
        name='frozen_inputs/source_only_training/'+path.relative_to(base).as_posix()
        target=HERE/name;target.parent.mkdir(parents=True,exist_ok=True);require(not target.exists(),'Duplicate source-only evidence')
        target.write_bytes(path.read_bytes());check(target,actual)
        private[name]=dict(sha256=actual['sha256'],bytes=actual['bytes']);source_only.append(name)
    banks=[]
    for old in parent['rgb_banks']:
        item=dict(old)
        for key in ('rgb_training','original_pilot_raw'):
            original=Path(old[key]).resolve(strict=True)
            require(original.is_relative_to(PARENT/'frozen_inputs'),'Inherited RGB origin outside frozen inputs')
            item[key]=str(HERE/'frozen_inputs'/original.relative_to(PARENT/'frozen_inputs'))
        item['source_only_training']=str(HERE/f"frozen_inputs/source_only_training/obj{old['object_id']}")
        banks.append(item)
    # Deduplicate pins only here, where source provenance is an unordered set;
    # native dependency manifests separately retain all ordered occurrences.
    pins={}
    for record in inherited:
        old=pins.setdefault(record['path'],record);require(old==record,'Conflicting inherited pin')
    for record in pins.values():
        check(record['path'],record)
    result=dict(version='silhouette_empty_mask_input_closure_v1',dataset_root=parent['dataset_root'],objects=OBJECTS,
                training=parent['training'],development=parent['development'],rgb_banks=banks,private_files=private,
                inherited_numeric_files=list(pins.values()),source_only_evidence_files=source_only,
                original_source_only_input_closure_sha256=digest((PARENT/'INPUT_CLOSURE.json').read_bytes()),
                private_source_freeze_sha256=digest((HERE/'PRIVATE_SOURCE_FREEZE.json').read_bytes()),
                protocol_sha256=PROTOCOL_SHA,preparer_sha256=digest(Path(__file__).read_bytes()),
                image_hash_origin=parent['image_hash_origin'],image_files_opened=0,image_decodes=0,matcher_calls=0)
    (HERE/'INPUT_CLOSURE.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def verify(images=None):
    closure=load(HERE/'INPUT_CLOSURE.json')
    require(closure['version']=='silhouette_empty_mask_input_closure_v1' and closure['objects']==OBJECTS,'Successor closure scope changed')
    require(digest((HERE/'PROTOCOL.json').read_bytes())==closure['protocol_sha256']==PROTOCOL_SHA,'Successor protocol changed')
    require(digest((HERE/'PRIVATE_SOURCE_FREEZE.json').read_bytes())==closure['private_source_freeze_sha256'],'Private source freeze changed')
    require(digest(Path(__file__).read_bytes())==closure['preparer_sha256'],'Input inheritance implementation changed')
    expected=set(closure['private_files'])
    observed={p.relative_to(HERE).as_posix() for p in (HERE/'frozen_inputs').rglob('*') if p.is_file()}
    require(observed==expected,'Successor numeric member set changed')
    for name,expected_pin in closure['private_files'].items():
        check(rebase_private(name),expected_pin)
    for record in closure['inherited_numeric_files']:
        check(record['path'],record)
    members=[]
    if images=='training':
        members=[(r[k],r[k+'_sha256'],r[k+'_bytes']) for r in closure['training'] for k in ('rgb','mask')]
    elif images=='development':
        members=[(r['rgb'],r['rgb_sha256'],r['rgb_bytes']) for r in closure['development']]
    require(images in (None,'training','development'),'Unknown image verification phase')
    for name,sha,size in members:
        check(ROOT/'datasets/tless_expanded'/relative(name),dict(sha256=sha,bytes=size))
    return dict(passed=True,image_files_opened=len(members),image_decodes=0,matcher_calls=0,image_phase=images,
                protocol_sha256=PROTOCOL_SHA,private_file_count=len(closure['private_files']),
                inherited_numeric_file_count=len(closure['inherited_numeric_files']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create',action='store_true');group.add_argument('--verify',action='store_true')
    parser.add_argument('--verify-images',choices=['training','development']);parser.add_argument('--cpu-slot-granted',action='store_true')
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    require(not args.output.exists(),'Output must be fresh')
    require(not args.verify_images or args.verify and args.cpu_slot_granted,'Image byte verification needs coordinated CPU slot')
    try:
        result=create() if args.create else verify(args.verify_images)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(passed=True,image_files_opened=result['image_files_opened'],image_decodes=0,matcher_calls=0)))
    except Exception as error:
        args.output.write_text(json.dumps(dict(incomplete=True,reason=str(error),missing_frames_are_not_negatives=True),indent=2)+'\n');raise


if __name__=='__main__':
    main()
