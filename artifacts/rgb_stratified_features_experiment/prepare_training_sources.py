"""Copy and attest exact original V11 source bytes; no image/bank reads."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'rgb_dilated_mask_experiment'
REV='b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
def record(data):return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def require(v,m):
    if not v:raise ValueError(m)
def prepare():
    require(not (HERE/'TRAINING_SOURCE_FREEZE.json').exists(),'Preserve existing snapshot')
    origin=BASE/'PRIVATE_SOURCE_FREEZE.json';manifest=json.loads(origin.read_text())
    require(manifest['git_revision']==REV and len(manifest['original_files'])==23,'Original V11 source scope changed')
    pending=[]
    for name,pin in manifest['original_files'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Unsafe source member')
        data=(BASE/'control_v11'/name).read_bytes();require(record(data)==pin,'Original source changed: '+name)
        pending.append(('control_v11',name,data,pin))
    for name,pin in manifest['helpers'].items():
        data=(BASE/'frozen_helpers'/name).read_bytes();require(record(data)=={k:pin[k] for k in ('bytes','sha256')},'Helper changed: '+name)
        pending.append(('frozen_helpers',name,data,record(data)))
    for directory in ('control_v11','frozen_helpers'):require(not (HERE/directory).exists(),'Fresh source directory required')
    for directory,name,data,pin in pending:
        dest=HERE/directory/name;dest.parent.mkdir(exist_ok=True,parents=True);dest.write_bytes(data)
    result=dict(schema='rgb_stratified_exact_v11_training_source_v1',git_revision=REV,
                origin=dict(path=str(origin.resolve()),**record(origin.read_bytes())),
                files={name:pin for directory,name,_,pin in pending if directory=='control_v11'},
                helpers={name:pin for directory,name,_,pin in pending if directory=='frozen_helpers'},
                sole_core_delta=None,core_translation_unit=str(HERE/'control_v11/line2Dup.cpp'),
                image_decodes=0,matcher_calls=0,bank_payload_reads=0)
    (HERE/'TRAINING_SOURCE_FREEZE.json').write_text(json.dumps(result,indent=2)+'\n')
    # Reuse the already tested local build-closure utility byte-for-byte.
    utility=BASE/'native_provenance.py';dest=HERE/'native_provenance.py'
    require(not dest.exists(),'Fresh utility destination required');dest.write_bytes(utility.read_bytes())
    (HERE/'NATIVE_PROVENANCE_ORIGIN.json').write_text(json.dumps(dict(origin=str(utility.resolve()),**record(utility.read_bytes())),indent=2)+'\n')
    print(json.dumps(dict(passed=True,core_files=23,helpers=3,core_delta=False,image_decodes=0,bank_payload_reads=0)))
if __name__=='__main__':prepare()
