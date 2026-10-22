"""Exact small contracts for the isolated Phase 1 numeric/native boundary."""
from pathlib import Path
import hashlib
import json
import re
import struct

OBJECTS = (1, 2, 5, 8, 12, 17)
SCENES = (1, 4, 6, 7, 8, 10, 12, 13)


def require(value, message):
    if not value:
        raise ValueError(message)


def scope(identities):
    identities = list(identities)
    require(len(set(identities)) == len(identities), 'Duplicate GT identity')
    require(all(len(row) == 4 and all(isinstance(v, int) for v in row) and
                row[0] in OBJECTS and row[1] in SCENES and min(row[2:]) >= 0 for row in identities),
            'GT identity outside fixed development scope')
    frames = {tuple(row[:3]) for row in identities}
    return dict(identities=len(identities), object_frames=len(frames),
                image_frames=len({row[1:] for row in frames}), full_class_search_replays=2*len(frames))


def score(raw, count):
    require(isinstance(raw, int) and isinstance(count, int) and 0 < count < 8192 and 0 <= raw <= 4*count,
            'Invalid raw score/count')
    product = struct.unpack('<f', struct.pack('<f', raw*100.))[0]
    return struct.unpack('<f', struct.pack('<f', product/(4*count)))[0]


def thresholds(raw, count):
    value = score(raw, count)
    return value > 85., value >= 85.


def reserve(directory, stage, run, pins):
    require(re.fullmatch(r'[a-z][a-z0-9_]*', stage) is not None, 'Unsafe stage name')
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory/(stage+'.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(dict(stage=stage, output=str(Path(run).resolve()), inputs=pins,
                       one_shot=True, incomplete_run_still_consumes_reservation=True), stream, indent=2)
        stream.write('\n')
    return path


def pin(path):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def check(value):
    require(pin(value['path']) == value, 'Pinned bytes changed: '+value['path'])
