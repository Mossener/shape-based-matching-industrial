"""Join separately verified training execution and independent exact geometry.

This aggregates existing receipts; it does not resample features, recompute
geometry, decode images or measure recognition quality.
"""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import native_provenance as p


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def same(a,b,message):
    p.require(json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False),message)


def pinned(value):
    p.check_pin(value)
    return read(value['path'])


def build(training_path,inputs_path,scanner_path,independent_path):
    training_pin,input_pin,scanner_pin,independent_pin=[p.file_pin(path) for path in
        (training_path,inputs_path,scanner_path,independent_path)]
    training=read(training_path); inputs=read(inputs_path)
    scanner=read(scanner_path); independent=read(independent_path)
    p.require(training.get('schema')=='rgb_stratified_training_execution_acceptance_v1' and
              all(training.get(key) is True for key in
                  ('real_training_accepted','source_runtime_accepted','numeric_audit_passed')) and
              training.get('production_promotion') is False,'Complete training acceptance required')
    numeric=pinned(training['independent_audit'])
    p.require(numeric.get('numeric_training_audit_passed') is True and
              numeric.get('public_numeric_training_complete') is True and
              numeric.get('comparison_feasible') is True and numeric.get('literal_only') is False,
              'Full independent training audit required')
    same(numeric['output_pins_before'],numeric['output_pins_after'],'Training audit output changed')
    p.require(inputs.get('schema')=='rgb_stratified_geometry_inputs_v1' and
              inputs.get('production_promotion') is False,'Accepted eighteen-bank declaration required')
    same(inputs['training_execution_acceptance'],training_pin,'Geometry training acceptance differs')
    same(inputs['source_numeric_audit'],training['independent_audit'],'Geometry training numeric audit differs')
    p.require(scanner.get('schema')=='rgb_stratified_guarded_geometry_runner_v1' and
              scanner.get('passed') is True,'Guarded scanner completion required')
    scan_guard=pinned(scanner['guard'])
    p.require(scan_guard.get('passed') is True and scan_guard.get('exit_code')==0,'Scanner watchdog failed')
    launch=pinned(scanner['launch'])
    for name,value in launch['limits'].items():
        same(scan_guard[name],value,'Scanner watchdog resource ceiling differs')
    same(scan_guard['command'],launch['command'],'Scanner watchdog command differs')
    scan=pinned(scanner['scanner_receipt'])
    p.require(scan.get('passed') is True and scan.get('scanned_banks')==18,'Complete scanner receipt required')
    same(scan['input_freeze'],input_pin,'Scanner input freeze differs')
    same(scan['source_numeric_audit'],training['independent_audit'],'Scanner training audit differs')
    same(scan['geometry_freeze'],scanner['geometry_freeze'],'Scanner geometry freeze differs')
    freeze=pinned(scanner['geometry_freeze'])
    p.require(freeze.get('schema')=='rgb_stratified_common_geometry_freeze_v1' and
              freeze.get('exact_geometry_computed') is True and
              freeze.get('independent_geometry_audit_required') is True and
              freeze.get('numeric_audit_passed') is False and freeze.get('production_promotion') is False,
              'Original computed-only scanner freeze required')
    same(freeze['training_freeze'],input_pin,'Geometry freeze input differs')
    p.require(independent.get('schema')=='rgb_stratified_independent_geometry_runner_receipt_v1' and
              independent.get('passed') is True and independent.get('scope')=='exact_geometry_only' and
              independent.get('guard',{}).get('passed') is True and
              independent['guard'].get('exit_code')==0,'Independent geometry runner failed')
    independent_reservation=pinned(independent['reservation'])
    p.check_pin(independent['consumed_marker'])
    independent_guard_pin=p.file_pin(Path(independent_reservation['execution'])/'guard_receipt.json')
    same(pinned(independent_guard_pin),independent['guard'],'Independent watchdog receipt differs')
    for name,value in independent_reservation['guard_limits'].items():
        same(independent['guard'][name],value,'Independent watchdog resource ceiling differs')
    same(independent_reservation['execution_source_pins'],
         [p.file_pin(value['path']) for value in independent_reservation['execution_source_pins']],
         'Independent geometry execution sources changed')
    geometry=pinned(independent['audit_output'])
    p.require(geometry.get('schema')=='rgb_stratified_independent_geometry_audit_v1' and
              geometry.get('passed') is True and geometry.get('accepted_independent_audit') is True and
              geometry.get('numeric_audit_passed') is True and geometry.get('scope')=='exact_geometry_only' and
              geometry.get('production_promotion') is False,'Independent exact geometry audit required')
    same(geometry['training_freeze'],input_pin,'Independent geometry input differs')
    same(geometry['geometry_freeze'],scanner['geometry_freeze'],'Independent scanner freeze differs')
    same(geometry['source_numeric_audit'],training['independent_audit'],'Independent training audit differs')
    same(geometry['input_pins_before'],geometry['input_pins_after'],'Geometry inputs changed during audit')
    same(geometry['auditor_sources_before'],geometry['auditor_sources_after'],'Independent geometry sources changed')
    for value in geometry['auditor_sources_after']:
        p.check_pin(value)
    same(geometry['computed_plan'],freeze['plan'],'Independent common padding differs')
    p.require([row['object_id'] for row in inputs['banks']]==[1,2,5,8,12,17],
              'Geometry object order differs')
    layers=2*sum(row[key] for row in inputs['banks'] for key in
                 ('control_template_count','pooled_template_count','stratified_template_count'))
    p.require(scan['loaded_layers']==freeze['plan']['loaded_layers']==layers,
              'Complete eighteen-bank layer coverage differs')
    for value in geometry['input_pins_after']:
        p.check_pin(value)
    for value in scanner['source_pins']+freeze['source_pins']:
        p.check_pin(value)
    values=[training_pin,input_pin,scanner_pin,independent_pin,training['independent_audit'],
            scanner['geometry_freeze'],scanner['scanner_receipt'],scanner['guard'],independent['audit_output']]
    values += [scanner['launch'],independent['reservation'],independent['consumed_marker'],independent_guard_pin]
    unique={value['path']:value for value in values}
    return dict(schema='independent_stratified_training_geometry_audit_v1',passed=True,
        scope='training_and_exact_geometry',numeric_audit_passed=True,production_promotion=False,
        training_execution_acceptance=training_pin,training_numeric_audit=training['independent_audit'],
        guarded_geometry_runner=scanner_pin,independent_geometry_runner=independent_pin,
        independent_geometry_audit=independent['audit_output'],input_pins=list(unique.values()),
        computed_plan=freeze['plan'],loaded_layers=layers,source=p.file_pin(__file__),
        quality_tested=False,image_decodes=0,native_calls=0,heldout_image_reads=0,
        limitation='Root aggregation of separate training/runtime and independent numeric receipts; no quality or speed result')


def fresh(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('training-acceptance','geometry-inputs','scanner-runner','independent-runner','report','acceptance'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    p.require(not args.report.exists() and not args.acceptance.exists(),'Fresh aggregate outputs required')
    report=build(args.training_acceptance,args.geometry_inputs,args.scanner_runner,args.independent_runner)
    fresh(args.report,report)
    scanner=read(args.scanner_runner)
    envelope=dict(schema='rgb_stratified_training_geometry_acceptance_v1',accepted_independent_audit=True,
        scope='training_and_exact_geometry',numeric_audit_passed=True,production_promotion=False,
        training_freeze=p.file_pin(args.geometry_inputs),geometry_freeze=scanner['geometry_freeze'],
        independent_audit=p.file_pin(args.report),quality_tested=False)
    fresh(args.acceptance,envelope)
    print(json.dumps(dict(passed=True,loaded_layers=report['loaded_layers'],quality_tested=False)))


if __name__=='__main__':main()
