"""Join independent numeric timing calculations with frozen V31 evidence."""
import argparse
import json
from pathlib import Path
import timing_audit as a
from evidence import Reader,loads,pin_schema,stage_gate,stage_read,validate_execution

HERE=Path(__file__).resolve().parent
EXPERIMENT=HERE.parent
ROOT=EXPERIMENT.parents[1]
REFS=('timing_stage','development_stage','quality_inputs','build_manifest','selftest','development_audit','quality_acceptance')


def acceptance_gate(reader,pins,timing):
    prior=loads(reader.check(pins['development_audit']));acceptance=loads(reader.check(pins['quality_acceptance']))
    a.need(prior.get('schema')=='independent_three_arm_quality_audit_v1' and prior.get('passed') is True and
        prior.get('numeric_audit_passed') is True and prior.get('scope')=='quality_all_three_arms' and
        prior.get('development_stage')==pins['development_stage'] and prior.get('arms')==list(a.ARMS) and
        prior.get('object_frame_pairs')==2400 and prior.get('production_promotion') is False and
        prior.get('common_padding_C0_full_raw_exact') is True and prior.get('pilot_overlap_full_raw_exact') is True,
        'complete independent three-arm development audit required')
    a.need(reader.index(prior['input_pins']).get(pins['development_stage']['path'])==pins['development_stage'],
        'independent development audit stage binding differs')
    a.need(acceptance.get('accepted_independent_audit') is True and acceptance.get('numeric_audit_passed') is True and
        acceptance.get('scope')=='quality_all_three_arms' and acceptance.get('production_promotion') is False and
        type(acceptance.get('primary_accuracy_hypothesis_passed')) is bool and
        acceptance['primary_accuracy_hypothesis_passed']==prior['primary_accuracy_hypothesis_passed'] and
        acceptance.get('development_stage')==pins['development_stage'] and acceptance.get('independent_audit')==pins['development_audit'],
        'independent quality acceptance binding differs')
    expected=dict(acceptance=pins['quality_acceptance'],independent_audit=pins['development_audit'],
        development_stage=pins['development_stage'],primary_accuracy_hypothesis_passed=acceptance['primary_accuracy_hypothesis_passed'])
    a.need(timing.get('quality_audit')==expected,'timing native independent audit gate binding differs')
    return prior,acceptance


