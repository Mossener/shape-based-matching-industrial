"""Narrow source/numeric boundary. Image byte access is deliberately absent."""
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PROTOCOL_SHA='e53932033a1460a89d6462b37b3aa863c39d4b29917cefbc3de332dceacbaa88'
DESIGN_SHA='c68320fec1a818edcf268fc5ec2c082ac216e175c0402d1a99bbd27a37c65e77'


def need(value, reason):
    if not value:raise ValueError(reason)


def numeric_path(path,root=ROOT):
    path,root=Path(path).resolve(),Path(root).resolve()
    need(path.is_relative_to(root),'Numeric path outside repository')
    name=path.name.lower()
    need(path.suffix.lower() in ('.json','.csv','.md','.py','.cpp','.hpp','.h','.txt') or
         name.endswith(('.csv.gz','.yml.gz','.jsonl.gz')),'Non-numeric/source file forbidden')
    return path


def data(path):
    return numeric_path(path).read_bytes()


def pin(path):
    path=numeric_path(path);content=path.read_bytes()
    return dict(path=str(path),bytes=len(content),sha256=hashlib.sha256(content).hexdigest())


def check(record):
    path=Path(record['path']);path=path if path.is_absolute() else ROOT/path
    actual=pin(path)
    need(actual['bytes']==record['bytes'] and actual['sha256']==record['sha256'],'Numeric/source SHA or size changed: '+str(path))


def load(path):
    return json.loads(data(path).decode('utf-8-sig'))


def specification():
    for name,expected in [('PROTOCOL.json',PROTOCOL_SHA),('DESIGN.md',DESIGN_SHA)]:
        need(hashlib.sha256(data(HERE/name)).hexdigest()==expected,'Frozen design/protocol changed')
    value=load(HERE/'PROTOCOL.json')
    for record in value['input_pins']+value['attempt_table_pins']+[value['design_pin']]:check(record)
    return value


def validate_masks(records,dataset_root,objects):
    root=Path(dataset_root).resolve();result=[];seen=set()
    for q in records:
        need(set(q)=={'object_id','image_id','path','bytes','sha256'},'Mask allowlist schema')
        obj,image=q['object_id'],q['image_id']
        need(type(obj) is int and obj in objects and obj not in (25,29),'Forbidden training object')
        need(type(image) is int and 0<=image<=999999,'Mask image id')
        expected=f'train_primesense/{obj:06d}/mask/{image:06d}_000000.png'
        need(q['path']==expected,'Non-allowlisted training mask path')
        path=(root/q['path']).resolve()
        need(path.is_relative_to(root) and path not in seen,'Mask escape or duplicate')
        need(type(q['bytes']) is int and q['bytes']>0 and re.fullmatch('[0-9a-f]{64}',q['sha256']),'Mask pin syntax')
        seen.add(path);result.append(dict(q,path=str(path)))
    return result
