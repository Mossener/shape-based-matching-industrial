"""One-shot resource-watched quality replay; reservation opens declarations only.

Real execution additionally requires the root's exclusive CPU grant. No image
or matcher call is performed by this wrapper or its independent child. A
passing numeric audit is separate from native source/runtime acceptance and
never promotes the candidate or authorizes another native stage by itself.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

from evidence import Reader,need,loads,pin_schema

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
AUDITOR=HERE/'quality_audit.py'
GUARD=HERE.parent/'execution_guard.py'
REGISTRY=HERE/'execution_reservations_v1'
SCHEMA='independent_three_arm_quality_reservation_v1'
RUNNER_SCHEMA='independent_three_arm_quality_runner_v1'
BUDGET=dict(wall_seconds=14400,rss_bytes=1536*1024*1024,output_bytes=512*1024*1024,
            execution_bytes=64*1024*1024,minimum_free_bytes=2*1024**3)


def file_pin(path):
    path=Path(path)
    need(all(not p.is_symlink() for p in (path,*path.parents)),'source/manifest symlink refused')
    path=path.resolve(strict=True); data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def source_pins():
    return [file_pin(path) for path in (Path(__file__),AUDITOR,HERE/'numeric.py',HERE/'evidence.py',
            HERE/'contract.py',HERE/'SOURCE_ORIGINS.json',GUARD,Path(sys.executable))]


def fresh_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream: json.dump(value,stream,indent=2); stream.write('\n')


def path_gate(path,root):
    path=Path(path).resolve(); need(path.is_relative_to(Path(root).resolve()),'audit path escaped workspace')
    return path


def reserve(stage_pin,evidence,reservation,root=ROOT):
    pin_schema(stage_pin); reader=Reader(root); stage=loads(reader.check(stage_pin))
    need(stage.get('stage')=='development' and stage.get('completed') is True and
         type(stage.get('native_exit_code')) is int and stage['native_exit_code']==0 and
         stage.get('actual_matcher_calls')==stage.get('maximum_matcher_calls')==14400,
         'complete development declaration required for reservation')
    evidence=path_gate(evidence,root); reservation=path_gate(reservation,root)
    stage_parent=Path(stage_pin['path']).resolve().parent
    need(not evidence.exists() and not reservation.exists(),'fresh evidence/reservation required')
    need(not evidence.is_relative_to(stage_parent) and not stage_parent.is_relative_to(evidence),
         'audit evidence must be outside native stage')
    lock=REGISTRY/(stage_pin['sha256']+'.json')
    need(not lock.exists(),'this stage already has its one quality-audit reservation')
    record=dict(schema=SCHEMA,runner_schema=RUNNER_SCHEMA,development_stage=stage_pin,
                evidence=str(evidence),reservation=str(reservation),budget=BUDGET,
                source_pins=source_pins(),reserved=True,stage_members_opened=False,
                matcher_calls=0,image_reads=0,production_promotion=False,
                policy='one attempt; persistent consumed marker; preserve partial evidence; no silent rerun')
    fresh_json(reservation,record)
    fresh_json(lock,dict(schema=SCHEMA,development_stage=stage_pin,reservation=file_pin(reservation)))
    return record


def run_guard(command,output,execution):
    spec=importlib.util.spec_from_file_location('v31_independent_quality_execution_guard',GUARD)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.run_guarded(command,dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=''),
        HERE,output,execution,maximum_seconds=BUDGET['wall_seconds'],maximum_rss_bytes=BUDGET['rss_bytes'],
        maximum_output_bytes=BUDGET['output_bytes'],maximum_execution_bytes=BUDGET['execution_bytes'],
        minimum_free_bytes=BUDGET['minimum_free_bytes'])


def execute(reservation,cpu_slot_granted,root=ROOT):
    need(cpu_slot_granted is True,'root exclusive quality-audit CPU grant required')
    reservation=path_gate(reservation,root); record=loads(reservation.read_bytes())
    need(record.get('schema')==SCHEMA and record.get('runner_schema')==RUNNER_SCHEMA and
         record.get('reserved') is True and record.get('budget')==BUDGET,'fixed quality reservation differs')
    need(record['reservation']==str(reservation),'reservation path binding differs')
    pin_schema(record['development_stage']); stage=record['development_stage']
    lock=REGISTRY/(stage['sha256']+'.json'); locked=loads(lock.read_bytes())
    need(locked['development_stage']==stage and locked['reservation']==file_pin(reservation),
         'exclusive stage reservation changed')
    evidence=path_gate(record['evidence'],root); need(not evidence.exists(),'fresh quality audit evidence required')
    consumed=REGISTRY/(stage['sha256']+'.consumed.json')
    need(not consumed.exists(),'quality reservation already consumed; no retry')
    fresh_json(consumed,dict(schema=SCHEMA,reservation=file_pin(reservation),development_stage=stage,
                            consumed=True,policy='failure also consumes this attempt'))
    evidence.mkdir(parents=True,exist_ok=False)
    output=evidence/'audit_output'; execution=evidence/'execution'
    guard=None; child=None; error=None; passed=False; after=None
    command=[sys.executable,'-B',str(AUDITOR),'--stage-freeze',stage['path'],
             '--stage-sha256',stage['sha256'],'--stage-bytes',str(stage['bytes']),'--output',str(output)]
    try:
        need(source_pins()==record['source_pins'],'quality audit sources/interpreter changed before execution')
        Reader(root).check(stage)
        fresh_json(evidence/'execution_provenance.json',dict(command=command,reservation=file_pin(reservation),
                   source_pins=record['source_pins'],budget=BUDGET,matcher_calls=0,image_reads=0))
        guard=run_guard(command,output,execution)
        child=loads((output/'result.json').read_bytes()) if (output/'result.json').is_file() else None
        need(isinstance(child,dict),'quality child did not produce a result')
        pass
        need(child.get('passed') is True and child.get('numeric_audit_passed') is True and
             child.get('development_stage')==stage and child.get('production_promotion') is False and
             type(child.get('primary_accuracy_hypothesis_passed')) is bool,'quality child result binding differs')
        Reader(root).check(stage)
        after=source_pins(); need(after==record['source_pins'],'quality audit sources/interpreter changed during execution')
        passed=True
    except Exception as caught:
        error=repr(caught)
    if not passed:
        output.mkdir(parents=True,exist_ok=True)
        if not (output/'failure.json').exists():
            fresh_json(output/'failure.json',dict(passed=False,error=error,matcher_calls=0,image_reads=0,
                                                production_promotion=False,reservation_consumed=True))
    artifacts=[file_pin(path) for path in sorted(output.rglob('*')) if path.is_file()]
    result=dict(schema=RUNNER_SCHEMA,passed=passed,numeric_audit_passed=passed,
                primary_accuracy_hypothesis_passed=child.get('primary_accuracy_hypothesis_passed') if child else None,
                development_stage=stage,reservation=file_pin(reservation),consumed=file_pin(consumed),guard=guard,
                source_pins_before=record['source_pins'],source_pins_after=after,command=command,
                evidence_files=artifacts,independent_audit=file_pin(output/'result.json') if (output/'result.json').is_file() else None,
                error=error,one_shot=True,failure_preserved=not passed,
                matcher_calls=0,image_reads=0,image_decodes=0,production_promotion=False,
                native_source_runtime_acceptance='separate root responsibility',
                limitations=['Watchdog observes process RSS/wall/output; it is not an OS allocation sandbox',
                             'Python executable and local/guard sources pinned; transitive runtime closure is separate root evidence',
                             'No RGB gradient/NMS candidate regeneration; no heldout/industrial accuracy claim',
                             'Numeric success does not itself authorize native timing or production promotion'])
    fresh_json(evidence/'RUNNER_RECEIPT.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True); mode.add_argument('--reserve-only',action='store_true'); mode.add_argument('--execute',action='store_true')
    p.add_argument('--reservation',type=Path,required=True); p.add_argument('--stage-freeze',type=Path)
    p.add_argument('--stage-sha256'); p.add_argument('--stage-bytes',type=int); p.add_argument('--evidence',type=Path)
    p.add_argument('--cpu-slot-granted',action='store_true'); args=p.parse_args()
    if args.reserve_only:
        need(args.stage_freeze and args.stage_sha256 and args.stage_bytes is not None and args.evidence,
             'reservation requires external trusted stage pin and fresh evidence path')
        result=reserve(dict(path=str(args.stage_freeze.resolve()),bytes=args.stage_bytes,sha256=args.stage_sha256),
                       args.evidence,args.reservation)
        print(json.dumps(dict(reserved=True,stage_members_opened=False,reservation=str(args.reservation.resolve()))))
        return 0
    result=execute(args.reservation,args.cpu_slot_granted)
    print(json.dumps(dict(passed=result['passed'],numeric_audit_passed=result['numeric_audit_passed'],
                         primary_accuracy_hypothesis_passed=result['primary_accuracy_hypothesis_passed'],
                         receipt=str(Path(result['independent_audit']['path']).parent.parent/'RUNNER_RECEIPT.json') if result['independent_audit'] else None)))
    return 0 if result['passed'] else 2


if __name__=='__main__': raise SystemExit(main())
