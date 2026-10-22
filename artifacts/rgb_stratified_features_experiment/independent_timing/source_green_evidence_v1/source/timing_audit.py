"""Independent V31 numeric timing replay. Never imports target evaluator code."""
from collections import defaultdict
import math
from pathlib import Path
from frozen_v30_timing import (AuditError,need,integer,finite,csv_rows,nearest_rank,_close,_summary_match)

HERE=Path(__file__).resolve().parent
OBJECTS=(1,2,5,8,12,17)
ARMS=('rgb_control','rgb_pooled_features','rgb_stratified_features')
PATHS=('fallback','fused')
VARIANTS=tuple((arm,path) for arm in ARMS for path in PATHS)
COMPARISONS=((ARMS[1],ARMS[0]),(ARMS[2],ARMS[0]),(ARMS[2],ARMS[1]))
FORMAL_ROUNDS=tuple(range(1,13))
EXPECTED_CALLS=29952
EXPECTED_FRAMES=64
FORMAL_ROWS=27648
INPUT_VERSION='rgb_stratified_quality_inputs_v1'
TIMING_HEADER='object_id,scene,image,frame_ordinal,round,warmup,order,arm,path,match_ms,external_call_ms,raw,selected,exact_own_reference'.split(',')
PAIR_HEADER='object_id,scene,image,frame_ordinal,round,path,numerator,denominator,match_ratio,external_ratio'.split(',')
BANK_HEADER='object_id,arm,templates,metadata_load_ms,bank_load_ms'.split(',')
PER_FRAME_HEADER='object_id,scene,image,arm,raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,eligible_gt,ignored,all_iou_sum,eligible_iou_sum,negative_fp'.split(',')
EQUALITY_HEADER='object_id,scene,image,arm,fallback_count,fused_count,exact_order_fields_score_bits,reference_exact,fallback_match_ms,fused_match_ms,fallback_external_ms,fused_external_ms'.split(',')


def expected_timing_frames(inputs):
    rows=inputs.get('development');need(isinstance(rows,list) and len(rows)==400,'400 development frames required')
    seen=set();result=[]
    for row in rows:
        scene,image=integer(row['scene_id']),integer(row['image_id'])
        need(scene in (1,4,6,7,8,10,12,13) and (scene,image) not in seen,'development identity/heldout scope differs')
        seen.add((scene,image));need(type(row['timing']) is bool,'timing flag must be boolean')
        if row['timing']:result.append((scene,image))
    need(len(result)==64,'exactly 64 timing frames required');return result


def expected_bank_templates(inputs):
    rows=inputs.get('banks');need(isinstance(rows,list) and [r['object_id'] for r in rows]==list(OBJECTS),'bank object order differs')
    result={}
    for row in rows:
        for arm,key in zip(ARMS,('control','pooled','stratified')):
            count=row[key+'_template_count'];need(type(count) is int and count>0,'positive observed bank count required')
            result[(row['object_id'],arm)]=count
    return result


def validate_timing_rows(rows,frame_keys,development_counts,expected_calls=EXPECTED_CALLS,objects=OBJECTS):
    need(len(rows)==expected_calls and len(objects)*len(frame_keys)*13*6==expected_calls,'13-round six-variant call count differs')
    need(len(set(frame_keys))==len(frame_keys) and len(set(objects))==len(objects),'duplicate timing scope')
    formal=defaultdict(list);by_frame={};balance={};index=0
    for obj in objects:
        for ordinal,(scene,image) in enumerate(frame_keys):
            positions={v:{p:0 for p in range(6)} for v in VARIANTS}
            for round_id in range(13):
                current={}
                for order in range(6):
                    row=rows[index];index+=1
                    need(tuple(integer(row[k]) for k in ('object_id','scene','image','frame_ordinal','round','order'))==
                         (obj,scene,image,ordinal,round_id,order),'timing route/frame ordinal/order differs')
                    need(integer(row['warmup'])==int(round_id==0),'warmup flag differs')
                    arm,path=VARIANTS[(order+ordinal+round_id)%6]
                    need((row['arm'],row['path'])==(arm,path),'timing variant rotation differs')
                    match=finite(row['match_ms'],positive=True);external=finite(row['external_call_ms'],positive=True)
                    need(external>=match,'external clock below match clock')
                    raw=integer(row['raw'],maximum=1000000);selected=integer(row['selected'])
                    need(selected<=raw and row['exact_own_reference']=='1','timing count/exact observation differs')
                    need(development_counts.get((obj,scene,image,arm))==(raw,selected),'timing counts differ from own development')
                    sample=dict(object_id=obj,scene=scene,image=image,frame_ordinal=ordinal,round=round_id,order=order,
                        arm=arm,path=path,match_ms=match,external_call_ms=external,raw=raw,selected=selected)
                    current[(arm,path)]=sample
                    if round_id:formal[(arm,path)].append(sample);positions[(arm,path)][order]+=1
                need(set(current)==set(VARIANTS),'all six variants required per round')
                by_frame[(obj,scene,image,round_id)]=current
            for variant,counts in positions.items():
                need(set(counts.values())=={2},'measured order positions must be balanced twice')
                balance[(obj,scene,image,*variant)]=counts
    need(set(formal)==set(VARIANTS) and all(len(formal[v])==len(objects)*len(frame_keys)*12 for v in VARIANTS),
         'formal sample coverage differs')
    return dict(formal=dict(formal),by_frame=by_frame,order_balance=balance)


