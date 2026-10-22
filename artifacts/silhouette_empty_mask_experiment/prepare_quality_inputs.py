"""Freeze numeric quality inputs after root training/union-plan audits; no images."""
import argparse
import json
from pathlib import Path

import native_provenance as p
import prepare_input_closure as inherited
import quality_contract as contract

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
EXPECTED={
    'PROTOCOL.json':'e4260feb88abc00532b096b1fdb602a4c5a785ec060788aa54ba821eacd4245b',
    'INPUT_CLOSURE.json':'cf8059280c45487beffd52fcec3130b3e566ad07cd3165872cedaef02f59c31d',
    'run_training_v1/BANK_FREEZE.json':'9d92659813a947ee9c4403324468e765e0e3fea0ac8268f2d1f3e1ee4f79b737',
    'run_plan_v1/COMMON_PADDING_FREEZE.json':'60608c3b1cd6b3d2f31b2a216e2886e43cb83cc1d74b96b80575f8ecbd9bfb50'}
DEST=HERE/'QUALITY_INPUT_FREEZE.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def create():
    p.require(not DEST.exists(),'Quality input freeze must be fresh');pins=[]
    for name,sha in EXPECTED.items():
        pin=p.file_pin(HERE/name);p.require(pin['sha256']==sha,'Reviewed training/plan input pin changed: '+name);pins.append(pin)
    inherited.verify();closure=read(HERE/'INPUT_CLOSURE.json');bank=read(HERE/'run_training_v1/BANK_FREEZE.json');plan=read(HERE/'run_plan_v1/COMMON_PADDING_FREEZE.json')
    p.require(bank['native_exit_zero'] is True and bank['comparison_feasible'] is True and bank['training_attempts_complete'] is True and
              bank['summary']['attempts']==20736 and bank['summary']['zero_success_objects']==bank['summary']['opencv_exception_attempts']==0,'Complete feasible six-bank training required')
    p.require(plan['passed'] is True and plan['bank_freeze']['sha256']==EXPECTED['run_training_v1/BANK_FREEZE.json'],'Plan is not bound to complete bank freeze')
    pins+=bank['files']+plan['files']
    for name in ['root_training_audit_closure_bound_20261022.json','root_plan_audit_20261022.json']:
        path=ROOT/'artifacts/independent_reviews/empty_mask_training_v1'/name
        audit=read(path);p.require(audit['passed'] is True,'Root independent training/plan audit must pass');pins.append(p.file_pin(path))
    for pin in pins:
        p.check_pin(pin)
    rgb=[]
    for item in closure['rgb_banks']:
        row=dict(item,binary_training=str(HERE/f"run_training_v1/native/obj{item['object_id']}"));rgb.append(row)
    result=dict(version='empty_mask_quality_inputs_v1',objects=closure['objects'],dataset_root=closure['dataset_root'],
                development=closure['development'],rgb_banks=rgb,
                common_padding_json=str(HERE/'run_plan_v1/native/common_padding_plan.json'),
                frozen_numeric_files=pins,protocol_sha256=EXPECTED['PROTOCOL.json'],
                inherited_input_closure_sha256=EXPECTED['INPUT_CLOSURE.json'],
                stages={mode:contract.stage_spec(mode) for mode in contract.CALLS},total_matcher_call_budget=22176,
                preparer=p.file_pin(Path(__file__)),stage_contract=p.file_pin(HERE/'quality_contract.py'),
                training_and_plan_build_sources_unchanged=True,dataset_image_reads=0,image_decodes=0,matcher_calls=0)
    DEST.write_text(json.dumps(result,indent=2)+'\n');return verify()


def verify():
    result=read(DEST);p.require(result['version']=='empty_mask_quality_inputs_v1' and result['objects']==[1,2,5,8,12,17] and
                             result['total_matcher_call_budget']==22176,'Quality input scope/budget changed')
    p.require(result['stages']=={mode:contract.stage_spec(mode) for mode in contract.CALLS},'Fixed quality stage schedule changed')
    p.check_pin(result['preparer']);p.check_pin(result['stage_contract'])
    for pin in result['frozen_numeric_files']:
        p.check_pin(pin)
    inherited.verify();return dict(passed=True,quality_input_freeze=p.file_pin(DEST),numeric_pins=len(result['frozen_numeric_files']),dataset_image_reads=0,image_decodes=0,matcher_calls=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--create',action='store_true');group.add_argument('--verify',action='store_true');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    p.require(not args.output.exists(),'Receipt must be fresh')
    try:
        result=create() if args.create else verify();args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    except Exception as error:
        args.output.write_text(json.dumps(dict(incomplete=True,reason=str(error),dataset_image_reads=0,matcher_calls=0),indent=2)+'\n');raise


if __name__=='__main__':
    main()
