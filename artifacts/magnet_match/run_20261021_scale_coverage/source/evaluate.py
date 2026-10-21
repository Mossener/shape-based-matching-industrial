"""Independent coarse box evaluation. No matcher execution or parameter fitting."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

def iou(a,b):
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    intersection=max(0,min(ax+aw,bx+bw)-max(ax,bx))*max(0,min(ay+ah,by+bh)-max(ay,by))
    union=aw*ah+bw*bh-intersection
    return intersection/union if union>0 else 0.

def nms(predictions,threshold=.3):
    ordered=sorted(predictions,key=lambda p:(-p['score'],p['template_id'],p['match_y'],p['match_x']))
    kept=[]
    for p in ordered:
        if not any(iou(p['box'],q['box'])>threshold for q in kept):kept.append(p)
    return kept

def count(predictions,gt,threshold=.5):
    available=set(range(len(gt)));tp=0
    for p in predictions:
        best=sorted(((iou(p['box'],gt[j]),j) for j in available),key=lambda q:(-q[0],q[1]))
        if best and best[0][0]>=threshold:
            available.remove(best[0][1]);tp+=1
    return dict(tp=tp,fp=len(predictions)-tp,fn=len(available),gt=len(gt))

def selftest():
    assert iou([0,0,10,10],[0,0,10,10])==1
    assert iou([0,0,10,10],[10,0,10,10])==0
    assert iou([0,0,5,10],[0,0,10,10])==.5
    def p(box,score,tid):return dict(box=box,score=score,template_id=tid,match_x=box[0],match_y=box[1])
    raw=[p([0,0,10,10],99,2),p([1,0,10,10],98,1),p([30,30,10,10],80,3)]
    kept=nms(raw);assert len(kept)==2
    assert count(kept,[[0,0,10,10]])==dict(tp=1,fp=1,fn=0,gt=1)
    assert count([],[[0,0,10,10]])==dict(tp=0,fp=0,fn=1,gt=1)
    assert count([raw[0]],[])==dict(tp=0,fp=1,fn=0,gt=0)
    assert count([p([0,0,5,10],99,0)],[[0,0,10,10]])['tp']==1

def evaluate(run,annotations):
    selftest()
    with (run/'matcher_candidates.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    by_image=defaultdict(list)
    for r in rows:
        p=dict(score=float(r['score']),template_id=int(r['template_id']),match_x=float(r['match_x']),match_y=float(r['match_y']),
               angle=float(r['angle_deg']),scale=float(r['scale']),
               box=[float(r['feature_bbox_'+k]) for k in ['x','y','w','h']])
        assert p['score']>=75 and p['box'][2]>0 and p['box'][3]>0
        by_image[(int(r['levels']),r['image'])].append(p)
    data=json.loads(annotations.read_text(encoding='utf-8'));images={r['file']:r for r in data['images']}
    with (run/'results.csv').open(newline='') as f:frames=list(csv.DictReader(f))
    assert len(frames)==7 and {r['image'] for r in frames}==set(images)
    output=[];groups=defaultdict(lambda:dict(tp=0,fp=0,fn=0,gt=0,images=0))
    for row in frames:
        raw=by_image[(int(row['levels']),row['image'])]
        assert len(raw)==int(row['candidates'])
        annotation=images[row['image']];gt=[o['bbox_xywh'] for o in annotation['objects']]
        kept=nms(raw);metrics=count(kept,gt)
        # Extra raw records overlapping a GT are duplicate hypotheses, not parts.
        matching_raw=sum(any(iou(p['box'],g)>=.5 for g in gt) for p in raw)
        touched_gt=sum(any(iou(p['box'],g)>=.5 for p in raw) for g in gt)
        item=dict(image=row['image'],levels=int(row['levels']),role=annotation['role'],raw_count=len(raw),
                  raw_matching_gt=matching_raw,raw_duplicate_hypotheses=max(0,matching_raw-touched_gt),
                  after_nms=len(kept),counts=metrics,best_iou=max((iou(p['box'],g) for p in kept for g in gt),default=0),detections=kept)
        output.append(item);group='source_selfcheck' if row['image']=='M01.bmp' else 'non_source_regression'
        groups[group]['images']+=1
        for k,v in metrics.items():groups[group][k]+=v
    for g in groups.values():
        g['precision']=g['tp']/(g['tp']+g['fp']) if g['tp']+g['fp'] else 0.
        g['recall']=g['tp']/(g['tp']+g['fn']) if g['tp']+g['fn'] else 0.
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(annotation_sha256=sha(annotations),raw_csv_sha256=sha(run/'matcher_candidates.csv'),
                results_csv_sha256=sha(run/'results.csv'),evaluator_sha256=sha(Path(__file__)),
                nms_iou=.3,nms_suppression_rule='IoU > .3',match_iou=.5,
                box_rule='Continuous L0 transformed point extent [min,max], width=max-min; no +1 or clipping',
                literal_tests_passed=True,groups=groups,images=output,
                limitations=['Seven supplied positive images only; source selfcheck separate',
                             'Manual boxes approximate +/-3 pixels; no pixel/angle/scale truth',
                             'No negative-image false-positive probability or general industrial accuracy',
                             'All images previously observed; this is same-group regression, not heldout'])
    (run/'coarse_localization.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(groups=groups,per_image=[{k:r[k] for k in ['image','raw_count','raw_duplicate_hypotheses','after_nms','counts','best_iou']} for r in output]),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path,nargs='?');p.add_argument('--annotations',type=Path,default=Path(__file__).with_name('manual_boxes.json'));p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test:selftest();print('PASS literal IoU, strict NMS, one-to-one, equality threshold, empty and negative examples')
    else:
        if a.run is None:p.error('run directory required')
        evaluate(a.run,a.annotations)
