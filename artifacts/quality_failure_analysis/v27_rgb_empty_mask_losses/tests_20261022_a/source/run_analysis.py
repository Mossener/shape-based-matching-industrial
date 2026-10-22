"""Replay all frozen V27 numeric frames; never open images or run native code."""
import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import traceback

from numeric import (Candidate, assign, bits, check_complete_scope, check_raw_paths,
                     check_selected, diagnose, f32, iou, need, nms_trace, order)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXP = ROOT/'artifacts/rgb_empty_mask_experiment'
NATIVE = EXP/'run_quality_development_v1/native'
OBJECTS = [1, 2, 5, 8, 12, 17]
ARMS = ['rgb_control', 'rgb_empty_mask']
RAW_HEADER = 'scene,image,variant,class_id,rank,score,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h'.split(',')
SELECTED_HEADER = 'object_id,scene,image,arm,rank,class_id,score,score_bits,template_id,training_image,angle,scale,match_x,match_y,bbox_x,bbox_y,bbox_w,bbox_h,allGT_label,allGT_id,eligible_label,eligible_id'.split(',')
PER_HEADER = 'object_id,scene,image,arm,raw,selected,tp,fp,fn,gt,eligible_tp,eligible_fp,eligible_fn,eligible_gt,ignored,all_iou_sum,eligible_iou_sum,negative_fp'.split(',')
EQ_HEADER = 'object_id,scene,image,arm,fallback_count,fused_count,exact_order_fields_score_bits,reference_exact,fallback_match_ms,fused_match_ms,fallback_external_ms,fused_external_ms'.split(',')
GT_HEADER = 'object_id,scene,image,gt_id,class_id,visibility,bbox_x,bbox_y,bbox_w,bbox_h'.split(',')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(data, header):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    need(reader.fieldnames == header, 'CSV schema differs')
    result = list(reader)
    need(all(None not in r and None not in r.values() for r in result), 'CSV row width differs')
    return result


class Evidence:
    def __init__(self, pins):
        self.pins = {str(Path(p['path']).resolve()).casefold(): p for p in pins}
        need(len(self.pins) == len(pins), 'Duplicate audit input pin')
        self.seen = {}

    def read(self, path):
        path = Path(path).resolve(strict=True)
        need(path.is_relative_to(ROOT/'artifacts') and path.suffix.lower() in ('.json', '.csv', '.gz'),
             'Only artifact numeric evidence may be read')
        need(not any(p.casefold() in {'datasets','heldout','magnet_match','磁片'} for p in path.relative_to(ROOT).parts),
             'Prohibited evidence path')
        pin = self.pins.get(str(path).casefold())
        need(pin is not None, 'Evidence not pinned by completed independent V27 audit: '+str(path))
        data = path.read_bytes()
        need(len(data) == pin['bytes'] and sha(data) == pin['sha256'], 'Pinned evidence changed')
        self.seen[str(path)] = dict(path=path.relative_to(ROOT).as_posix(), bytes=len(data), sha256=sha(data))
        return data

    def json(self, path):
        return json.loads(self.read(path))

    def recheck(self):
        for path in list(self.seen):
            self.read(path)


def pose(m):
    return m['training_image_id'], f32(m['angle']), f32(m['scale'])


def parse_candidate(row, obj, metadata):
    template = int(row['template_id'])
    need(row['class_id'] == f'tless_object_{obj}' and template in metadata, 'Candidate class/template differs')
    m = metadata[template]
    score = float(row['score'])
    need(math.isfinite(score) and score == f32(score) and 85 <= score <= 100, 'Invalid float32 raw score')
    x, y = int(row['match_x']), int(row['match_y'])
    sx, sy, w, h = m['warped_mask_bbox']
    box = tuple(float(row['bbox_'+a]) for a in ('x','y','w','h'))
    need(box == (x-64+sx-m['tl_x'], y-64+sy-m['tl_y'], w, h), 'Official box origin differs')
    actual_pose = int(row['training_image']), f32(row['angle']), f32(row['scale'])
    need(actual_pose == pose(m), 'Candidate training pose differs')
    return Candidate(row['class_id'], template, x, y, bits(score), box, actual_pose)


