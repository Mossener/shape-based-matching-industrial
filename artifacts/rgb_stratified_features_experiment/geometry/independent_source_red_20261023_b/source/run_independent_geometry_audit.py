"""Reserve and execute one independently recomputed, bounded geometry audit.

Reservation verifies numeric declarations without opening bank payloads. The
root owns approval of the source/runtime closure and the single real launch.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True
import independent_geometry_audit as audit

HERE=Path(__file__).resolve().parent
EXPERIMENT=HERE.parent
GUARD_LIMITS=dict(maximum_seconds=1800.,maximum_rss_bytes=1610612736,
                  maximum_output_bytes=268435456,maximum_execution_bytes=33554432,
                  minimum_free_bytes=536870912)


def execution_sources():
    return audit.source_pins()+[audit.file_pin(EXPERIMENT/'execution_guard.py'),audit.file_pin(sys.executable)]


def paths(reservation,evidence,execution):
    reservation,evidence,execution=(Path(p).resolve() for p in (reservation,evidence,execution))
    for path in (reservation,evidence,execution):
        audit.require(path.parent.is_dir(),'Existing reservation/output parent required')
        audit.require(not path.exists(),'Fresh reservation and output paths required')
    audit.require(evidence!=execution and not evidence.is_relative_to(execution) and
                  not execution.is_relative_to(evidence),'Separate audit and execution output paths required')
    audit.require(not reservation.is_relative_to(evidence) and not reservation.is_relative_to(execution),
                  'Reservation must stay outside guarded output paths')
    marker=Path(str(reservation)+'.consumed.json')
    audit.require(not marker.exists(),'Existing consumed marker forbids reservation reuse')
    return reservation,evidence,execution


def declaration(input_pin,scanner_pin,*,read_bytes=None):
    """Inspect only the two freezes and training audit, never banks/reports."""
    inputs=audit.json_object(audit.read_pin(input_pin,audit.JSON_LIMIT,read_bytes=read_bytes))
    scanner=audit.json_object(audit.read_pin(scanner_pin,audit.JSON_LIMIT,read_bytes=read_bytes))
    training=audit.json_object(audit.read_pin(inputs['source_numeric_audit'],audit.JSON_LIMIT,read_bytes=read_bytes))
    audit.preflight(inputs,training)
    audit.require(scanner.get('schema')=='rgb_stratified_common_geometry_freeze_v1' and
                  scanner.get('exact_geometry_computed') is True and
                  scanner.get('independent_geometry_audit_required') is True and
                  scanner.get('numeric_audit_passed') is False and scanner.get('production_promotion') is False,
                  'Accepted scanner declaration required')
    audit.exact_equal(scanner['training_freeze'],input_pin,'scanner.training_freeze')
    audit.exact_equal(scanner['source_numeric_audit'],inputs['source_numeric_audit'],'scanner.source_numeric_audit')
    for field in ('image_reads','image_decodes','native_executions','matcher_calls'):
        audit.require(type(scanner.get(field)) is int and scanner[field]==0,'Scanner declaration activity differs')
    for field in ('geometry_report','common_padding_plan','reservation'):
        audit.validate_pin(scanner[field])
    sources=scanner.get('source_pins')
    audit.require(type(sources) is list and len(sources)==4 and
                  {Path(p['path']).name for p in sources}=={'run_geometry.py','planner.py','strict_bank_reader.py','PROTOCOL.json'},
                  'Complete scanner source declaration required')
    for pin in sources:audit.validate_pin(pin)
    complete=[input_pin,scanner_pin,inputs['source_numeric_audit'],scanner['geometry_report'],
              scanner['common_padding_plan'],scanner['reservation'],*sources]
    for row in inputs['bank_files']:complete.extend((row['bank'],row['metadata']))
    complete.extend(row['file'] for row in inputs['original_attempts'])
    unique={}
    for pin in complete:
        if pin['path'] in unique:audit.exact_equal(pin,unique[pin['path']],'duplicate_declared_pin')
        unique[pin['path']]=pin
    return inputs,scanner,[unique[p] for p in sorted(unique)]


def reserve(input_pin,scanner_pin,reservation,evidence,execution,*,read_bytes=None):
    reservation,evidence,execution=paths(reservation,evidence,execution)
    inputs,scanner,declared=declaration(input_pin,scanner_pin,read_bytes=read_bytes)
    sources=execution_sources()
    value=dict(schema='rgb_stratified_independent_geometry_reservation_v1',reserved=True,
               training_freeze=input_pin,geometry_freeze=scanner_pin,
               source_numeric_audit=inputs['source_numeric_audit'],declared_input_pins=declared,
               execution_source_pins=sources,guard_limits=GUARD_LIMITS,
               evidence=str(evidence),execution=str(execution),production_promotion=False,
               scope='exact_geometry_only',bank_payloads_opened=0,image_reads=0,native_executions=0,
               runtime_closure='Pinned interpreter and direct sources; root owns transitive Python runtime acceptance')
    audit.write_fresh_json(reservation,value)
    return value


def execute(reservation,*,read_bytes=None,guard=None):
    reservation=Path(reservation).resolve()
    record=audit.json_object(audit.disk_bytes(reservation,audit.JSON_LIMIT))
    audit.require(record.get('schema')=='rgb_stratified_independent_geometry_reservation_v1' and
                  record.get('reserved') is True,'Independent audit reservation required')
    marker=Path(str(reservation)+'.consumed.json')
    audit.require(not marker.exists(),'Independent audit reservation already consumed')
    evidence=Path(record['evidence']);execution=Path(record['execution'])
    audit.require(not evidence.exists() and not execution.exists(),'Independent audit output must remain fresh')
    audit.require(evidence.parent.is_dir() and execution.parent.is_dir(),'Existing output parents required')
    audit.require(evidence.is_absolute() and execution.is_absolute() and evidence==evidence.resolve() and
                  execution==execution.resolve() and evidence!=execution and not evidence.is_relative_to(execution) and
                  not execution.is_relative_to(evidence) and not reservation.is_relative_to(evidence) and
                  not reservation.is_relative_to(execution),'Invalid independent audit output separation')
    reservation_pin=audit.file_pin(reservation)
    # Persistent consumption precedes source/input rechecks and every child call.
    audit.write_fresh_json(marker,dict(reservation=reservation_pin,consumed=True,automatic_retry=False))
    evidence.mkdir()
    result=dict(schema='rgb_stratified_independent_geometry_runner_receipt_v1',passed=False,
                reservation=reservation_pin,consumed_marker=audit.file_pin(marker),scope='exact_geometry_only',
                production_promotion=False,guard_limits=GUARD_LIMITS,actual_launches=0,
                failure_preserved=True,automatic_retry=False)
    try:
        audit.exact_equal(record['guard_limits'],GUARD_LIMITS,'reservation.guard_limits')
        audit.exact_equal(record['execution_source_pins'],execution_sources(),'reservation.execution_source_pins')
        inputs,scanner,declared=declaration(record['training_freeze'],record['geometry_freeze'],read_bytes=read_bytes)
        audit.exact_equal(declared,record['declared_input_pins'],'reservation.declared_input_pins')
        child=evidence/'audit_output'
        command=[sys.executable,'-B',str(HERE/'independent_geometry_audit.py')]
        for flag,pin in (('inputs',record['training_freeze']),('scanner-freeze',record['geometry_freeze'])):
            command.extend(('--'+flag,pin['path'],'--'+flag+'-bytes',str(pin['bytes']),
                            '--'+flag+'-sha256',pin['sha256']))
        command.extend(('--output',str(child)))
        if guard is None:
            if str(EXPERIMENT) not in sys.path:sys.path.insert(0,str(EXPERIMENT))
            from execution_guard import run_guarded
            guard=run_guarded
        result['actual_launches']=1
        guarded=guard(command,dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),HERE,child,execution,**GUARD_LIMITS)
        result['guard']=guarded
        audit.require(type(guarded) is dict and guarded.get('passed') is True and guarded.get('exit_code')==0,
                      'Independent geometry guarded child failed')
        receipt=child/'INDEPENDENT_GEOMETRY_AUDIT.json'
        output=audit.json_object(audit.disk_bytes(receipt,audit.JSON_LIMIT))
        audit.require(output.get('schema')=='rgb_stratified_independent_geometry_audit_v1' and
                      output.get('accepted_independent_audit') is True and output.get('numeric_audit_passed') is True and
                      output.get('scope')=='exact_geometry_only' and output.get('production_promotion') is False,
                      'Independent geometry child did not accept exact geometry')
        audit.exact_equal(output['training_freeze'],record['training_freeze'],'child.training_freeze')
        audit.exact_equal(output['geometry_freeze'],record['geometry_freeze'],'child.geometry_freeze')
        audit.exact_equal(output['source_numeric_audit'],record['source_numeric_audit'],'child.source_numeric_audit')
        audit.exact_equal(output['input_pins_before'],output['input_pins_after'],'child.input_pins')
        audit.exact_equal(record['execution_source_pins'],execution_sources(),'execution_sources_after')
        audit.exact_equal(reservation_pin,audit.file_pin(reservation),'reservation_after')
        result.update(passed=True,failure_preserved=False,audit_output=audit.file_pin(receipt),
                      source_numeric_audit=output['source_numeric_audit'],computed_plan=output['computed_plan'])
    except (ValueError,TypeError,KeyError,OverflowError,OSError,EOFError) as error:
        result.update(error_type=type(error).__name__,error=str(error))
    audit.write_fresh_json(evidence/'RUNNER_RECEIPT.json',result)
    return result


def main(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--reserve-only',action='store_true');modes.add_argument('--execute',action='store_true')
    parser.add_argument('--reservation',required=True,type=Path)
    for name in ('inputs','scanner-freeze'):
        parser.add_argument('--'+name,type=Path);parser.add_argument('--'+name+'-bytes',type=int)
        parser.add_argument('--'+name+'-sha256')
    parser.add_argument('--evidence',type=Path);parser.add_argument('--execution',type=Path)
    args=parser.parse_args(arguments)
    if args.execute:
        result=execute(args.reservation)
        print(audit.json.dumps(dict(passed=result['passed'],actual_launches=result['actual_launches'])))
        return 0 if result['passed'] else 2
    for name in ('inputs','inputs_bytes','inputs_sha256','scanner_freeze','scanner_freeze_bytes','scanner_freeze_sha256','evidence','execution'):
        if getattr(args,name) is None:parser.error('--reserve-only requires '+name.replace('_','-'))
    ip=dict(path=str(args.inputs.resolve()),bytes=args.inputs_bytes,sha256=args.inputs_sha256)
    fp=dict(path=str(args.scanner_freeze.resolve()),bytes=args.scanner_freeze_bytes,sha256=args.scanner_freeze_sha256)
    reserve(ip,fp,args.reservation,args.evidence,args.execution)
    print(audit.json.dumps(dict(reserved=True,bank_payloads_opened=0)))
    return 0


if __name__=='__main__':raise SystemExit(main())