def validate_pair_rows(rows,by_frame,frame_keys,objects=OBJECTS):
    need(len(rows)==len(objects)*len(frame_keys)*12*2*3,'paired CSV row coverage differs');index=0
    for obj in objects:
        for ordinal,(scene,image) in enumerate(frame_keys):
            for round_id in FORMAL_ROUNDS:
                current=by_frame[(obj,scene,image,round_id)]
                for path in PATHS:
                    for n,d in COMPARISONS:
                        row=rows[index];index+=1
                        need(tuple(integer(row[k]) for k in ('object_id','scene','image','frame_ordinal','round'))==
                             (obj,scene,image,ordinal,round_id) and (row['path'],row['numerator'],row['denominator'])==(path,n,d),
                             'pair identity/round/path/direction differs')
                        a,b=current[(n,path)],current[(d,path)]
                        _close(row['match_ratio'],a['match_ms']/b['match_ms'],'pair/match')
                        _close(row['external_ratio'],a['external_call_ms']/b['external_call_ms'],'pair/external')
    return dict(rows=index)


def recompute_statistics(groups):
    need(set(groups)==set(VARIANTS),'six formal groups required');variants=[]
    for arm,path in VARIANTS:
        values=groups[(arm,path)]
        variants.append(dict(arm=arm,path=path,samples=len(values),
            match_median_ms=nearest_rank((r['match_ms'] for r in values),.5),
            match_p95_ms=nearest_rank((r['match_ms'] for r in values),.95),
            external_median_ms=nearest_rank((r['external_call_ms'] for r in values),.5),
            external_p95_ms=nearest_rank((r['external_call_ms'] for r in values),.95)))
    paired=[]
    for path in PATHS:
        for n,d in COMPARISONS:
            indexes=[]
            for arm in (n,d):
                values=groups[(arm,path)];idx={(r['object_id'],r['scene'],r['image'],r['round']):r for r in values}
                need(len(idx)==len(values),'duplicate paired sample identity');indexes.append(idx)
            left,right=indexes;need(set(left)==set(right),'paired sample scope differs')
            match=[left[k]['match_ms']/right[k]['match_ms'] for k in sorted(left)]
            external=[left[k]['external_call_ms']/right[k]['external_call_ms'] for k in sorted(left)]
            paired.append(dict(path=path,numerator=n,denominator=d,samples=len(match),
                match_ratio_median=nearest_rank(match,.5),match_ratio_p95=nearest_rank(match,.95),
                external_ratio_median=nearest_rank(external,.5),external_ratio_p95=nearest_rank(external,.95)))
    return variants,paired


def validate_stage_summary(summary,variants):
    _summary_match(summary,dict(passed=1,stage='timing',objects=list(OBJECTS),unique_frames=64,
        object_frame_combinations=384,matcher_calls=29952,warmup_rounds=1,measured_rounds=12,formal_rows=27648,
        exact_own_reference_every_call=1,decode_and_bank_load_excluded_from_external_call=1,paired_performance_benchmark=1),'stage_summary')
    finite(summary.get('decode_total_ms'),positive=True);rss=finite(summary.get('peak_rss_bytes'),positive=True)
    need(rss.is_integer() and rss<=1610612736,'timing RSS ceiling differs')
    actual=summary.get('variants');need(isinstance(actual,list) and len(actual)==len(variants)==6,'six variant summaries required')
    for index,expected in enumerate(variants):_summary_match(actual[index],expected,'variant/%d'%index)
    need('paired_empty_mask_over_rgb' not in summary,'old two-arm paired summary leaked into V31')


def _mean(values):
    values=list(values);need(values,'nonempty equal-weight population required');return math.fsum(values)/len(values)


