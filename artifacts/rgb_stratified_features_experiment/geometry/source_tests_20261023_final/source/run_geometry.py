"""One-shot pinned numeric-only common geometry scan for all eighteen banks.

Reserve only after the root has accepted training.  Reserve mode reads the
input declaration and source numeric-audit JSON, never bank payloads.  Execute
consumes the reservation once, scans all selected features with the independent
strict reader, and writes fresh geometry artifacts.  There are no image or
native-code dependencies.  A failure is retained; this runner never retries.
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
import sys
from typing import Callable

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
INDEPENDENT = EXPERIMENT / 'independent'
if str(INDEPENDENT) not in sys.path:
    sys.path.insert(0, str(INDEPENDENT))
import strict_bank_reader
from planner import Bank, BankTemplate, OBJECTS, plan_all, bank_from_records

ARM_ROWS = (('C0','control','rgb_control'),('P','pooled','rgb_pooled_features'),
            ('B','stratified','rgb_stratified_features'))
INPUT_SCHEMA = 'rgb_stratified_geometry_inputs_v1'
RESERVATION_SCHEMA = 'rgb_stratified_geometry_reservation_v1'
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_BANK_BYTES = 512 * 1024 * 1024
MAX_CSV_BYTES = 16 * 1024 * 1024
Read = Callable[[Path], bytes]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _disk_read(path):
    path = Path(path)
    require(not path.is_symlink(), 'Pinned source cannot be a symlink')
    return path.read_bytes()


def pin_bytes(path, contents):
    return dict(path=str(Path(path).resolve()), bytes=len(contents),
                sha256=hashlib.sha256(contents).hexdigest())


def file_pin(path):
    return pin_bytes(path, _disk_read(path))


def validate_pin(pin):
    require(isinstance(pin,dict) and set(pin)=={'path','bytes','sha256'} and
            isinstance(pin['path'],str) and Path(pin['path']).is_absolute() and
            type(pin['bytes']) is int and pin['bytes']>=0 and
            isinstance(pin['sha256'],str) and len(pin['sha256'])==64 and
            all(ch in '0123456789abcdef' for ch in pin['sha256']), 'Complete canonical file pin required')
    require(str(Path(pin['path']).resolve())==pin['path'], 'Pinned path must be canonical absolute path')


def read_checked(pin, maximum, *, read_bytes=_disk_read):
    validate_pin(pin)
    require(pin['bytes']<=maximum, 'Pinned numeric artifact exceeds bounded read limit')
    data=read_bytes(Path(pin['path']))
    require(isinstance(data,bytes) and pin_bytes(pin['path'],data)==pin,
            'Numeric/bank content pin differs: '+pin['path'])
    return data


def _json(data):
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate JSON key: '+key)
            result[key]=value
        return result
    def reject(value):
        raise ValueError('Nonfinite JSON constant: '+value)
    value=json.loads(data.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=reject)
    require(isinstance(value,dict),'Numeric JSON root must be an object')
    return value


def _small(pin):
    return {name:pin[name] for name in ('bytes','sha256')}


def validate_inputs(inputs, audit):
    """Validate every declaration and audit association before bank reads."""
    require(isinstance(inputs,dict) and inputs.get('schema')==INPUT_SCHEMA,'Geometry input schema differs')
    require(inputs.get('production_promotion') is False,'Geometry cannot promote production')
    require(not set(inputs).intersection({'source_size','base_padding','pyramid_t','limits','plan','geometry'}),
            'Geometry input cannot override frozen query geometry/resource limits')
    validate_pin(inputs['source_numeric_audit'])
    require(Path(inputs['source_numeric_audit']['path']).suffix.lower()=='.json','Source numeric audit must be JSON')
    require(isinstance(audit,dict) and audit.get('schema')=='independent_stratified_training_audit_v1' and
            audit.get('numeric_training_audit_passed') is True and
            audit.get('public_numeric_training_complete') is True and audit.get('literal_only') is False and
            audit.get('comparison_feasible') is True,'Complete successful public numeric training audit required')
    counts=audit.get('counts',{})
    require(isinstance(counts,dict) and all(type(counts.get(name)) is int and counts[name]==value for name,value in
            (('shared_poses',20736),('shared_pools',41472),('arm_attempts',41472),('layer_status_rows',82944))),
            'Source numeric training audit does not cover the complete public schedule')
    require(audit.get('output_pins_before')==audit.get('output_pins_after') and
            isinstance(audit.get('output_pins_after'),dict),'Numeric audit output closure changed')
    require(isinstance(audit.get('input_pins'),dict),'Numeric audit must pin original numeric inputs')
    successful=audit.get('successful_templates')
    require(isinstance(successful,dict) and set(successful)=={'P','B'} and
            all(isinstance(successful[a],list) and len(successful[a])==6 and
                all(type(n) is int and n>0 for n in successful[a]) for a in ('P','B')),
            'Numeric audit successful-template counts are incomplete')
    training_run=Path(inputs['training_run'])
    require(training_run.is_absolute(),'Training run path must be absolute')
    training_run=training_run.resolve()
    rows=inputs.get('banks')
    require(isinstance(rows,list) and [r.get('object_id') if isinstance(r,dict) else None for r in rows]==list(OBJECTS),
            'Accepted bank rows must be ordered [1,2,5,8,12,17]')
    by_key={}
    for index,row in enumerate(rows):
        require(type(row['object_id']) is int,'Bank object ID must be an integer')
        for arm,prefix,native in ARM_ROWS:
            directory=row.get(prefix+'_training'); count=row.get(prefix+'_template_count')
            require(isinstance(directory,str) and Path(directory).is_absolute(), 'Accepted bank directory must be absolute')
            require(type(count) is int and count>0,'Accepted template count must be a positive integer')
            directory=Path(directory).resolve()
            if arm!='C0':
                require(directory==training_run/native/('obj'+str(row['object_id'])),
                        'P/B bank directory differs from audited training run')
                require(count==successful[arm][index],'Accepted P/B count differs from numeric audit')
            by_key[(arm,row['object_id'])]={'directory':directory,'count':count}
    file_rows=inputs.get('bank_files')
    require(isinstance(file_rows,list) and len(file_rows)==18,'Eighteen explicitly pinned banks required')
    ordered_files={}
    for row in file_rows:
        require(isinstance(row,dict) and set(row)=={'arm','object_id','bank','metadata'},'Bank pin row fields differ')
        key=(row['arm'],row['object_id'])
        require(type(row['object_id']) is int and key in by_key and key not in ordered_files,
                'Unexpected/duplicate pinned bank')
        base=by_key[key]['directory']; cls='tless_object_'+str(key[1])
        for name,filename in (('bank','templates_'+cls+'.yml.gz'),('metadata','template_metadata.json')):
            pin=row[name];validate_pin(pin)
            require(Path(pin['path'])==base/filename,'Bank pin path differs from accepted bank directory')
            if key[0]!='C0':
                relative=Path(pin['path']).relative_to(training_run).as_posix()
                require(audit['output_pins_after'].get(relative)==_small(pin),
                        'P/B bank pin differs from source numeric audit')
        ordered_files[key]=dict(row,count=by_key[key]['count'])
    originals=inputs.get('original_attempts')
    require(isinstance(originals,list) and [r.get('object_id') if isinstance(r,dict) else None for r in originals]==list(OBJECTS),
            'Six ordered original attempt CSV pins required')
    for row in originals:
        require(set(row)=={'object_id','file'} and type(row['object_id']) is int,'Original attempt row fields differ')
        validate_pin(row['file'])
        require(Path(row['file']['path']).suffix.lower()=='.csv','Original attempts must be numeric CSV')
        require(audit['input_pins'].get(row['file']['path'])==_small(row['file']),
                'Original attempt CSV is not bound to source numeric audit')
    return ordered_files,originals


def _integer(text, name):
    require(isinstance(text,str) and text and str(int(text))==text,'Canonical integer required for '+name)
    return int(text)


def _pose(image,angle,scale):
    require(type(image) is int and image>=0 and type(angle) in (int,float) and
            type(scale) in (int,float) and math.isfinite(angle) and math.isfinite(scale) and scale>0,
            'Invalid metadata pose identity')
    return image,float(angle),float(scale)


def _original_canvas_maps(contents,obj):
    rows=list(csv.reader(io.StringIO(contents.decode('utf-8-sig'),newline='')))
    require(bool(rows) and len(rows[0])==len(set(rows[0])),'Duplicate/missing original CSV header')
    required={'class_id','training_image','angle','scale','success','template_id','canvas'}
    require(required.issubset(rows[0]) and all(len(row)==len(rows[0]) for row in rows[1:]),'Malformed original CSV')
    poses={}; successful={}
    for raw in rows[1:]:
        row=dict(zip(rows[0],raw))
        require(row['class_id']=='tless_object_'+str(obj),'Original attempt class differs')
        image=_integer(row['training_image'],'training_image');angle=float(row['angle']);scale=float(row['scale'])
        key=_pose(image,angle,scale);canvas=_integer(row['canvas'],'canvas')
        require(key not in poses and 4<=canvas<=2048,'Duplicate/invalid original pose canvas')
        poses[key]=canvas
        ok=_integer(row['success'],'success');tid=_integer(row['template_id'],'template_id')
        require(ok in (0,1),'Original attempt success must be binary')
        if ok:
            require(tid==len(successful),'Original successful template IDs must be dense')
            successful[tid]=(key,canvas)
        else:
            require(tid==-1,'Failed original template ID must be -1')
    require(poses and successful,'Original pose/canvas evidence is empty')
    return poses,successful


def _read_bank(pin,read_bytes):
    compressed=read_checked(pin,MAX_BANK_BYTES,read_bytes=read_bytes)
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            decoded=stream.read(MAX_BANK_BYTES+1)
        require(len(decoded)<=MAX_BANK_BYTES,'Decoded bank exceeds bounded read limit')
        return decoded.decode('utf-8'),len(decoded)
    except (OSError,EOFError,UnicodeError) as error:
        raise ValueError('Invalid compressed numeric bank') from error


def build_geometry(inputs,audit,*,read_bytes=_disk_read):
    files,originals=validate_inputs(inputs,audit)
    canvas_maps={row['object_id']:_original_canvas_maps(
        read_checked(row['file'],MAX_CSV_BYTES,read_bytes=read_bytes),row['object_id']) for row in originals}
    loaded=[];bank_reports=[];feature_count=0;read_pins=[]
    for arm,prefix,native in ARM_ROWS:
        for obj in OBJECTS:
            record=files[(arm,obj)]; cls='tless_object_'+str(obj)
            text,logical_bytes=_read_bank(record['bank'],read_bytes)
            raw=strict_bank_reader.parse_bank(text,cls)
            meta=_json(read_checked(record['metadata'],MAX_JSON_BYTES,read_bytes=read_bytes))
            require(set(meta)=={'templates'} and isinstance(meta['templates'],list),'Historical metadata root differs')
            require(len(raw)==record['count']==len(meta['templates']),'Actual bank/metadata count differs from accepted count')
            poses,original_successful=canvas_maps[obj]
            if arm=='C0':require(len(original_successful)==record['count'],'C0 count differs from original successful attempts')
            base=bank_from_records(arm,obj,cls,raw);templates=[]
            for tid,(layers,metadata) in enumerate(zip(raw,meta['templates'])):
                require(isinstance(metadata,dict) and metadata.get('class_id')==cls and
                        type(metadata.get('template_id')) is int and metadata['template_id']==tid,'Metadata ID/class differs')
                key=_pose(metadata.get('training_image_id'),metadata.get('angle'),metadata.get('scale'))
                require(key in poses,'Metadata pose is absent from original canvas schedule')
                canvas=poses[key]
                if arm=='C0':require(original_successful[tid]==(key,canvas),'C0 metadata pose differs from original successful template')
                require(metadata.get('tl_x')==layers[0]['tl_x'] and metadata.get('tl_y')==layers[0]['tl_y'],
                        'Metadata own-layer origin differs from serialized L0')
                for layer in layers:
                    strict_bank_reader.geometry(layer,canvas)
                    feature_count+=len(layer['features'])
                templates.append(BankTemplate(tid,base.templates[tid].layers,canvas_size=(canvas,canvas)))
            loaded.append(Bank(arm,obj,cls,tuple(templates)))
            read_pins.extend((record['bank'],record['metadata']))
            bank_reports.append(dict(arm=arm,object_id=obj,class_id=cls,templates=len(raw),layers=2*len(raw),
                                     bank=record['bank'],metadata=record['metadata'],logical_bank_bytes=logical_bytes))
    counts={(arm,obj):record['count'] for (arm,obj),record in files.items()}
    plan=plan_all(tuple(loaded),counts)
    plan_json=plan.to_dict();geometry=plan_json.pop('layer_requirements')
    return dict(schema='rgb_stratified_bank_geometry_report_v1',plan=plan_json,banks=bank_reports,
                scanned_banks=len(loaded),loaded_layers=plan.loaded_layers,actual_features_scanned=feature_count,
                layer_geometry=geometry,all_features_scanned=True,feature_filtering=False,pose_filtering=False,
                input_bank_files=read_pins,original_attempts=[r['file'] for r in originals],
                source_numeric_audit=inputs['source_numeric_audit'],image_reads=0,image_decodes=0,
                native_executions=0,matcher_calls=0,production_promotion=False)


def _fresh_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def source_pins():
    return [file_pin(p) for p in (Path(__file__),HERE/'planner.py',INDEPENDENT/'strict_bank_reader.py',
                                  EXPERIMENT/'PROTOCOL.json')]


def reserve(input_pin,output,reservation,*,read_bytes=_disk_read):
    reservation=Path(reservation).resolve();output=Path(output).resolve()
    require(not reservation.exists(),'Geometry reservation already exists; no second attempt')
    require(not output.exists(),'Geometry output must be fresh')
    require(not reservation.is_relative_to(output),'Reservation must be outside its fresh output directory')
    require(Path(input_pin['path']).suffix.lower()=='.json','Geometry input freeze must be JSON')
    inputs=_json(read_checked(input_pin,MAX_JSON_BYTES,read_bytes=read_bytes))
    audit=_json(read_checked(inputs['source_numeric_audit'],MAX_JSON_BYTES,read_bytes=read_bytes))
    validate_inputs(inputs,audit)
    record=dict(schema=RESERVATION_SCHEMA,stage='all_eighteen_bank_geometry',reserved=True,
                policy='single attempt; preserve failures; no silent rerun; no bank/image read during reservation',
                input_freeze=input_pin,source_numeric_audit=inputs['source_numeric_audit'],output=str(output),
                source_pins=source_pins(),bank_payloads_read=0,image_reads=0,native_executions=0,matcher_calls=0)
    _fresh_json(reservation,record)
    return record


def execute(reservation,*,read_bytes=_disk_read):
    reservation=Path(reservation).resolve();record=_json(_disk_read(reservation))
    require(record.get('schema')==RESERVATION_SCHEMA and record.get('reserved') is True,'Invalid geometry reservation')
    output=Path(record['output']).resolve()
    consumed=reservation.with_name(reservation.name+'.consumed.json')
    require(not consumed.exists(),'Geometry reservation already consumed; preserve its marker')
    require(not output.exists(),'Geometry execution already consumed; output must remain preserved')
    _fresh_json(consumed,dict(schema='rgb_stratified_geometry_consumed_v1',reservation=file_pin(reservation),
                              output=str(output),policy='consumed before any bank read; failure still consumes reservation'))
    output.mkdir(parents=True,exist_ok=False)
    result=dict(schema='rgb_stratified_geometry_execution_receipt_v1',passed=False,reservation=file_pin(reservation),
                reservation_consumed=file_pin(consumed),
                input_freeze=record['input_freeze'],source_numeric_audit=record['source_numeric_audit'],
                native_executions=0,image_reads=0,image_decodes=0,matcher_calls=0,production_promotion=False)
    try:
        for pin in record['source_pins']:
            require(file_pin(pin['path'])==pin,'Geometry source changed after reservation')
        inputs=_json(read_checked(record['input_freeze'],MAX_JSON_BYTES,read_bytes=read_bytes))
        require(inputs.get('source_numeric_audit')==record['source_numeric_audit'],'Reservation source audit pin differs')
        audit=_json(read_checked(record['source_numeric_audit'],MAX_JSON_BYTES,read_bytes=read_bytes))
        report=build_geometry(inputs,audit,read_bytes=read_bytes)
        # Check every source declaration and bank payload again before freezing
        # the result. Full payloads are hashed, never filtered or truncated.
        for pin in report['input_bank_files']+report['original_attempts']+[record['input_freeze'],record['source_numeric_audit']]:
            read_checked(pin,MAX_BANK_BYTES,read_bytes=read_bytes)
        for pin in record['source_pins']:
            require(file_pin(pin['path'])==pin,'Geometry source changed during execution')
        report_path=output/'bank_geometry_report.json';plan_path=output/'common_padding_plan.json'
        _fresh_json(report_path,report);_fresh_json(plan_path,report['plan'])
        freeze=dict(schema='rgb_stratified_common_geometry_freeze_v1',plan=report['plan'],
                    training_freeze=record['input_freeze'],source_numeric_audit=record['source_numeric_audit'],
                    geometry_report=file_pin(report_path),common_padding_plan=file_pin(plan_path),
                    reservation=file_pin(reservation),source_pins=record['source_pins'],
                    exact_geometry_computed=True,independent_geometry_audit_required=True,
                    numeric_audit_passed=False,production_promotion=False,image_reads=0,image_decodes=0,
                    native_executions=0,matcher_calls=0)
        freeze_path=output/'GEOMETRY_FREEZE.json';_fresh_json(freeze_path,freeze)
        result.update(passed=True,geometry_freeze=file_pin(freeze_path),geometry_report=file_pin(report_path),
                      common_padding_plan=file_pin(plan_path),scanned_banks=report['scanned_banks'],
                      loaded_layers=report['loaded_layers'],actual_features_scanned=report['actual_features_scanned'])
    except (ValueError,TypeError,KeyError,OverflowError,OSError,EOFError) as error:
        result.update(error_type=type(error).__name__,error=str(error),failure_preserved=True)
        _fresh_json(output/'failure.json',result)
    _fresh_json(output/'receipt.json',result)
    return result


def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path)
    parser.add_argument('--inputs-sha256')
    parser.add_argument('--inputs-bytes',type=int)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--reservation',required=True,type=Path)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--reserve-only',action='store_true');mode.add_argument('--execute',action='store_true')
    args=parser.parse_args(arguments)
    if args.reserve_only:
        require(args.inputs is not None and args.inputs_sha256 is not None and args.inputs_bytes is not None and
                args.output is not None,'Reserve mode requires externally pinned input declaration and fresh output')
        input_pin=dict(path=str(args.inputs.resolve()),bytes=args.inputs_bytes,sha256=args.inputs_sha256)
        reserve(input_pin,args.output,args.reservation)
        print(json.dumps(dict(reserved=True,bank_payloads_read=0,image_reads=0)))
        return 0
    require(args.inputs is None and args.inputs_sha256 is None and args.inputs_bytes is None and args.output is None,
            'Execute receives its complete input/output declaration only from the reservation')
    result=execute(args.reservation)
    print(json.dumps(result))
    return 0 if result['passed'] else 2


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,TypeError,KeyError,OSError) as error:
        print(json.dumps(dict(passed=False,error_type=type(error).__name__,error=str(error))),file=sys.stderr)
        raise SystemExit(2)
