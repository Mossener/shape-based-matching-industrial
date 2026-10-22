"""Create a separate marker binding an independent audit and two original freezes.

The marker never edits audited evidence. Caller chooses the independent audit;
passed=True alone is insufficient: its pinned input closure must include both
exact current freeze bytes. This does not substitute for human audit review.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise ValueError(message)


def pin(path):
    path=Path(path).resolve(strict=True);data=path.read_bytes()
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def accept(training,plan,audit,destination):
    destination=Path(destination)
    require(not destination.exists(),'Audit acceptance must be new; do not rewrite frozen evidence')
    training_pin,plan_pin,audit_pin=pin(training),pin(plan),pin(audit)
    require(len({training_pin['path'],plan_pin['path'],audit_pin['path'],str(destination.resolve())})==4,'Acceptance/audit/freeze paths must differ')
    receipt=json.loads(Path(audit).read_text())
    require(receipt.get('passed') is True,'Independent audit did not pass')
    inputs=receipt.get('input_pins',{})
    if isinstance(inputs,list):
        require(all(isinstance(p,dict) and 'path' in p for p in inputs),'Invalid independent input-pin list')
        keys=[str(Path(p['path']).resolve()) for p in inputs]
        require(len(keys)==len(set(keys)),'Duplicate independent input pins')
        inputs=dict(zip(keys,inputs))
    require(isinstance(inputs,dict),'Independent input pins required')
    for expected in (training_pin,plan_pin):
        observed=inputs.get(expected['path'])
        require(isinstance(observed,dict) and all(observed.get(k)==expected[k] for k in ('sha256','bytes')),'Independent audit did not bind exact training and plan freeze')
    marker=dict(schema='rgb_dilated_mask_independent_audit_acceptance_v1',accepted_independent_audit=True,
                scope='training_and_exact_geometry',training_freeze=training_pin,plan_freeze=plan_pin,independent_audit=audit_pin,
                marker_creator=pin(Path(__file__)),source='Separate acceptance after root review; originals unchanged',image_decodes=0,matcher_calls=0)
    # Input pins are compared again immediately before exclusive marker write.
    require(pin(training)==training_pin and pin(plan)==plan_pin and pin(audit)==audit_pin,'Audit/freeze changed during acceptance')
    with destination.open('x') as stream:stream.write(json.dumps(marker,indent=2)+'\n')
    return marker


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training-freeze',type=Path,default=HERE/'run_training_v1/BANK_FREEZE.json')
    parser.add_argument('--plan-freeze',type=Path,default=HERE/'run_plan_v1/COMMON_PADDING_FREEZE.json')
    parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=HERE/'AUDIT_ACCEPTANCE.json')
    args=parser.parse_args()
    require(args.output.resolve().is_relative_to(HERE),'Acceptance output must be inside experiment')
    print(json.dumps(accept(args.training_freeze,args.plan_freeze,args.audit,args.output),indent=2))
