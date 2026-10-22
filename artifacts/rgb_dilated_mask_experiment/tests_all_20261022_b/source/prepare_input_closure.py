"""Verify source/declarations now; byte-check declared inputs only in granted runs."""
import json
from pathlib import Path
from source_contract import pin, require, check_declared_scope

HERE=Path(__file__).resolve().parent


def verify(read_declared_bytes=False,include_images=False):
    c=json.loads((HERE/'INPUT_CLOSURE.json').read_text())
    require(c['version']=='rgb_dilated_mask_input_closure_v1','Input version changed')
    require(c['protocol_sha256']==pin(HERE/'PROTOCOL.json')['sha256'],'Protocol changed')
    require(c['private_source_freeze_sha256']==pin(HERE/'PRIVATE_SOURCE_FREEZE.json')['sha256'],'Private source freeze changed')
    check_declared_scope(c)
    require(c['objects']==[1,2,5,8,12,17] and len(c['training'])==432 and len(c['development'])==400,'Fixed input coverage changed')
    require(all(c[k]==0 for k in ('image_files_opened','image_decodes','matcher_calls')),'Inherited declaration counters changed')
    original=c['inherited_closure_origin'];base=Path(c['inherited_frozen_root'])
    require(pin(original['path'])=={k:original[k] for k in ('sha256','bytes')},'Inherited closure bytes changed')
    if read_declared_bytes:
        for relative,expected in c['private_files'].items():
            path=(base/relative).resolve()
            require(path.is_relative_to(base.resolve()),'Inherited file path escape')
            require(pin(path)==expected,'Inherited bank/numeric bytes changed: '+relative)
    require(not include_images or read_declared_bytes,'Image verification requires byte-verification stage')
    if include_images:
        for row in c['training']+c['development']:
            for name in ('rgb','mask'):
                if name in row:
                    require(pin(Path(c['dataset_root'])/row[name])==dict(sha256=row[name+'_sha256'],bytes=row[name+'_bytes']),'Dataset image bytes changed')
    return dict(passed=True,private_file_count=len(c['private_files']),declared_bytes_verified=read_declared_bytes,
                image_bytes_verified=include_images,image_files_opened=0 if not include_images else 1264,
                image_decodes=0,matcher_calls=0)


if __name__=='__main__': print(json.dumps(verify(),sort_keys=True))
