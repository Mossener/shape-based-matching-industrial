"""Parent stage completion/schedule gate, distinct from full numeric quality audit."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=ROOT/'artifacts/silhouette_empty_mask_experiment'
sys.path.insert(0,str(HERE))
import run_quality as q
import native_provenance as p


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('old_gate','pilot','development'),required=True)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    p.require(not args.output.exists(),'Fresh receipt required')
    source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    _,build_pin=q.build_gate(HERE/'build_quality_v1/build_manifest.json')
    input_pin=p.file_pin(HERE/'QUALITY_INPUT_FREEZE.json')
    q.stage_gate(HERE/'run_quality_selftest_v1','selftest',build_pin,input_pin)
    stage,stage_pin=q.stage_gate(args.run,args.stage,build_pin,input_pin)
    frozen=q.load(HERE/'QUALITY_INPUT_FREEZE.json')
    frames=[(f['scene_id'],f['image_id']) for f in frozen['development']
            if args.stage=='development' or f['pilot']]
    arms=['rgb'] if args.stage=='old_gate' else ['rgb','binary_empty_mask']
    path=args.run/'native/candidate_equality.csv'
    rows=list(csv.DictReader(io.StringIO(path.read_text())))
    expected=[(str(o),str(s),str(i),arm) for o in [1,2,5,8,12,17]
              for s,i in frames for arm in arms]
    p.require([(r['object_id'],r['scene'],r['image'],r['arm']) for r in rows]==expected,
              'Exact fixed stage route differs')
    p.require(all(r['exact_order_fields_score_bits']==r['reference_exact']=='1' and
                  int(r['fallback_count'])==int(r['fused_count'])>=0 for r in rows),
              'Native complete ordered equality declaration failed')
    s=stage['summary']
    p.require(s['objects']==[1,2,5,8,12,17] and s['unique_frames']==len(frames) and
              s['object_frame_combinations']==6*len(frames) and
              s['exact_same_arm_paths']==s['complete_raw_archives']==1 and
              s['paired_performance_benchmark']==0,'Stage scope differs')
    q.inputs.verify()
    p.require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==source_sha,'Source changed')
    report=dict(passed=True,stage=args.stage,stage_freeze=stage_pin,build_manifest=build_pin,
                quality_inputs=input_pin,equality_csv=p.file_pin(path),rows=len(rows),
                native_declared_matcher_calls=s['matcher_calls'],matcher_calls_in_review=0,
                image_decodes_in_review=0,audit_source_sha256=source_sha,
                limitation='Source/byte/schedule/completion gate; native declares exact raw equality, full independent quality arithmetic remains separate')
    with args.output.open('x') as stream:
        stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