def read_raw(e, obj, arm, frame, path, metadata):
    stem = NATIVE/f'obj{obj}'/arm/f's{frame[0]}_i{frame[1]}_{path}_raw'
    encoded = e.read(str(stem)+'.csv.gz')
    manifest = e.json(str(stem)+'_manifest.json')
    plain = gzip.decompress(encoded)
    table = rows(plain, RAW_HEADER)
    need((manifest['scene_id'], manifest['image_id'], manifest['variant'], manifest['raw_candidate_count'],
          manifest['compressed_bytes'], manifest['uncompressed_bytes']) ==
         (*frame, path, len(table), len(encoded), len(plain)), 'Raw archive manifest differs')
    result = []
    for rank, row in enumerate(table):
        need((int(row['scene']),int(row['image']),row['variant'],int(row['rank'])) == (*frame,path,rank),
             'Raw frame/rank/path differs')
        result.append(parse_candidate(row,obj,metadata))
    need(result == sorted(result,key=order), 'Raw canonical order differs')
    return result


def write_csv(path, records, header=None):
    with path.open('w', newline='', encoding='utf-8') as stream:
        header = header or list(records[0])
        writer = csv.DictWriter(stream, fieldnames=header)
        writer.writeheader()
        for record in records:
            writer.writerow({k: json.dumps(v,separators=(',',':')) if isinstance(v,(list,tuple,dict)) else v
                             for k,v in record.items()})


def candidate_fields(raw, rank, prefix):
    c = raw[rank]
    return {prefix+k:v for k,v in dict(raw_rank=rank,class_id=c.cls,template_id=c.template,
            match_x=c.x,match_y=c.y,score_bits=c.score_bits,score=c.score,box=c.box,pose=c.pose).items()}


