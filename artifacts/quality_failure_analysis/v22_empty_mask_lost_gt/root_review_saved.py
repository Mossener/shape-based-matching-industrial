"""Independent saved-table arithmetic and source/input integrity review."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def main():
    run=HERE/'run_20261022_v1'
    result=json.loads((run/'result.json').read_bytes())
    for pin in result['input_pins']+result['source_pins']:
        data=(ROOT/pin['path']).read_bytes()
        assert len(data)==pin['bytes'] and hashlib.sha256(data).hexdigest()==pin['sha256'],pin['path']
    with (run/'per_gt.csv').open(encoding='utf-8',newline='') as stream:
        gt=list(csv.DictReader(stream))
    with (run/'per_positive_frame.csv').open(encoding='utf-8',newline='') as stream:
        frames=list(csv.DictReader(stream))
    identities={(int(r['object_id']),int(r['scene']),int(r['image']),int(r['gt_id'])) for r in gt}
    assert len(identities)==len(gt)==400
    assert Counter(r['status'] for r in gt)==dict(retained=148,lost=67,new=59,neither=126)
    lost=[r for r in gt if r['status']=='lost']
    assert Counter(r['binary_category'] for r in lost)==dict(no_raw_candidate_ge_0_5=57,all_overlapping_raw_suppressed_by_nms=10)
    for obj in [1,2,5,8,12,17]:
        subset=[r for r in gt if int(r['object_id'])==obj]
        native=next(r for r in result['per_object'] if r['object_id']==obj)
        assert len(subset)==native['gt'] and Counter(r['status'] for r in subset)==native['status']
        assert Counter(r['binary_category'] for r in subset if r['status']=='lost')==native['lost_categories']
    for arm in ['rgb','binary_empty_mask']:
        subset=[r for r in frames if r['arm']==arm]
        assert len(subset)==350
        for field,total in result['capacity'][arm].items():
            assert sum(int(r[field]) for r in subset)==total,(arm,field)
        for r in subset:
            assert int(r['gt'])>=int(r['raw_capacity'])>=int(r['selected_capacity'])>=int(r['actual_tp'])
            assert int(r['raw_capacity_deficit'])+int(r['raw_to_selected_capacity_loss'])+int(r['assignment_capacity_loss'])==int(r['gt'])-int(r['actual_tp'])
    details=json.loads((run/'lost_gt_details.json').read_bytes())
    assert len(details)==67
    nms=[r for r in details if r['binary_category']=='all_overlapping_raw_suppressed_by_nms']
    assert len(nms)==10
    blockers=[b for r in nms for b in r['suppression_blockers']]
    assert blockers and all(b['selected_label']=='FP' and b['selected_gt_id']==-1 and b['gt_iou']<.5 for b in blockers)
    assert all(r['rgb_tp_pose_in_binary_bank'] and r['binary_bank_best_size_iou']>=.5 for r in details)
    report=dict(passed=True,source_and_input_pins=len(result['input_pins'])+len(result['source_pins']),gt_rows=len(gt),positive_frame_arm_rows=len(frames),lost=67,no_postconsolidation_raw=57,nms_losses=10,all_nms_blockers_selected_fp=True,matcher_calls=0,image_decodes=0,limitation='Arithmetic/source review; does not independently rerun NMS or interpret pixel evidence.',reviewed_result_sha256=hashlib.sha256((run/'result.json').read_bytes()).hexdigest())
    destination=HERE/'root_review_saved_20261022.json'
    with destination.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(report))

if __name__=='__main__':
    main()
