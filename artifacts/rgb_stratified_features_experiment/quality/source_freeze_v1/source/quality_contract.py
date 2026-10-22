"""Fixed V31 three-arm schedule and source/declaration-only gates.

No function in this module decodes images, reads banks or invokes native code.
Static native-source checks do not establish C++ compilation or correctness.
"""
import json
from pathlib import Path

OBJECTS=(1,2,5,8,12,17)
ARMS=('rgb_control','rgb_pooled_features','rgb_stratified_features')
PATHS=('fallback','fused')
CALLS={'old_gate':96,'pilot':288,'development':14400,'timing':29952}
PREVIOUS={'old_gate':None,'pilot':'old_gate','development':'pilot','timing':'development'}
TOTAL_CALLS=44736


def require(value,message):
    if not value:raise ValueError(message)


def stage_spec(mode):
    require(mode in CALLS,'Only fixed development stages are permitted')
    return dict(frames=64 if mode=='timing' else 400 if mode=='development' else 8,
        arms=list(ARMS[:1] if mode=='old_gate' else ARMS),paths=list(PATHS),
        rounds=13 if mode=='timing' else 1,warmup_rounds=1 if mode=='timing' else 0,
        measured_rounds=12 if mode=='timing' else 0,maximum_calls=CALLS[mode],
        soft_minutes=90 if mode=='timing' else 240 if mode=='development' else 30)


def timing_order(frame_ordinal,round_index):
    require(type(frame_ordinal) is int and 0<=frame_ordinal<64,'Fixed timing-frame ordinal required')
    require(type(round_index) is int and 0<=round_index<13,'Fixed timing round required')
    return [(position+frame_ordinal+round_index)%6 for position in range(6)]


def validate_padding(plan):
    require(plan.get('banks')==18 and plan.get('geometry_feasible') in (True,1),'Accepted 18-bank geometry required')
    w,h=plan['width'],plan['height'];a=plan['padding_ltrb']
    require(type(w) is int and type(h) is int and len(a)==4 and all(type(x) is int for x in a),'Integer geometry required')
    require(a[0]==64 and a[1]==64 and a[2]>=64 and a[3]>=228 and
        w==720+a[0]+a[2] and h==540+a[1]+a[3] and w>=848 and h>=832 and
        w%16==0 and h%16==0 and w<=2048 and h<=2048 and w*h<=2097152 and
        w*h*512<=1073741824,'Common padding phase/formula/resource gate differs')
    return list(a)


def validate_pin(pin):
    require(isinstance(pin,dict) and set(pin)=={'path','bytes','sha256'} and
        isinstance(pin['path'],str) and pin['path'] and type(pin['bytes']) is int and pin['bytes']>=0 and
        isinstance(pin['sha256'],str) and len(pin['sha256'])==64 and
        all(ch in '0123456789abcdef' for ch in pin['sha256']),'Complete SHA256/byte/path pin required')


def validate_quality_acceptance(a,development_pin):
    require(a.get('accepted_independent_audit') is True and a.get('scope')=='quality_all_three_arms' and
        a.get('numeric_audit_passed') is True and a.get('production_promotion') is False and
        type(a.get('primary_accuracy_hypothesis_passed')) is bool and
        a.get('development_stage')==development_pin,'Independent complete three-arm quality audit required')
    validate_pin(a['development_stage']);validate_pin(a['independent_audit'])


def reserve(directory,mode,run,previous_freeze=None):
    spec=stage_spec(mode);require(PREVIOUS[mode] is None or previous_freeze is not None,'Previous complete stage required')
    d=Path(directory);d.mkdir(parents=True,exist_ok=True)
    record=dict(stage=mode,run=str(run),maximum_calls=spec['maximum_calls'],previous_stage=PREVIOUS[mode],
        previous_freeze=previous_freeze,total_protocol_maximum=TOTAL_CALLS,
        policy='One attempt per fixed stage; preserve reservation and partial evidence; missing frames are never negatives')
    with (d/(mode+'.json')).open('x',encoding='utf-8') as stream:stream.write(json.dumps(record,indent=2)+'\n')
    return record


def validate_native_sources(root):
    root=Path(root)
    required={
        'quality_eval.cpp':[
            '#include "../frozen_helpers/tless_eval.cpp"','mode=="selftest"',
            'std::array<Bank,3>','std::array<line2Dup::MatchWorkspace,6>',
            'if(arm==0 && !gate)','str(item["c0_common_raw"])',
            'gate?96:mode=="pilot"?288:14400','calls==29952','round<13',
            '(order+frameOrdinal+round)%6','"measured_rounds"<<12','int(plan["banks"])==18'],
        'quality_support.hpp':[
            '"rgb_control","rgb_pooled_features","rgb_stratified_features"',
            'scoreBits(a.score)==scoreBits(b.score)','++calls;',
            'need(calls<maximumCalls','p.width==720+p.ltrb[0]+p.ltrb[2]',
            'p.height==540+p.ltrb[1]+p.ltrb[3]','readClasses({cls}',
            'postprocess(result.raw,Config{},85)','writeRaw(directory,frame,path,result.raw,bank.meta)']}
    for name,anchors in required.items():
        file=root/name;require(file.is_file(),'Missing native quality source: '+name)
        text=file.read_text(encoding='utf-8')
        for anchor in anchors:require(anchor in text,'Native source contract missing '+name+': '+anchor)
        for forbidden in ('rgb_dilated_mask_quality_inputs_v1','private_v11/line2Dup.cpp','round<8','calls==12288'):
            require(forbidden not in text,'Old two-arm contract leaked into '+name+': '+forbidden)
    return dict(passed=True,native_runs=0,image_decodes=0,matcher_calls=0,
        limitation='Static source contract only; compilation and native semantic selftests remain required')
