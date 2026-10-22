"""Run the complete observer only with root's native CPU-slot grant."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import input_contract as c
import native_provenance as p


def verify_build(build):
    c.need(build['passed'] is True,'Incomplete build')
    for record in build['sources']+build['tools_libraries']+build['compiler_runtime']['files']+build['executable_runtime']['files']+build['dependencies']+[build['executable'],build['object'],build['dependency_file']]:p.check_pin(record)


def verify_inputs(freeze):
    c.need(freeze['completed'] and freeze['counts']==dict(poses=20736,attempt_layers=124416,banks=18,masks=432),'Input freeze coverage')
    for record in freeze['files']+freeze['sources']+freeze['members']:c.check(record)
    observer=c.load(next(q['path'] for q in freeze['members'] if Path(q['path']).name=='observer_inputs.json'))
    # No image byte checker is called here. Native hashes each allowlisted mask
    # immediately before/after its sole decode and records those accesses.
    original=c.specification();closure=c.load(c.ROOT/'artifacts/rgb_empty_mask_experiment/INPUT_CLOSURE.json')
    allowed=c.validate_masks(original['training_mask_allowlist'],closure['dataset_root'],original['objects'])
    c.need(observer['masks']==freeze['masks']==allowed,'Observer mask allowlist differs')
    return observer


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',required=True,type=Path)
    parser.add_argument('--inputs',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--selftest-audit',required=True,type=Path)
    parser.add_argument('--cpu-slot-granted',action='store_true');args=parser.parse_args()
    c.need(args.cpu_slot_granted,'Await root native CPU-slot grant')
    out=args.output.resolve();c.need(out.is_relative_to(c.HERE) and not out.exists(),'Fresh run directory inside experiment required');out.mkdir()
    attempted=False
    try:
        build=c.load(args.build);freeze=c.load(args.inputs);verify_build(build);verify_inputs(freeze)
        fixture=c.load(args.selftest_audit);c.need(fixture['passed'] and fixture['pixel_maps']==35,'Independent native fixture gate missing')
        c.need(fixture['build']==c.pin(args.build),'Synthetic fixture belongs to another build')
        for record in fixture['sources']+fixture['inputs']:c.check(record)
        observer_input=next(q['path'] for q in freeze['members'] if Path(q['path']).name=='observer_inputs.json')
        exe=Path(build['executable']['path']);compiler=Path(build['compiler']);opencv=Path(build['opencv'])
        env=dict(os.environ);env['PATH']=str(compiler.parent)+';'+str(opencv/'build/bin')+';'+env.get('PATH','')
        command=[str(exe),observer_input,str(out/'native')]
        (out/'reservation.json').write_text(json.dumps(dict(command=command,maximum_mask_decodes=432,maximum_matcher_calls=0),indent=2)+'\n')
        attempted=True;run=subprocess.run(command,cwd=out,env=env,capture_output=True)
        (out/'native.stdout.txt').write_bytes(run.stdout);(out/'native.stderr.txt').write_bytes(run.stderr)
        verify_build(build);verify_inputs(freeze)
        c.need(run.returncode==0,'Native observer failed; partial outputs preserved')
        summary=c.load(out/'native/execution_summary.json')
        c.need(summary['passed'] and summary['training_mask_imread_calls']==432 and summary['poses']==20736 and summary['class_bank_loads']==18,'Native coverage')
        for key in ('matcher_calls','addTemplate_calls','gradient_extraction_calls','rgb_image_decodes','development_image_decodes','heldout_image_decodes'):c.need(summary[key]==0,'Forbidden native operation')
        reads=list(csv.DictReader((out/'native/mask_reads.csv').read_text().splitlines()))
        expected={(q['object_id'],q['image_id']):q for q in freeze['masks']};seen=set()
        for row in reads:
            key=(int(row['object_id']),int(row['image']));c.need(key in expected and key not in seen,'Mask read receipt scope');seen.add(key)
            c.need(row['sha256']==expected[key]['sha256'] and int(row['bytes'])==expected[key]['bytes'],'Native mask receipt pin')
        c.need(seen==set(expected),'Missing native mask receipt')
        members=[c.pin(q) for q in sorted((out/'native').iterdir()) if q.is_file()]
        c.need(len([q for q in members if Path(q['path']).name.startswith('maps_')])==432,'Full view map packs missing')
        result=dict(completed=True,native_exit=0,build=c.pin(args.build),inputs=c.pin(args.inputs),selftest=c.pin(args.selftest_audit),sources=[c.pin(c.HERE/'run_observer.py'),c.pin(c.HERE/'input_contract.py')],files=members,
                    execution_files=[c.pin(out/q) for q in ('reservation.json','native.stdout.txt','native.stderr.txt')],summary=summary,
                    independent_pixel_generation_verified=False,limitation='Native warp/pyrDown outputs await numeric pack replay and literal native geometry fixtures')
        (out/'OBSERVATION_FREEZE.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(passed=True,masks=432,poses=20736,feature_rows=summary['feature_rows'],matcher_calls=0)))
    except Exception as error:
        (out/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),native_attempted=attempted,matcher_calls=0,image_decode_count='see native mask receipts; incomplete run is not assigned zero'),indent=2)+'\n')
        raise


if __name__=='__main__':main()
