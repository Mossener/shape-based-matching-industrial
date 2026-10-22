"""Byte-verify only fixed quality-stage inputs; no decode or native execution.

Called solely by separately authorized quality runs. No training images,
heldout images, object 25/29 or private images are opened.
"""
import json
from pathlib import Path
import native_provenance as p
import prepare_quality_inputs as declarations
from source_contract import check_declared_scope

HERE=Path(__file__).resolve().parent


def read(path):return json.loads(Path(path).read_text())


def verify(mode):
    p.require(mode in ('selftest','old_gate','pilot','development','timing'),'Unknown fixed quality stage')
    declarations.verify()
    closure=read(HERE/'INPUT_CLOSURE.json');quality=read(HERE/'QUALITY_INPUT_FREEZE.json')
    check_declared_scope(closure)
    p.require(closure['objects']==quality['objects']==[1,2,5,8,12,17] and len(closure['development'])==400,'Quality scope changed')
    observed=[]
    def checked(pin):
        p.check_pin(pin);observed.append(pin)
    acceptance=read(HERE/'AUDIT_ACCEPTANCE.json')
    p.require(acceptance['accepted_independent_audit'] is True and acceptance['scope']=='training_and_exact_geometry','Missing accepted independent audit')
    for name,expected_name in (('training_freeze','BANK_FREEZE.json'),('plan_freeze','COMMON_PADDING_FREEZE.json')):
        freeze_pin=acceptance[name];checked(freeze_pin)
        location=Path(freeze_pin['path']);p.require(location.name==expected_name and location.is_relative_to(HERE),'Acceptance points outside experiment')
        freeze=read(location)
        p.require(freeze.get('native_exit_zero',freeze.get('passed')) is True,'Incomplete training or plan freeze')
        records=freeze['files'];members=[]
        for pin in records:
            path=Path(pin['path']).resolve()
            p.require(path.is_relative_to(location.parent) and path not in members,'Unsafe/duplicate frozen native output')
            members.append(path);checked(pin)
        actual={q.resolve() for q in location.parent.rglob('*') if q.is_file() and q.name not in ('.gitignore',expected_name)}
        p.require(actual==set(members),'Frozen complete training/plan membership changed')
        for pin in freeze['execution_files']:checked(pin)
        if 'reservation' in freeze:checked(freeze['reservation'])
    checked(acceptance['independent_audit'])
    if 'marker_creator' in acceptance:checked(acceptance['marker_creator'])
    base=Path(closure['inherited_frozen_root']).resolve()
    # Native always loads control metadata and serialized features, and only
    # old_gate replays the historical old-padding raw reference archives.
    required=set()
    for bank in closure['rgb_banks']:
        obj=bank['object_id'];p.require(obj in closure['objects'],'Reserved quality bank')
        directory=Path(bank['rgb_training']).resolve();p.require(directory==base/'frozen_inputs'/('obj'+str(obj))/'rgb_training','Control directory changed')
        required.update([directory/'template_metadata.json',directory/('templates_tless_object_'+str(obj)+'.yml.gz')])
        if mode=='old_gate':
            raw=Path(bank['original_pilot_raw']).resolve()
            p.require(raw==base/'frozen_inputs'/('obj'+str(obj))/'original_pilot_raw','Historical raw directory changed')
            for frame in closure['development']:
                if frame['pilot']:
                    for path in ('fallback','fused'):
                        prefix='s'+str(frame['scene_id'])+'_i'+str(frame['image_id'])+'_'+path+'_raw'
                        required.add(raw/(prefix+'.csv.gz'));required.add(raw/(prefix+'_manifest.json'))
    for path in sorted(required):
        relative=path.relative_to(base).as_posix();expected=closure['private_files'].get(relative)
        p.require(expected is not None,'Unlisted inherited quality input')
        checked(dict(path=str(path),**expected))
    dataset=Path(closure['dataset_root'])
    index_pin=dict(path=str((dataset/'index.json').resolve()),**closure['private_files']['frozen_inputs/dataset_index.json'])
    checked(index_pin)
    images=[]
    if mode!='selftest':
        for frame in closure['development']:
            if mode=='development' or (frame['timing'] if mode=='timing' else frame['pilot']):
                pin=dict(path=str((dataset/frame['rgb']).resolve()),sha256=frame['rgb_sha256'],bytes=frame['rgb_bytes'])
                checked(pin);images.append(pin)
    p.require(len(images)==(0 if mode=='selftest' else 400 if mode=='development' else 64 if mode=='timing' else 8),'Quality image-byte verification schedule changed')
    return dict(passed=True,stage=mode,pins=observed,image_byte_files_checked=len(images),image_decodes=0,matcher_calls=0,
                training_image_files_checked=0,heldout_image_files_checked=0)