def run(output, protocol):
    audit_path = ROOT/protocol['audit_receipt']['path']
    audit_data = audit_path.read_bytes()
    need(sha(audit_data) == protocol['audit_receipt']['sha256'], 'Frozen independent V27 audit changed')
    audit = json.loads(audit_data)
    need(audit['passed'] is True and audit['stage']=='development' and audit['object_frame_pairs']==2400,
         'Independent V27 audit scope differs')
    e = Evidence(audit['input_pins'])
    inputs = e.json(EXP/'QUALITY_INPUT_FREEZE.json')
    need(inputs['objects']==OBJECTS, 'Objects differ')
    frames = [(r['scene_id'],r['image_id']) for r in inputs['development']]
    need(len(frames)==len(set(frames))==400 and sorted({s for s,_ in frames})==protocol['scope']['scenes'],
         'Frozen frame scope differs')
    expected={(obj,*frame,arm) for obj in OBJECTS for frame in frames for arm in ARMS}
    gt_by_frame=defaultdict(list)
    for r in rows(e.read(NATIVE/'ground_truth.csv'),GT_HEADER):
        obj,scene,image,gid=(int(r[k]) for k in ('object_id','scene','image','gt_id'))
        need(obj in OBJECTS and (scene,image) in frames and r['class_id']==f'tless_object_{obj}', 'GT scope differs')
        gt_by_frame[(obj,scene,image)].append(dict(gt_id=gid,box=tuple(float(r['bbox_'+a]) for a in ('x','y','w','h')),
                                                      visibility=float(r['visibility'])))
    need(sum(map(len,gt_by_frame.values()))==400, 'GT identities incomplete')
    selected=defaultdict(list)
    for r in rows(e.read(NATIVE/'selected_detections.csv'),SELECTED_HEADER):
        key=(int(r['object_id']),int(r['scene']),int(r['image']),r['arm'])
        need(key in expected and int(r['rank'])==len(selected[key]), 'Selected scope/rank differs')
        selected[key].append(r)
    per_rows=rows(e.read(NATIVE/'per_frame_metrics.csv'),PER_HEADER)
    key_for=lambda r:(int(r['object_id']),int(r['scene']),int(r['image']),r['arm'])
    check_complete_scope([key_for(r) for r in per_rows],expected)
    per={key_for(r):r for r in per_rows}
    equality_rows=rows(e.read(NATIVE/'candidate_equality.csv'),EQ_HEADER)
    check_complete_scope([key_for(r) for r in equality_rows],expected)
    equality={key_for(r):r for r in equality_rows}
    summary=e.json(NATIVE/'stage_summary.json')
    totals={a:Counter() for a in ARMS}; gt_arm_rows=[]; gt_rows=[]; edges=[]; competitions=[]; frame_rows=[]
    for obj in OBJECTS:
        bank=next(b for b in inputs['rgb_banks'] if b['object_id']==obj)
        metadata={}
        for arm,directory,count in [('rgb_control',bank['rgb_training'],bank['rgb_template_count']),
                                    ('rgb_empty_mask',bank['treatment_training'],bank['treatment_template_count'])]:
            records=e.json(Path(directory)/'template_metadata.json')['templates']
            need(len(records)==count and [m['template_id'] for m in records]==list(range(count)), 'Bank count/order differs')
            metadata[arm]={m['template_id']:m for m in records}
        for scene,image in frames:
            truth=gt_by_frame[(obj,scene,image)]
            need(len({t['gt_id'] for t in truth})==len(truth), 'Duplicate GT identity')
            values={}
            for arm in ARMS:
                key=(obj,scene,image,arm)
                raw=read_raw(e,obj,arm,(scene,image),'fallback',metadata[arm])
                fused=read_raw(e,obj,arm,(scene,image),'fused',metadata[arm])
                check_raw_paths(raw,fused)
                kept,blockers=nms_trace(raw)
                labels=assign(raw,kept,truth); eligible=assign(raw,kept,truth,True)
                actual=[]
                for r in selected[key]:
                    c=parse_candidate(r,obj,metadata[arm]);need(int(r['score_bits'])==c.score_bits,'Selected score bits differ')
                    actual.append((c,(r['allGT_label'],int(r['allGT_id'])),(r['eligible_label'],int(r['eligible_id']))))
                check_selected(raw,kept,actual,labels,eligible)
                counts=Counter(label for label,_ in labels); ec=Counter(label for label,_ in eligible)
                expected_counts=dict(raw=len(raw),selected=len(kept),tp=counts['TP'],fp=counts['FP'],fn=len(truth)-counts['TP'],gt=len(truth),
                    eligible_tp=ec['TP'],eligible_fp=ec['FP'],eligible_fn=sum(t['visibility']>=.5 for t in truth)-ec['TP'],
                    eligible_gt=sum(t['visibility']>=.5 for t in truth),ignored=ec['IGNORE'],negative_fp=counts['FP'] if not truth else 0)
                need(all(int(per[key][k])==v for k,v in expected_counts.items()),'Per-frame numeric totals differ')
                need(int(equality[key]['fallback_count'])==int(equality[key]['fused_count'])==len(raw) and
                     equality[key]['exact_order_fields_score_bits']==equality[key]['reference_exact']=='1','Raw equality totals differ')
                totals[arm].update(expected_counts)
                frame_rows.append(dict(object_id=obj,scene=scene,image=image,arm=arm,**expected_counts))
                label_map=dict(zip(kept,labels)); eligible_map=dict(zip(kept,eligible)); arm_diagnostics={}
                for t in truth:
                    d=diagnose(t['gt_id'],truth,raw,kept,blockers,labels);arm_diagnostics[t['gt_id']]=d
                    common=dict(object_id=obj,scene=scene,image=image,gt_id=t['gt_id'],arm=arm,visibility=t['visibility'])
                    entry=dict(**common,**{k:v for k,v in d.items() if k not in ('hit_ranks','selected_hit_ranks','suppression','competition')})
                    entry['nms_blocker_fp_edges']=sum(r['blocker_is_fp'] for r in d['suppression'])
                    entry['nms_blocker_tp_edges']=sum(not r['blocker_is_fp'] for r in d['suppression'])
                    gt_arm_rows.append(entry)
                    for edge in d['suppression']:
                        first=edge['blocker_raw_rank']; rank=edge['raw_rank']
                        edges.append(dict(**common,category=d['category'],**edge,
                            candidate_gt_iou=iou(raw[rank].box,t['box']),blocker_gt_iou=iou(raw[first].box,t['box']),
                            candidate_blocker_iou=iou(raw[rank].box,raw[first].box),
                            blocker_eligible_label=eligible_map[first][0],blocker_eligible_gt_id=eligible_map[first][1],
                            **candidate_fields(raw,rank,'candidate_'),**candidate_fields(raw,first,'blocker_')))
                    for conflict in d['competition']:
                        r=conflict['raw_rank']; owner=next(g for g in truth if g['gt_id']==conflict['selected_gt_id'])
                        competitions.append(dict(**common,**conflict,candidate_gt_iou=iou(raw[r].box,t['box']),
                            assigned_owner_iou=iou(raw[r].box,owner['box']),**candidate_fields(raw,r,'candidate_')))
                values[arm]=arm_diagnostics
            for t in truth:
                a=values[ARMS[0]][t['gt_id']]; b=values[ARMS[1]][t['gt_id']]
                status='retained' if a['matched'] and b['matched'] else 'lost' if a['matched'] else 'gained' if b['matched'] else 'neither'
                gt_rows.append(dict(object_id=obj,scene=scene,image=image,gt_id=t['gt_id'],visibility=t['visibility'],status=status,
                    rgb_control_category=a['category'],rgb_empty_mask_category=b['category'],
                    rgb_control_best_raw_iou=a['best_raw_iou'],rgb_empty_mask_best_raw_iou=b['best_raw_iou']))
        print(json.dumps(dict(object_id=obj,object_frames=400,arms=2,all_raw_and_selected_replayed=True)),flush=True)
    status=Counter(r['status'] for r in gt_rows)
    need(status==Counter(protocol['frozen_expected']['allGT_status']),'GT cross-arm identity closure differs')
    for arm in ARMS:
        frozen=protocol['frozen_expected'][arm]
        need(all(totals[arm][k]==v for k,v in frozen.items()),'Frozen total TP/FP/raw differs')
        need(totals[arm]['tp']==summary[arm]['allGT']['tp'] and totals[arm]['eligible_tp']==summary[arm]['visibility_ge_0_5']['tp'],
             'Native pooled TP differs')
    # Every GT/arm row receives its cross-arm stratum only after full replay.
    identity_status={(r['object_id'],r['scene'],r['image'],r['gt_id']):r['status'] for r in gt_rows}
    for row in gt_arm_rows:
        row['status']=identity_status[tuple(row[k] for k in ('object_id','scene','image','gt_id'))]
    def group_report(obj=None,scene=None,status=None):
        values=[r for r in gt_arm_rows if (obj is None or r['object_id']==obj) and
                (scene is None or r['scene']==scene) and (status is None or r['status']==status)]
        return {a:dict(sorted(Counter(r['category'] for r in values if r['arm']==a).items())) for a in ARMS}
    e.recheck();need(audit_path.read_bytes()==audit_data,'Independent audit changed during diagnosis')
    result=dict(passed=True,version=protocol['version'],full_object_frame_arm_replays=4800,
        development_frames=400,object_frame_pairs=2400,gt_identities=400,gt_arm_rows=800,
        full_raw_rows_per_path={a:totals[a]['raw'] for a in ARMS},full_selected_totals={a:dict(totals[a]) for a in ARMS},
        identity_status=dict(status),categories=group_report(),
        by_status={s:group_report(status=s) for s in ('retained','lost','gained','neither')},
        per_object=[dict(object_id=o,categories=group_report(obj=o)) for o in OBJECTS],
        per_scene=[dict(scene=s,categories=group_report(scene=s)) for s in protocol['scope']['scenes']],
        suppression_edges=len(edges),suppression_edges_by_blocker_label=dict(Counter(r['blocker_label'] for r in edges)),
        assignment_competition_edges=len(competitions),matcher_calls=0,image_decodes=0,dataset_files_opened=0,
        heldout_frames_processed=0,reserved_objects_processed=0,limitations=protocol['limits'],
        audit_receipt=protocol['audit_receipt'],input_pins=list(e.seen.values()))
    write_csv(output/'per_gt_arm.csv',gt_arm_rows);write_csv(output/'per_gt.csv',gt_rows)
    write_csv(output/'per_frame.csv',frame_rows)
    write_csv(output/'suppression_edges.csv',edges,header=list(edges[0]) if edges else ['object_id','scene','image','gt_id','arm','raw_rank','blocker_raw_rank','blocker_label','blocker_is_fp'])
    write_csv(output/'assignment_competition.csv',competitions,header=list(competitions[0]) if competitions else ['object_id','scene','image','gt_id','arm','raw_rank','selected_gt_id'])
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();need(output.is_relative_to(HERE) and not output.exists(),'Fresh contained output required')
    output.mkdir();source=output/'source';source.mkdir()
    pins=[]
    for name in ['numeric.py','run_analysis.py','test_diagnostic.py','PROTOCOL.json','ORIGIN.json']:
        data=(HERE/name).read_bytes();(source/name).write_bytes(data)
        pins.append(dict(name=name,bytes=len(data),sha256=sha(data)))
    (output/'source_pins.json').write_text(json.dumps(pins,indent=2)+'\n')
    try:
        result=run(output,json.loads((HERE/'PROTOCOL.json').read_text()))
        print(json.dumps(dict(passed=True,identity_status=result['identity_status'],categories=result['categories'])))
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),partial_not_quality_evidence=True,
                                                         matcher_calls=0,image_decodes=0),indent=2)+'\n')
        (output/'traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise


if __name__=='__main__':
    main()