def run(input_pin,output):
    output=Path(output).resolve();a.need(output.is_relative_to(HERE) and not output.exists(),'fresh contained timing audit output required')
    output.mkdir(parents=True);reader=Reader(ROOT);spec=loads(reader.check(input_pin))
    a.need(spec.get('schema')=='rgb_stratified_independent_timing_inputs_v1','timing audit input schema differs')
    pins={name:spec[name] for name in REFS}
    for pin in pins.values():pin_schema(pin)
    timing,native=stage_gate(reader,pins['timing_stage'],'timing',29952,True)
    development,previous=stage_gate(reader,pins['development_stage'],'development',14400)
    selftest,_=stage_gate(reader,pins['selftest'],'selftest',0)
    build=loads(reader.check(pins['build_manifest']))
    a.need(build.get('passed') is True and build.get('target')=='rgb_stratified_quality','separate quality build required')
    a.need(development['quality_inputs']==selftest['quality_inputs']==pins['quality_inputs'] and
        development['build_manifest']==selftest['build_manifest']==pins['build_manifest'],'development/selftest input/source binding differs')
    inputs=loads(reader.check(pins['quality_inputs']))
    a.need(inputs.get('version')==a.INPUT_VERSION and inputs.get('objects')==list(a.OBJECTS) and
        inputs.get('arms')==list(a.ARMS) and inputs.get('total_matcher_call_budget')==44736 and all(inputs.get(k)==0 for k in
        ('dataset_image_reads','training_image_reads','image_decodes','matcher_calls')),'V31 timing input scope differs')
    frames=a.expected_timing_frames(inputs);templates=a.expected_bank_templates(inputs)
    prior,acceptance=acceptance_gate(reader,pins,timing)
    validate_execution(reader,timing,pins['timing_stage'],native,pins,build)
    counts=a.parse_development_counts(stage_read(reader,development,previous/'per_frame_metrics.csv',prior))
    a.validate_reference_coverage(inputs,counts,stage_read(reader,development,previous/'candidate_equality.csv',prior))
    archive_pins=reader.index(development['files']);prior_pins=reader.index(prior['input_pins'])
    for obj in a.OBJECTS:
        for scene,image in frames:
            for arm in a.ARMS:
                for path in a.PATHS:
                    prefix=f's{scene}_i{image}_{path}_raw';directory=previous/f'obj{obj}'/arm
                    manifest=loads(stage_read(reader,development,directory/(prefix+'_manifest.json'),prior))
                    a.need((manifest['scene_id'],manifest['image_id'],manifest['variant'])==(scene,image,path) and
                        manifest['class_id']==f'tless_object_{obj}' and manifest['class_ids']==[f'tless_object_{obj}'] and
                        manifest['raw_candidate_count']==counts[(obj,scene,image,arm)][0],'own development raw manifest identity/count differs')
                    archive=str((directory/(prefix+'.csv.gz')).resolve());pin=archive_pins.get(archive)
                    a.need(pin is not None and prior_pins.get(archive)==pin and pin['bytes']>0 and
                        str(Path(manifest['path']).resolve())==archive,'own development raw signature binding differs')
    rows=a.csv_rows(stage_read(reader,timing,native/'timing_samples.csv'),a.TIMING_HEADER)
    grouped=a.validate_timing_rows(rows,frames,counts)
    pairs=a.validate_pair_rows(a.csv_rows(stage_read(reader,timing,native/'timing_pairs.csv'),a.PAIR_HEADER),grouped['by_frame'],frames)
    bank_rows=a.validate_bank_rows(stage_read(reader,timing,native/'bank_load_timings.csv'),templates)
    variants,paired=a.recompute_statistics(grouped['formal']);summary=loads(stage_read(reader,timing,native/'stage_summary.json'))
    a.need(summary==timing['summary'],'timing frozen/native summary differs');a.validate_stage_summary(summary,variants)
    additional=a.additional_equal_frame_summary(grouped['by_frame'])
    sources=sorted(p for p in HERE.iterdir() if p.is_file() and p.suffix in ('.py','.md','.json'))
    (output/'source').mkdir()
    for path in sources:(output/'source'/path.name).write_bytes(reader.read(path))
    reader.recheck()
    result=dict(schema='independent_three_arm_timing_audit_v1',passed=True,numeric_audit_passed=True,
        timing_rows=len(rows),formal_rows=27648,paired_rows=pairs['rows'],stage='timing',variants=variants,
        paired_same_round=paired,additional_equal_frame=additional,bank_load_timings=bank_rows,
        balanced_order_positions_per_frame_variant=2,formal_samples_per_variant=4608,
        timing_stage=pins['timing_stage'],development_stage=pins['development_stage'],quality_acceptance=pins['quality_acceptance'],
        primary_accuracy_hypothesis_passed=prior['primary_accuracy_hypothesis_passed'],production_promotion=False,
        native_runs=0,image_reads=0,image_decodes=0,matcher_calls=0,input_pins=list(reader.seen.values()),
        limitations=['Timed full raw output is not archived; native exact_own_reference observations cannot independently reconstruct each timed call.',
            'Own-arm raw archive signatures are linked to the completed independent quality audit without reopening gzip payloads.',
            'Decode, bank load, output and raw comparison are excluded from paired external-call clocks.',
            'Warm workspaces on fixed development frames do not establish cold-start or heldout industrial performance.'])
    (output/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--inputs',type=Path,required=True)
    ap.add_argument('--inputs-sha256',required=True);ap.add_argument('--inputs-bytes',type=int,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--cpu-slot-granted',action='store_true')
    args=ap.parse_args();a.need(args.cpu_slot_granted,'Await independent numeric timing audit CPU grant')
    pin=dict(path=str(args.inputs.resolve()),bytes=args.inputs_bytes,sha256=args.inputs_sha256)
    out=args.output.resolve();absent=not out.exists()
    try:result=run(pin,out)
    except Exception as error:
        if absent and out.is_relative_to(HERE) and out.is_dir():
            (out/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),native_runs=0,image_decodes=0,
                no_timing_claim_from_partial_evidence=True),indent=2)+'\n',encoding='utf-8')
        raise
    print(json.dumps(dict(passed=result['passed'],formal_rows=result['formal_rows'],paired_rows=result['paired_rows'],native_runs=0)))


if __name__=='__main__':main()
