"""Fixed, one-reservation-per-stage 22,176-call development contract."""
import json
from pathlib import Path

CALLS={'old_gate':96,'pilot':192,'development':9600,'timing':12288}
PREVIOUS={'old_gate':None,'pilot':'old_gate','development':'pilot','timing':'development'}


def require(value,message):
    if not value:
        raise ValueError(message)


def stage_spec(mode):
    require(mode in CALLS,'Only fixed development stages are permitted')
    return dict(frames=64 if mode=='timing' else 400 if mode=='development' else 8,
                arms=['rgb'] if mode=='old_gate' else ['rgb_control','rgb_dilated_mask'],paths=['fallback','fused'],
                rounds=8 if mode=='timing' else 1,maximum_calls=CALLS[mode],
                soft_minutes=60 if mode=='timing' else 180 if mode=='development' else 20)


def reserve(directory,mode,run,previous_freeze=None):
    spec=stage_spec(mode);directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    require(not (directory/(mode+'.json')).exists(),'Stage already reserved; unknown/partial calls cannot be silently rerun')
    require(PREVIOUS[mode] is None or previous_freeze is not None,'Previous complete frozen stage required')
    # O_EXCL semantics preserve one reservation even if execution later fails.
    record=dict(stage=mode,run=str(run),maximum_calls=spec['maximum_calls'],previous_stage=PREVIOUS[mode],
                previous_freeze=previous_freeze,total_protocol_maximum=22176,
                policy='One attempt per fixed stage; reservation survives failure; missing frames are never negatives')
    with (directory/(mode+'.json')).open('x') as stream:
        stream.write(json.dumps(record,indent=2)+'\n')
    return record
