"""One-shot guarded shared training or synthetic integration execution."""
import argparse
import gzip
import json
import os
from pathlib import Path
import sys
import native_provenance as p
import execution_guard as guard

HERE=Path(__file__).resolve().parent
OBJECTS=[1,2,5,8,12,17]
def read(path):return json.loads(Path(path).read_text())
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def build_gate(path):
    build=read(path)
    p.require(build['passed'] and len(build['dependency_units'])==2,'Complete two-TU build required')
    p.require([unit['source'] for unit in build['dependency_units']]==[str(HERE/'control_v11/line2Dup.cpp'),str(HERE/'train_shared_features.cpp')],'Unexpected core/adapter source')
    p.require(len(build['commands'])==5 and all(row['exit_code']==0 for row in build['commands']),'Incomplete compiler commands')
    pins=build['project_sources']+build['compiler_tools_and_link_libraries']+build['compiler_runtime_closure']['files']+build['executable_runtime_closure']['files']+[build['executable']]
    for unit in build['dependency_units']:pins+=unit['dependencies']+[unit['object'],unit['dependency_file']]
    for pin in pins:p.check_pin(pin)
    return build
def inputs_gate(images):
    data=read(HERE/'TRAINING_INPUT_FREEZE.json')
    p.require(data['schema']=='rgb_stratified_training_inputs_v1' and data['objects']==OBJECTS and len(data['training'])==432,'Wrong training declarations')
    for field in ('origin','protocol','design_errata','pack_format'):p.check_pin(data[field])
    root=Path(data['dataset_root']).resolve();seen=set();pins=[]
    for row in data['training']:
        obj,image=row['object_id'],row['image_id'];p.require(obj in OBJECTS and (obj,image) not in seen,'Training view scope/duplicate');seen.add((obj,image))
        for name,rel in [('rgb',f'train_primesense/{obj:06d}/rgb/{image:06d}.png'),('mask',f'train_primesense/{obj:06d}/mask/{image:06d}_000000.png')]:
            p.require(row[name]==rel,'Unexpected training path')
            path=(root/rel).resolve();p.require(path.is_relative_to(root),'Training path escaped dataset')
            if images:
                expected=dict(path=str(path),bytes=row[name+'_bytes'],sha256=row[name+'_sha256']);p.check_pin(expected);pins.append(expected)
    p.require(all(sum(obj==o for obj,_ in seen)==72 for o in OBJECTS),'Missing training view')
    p.require([r['object_id'] for r in data['original_attempts']]==OBJECTS,'Geometry object scope changed')
    for row in data['original_attempts']:p.check_pin(row['pin'])
    return data,pins
def verify_modules(output,build):
    paths=read(output/'loaded_modules.json')['loaded_modules'];p.require(paths and len(paths)==len(set(s.casefold() for s in paths)),'Loaded modules duplicate/missing')
    runtime={str(Path(pin['path']).resolve()).casefold():pin for pin in build['executable_runtime_closure']['files']}
    windows=Path(os.environ.get('SystemRoot','C:/Windows')).resolve();non_system=[];system=[]
    for value in paths:
        path=Path(value).resolve()
        if path.is_relative_to(windows):system.append(str(path));continue
        p.require(str(path).casefold() in runtime,'Actual loaded non-system module absent from frozen import closure: '+str(path))
        pin=runtime[str(path).casefold()];p.check_pin(pin);non_system.append(pin)
    return dict(non_system=non_system,system_module_paths=system,limitation='OS modules named, not hashed; module sample is captured at normal native completion')
