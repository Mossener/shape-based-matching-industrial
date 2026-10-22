"""Second, standalone clock arithmetic review; no target/auditor imports."""
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
EXP=ROOT/'artifacts/silhouette_empty_mask_experiment'

def q(values,p):
    return sorted(values)[math.ceil(len(values)*p)-1]

def close(a,b):
    assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12),(a,b)

def main():
    csvpath=EXP/'run_quality_timing_v1/native/timing_samples.csv'
    summarypath=EXP/'run_quality_timing_v1/native/stage_summary.json'
    native=json.loads(summarypath.read_bytes())
    inputs=json.loads((EXP/'QUALITY_INPUT_FREEZE.json').read_bytes())
    frames=[(r['scene_id'],r['image_id']) for r in inputs['development'] if r['timing']]
    with csvpath.open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    assert len(frames)==64 and len(rows)==12288
    variants=[('rgb','fallback'),('rgb','fused'),('binary_empty_mask','fallback'),('binary_empty_mask','fused')]
    desired=[(obj,scene,image,round_,order,*variants[(order+round_)%4]) for obj in [1,2,5,8,12,17] for scene,image in frames for round_ in range(8) for order in range(4)]
    values=defaultdict(lambda:defaultdict(list))
    pairs=defaultdict(dict)
    for row,route in zip(rows,desired):
        actual=tuple(int(row[k]) for k in ['object_id','scene','image','round','order'])+(row['arm'],row['path'])
        assert actual==route
        assert int(row['warmup'])==int(route[3]==0) and int(row['exact_own_reference'])==1
        match,external=float(row['match_ms']),float(row['external_call_ms'])
        assert math.isfinite(match) and math.isfinite(external) and 0<match<=external
        if route[3]==0:
            continue
        for metric,value in [('match',match),('external',external)]:
            values[(row['arm'],row['path'])][metric].append(value)
            key=route[:4]+(row['path'],metric)
            assert row['arm'] not in pairs[key]
            pairs[key][row['arm']]=value
    for v in native['variants']:
        group=values[(v['arm'],v['path'])]
        assert all(len(a)==v['samples']==2688 for a in group.values())
        for metric,a in group.items():
            close(q(a,.5),v[metric+'_median_ms']);close(q(a,.95),v[metric+'_p95_ms'])
    ratios=defaultdict(list)
    frame_ratios=defaultdict(list)
    for key,arms in pairs.items():
        assert set(arms)=={'rgb','binary_empty_mask'}
        ratio=arms['binary_empty_mask']/arms['rgb']
        ratios[key[-2:]].append(ratio)
        frame_ratios[key[:3]+key[-2:]].append(ratio)
    for v in native['paired_binary_over_rgb']:
        for metric in ['match','external']:
            a=ratios[(v['path'],metric)]
            assert len(a)==v['samples']==2688
            close(q(a,.5),v[metric+'_ratio_median']);close(q(a,.95),v[metric+'_ratio_p95'])
    detail={}
    for path in ['fallback','fused']:
        for metric in ['match','external']:
            medians=[statistics.median(v) for k,v in frame_ratios.items() if k[-2:]==(path,metric)]
            assert len(medians)==384
            detail[path+'/'+metric]=dict(frames=384,regressions=sum(v>1 for v in medians),mean_frame_paired_median=statistics.mean(medians),per_object=[])
            for obj in [1,2,5,8,12,17]:
                group=[statistics.median(v) for k,v in frame_ratios.items() if k[0]==obj and k[-2:]==(path,metric)]
                assert len(group)==64
                detail[path+'/'+metric]['per_object'].append(dict(object_id=obj,frames=64,regressions=sum(v>1 for v in group),mean_frame_paired_median=statistics.mean(group)))
    report=dict(passed=True,timing_rows=len(rows),formal_rows=sum(len(v['match']) for v in values.values()),route_and_native_quantiles_recomputed=True,frame_regressions=detail,matcher_calls=0,image_decodes=0,input_pins=[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [csvpath,summarypath,EXP/'QUALITY_INPUT_FREEZE.json']],limitation='Second route/arithmetic check; full timed raw rows were not archived and are not independently reconstructed.')
    with (HERE/'root_arithmetic_review_20261022.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(report))

if __name__=='__main__':
    main()
