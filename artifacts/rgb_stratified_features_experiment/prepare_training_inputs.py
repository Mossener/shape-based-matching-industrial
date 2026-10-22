"""Freeze inherited training declarations and attempt geometry, without images."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ORIGIN=HERE.parent/'rgb_dilated_mask_experiment/INPUT_CLOSURE.json'
EXPECTED='9f0a6fd135716495cb51cde6918a022fd6514e2177941cd453ff6eb19a83f2ff'
OBJECTS=[1,2,5,8,12,17]
def pin(path):
    data=path.read_bytes();return dict(path=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def require(v,m):
    if not v:raise ValueError(m)
def main():
    output=HERE/'TRAINING_INPUT_FREEZE.json';require(not output.exists(),'Preserve existing input freeze')
    origin=pin(ORIGIN);require(origin['sha256']==EXPECTED,'Frozen inherited closure changed')
    data=json.loads(ORIGIN.read_text());require(data['objects']==OBJECTS,'Object scope changed')
    rows=data['training'];require(len(rows)==432,'Complete 432 training pairs required')
    seen=set()
    for row in rows:
        obj,image=row['object_id'],row['image_id'];require(obj in OBJECTS and (obj,image) not in seen,'Wrong/duplicate training view');seen.add((obj,image))
        require(row['rgb']==f'train_primesense/{obj:06d}/rgb/{image:06d}.png' and row['mask']==f'train_primesense/{obj:06d}/mask/{image:06d}_000000.png','Unexpected training path')
        for name in ('rgb','mask'):
            require(len(row[name+'_sha256'])==64 and row[name+'_bytes']>0,'Invalid inherited image pin')
    require(all(sum(obj==o for obj,_ in seen)==72 for o in OBJECTS),'72 views per object required')
    require([b['object_id'] for b in data['rgb_banks']]==OBJECTS,'Original bank order changed')
    attempts=[dict(object_id=b['object_id'],pin=pin(Path(b['rgb_training'])/'template_attempts.csv')) for b in data['rgb_banks']]
    result=dict(schema='rgb_stratified_training_inputs_v1',origin=origin,dataset_root=data['dataset_root'],objects=OBJECTS,
                training=rows,original_attempts=attempts,expected_shared_poses=20736,expected_pools=41472,
                expected_rgb_decodes=432,expected_mask_decodes=432,expected_matcher_calls=0,
                image_bytes_read=0,image_decodes=0,bank_payload_reads=0,matcher_calls=0,
                protocol=pin(HERE/'PROTOCOL.json'),design_errata=pin(HERE/'DESIGN_ERRATA_1.md'),pack_format=pin(HERE/'PACK_FORMAT_V1.md'))
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,training_pairs=432,numeric_geometry_files=6,image_bytes_read=0,bank_payload_reads=0)))
if __name__=='__main__':main()
