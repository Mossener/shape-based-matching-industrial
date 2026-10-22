"""One-shot reserved foreground runner for the independent numeric timing audit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import evidence as e
import timing_audit as a

HERE=Path(__file__).resolve().parent
EXPERIMENT=HERE.parent


def pin(path):
    path=Path(path).resolve(strict=True);digest=hashlib.sha256();size=0
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):size+=len(data);digest.update(data)
    return dict(path=str(path),bytes=size,sha256=digest.hexdigest())


def fresh_json(path,data):
    with Path(path).open('x',encoding='utf-8') as stream:json.dump(data,stream,indent=2,allow_nan=False);stream.write('\n')


def source_pins():
    paths=sorted(p for p in HERE.iterdir() if p.is_file() and
                 (p.suffix in ('.py','.md') or p.name in ('ORIGIN.json','SOURCE_STATUS.json')))
    paths += [EXPERIMENT/'execution_guard.py',Path(sys.executable)]
    return [pin(p) for p in paths]


def reserve(input_pin,output,reservation):
    e.pin_schema(input_pin);reader=e.Reader(e.ROOT);spec=e.loads(reader.check(input_pin))
    a.need(spec.get('schema')=='rgb_stratified_independent_timing_inputs_v1','timing reference declaration required')
    for key in ('timing_stage','development_stage','quality_inputs','build_manifest','selftest','development_audit','quality_acceptance'):
        e.pin_schema(spec[key])
    output=Path(output).resolve();reservation=Path(reservation).resolve()
    a.need(output.is_relative_to(HERE) and not output.exists(),'fresh contained audit output required')
    a.need(reservation.is_relative_to(HERE) and not reservation.exists(),'fresh contained reservation required')
    execution=output.with_name(output.name+'_execution');receipt=output.with_name(output.name+'_RUNNER.json')
    a.need(not execution.exists() and not receipt.exists(),'fresh guard and receipt paths required')
    output.parent.mkdir(parents=True,exist_ok=True);reservation.parent.mkdir(parents=True,exist_ok=True)
    locks=HERE/'audit_reservations';locks.mkdir(exist_ok=True)
    lock=locks/'timing.json';a.need(not lock.exists(),'Timing audit already reserved; explicit successor required')
    record=dict(schema='independent_three_arm_timing_reservation_v1',input_pin=input_pin,
        timing_stage=spec['timing_stage'],output=str(output),execution=str(execution),receipt=str(receipt),
        source_pins=source_pins(),native_runs=0,image_decodes=0,passed=False)
    fresh_json(reservation,record)
    fresh_json(lock,dict(reservation=pin(reservation),timing_stage=record['timing_stage']))
    return record


def dispatch(command,env,output,execution,guard):
    output,execution=Path(output).resolve(),Path(execution).resolve()
    a.need(output.parent.is_dir() and execution.parent.is_dir(),'existing guard parents required')
    a.need(not output.exists() and not execution.exists(),'fresh separate audit/guard paths required')
    a.need(output!=execution and not output.is_relative_to(execution) and not execution.is_relative_to(output),
        'audit and guard outputs must not overlap')
    return guard.run_guarded(command,env,HERE,output,execution,maximum_seconds=5400,
        maximum_rss_bytes=1610612736,maximum_output_bytes=4294967296,maximum_execution_bytes=67108864)


def record_gate(record,reservation):
    a.need(Path(reservation).resolve().is_relative_to(HERE) and
        record.get('schema')=='independent_three_arm_timing_reservation_v1' and record.get('passed') is False,
        'contained initial timing reservation required')
    e.pin_schema(record['input_pin']);e.pin_schema(record['timing_stage'])
    output,execution,receipt=map(Path,(record['output'],record['execution'],record['receipt']))
    a.need(all(p.is_absolute() and p.resolve()==p and p.is_relative_to(HERE) for p in (output,execution,receipt)) and
        execution==output.with_name(output.name+'_execution') and receipt==output.with_name(output.name+'_RUNNER.json'),
        'consumed timing paths escaped fixed sibling scope')
    a.need(record['source_pins']==source_pins(),'consumed timing source/runtime pin membership differs')


def execute(reservation,guard):
    reservation=Path(reservation).resolve();record=e.loads(reservation.read_bytes())
    record_gate(record,reservation)
    lock=e.loads((HERE/'audit_reservations/timing.json').read_bytes())
    a.need(lock==dict(reservation=pin(reservation),timing_stage=record['timing_stage']),'reservation lock differs')
    consumed=reservation.with_suffix(reservation.suffix+'.consumed.json')
    fresh_json(consumed,dict(reservation=pin(reservation),no_silent_rerun=True))
    output,execution,receipt=map(Path,(record['output'],record['execution'],record['receipt']))
    result=dict(schema='independent_three_arm_timing_runner_v1',passed=False,input_pin=record['input_pin'],
        timing_stage=record['timing_stage'],reservation=pin(reservation),consumed=pin(consumed),
        native_runs=0,image_decodes=0,matcher_calls=0,production_promotion=False)
    try:
        a.need(all(pin(p['path'])==p for p in record['source_pins']),'audit source/runtime changed after reservation')
        a.need(pin(record['input_pin']['path'])==record['input_pin'],'timing references changed after reservation')
        command=[sys.executable,'-B',str(HERE/'audit.py'),'--inputs',record['input_pin']['path'],
            '--inputs-sha256',record['input_pin']['sha256'],'--inputs-bytes',str(record['input_pin']['bytes']),
            '--output',str(output),'--cpu-slot-granted']
        result['command']=command
        watched=dispatch(command,dict(os.environ),output,execution,guard)
        result['guard']=watched
        a.need(watched.get('passed') is True,'independent timing audit watchdog failed')
        child=e.loads((output/'result.json').read_bytes())
        a.need(child.get('schema')=='independent_three_arm_timing_audit_v1' and child.get('passed') is True and
            child.get('numeric_audit_passed') is True and child.get('timing_stage')==record['timing_stage'] and
            child.get('timing_rows')==29952 and child.get('formal_rows')==child.get('paired_rows')==27648 and
            child.get('production_promotion') is False,'complete independent timing result required')
        a.need(all(pin(p['path'])==p for p in record['source_pins']) and
            pin(record['input_pin']['path'])==record['input_pin'],'audit source/input changed during execution')
        result.update(passed=True,numeric_audit_passed=True,result=pin(output/'result.json'),source_pins=record['source_pins'])
    except BaseException as error:result.update(incomplete=True,reason=repr(error),no_timing_claim_from_partial_evidence=True)
    fresh_json(receipt,result)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--reserve-only',action='store_true');mode.add_argument('--execute',action='store_true')
    ap.add_argument('--reservation',type=Path,required=True);ap.add_argument('--inputs',type=Path)
    ap.add_argument('--inputs-sha256');ap.add_argument('--inputs-bytes',type=int);ap.add_argument('--output',type=Path)
    ap.add_argument('--cpu-slot-granted',action='store_true');args=ap.parse_args()
    if args.reserve_only:
        a.need(args.inputs is not None and args.inputs_sha256 is not None and args.inputs_bytes is not None and args.output is not None,
            'reservation requires externally pinned input and fresh output')
        reserve(dict(path=str(args.inputs.resolve()),bytes=args.inputs_bytes,sha256=args.inputs_sha256),args.output,args.reservation)
        print(json.dumps(dict(reserved=True,native_runs=0,image_decodes=0)));return
    a.need(args.cpu_slot_granted,'Await coordinated independent timing CPU slot')
    a.need(args.inputs is None and args.inputs_sha256 is None and args.inputs_bytes is None and args.output is None,
        'execute receives paths only from reservation')
    sys.path.insert(0,str(EXPERIMENT));import execution_guard as guard
    result=execute(args.reservation,guard);print(json.dumps(dict(passed=result['passed'],native_runs=0,image_decodes=0)))
    if not result['passed']:raise SystemExit(2)


if __name__=='__main__':main()
