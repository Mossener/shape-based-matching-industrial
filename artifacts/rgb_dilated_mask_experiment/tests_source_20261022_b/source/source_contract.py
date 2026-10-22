"""Pure standard-library guards and literal toy reference, never native IO."""
import hashlib
from pathlib import Path

OBJECTS=[1,2,5,8,12,17]
HELDOUT={11,14,15,16,17,18,19,20}


def require(value,message):
    if not value: raise ValueError(message)


def pin(path):
    data=Path(path).read_bytes()
    return dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def check_declared_scope(value):
    require(set(value['objects']).issubset(OBJECTS),'Reserved/unregistered object')
    for row in value.get('development',[]):
        require(int(row['scene_id']) not in HELDOUT,'Heldout scene')
    for row in value.get('training',[]):
        require(row['object_id'] in OBJECTS,'Reserved training object')
        for name in ('rgb','mask'):
            path=str(row.get(name,'')).replace('\\','/').lower()
            require(not any(word in path for word in ('magnet','smd','private')),'Private input path')
            require('..' not in Path(path).parts,'Unsafe input path')


def validate_attempts(rows,expected):
    require(len(rows)==len(expected),'Missing or duplicate attempt')
    seen=set();successful=0
    for row in rows:
        pose=tuple(row['pose'])
        require(pose in expected and pose not in seen,'Missing/duplicate pose')
        seen.add(pose)
        require(row['geometry']==expected[pose],'Changed official geometry')
        require(row['success'] in (0,1),'Invalid success flag')
        if row['success']:
            require(row['template_id']==successful and row['error']=='','Non-dense ID or invalid success')
            require(len(row['features'])==2 and all(n>0 for n in row['features']),'Missing actual feature layer')
            successful+=1
        else:
            require(row['template_id']==-1 and row['features']==[0,0] and
                    row['error'] in ('insufficient_features','opencv_exception'),'Invalid failure evidence')
    return successful


def toy_morphology(mask,operation):
    require(operation in ('dilate','erode'),'Unknown toy operator')
    require(mask and mask[0] and all(len(r)==len(mask[0]) for r in mask),'Rectangular nonempty toy mask required')
    height,width=len(mask),len(mask[0]);choose=max if operation=='dilate' else min
    return [[choose(mask[min(height-1,max(0,y+dy))][min(width-1,max(0,x+dx))]
                    for dy in (-1,0,1) for dx in (-1,0,1)) for x in range(width)] for y in range(height)]
