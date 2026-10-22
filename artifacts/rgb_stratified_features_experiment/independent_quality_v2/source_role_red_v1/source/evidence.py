"""Strict pinned numeric file access; no image or native dependencies."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re

IMAGE_SUFFIXES={'.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp','.smd'}


def need(condition,message):
    if not condition: raise ValueError(message)


def sha(data): return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result={}
    for key,value in pairs:
        need(key not in result,'duplicate JSON key: '+key)
        result[key]=value
    return result


def loads(data):
    def bad(value): raise ValueError('nonfinite JSON token: '+value)
    return json.loads(data.decode('utf-8-sig'),object_pairs_hook=unique_object,parse_constant=bad)


def integer(value,minimum=None,maximum=None):
    need(type(value) is not bool,'boolean integer refused')
    text=str(value)
    need(re.fullmatch(r'(?:0|-?[1-9][0-9]*)',text) is not None,'noncanonical integer')
    number=int(text)
    need(minimum is None or number>=minimum,'integer below bound')
    need(maximum is None or number<=maximum,'integer above bound')
    return number


def number(value,positive=False):
    need(type(value) is not bool,'boolean number refused')
    result=float(value)
    need(math.isfinite(result) and (not positive or result>0),'nonfinite/nonpositive number')
    return result


def native_count(value,maximum=None):
    """FileStorage writes some integral counters as JSON doubles."""
    need(type(value) in (int,float),'native integral counter required')
    result=number(value)
    need(result>=0 and result.is_integer() and (maximum is None or result<=maximum),
         'native integral counter outside bound')
    return int(result)


def table(data,header):
    reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''))
    need(reader.fieldnames==list(header),'CSV schema differs')
    rows=list(reader)
    need(all(None not in row and None not in row.values() for row in rows),'CSV width differs')
    return rows


def pin_schema(pin):
    need(isinstance(pin,dict) and set(pin)=={'path','bytes','sha256'},'complete file pin required')
    need(isinstance(pin['path'],str) and Path(pin['path']).is_absolute(),'absolute pin path required')
    need(type(pin['bytes']) is int and 0<=pin['bytes']<=4*1024**3,'pin size out of bound')
    need(isinstance(pin['sha256'],str) and re.fullmatch('[0-9a-f]{64}',pin['sha256']) is not None,
         'invalid SHA256 pin')


class Reader:
    """Only registered pins may be read, and every read verifies size/SHA."""
    def __init__(self,root):
        self.root=Path(root).resolve(); self.pins={}; self.seen={}

    def allowed(self,path):
        path=Path(path)
        need(all(not part.is_symlink() for part in (path,*path.parents)),'numeric symlink refused')
        resolved=path.resolve(strict=True)
        need(resolved.is_relative_to(self.root),'numeric path escaped root')
        need(resolved.suffix.lower() not in IMAGE_SUFFIXES,'image/private byte access refused')
        datasets=self.root/'datasets'
        need(not resolved.is_relative_to(datasets) or resolved==datasets/'tless_expanded/index.json',
             'dataset access outside frozen numeric index refused')
        return resolved

    def register(self,pin):
        pin_schema(pin); path=self.allowed(pin['path'])
        key=str(path)
        canonical=dict(pin,path=key)
        need(self.pins.setdefault(key,canonical)==canonical,'conflicting numeric pin')
        return canonical

    def read(self,path):
        path=self.allowed(path); key=str(path)
        need(key in self.pins,'unregistered numeric read: '+key)
        pin=self.pins[key]
        need(path.stat().st_size==pin['bytes'],'numeric pin size changed: '+key)
        data=path.read_bytes()
        need(len(data)==pin['bytes'] and sha(data)==pin['sha256'],'numeric SHA changed: '+key)
        self.seen[key]=pin
        return data

    def check(self,pin):
        pin=self.register(pin)
        return self.read(pin['path'])

    def json(self,path): return loads(self.read(path))

    def recheck(self):
        for pin in list(self.seen.values()): self.check(pin)


def rows_by(rows,key):
    result={}
    for row in rows:
        identity=key(row)
        need(identity not in result,'duplicate row identity')
        result[identity]=row
    return result
