"""Independent exact numeric geometry audit; no planner/scanner algorithm imports.

Only strict_bank_reader.parse_bank is shared for the YAML grammar. All feature
extents, own-origin/canvas checks, layer requirements, alignment, resource gates
and report comparisons are implemented here from the frozen specification.
This does not decode images, execute native code, or audit training selection.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
EXPERIMENT=HERE.parent
if str(EXPERIMENT/'independent') not in sys.path:sys.path.insert(0,str(EXPERIMENT/'independent'))
from strict_bank_reader import parse_bank

OBJECTS=(1,2,5,8,12,17)
ARMS=(('C0','control','rgb_control'),('P','pooled','rgb_pooled_features'),('B','stratified','rgb_stratified_features'))
JSON_LIMIT=64*1024*1024
BANK_LIMIT=512*1024*1024
CSV_LIMIT=16*1024*1024
U64_MAX=(1<<64)-1


def require(value,message):
    if not value:raise ValueError(message)


def checked_u64(value):
    require(type(value) is int and value>=0,'Unsigned integer required')
    if value>U64_MAX:raise OverflowError('Independent geometry uint64 overflow')
    return value


def common_plan(required_width,required_height,loaded_layers):
    """Frozen two-level formula, independently implemented with wide integers."""
    width_need=max(848,checked_u64(required_width));height_need=max(832,checked_u64(required_height))
    alignment=math.lcm(4,2*8)
    # The inherited helper checks the addition used by ceil alignment as well.
    width=checked_u64((checked_u64(width_need+alignment-1)//alignment)*alignment)
    height=checked_u64((checked_u64(height_need+alignment-1)//alignment)*alignment)
    pixels=checked_u64(width*height);memory=checked_u64(pixels*512)
    require(width<=2048 and height<=2048 and pixels<=2097152 and memory<=1073741824,
            'Independent full-bank geometry exceeds frozen resource limits')
    return dict(source_size=[720,540],width=width,height=height,alignment=alignment,
                padding_ltrb=[64,64,width-720-64,height-540-64],pixels=pixels,
                estimated_dynamic_bytes=memory,banks=18,loaded_layers=loaded_layers,
                geometry_feasible=1,development_images_decoded=0,matcher_calls=0)


def pin_data(path,data):
    return {'path':str(Path(path).resolve()),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def disk_bytes(path,maximum=BANK_LIMIT):
    path=Path(path)
    require(not path.is_symlink() and path.is_file(),'Missing/nonregular numeric evidence')
    require(path.stat().st_size<=maximum,'Actual numeric evidence exceeds bounded read')
    with path.open('rb') as stream:data=stream.read(maximum+1)
    require(len(data)<=maximum,'Numeric evidence grew past bounded read')
    return data


def file_pin(path):return pin_data(path,disk_bytes(path))


def validate_pin(pin):
    require(type(pin) is dict and set(pin)=={'path','bytes','sha256'} and type(pin['path']) is str and
            Path(pin['path']).is_absolute() and str(Path(pin['path']).resolve())==pin['path'] and
            type(pin['bytes']) is int and pin['bytes']>=0 and type(pin['sha256']) is str and
            re.fullmatch('[0-9a-f]{64}',pin['sha256']) is not None,'Complete canonical numeric pin required')


def read_pin(pin,maximum,*,read_bytes=None):
    validate_pin(pin);require(pin['bytes']<=maximum,'Declared numeric evidence exceeds bounded read')
    data=disk_bytes(pin['path'],maximum) if read_bytes is None else read_bytes(Path(pin['path']))
    require(type(data) is bytes and pin_data(pin['path'],data)==pin,'Independent acquisition pin differs: '+pin['path'])
    return data


def json_object(data):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate numeric JSON field '+key);result[key]=value
        return result
    def bad(value):raise ValueError('Invalid nonfinite JSON '+value)
    result=json.loads(data.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=bad)
    require(type(result) is dict,'Numeric evidence root must be an object')
    return result


def exact_equal(observed,expected,path='value'):
    """Compare complete keys/order/types, including bool-vs-int distinctions."""
    require(type(observed) is type(expected),'Independent type differs at '+path)
    if type(expected) is dict:
        require(set(observed)==set(expected),'Independent fields differ at '+path)
        for key in expected:exact_equal(observed[key],expected[key],path+'.'+key)
    elif type(expected) is list:
        require(len(observed)==len(expected),'Independent ordered row count differs at '+path)
        for index,(a,b) in enumerate(zip(observed,expected)):exact_equal(a,b,path+'['+str(index)+']')
    else:require(observed==expected,'Independent value differs at '+path)


def source_pins():
    # Deliberately excludes planner.py and run_geometry.py algorithm sources.
    return [file_pin(path) for path in (Path(__file__),HERE/'run_independent_geometry_audit.py',
            EXPERIMENT/'independent/strict_bank_reader.py',EXPERIMENT/'PROTOCOL.json',
            EXPERIMENT/'frozen_helpers/padding_plan.hpp')]


def preflight(inputs,training_audit):
    """Independent declaration validation; no bank payloads are needed here."""
    require(inputs.get('schema')=='rgb_stratified_geometry_inputs_v1' and inputs.get('production_promotion') is False,
            'Independent audit requires the accepted geometry input schema')
    require(not set(inputs)&{'source_size','base_padding','pyramid_t','limits','plan','geometry'},'Frozen geometry override forbidden')
    validate_pin(inputs['source_numeric_audit'])
    require(training_audit.get('schema')=='independent_stratified_training_audit_v1' and
            training_audit.get('numeric_training_audit_passed') is True and
            training_audit.get('public_numeric_training_complete') is True and
            training_audit.get('literal_only') is False and training_audit.get('comparison_feasible') is True,
            'Complete public source numeric training audit required')
    for key,expected in {'shared_poses':20736,'shared_pools':41472,'arm_attempts':41472,'layer_status_rows':82944}.items():
        actual=training_audit.get('counts',{}).get(key)
        require(type(actual) is int and actual==expected,'Source training audit schedule count differs')
    before,after=training_audit.get('output_pins_before'),training_audit.get('output_pins_after')
    require(type(before) is dict and type(after) is dict and before==after,'Source training audit output pin closure differs')
    input_pins=training_audit.get('input_pins');require(type(input_pins) is dict,'Source audit input pins missing')
    successes=training_audit.get('successful_templates')
    require(type(successes) is dict and set(successes)=={'P','B'} and all(type(successes[a]) is list and
            len(successes[a])==6 and all(type(n) is int and n>0 for n in successes[a]) for a in ('P','B')),
            'Source audit successful bank counts missing')
    run=Path(inputs['training_run']);require(run.is_absolute(),'Audited training run must be absolute');run=run.resolve()
    rows=inputs.get('banks')
    require(type(rows) is list and len(rows)==6,'Six accepted training bank rows required')
    directories={};counts={}
    for index,obj in enumerate(OBJECTS):
        row=rows[index];require(type(row) is dict and type(row.get('object_id')) is int and row['object_id']==obj,
                                'Frozen bank object order differs')
        for arm,prefix,native in ARMS:
            directory=row.get(prefix+'_training');count=row.get(prefix+'_template_count')
            require(type(directory) is str and Path(directory).is_absolute() and type(count) is int and count>0,
                    'Accepted concrete bank/count missing')
            directories[(arm,obj)]=Path(directory).resolve();counts[(arm,obj)]=count
            if arm!='C0':
                require(directories[(arm,obj)]==run/native/('obj'+str(obj)) and count==successes[arm][index],
                        'Accepted bank/count differs from source numeric training audit')
    file_rows=inputs.get('bank_files');require(type(file_rows) is list and len(file_rows)==18,'All eighteen bank file pins required')
    files={}
    for row in file_rows:
        require(type(row) is dict and set(row)=={'arm','object_id','bank','metadata'},'Bank pin fields differ')
        key=(row['arm'],row['object_id'])
        require(type(row['object_id']) is int and key in directories and key not in files,'Duplicate/unknown bank file row')
        for field,name in (('bank','templates_tless_object_'+str(key[1])+'.yml.gz'),('metadata','template_metadata.json')):
            pin=row[field];validate_pin(pin)
            require(Path(pin['path'])==directories[key]/name,'Pinned bank path differs from accepted row')
            if key[0]!='C0':
                relative=Path(pin['path']).relative_to(run).as_posix()
                require(after.get(relative)=={'bytes':pin['bytes'],'sha256':pin['sha256']},'Pinned P/B bank differs from source numeric audit')
        files[key]=row
    originals=inputs.get('original_attempts')
    require(type(originals) is list and len(originals)==6,'Six original CSV pins required')
    for index,row in enumerate(originals):
        require(type(row) is dict and set(row)=={'object_id','file'} and type(row['object_id']) is int and
                row['object_id']==OBJECTS[index],'Original CSV object order differs')
        pin=row['file'];validate_pin(pin)
        require(Path(pin['path']).suffix.lower()=='.csv' and input_pins.get(pin['path'])=={'bytes':pin['bytes'],'sha256':pin['sha256']},
                'Original pose CSV is not pinned by source numeric audit')
    return files,counts,originals


def pose_key(image,angle,scale):
    require(type(image) is int and image>=0 and type(angle) in (int,float) and type(scale) in (int,float) and
            math.isfinite(angle) and math.isfinite(scale) and scale>0,'Invalid numeric template pose')
    return image,float(angle),float(scale)


def original_canvases(data,obj):
    records=list(csv.reader(io.StringIO(data.decode('utf-8-sig'),newline='')))
    require(records and len(records[0])==len(set(records[0])),'Original CSV duplicate/missing header')
    header=records[0]
    require({'class_id','training_image','angle','scale','success','template_id','canvas'}<=set(header),
            'Original CSV geometry columns missing')
    poses={};control=[]
    def integer(value):
        require(re.fullmatch(r'-?(0|[1-9][0-9]*)',value) is not None,'Original CSV noncanonical integer')
        return int(value)
    for values in records[1:]:
        require(len(values)==len(header),'Original CSV record width differs');row=dict(zip(header,values))
        require(row['class_id']=='tless_object_'+str(obj),'Original CSV class differs')
        identity=pose_key(integer(row['training_image']),float(row['angle']),float(row['scale']))
        side=integer(row['canvas']);require(identity not in poses and 4<=side<=2048,'Duplicate/invalid original pose canvas')
        poses[identity]=side;ok=integer(row['success']);tid=integer(row['template_id'])
        require(ok in (0,1),'Original success is not binary')
        if ok:
            require(tid==len(control),'Original successful IDs are not dense');control.append((identity,side))
        else:require(tid==-1,'Original failed ID is not -1')
    require(poses and control,'Original pose schedule is empty')
    return poses,control


def recompute(inputs,training_audit,acquire):
    """Recompute every report field from records, without scanner answers."""
    files,counts,originals=preflight(inputs,training_audit)
    canvases={r['object_id']:original_canvases(acquire(r['file'],CSV_LIMIT),r['object_id']) for r in originals}
    bank_rows=[];layer_rows=[];input_files=[];features_total=0;needed_w=848;needed_h=832
    for arm,prefix,native in ARMS:
        for obj in OBJECTS:
            row=files[(arm,obj)];cls='tless_object_'+str(obj)
            compressed=acquire(row['bank'],BANK_LIMIT)
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:logical=stream.read(BANK_LIMIT+1)
                require(len(logical)<=BANK_LIMIT,'Decoded independent bank exceeds limit')
                templates=parse_bank(logical.decode('utf-8'),cls)
            except (OSError,EOFError,UnicodeError) as error:raise ValueError('Invalid independently parsed bank') from error
            metadata=json_object(acquire(row['metadata'],JSON_LIMIT))
            require(set(metadata)=={'templates'} and type(metadata['templates']) is list,'Independent metadata root differs')
            require(len(templates)==len(metadata['templates'])==counts[(arm,obj)],'Independent complete bank count differs')
            poses,control=canvases[obj]
            if arm=='C0':require(len(control)==len(templates),'C0 count differs from original complete successful schedule')
            for tid,(layers,meta) in enumerate(zip(templates,metadata['templates'])):
                require(type(meta) is dict and meta.get('class_id')==cls and type(meta.get('template_id')) is int and meta['template_id']==tid,
                        'Independent metadata template identity differs')
                identity=pose_key(meta.get('training_image_id'),meta.get('angle'),meta.get('scale'))
                require(identity in poses,'Independent metadata pose absent from original schedule');canvas=poses[identity]
                if arm=='C0':require(control[tid]==(identity,canvas),'C0 ordered successful pose differs')
                require(type(meta.get('tl_x')) is int and type(meta.get('tl_y')) is int and
                        meta['tl_x']==layers[0]['tl_x'] and meta['tl_y']==layers[0]['tl_y'],'Metadata L0 origin differs')
                require(len(layers)==2,'Independent pyramid is incomplete')
                for level,layer in enumerate(layers):
                    require(layer['pyramid_level']==level and layer['width']>0 and layer['height']>0,
                            'Malformed independent layer geometry')
                    xs=[];ys=[];ax=[];ay=[];side=canvas//(2**level)
                    for feature in layer['features']:
                        x,y,label=feature
                        require(type(x) is int and type(y) is int and type(label) is int and 0<=label<=7 and
                                0<=x<=layer['width'] and 0<=y<=layer['height'],'Independent feature extent/label invalid')
                        absolute_x=x+layer['tl_x'];absolute_y=y+layer['tl_y']
                        require(0<=absolute_x<side and 0<=absolute_y<side,'Independent feature outside own-layer training canvas')
                        xs.append(x);ys.append(y);ax.append(absolute_x);ay.append(absolute_y)
                    require(xs,'Independent layer has no selected feature');features_total+=len(xs)
                    if level==0:
                        local_w=checked_u64(layer['width']+64);local_h=checked_u64(layer['height']+64)
                    else:
                        local_w=max(layer['width'],checked_u64(max(xs)+1));local_h=max(layer['height'],checked_u64(max(ys)+1))
                    projected_w=checked_u64(local_w*(2**level));projected_h=checked_u64(local_h*(2**level))
                    needed_w=max(needed_w,projected_w);needed_h=max(needed_h,projected_h)
                    layer_rows.append(dict(level=level,width=layer['width'],height=layer['height'],tl_x=layer['tl_x'],tl_y=layer['tl_y'],
                        actual_features=len(xs),min_x=min(xs),min_y=min(ys),max_x=max(xs),max_y=max(ys),
                        min_absolute_x=min(ax),min_absolute_y=min(ay),max_absolute_x=max(ax),max_absolute_y=max(ay),
                        canvas_width=side,canvas_height=side,arm=arm,object_id=obj,class_id=cls,template_id=tid,
                        needed_width=local_w,needed_height=local_h,projected_width=projected_w,projected_height=projected_h))
            bank_rows.append(dict(arm=arm,object_id=obj,class_id=cls,templates=len(templates),layers=2*len(templates),
                                  bank=row['bank'],metadata=row['metadata'],logical_bank_bytes=len(logical)))
            input_files.extend([row['bank'],row['metadata']])
    plan=common_plan(needed_w,needed_h,len(layer_rows))
    return dict(schema='rgb_stratified_bank_geometry_report_v1',plan=plan,banks=bank_rows,scanned_banks=18,
                loaded_layers=len(layer_rows),actual_features_scanned=features_total,layer_geometry=layer_rows,
                all_features_scanned=True,feature_filtering=False,pose_filtering=False,input_bank_files=input_files,
                original_attempts=[r['file'] for r in originals],source_numeric_audit=inputs['source_numeric_audit'],
                image_reads=0,image_decodes=0,native_executions=0,matcher_calls=0,production_promotion=False)


def audit_geometry(input_pin,scanner_pin,*,read_bytes=None):
    acquired={};auditor_before=source_pins()
    def acquire(pin,maximum):
        data=read_pin(pin,maximum,read_bytes=read_bytes)
        if pin['path'] in acquired:exact_equal(acquired[pin['path']][0],pin,'repeated_input_pin')
        acquired[pin['path']]=(dict(pin),maximum)
        return data
    for pin in (input_pin,scanner_pin):
        validate_pin(pin);require(Path(pin['path']).suffix.lower()=='.json','Geometry/audit freezes must be numeric JSON')
    inputs=json_object(acquire(input_pin,JSON_LIMIT));freeze=json_object(acquire(scanner_pin,JSON_LIMIT))
    require(freeze.get('schema')=='rgb_stratified_common_geometry_freeze_v1' and
            freeze.get('exact_geometry_computed') is True and freeze.get('independent_geometry_audit_required') is True and
            freeze.get('numeric_audit_passed') is False and freeze.get('production_promotion') is False,
            'Unaccepted scanner geometry freeze required')
    exact_equal(freeze['training_freeze'],input_pin,'scanner.training_freeze')
    exact_equal(freeze['source_numeric_audit'],inputs['source_numeric_audit'],'scanner.source_numeric_audit')
    for name in ('image_reads','image_decodes','native_executions','matcher_calls'):
        require(type(freeze.get(name)) is int and freeze[name]==0,'Scanner freeze nonzero/invalid '+name)
    training_audit=json_object(acquire(inputs['source_numeric_audit'],JSON_LIMIT))
    preflight(inputs,training_audit)
    scanner_sources=freeze.get('source_pins')
    require(type(scanner_sources) is list and len(scanner_sources)==4 and
            {Path(p['path']).name for p in scanner_sources}=={'run_geometry.py','planner.py','strict_bank_reader.py','PROTOCOL.json'},
            'Scanner complete source pin set differs')
    for pin in scanner_sources:acquire(pin,JSON_LIMIT)
    acquire(freeze['reservation'],JSON_LIMIT)
    observed=json_object(acquire(freeze['geometry_report'],BANK_LIMIT))
    standalone=json_object(acquire(freeze['common_padding_plan'],JSON_LIMIT))
    expected=recompute(inputs,training_audit,acquire)
    exact_equal(observed,expected,'scanner_report')
    exact_equal(freeze['plan'],expected['plan'],'scanner_freeze.plan')
    exact_equal(standalone,expected['plan'],'standalone.plan')
    pins_before=[row[0] for key,row in sorted(acquired.items())]
    for pin,maximum in acquired.values():read_pin(pin,maximum,read_bytes=read_bytes)
    auditor_after=source_pins();exact_equal(auditor_after,auditor_before,'independent_auditor_sources')
    digest=hashlib.sha256(json.dumps(expected,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return dict(schema='rgb_stratified_independent_geometry_audit_v1',passed=True,accepted_independent_audit=True,
                scope='exact_geometry_only',numeric_audit_passed=True,production_promotion=False,
                training_freeze=input_pin,geometry_freeze=scanner_pin,source_numeric_audit=inputs['source_numeric_audit'],
                geometry_report=freeze['geometry_report'],computed_plan=expected['plan'],
                scanned_banks=18,loaded_layers=expected['loaded_layers'],actual_features_scanned=expected['actual_features_scanned'],
                all_report_fields_compared=True,report_recomputed_sha256=digest,
                input_pins={p['path']:{k:p[k] for k in ('bytes','sha256')} for p in pins_before},
                input_pins_before=pins_before,input_pins_after=pins_before,
                auditor_sources_before=auditor_before,auditor_sources_after=auditor_after,
                image_reads=0,image_decodes=0,native_executions=0,matcher_calls=0,
                limitations=['Strict YAML grammar parser shared; all geometry calculations independent',
                             'Training sampler/native runtime/resource acceptance remains separate',
                             'Geometry correctness does not establish accuracy or performance'])


def write_fresh_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','scanner-freeze'):
        parser.add_argument('--'+name,required=True,type=Path)
        parser.add_argument('--'+name+'-bytes',required=True,type=int)
        parser.add_argument('--'+name+'-sha256',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(arguments);output=args.output.resolve()
    require(not output.exists(),'Independent geometry child output must be fresh');output.mkdir(parents=True)
    ip=dict(path=str(args.inputs.resolve()),bytes=args.inputs_bytes,sha256=args.inputs_sha256)
    fp=dict(path=str(args.scanner_freeze.resolve()),bytes=args.scanner_freeze_bytes,sha256=args.scanner_freeze_sha256)
    try:
        result=audit_geometry(ip,fp)
    except (ValueError,TypeError,KeyError,OverflowError,OSError,EOFError) as error:
        result=dict(schema='rgb_stratified_independent_geometry_audit_v1',passed=False,accepted_independent_audit=False,
                    scope='exact_geometry_only',numeric_audit_passed=False,production_promotion=False,
                    error_type=type(error).__name__,error=str(error),failure_preserved=True,image_reads=0,native_executions=0)
    write_fresh_json(output/'INDEPENDENT_GEOMETRY_AUDIT.json',result)
    print(json.dumps(dict(numeric_audit_passed=result['numeric_audit_passed'],scope=result['scope'])))
    return 0 if result['numeric_audit_passed'] else 2


if __name__=='__main__':raise SystemExit(main())