def output_gate(output,mode):
    summary=read(output/'training_summary.json');literal=mode=='literal';n=1 if literal else 20736
    expected=dict(complete=True,literal_only=literal,shared_poses=n,shared_pools=2*n,arm_attempts=2*n,arm_layer_rows=4*n,gradient_pyramids=n,pyramid_downs=n,rgb_decodes=0 if literal else 432,mask_decodes=0 if literal else 432,total_imread_calls=0 if literal else 864,matcher_calls=0)
    p.require(all(summary[k]==v and type(summary[k]) is type(v) for k,v in expected.items()),'Incomplete native training counters')
    p.require(summary['successful_templates']['P']==summary['successful_templates']['B'] and len(summary['successful_templates']['P'])==(1 if literal else 6) and all(c>0 for c in summary['successful_templates']['P']),'Zero/mismatched success object')
    p.require(summary['peak_rss_bytes']<=1610612736,'Native peak RSS exceeded')
    # Total uncompressed payload: gzip files are decompressed, text is counted
    # as exact saved bytes. This is execution accounting, not sampling audit.
    logical=physical=0;files=[]
    for path in sorted(output.rglob('*')):
        if not path.is_file():continue
        p.require(not path.is_symlink(),'Output symlink forbidden');size=path.stat().st_size;physical+=size
        if path.suffix=='.gz':
            with gzip.open(path,'rb') as stream:
                while chunk:=stream.read(65536):
                    logical+=len(chunk);p.require(logical<=34359738368,'Logical output ceiling')
        else:logical+=size
        files.append(p.file_pin(path))
    p.require(physical<=4294967296 and logical<=34359738368,'Output resource ceiling')
    summary_bytes=(output/'training_summary.json').stat().st_size
    p.require(summary['physical_bytes_before_summary']+summary_bytes==physical,'Native total physical accounting differs from actual output')
    p.require(summary['logical_payload_bytes']+summary_bytes==logical,'Native total logical accounting differs from complete decoded output')
    return dict(summary=summary,physical_bytes=physical,logical_bytes=logical,files=files,independent_training_audit=False,accuracy_tested=False)
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--mode',choices=['literal','train'],required=True)
    ap.add_argument('--build-manifest',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--cpu-slot-granted',action='store_true');args=ap.parse_args()
    p.require(args.cpu_slot_granted,'Coordinated actual execution slot required')
    output=args.output.resolve();execution=output.with_name(output.name+'_execution');provenance_path=output.with_name(output.name+'_PROVENANCE.json')
    p.require(output.is_relative_to(HERE) and not output.exists() and not execution.exists() and not provenance_path.exists(),'Fresh contained execution required')
    build=build_gate(args.build_manifest);data,image_pins=inputs_gate(args.mode=='train')
    scripts=[p.file_pin(HERE/name) for name in ('run_training.py','execution_guard.py','native_provenance.py')]
    reservations=HERE/'execution_reservations';reservations.mkdir(exist_ok=True)
    reservation=reservations/(args.mode+'.json')
    command=[build['executable']['path'],'--mode',args.mode,'--output',str(output)]
    if args.mode=='train':command+=['--inputs',str(HERE/'TRAINING_INPUT_FREEZE.json')]
    record=dict(mode=args.mode,command=command,build_manifest=p.file_pin(args.build_manifest),input_freeze=p.file_pin(HERE/'TRAINING_INPUT_FREEZE.json'),image_pins=image_pins,script_pins=scripts,expected_shared_poses=1 if args.mode=='literal' else 20736,expected_matcher_calls=0,passed=False)
    # Every actual attempt gets a persistent reservation. Correctness/resource
    # failure needs an explicit successor; the original cannot silently rerun.
    with reservation.open('x') as stream:stream.write(json.dumps(record,indent=2)+'\n')
    record['reservation']=p.file_pin(reservation);dump(provenance_path,record)
    try:
        env=dict(os.environ);env['PATH']=str(Path(build['compiler']).parent)+';'+str(Path(build['opencv'])/'build/bin')+';'+env.get('PATH','')
        run=guard.run_guarded(command,env,HERE,output,execution,maximum_seconds=30 if args.mode=='literal' else 5400,minimum_free_bytes=0 if args.mode=='literal' else 8589934592)
        record['guard']=p.file_pin(execution/'guard_receipt.json');p.require(run['passed'],'Native run failed/incomplete: '+str(run['reason']))
        build_gate(args.build_manifest)
        for pin in scripts+image_pins+[record['reservation'],record['input_freeze']]:p.check_pin(pin)
        _,after=inputs_gate(args.mode=='train');p.require(after==image_pins,'Pre/post training image pins differ')
        record.update(output_gate(output,args.mode));record['actual_loaded_modules']=verify_modules(output,build);record['passed']=True
        dump(provenance_path,record)
        print(json.dumps(dict(passed=True,mode=args.mode,shared_poses=record['summary']['shared_poses'],shared_pools=record['summary']['shared_pools'],image_decodes=record['summary']['total_imread_calls'],matcher_calls=0,independent_training_audit=False)))
    except BaseException as error:
        record.update(incomplete=True,reason=repr(error));dump(provenance_path,record);raise
if __name__=='__main__':main()