def additional_equal_frame_summary(by_frame,objects=OBJECTS,expected_frames=EXPECTED_FRAMES):
    frames=defaultdict(dict)
    for (obj,scene,image,round_id),samples in by_frame.items():
        if round_id in FORMAL_ROUNDS:frames[(obj,scene,image)][round_id]=samples
    need(len(frames)==len(objects)*expected_frames,'equal-frame coverage differs');items=[]
    for (obj,scene,image),rounds in sorted(frames.items()):
        need(set(rounds)==set(FORMAL_ROUNDS),'all twelve formal rounds required')
        variants={}
        for arm,path in VARIANTS:
            samples=[rounds[r][(arm,path)] for r in FORMAL_ROUNDS]
            variants[arm+'/'+path]=dict(match_median_ms=nearest_rank((s['match_ms'] for s in samples),.5),
                external_median_ms=nearest_rank((s['external_call_ms'] for s in samples),.5))
        comparisons={}
        for path in PATHS:
            for n,d in COMPARISONS:
                ratios={clock:[rounds[r][(n,path)][clock]/rounds[r][(d,path)][clock] for r in FORMAL_ROUNDS]
                        for clock in ('match_ms','external_call_ms')}
                comparisons[n+'/'+d+'/'+path]=dict(match_ratio_median=nearest_rank(ratios['match_ms'],.5),
                    match_ratio_p95=nearest_rank(ratios['match_ms'],.95),
                    external_ratio_median=nearest_rank(ratios['external_call_ms'],.5),
                    external_ratio_p95=nearest_rank(ratios['external_call_ms'],.95))
        items.append(dict(object_id=obj,scene=scene,image=image,variants=variants,comparisons=comparisons))
    def average(values):
        return {section:{key:{'mean_frame_'+field:_mean(v[section][key][field] for v in values)
                for field in values[0][section][key]} for key in values[0][section]}
                for section in ('variants','comparisons')}
    per_object=[]
    for obj in objects:
        subset=[v for v in items if v['object_id']==obj];need(len(subset)==expected_frames,'per-object equal-frame scope differs')
        per_object.append(dict(object_id=obj,frames=len(subset),**average(subset)))
    overall={section:{key:{field:_mean(v[section][key][field] for v in per_object)
                for field in per_object[0][section][key]} for key in per_object[0][section]}
                for section in ('variants','comparisons')}
    regressions=[]
    for path in PATHS:
        for n,d in COMPARISONS:
            key=n+'/'+d+'/'+path
            regressions.append(dict(numerator=n,denominator=d,path=path,frames=len(items),
                frames_match_ratio_gt1=sum(v['comparisons'][key]['match_ratio_median']>1 for v in items),
                frames_external_ratio_gt1=sum(v['comparisons'][key]['external_ratio_median']>1 for v in items),
                frames_match_p95_ratio_gt1=sum(v['comparisons'][key]['match_ratio_p95']>1 for v in items),
                frames_external_p95_ratio_gt1=sum(v['comparisons'][key]['external_ratio_p95']>1 for v in items)))
    return dict(definition='Twelve same-round paired ratios then nearest-rank frame median/p95; equal frame then equal object means',
        frame_medians=items,per_object=per_object,equal_object_overall=overall,frame_regressions=regressions)


def parse_development_counts(data):
    result={}
    for row in csv_rows(data,PER_FRAME_HEADER):
        key=tuple(integer(row[k]) for k in ('object_id','scene','image'))+(row['arm'],)
        need(key[0] in OBJECTS and key[3] in ARMS and key not in result,'development count identity differs')
        raw,selected=integer(row['raw'],maximum=1000000),integer(row['selected']);need(selected<=raw,'selected exceeds raw');result[key]=(raw,selected)
    need(len(result)==6*400*3,'complete development count coverage required');return result


def validate_reference_coverage(inputs,counts,equality_data):
    expected={(obj,integer(f['scene_id']),integer(f['image_id']),arm) for obj in OBJECTS for f in inputs['development'] for arm in ARMS}
    need(set(counts)==expected,'development references differ from frozen frames');seen=set()
    for row in csv_rows(equality_data,EQUALITY_HEADER):
        key=tuple(integer(row[k]) for k in ('object_id','scene','image'))+(row['arm'],)
        need(key in expected and key not in seen,'development equality identity differs');seen.add(key)
        need(integer(row['fallback_count'])==integer(row['fused_count'])==counts[key][0] and
             row['exact_order_fields_score_bits']==row['reference_exact']=='1','development raw/path equality differs')
    need(seen==expected,'development equality coverage differs')


def validate_bank_rows(data,expected_templates,objects=OBJECTS):
    rows=csv_rows(data,BANK_HEADER);keys=[(obj,arm) for obj in objects for arm in ARMS]
    need(len(rows)==len(keys),'bank timing row count differs');result=[]
    for row,key in zip(rows,keys):
        need((integer(row['object_id']),row['arm'])==key and integer(row['templates'],minimum=1)==expected_templates[key],'bank order/count differs')
        result.append(dict(object_id=key[0],arm=key[1],templates=expected_templates[key],
            metadata_load_ms=finite(row['metadata_load_ms'],positive=True),bank_load_ms=finite(row['bank_load_ms'],positive=True)))
    return result
