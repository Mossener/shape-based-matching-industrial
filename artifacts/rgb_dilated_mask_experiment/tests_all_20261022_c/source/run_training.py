"""Gated one-shot training/planner; all partial evidence survives failure.

Writes native outputs at --output and execution logs in a fresh sibling
--output_execution directory. Validation here is not an independent audit.
"""
import argparse
import csv
import gzip
import itertools
import json
import os
from pathlib import Path
import subprocess

import freeze_private_sources as frozen
import native_provenance as p
import prepare_input_closure as inputs
from bank_reader import parse_bank
from training_numeric import inspect_object, audit_bank

HERE=Path(__file__).resolve().parent
OBJECTS=[1,2,5,8,12,17]


def read(path):return json.loads(Path(path).read_text())
def table(path):
    with Path(path).open(newline='') as stream:return list(csv.DictReader(stream))


def build_gate(path):
    m=read(path)
    p.require(m['passed'] and m['target']=='training' and m['core_arm']=='treatment' and
              m['actual_private_core']==str(HERE/'private_v11/line2Dup.cpp'),'Actual separate treatment training build required')
    p.require(len(m['commands'])==5 and all(c['exit_code']==0 for c in m['commands']) and
              [u['source'] for u in m['dependency_units']]==[str(HERE/'private_v11/line2Dup.cpp'),str(HERE/'train_rgb_dilated_mask.cpp')], 'Unexpected training translation units')
    pins=m['project_sources']+m['compiler_tools_and_link_libraries']+m['compiler_runtime_closure']['files']+m['executable_runtime_closure']['files']+[m['executable']]
    for unit in m['dependency_units']:pins+=unit['dependencies']+[unit['object'],unit['dependency_file']]
    for pin in pins:p.check_pin(pin)
    return m


def validate_training(output,closure):
    summary=read(output/'training_summary.json');results=[]
    p.require([r['object_id'] for r in summary['objects']]==OBJECTS,'Training summary object scope changed')
    for b in closure['rgb_banks']:
        obj=b['object_id'];directory=output/('obj'+str(obj));rows=table(directory/'template_attempts.csv')
        control=table(Path(b['rgb_training'])/'template_attempts.csv')
        views=[r['image_id'] for r in closure['training'] if r['object_id']==obj]
        p.require(len(views)==len(set(views))==72,'Training views changed')
        expected=set(itertools.product(views,range(0,360,30),[.75,1.,1.5,2.]))
        result=inspect_object(obj,rows,control,read(directory/'template_metadata.json')['templates'],expected)
        result.update(audit_bank(directory,obj,rows,table(directory/'feature_geometry.csv'),lambda path:Path(path).read_bytes()))
        config=read(directory/'training_config.json')
        p.require(config['training_source']=='frozen grayscale RGB warp' and
                  config['feature_selection_mask']=='official warped mask; per-layer 3x3 dilation' and
                  config['features']==32 and config['pyramid_T']==[4,8] and config['weak_threshold']==20 and config['strong_threshold']==40 and
                  config['angle_step']==30 and config['scales']==[.75,1.,1.5,2.] and config['training_border']==16 and
                  config['all_original_pose_geometries_equal']==1,'Training algorithm/config geometry changed')
        p.require(result['successful_templates']>0 and result['opencv_exception_attempts']==0,'Incomplete treatment object')
        report=next(r for r in summary['objects'] if r['object_id']==obj)
        p.require(all(result[k]==report[k] for k in ('object_id','attempts','successful_templates','opencv_exception_attempts')) and Path(report['directory'])==directory,'Object summary differs')
        results.append(result)
    p.require(summary['attempts']==sum(r['attempts'] for r in results)==20736 and
              summary['zero_success_objects']==summary['opencv_exception_attempts']==summary['matcher_calls']==0 and
              summary['training_attempts_complete']==summary['comparison_feasible']==1 and summary['incomplete_comparison']==0,'Incomplete full training')
    return dict(passed=True,objects=results,attempts=20736,summary=summary,
                successful_templates={str(r['object_id']):r['successful_templates'] for r in results},
                image_decodes=0,matcher_calls=0,independent_audit=False,
                limitation='Reused numeric/serialized validators; independent fresh audit remains required')


def validate_plan(output,closure,training):
    rows=table(output/'loaded_layers.csv');computed=[]
    counts=read(training/'BANK_FREEZE.json')['successful_templates']
    for b in closure['rgb_banks']:
        obj=b['object_id'];cls='tless_object_'+str(obj)
        for arm,directory,count in [('rgb_control',Path(b['rgb_training']),b['rgb_template_count']),('rgb_dilated_mask',training/('obj'+str(obj)),counts[str(obj)])]:
            bank=parse_bank(gzip.decompress((directory/('templates_'+cls+'.yml.gz')).read_bytes()).decode(),cls)
            p.require(len(bank)==count,'Planner bank count changed')
            for tid,layers in enumerate(bank):
                for level,t in enumerate(layers):
                    xs,ys=zip(*[(f[0],f[1]) for f in t['features']])
                    item=dict(arm=arm,object_id=obj,class_id=cls,template_id=tid,level=level,width=t['width'],height=t['height'],min_x=min(xs),min_y=min(ys),max_x=max(xs),max_y=max(ys),actual_features=len(xs))
                    p.require(item['width']>0 and item['height']>0 and 0<=min(xs)<=max(xs)<=t['width'] and 0<=min(ys)<=max(ys)<=t['height'],'Invalid planner feature bounds')
                    if level==0:p.require(t['width']<=784 and t['height']<=768,'Fine layer exceeds fixed local-search gate')
                    else:p.require(max(t['width'],max(xs)+1)<=424 and max(t['height'],max(ys)+1)<=416,'Coarse layer exceeds fixed canvas')
                    computed.append(item)
    p.require(len(computed)==len(rows) and all(all(row[k]==str(v) for k,v in expected.items()) for row,expected in zip(rows,computed)),'Loaded geometry differs from complete serialized bank union')
    plan=read(output/'common_padding_plan.json')
    expected=dict(source_size=[720,540],width=848,height=832,alignment=16,padding_ltrb=[64,64,64,228],pixels=848*832,estimated_dynamic_bytes=848*832*512,banks=12,loaded_layers=len(rows),geometry_feasible=1,development_images_decoded=0,matcher_calls=0)
    p.require(plan==expected,'Fixed plan changed or enlarged')
    return dict(passed=True,plan=plan,serialized_layers_checked=len(rows),independent_audit=False,image_decodes=0,matcher_calls=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['train','plan'],required=True)
    parser.add_argument('--build-manifest',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--training',type=Path);parser.add_argument('--cpu-slot-granted',action='store_true')
    args=parser.parse_args();p.require(args.cpu_slot_granted,'Await coordinated training/planner CPU slot')
    output=args.output.resolve();execution=output.with_name(output.name+'_execution')
    p.require(output.is_relative_to(HERE) and not output.exists() and not execution.exists(),'Fresh native output and execution directory required')
    execution.mkdir();native_exit=None
    try:
        build=build_gate(args.build_manifest);closure=read(HERE/'INPUT_CLOSURE.json')
        reservations=HERE/'training_stage_reservations';reservations.mkdir(exist_ok=True)
        reservation=reservations/(args.mode+'.json')
        with reservation.open('x') as stream:
            stream.write(json.dumps(dict(mode=args.mode,output=str(output),build_manifest=p.file_pin(args.build_manifest),
                maximum_attempts=20736 if args.mode=='train' else 0,matcher_calls=0,
                policy='One native attempt per fixed stage; preserve reservation and partial output on failure'),indent=2)+'\n')
        reservation_pin=p.file_pin(reservation)
        frozen.verify(HERE/'private_v11',read(HERE/'PRIVATE_SOURCE_FREEZE.json'))
        inputs.verify(read_declared_bytes=True)
        script_pins=[p.file_pin(HERE/n) for n in ('run_training.py','training_numeric.py','bank_reader.py','TRAINING_VALIDATOR_ORIGIN.json')]
        training=None;train_freeze=None
        if args.mode=='train':
            p.require(args.training is None,'Training must not consume a prior treatment bank')
            # Training-only bytes: no development images before the geometry gate.
            for row in closure['training']:
                for name in ('rgb','mask'):
                    p.require(p.file_pin(Path(closure['dataset_root'])/row[name])==dict(path=str((Path(closure['dataset_root'])/row[name]).resolve()),sha256=row[name+'_sha256'],bytes=row[name+'_bytes']),'Training image bytes changed')
        else:
            p.require(args.training is not None,'Complete frozen treatment training required')
            training=args.training.resolve(strict=True);train_freeze=p.file_pin(training/'BANK_FREEZE.json')
            bank=read(train_freeze['path']);p.require(bank['native_exit_zero'] and bank['comparison_feasible'] and bank['attempts']==20736,'Incomplete training cannot be planned')
            for pin in bank['files']+bank['execution_files']:p.check_pin(pin)
        command=[build['executable']['path'],'--mode',args.mode,'--output',str(output),'--closure',str(HERE/'INPUT_CLOSURE.json')]
        if training:command+=['--training',str(training)]
        env=dict(os.environ);env['PATH']=str(Path(build['compiler']).parent)+';'+str(Path(build['opencv'])/'build/bin')+';'+env.get('PATH','')
        receipt=dict(command=command,mode=args.mode,build_manifest=p.file_pin(args.build_manifest),input_closure=p.file_pin(HERE/'INPUT_CLOSURE.json'),script_pins=script_pins,training_freeze=train_freeze,reservation=reservation_pin,native_exit_code=None,matcher_calls=0)
        (execution/'execution_provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')
        with (execution/'stdout.txt').open('wb') as stdout,(execution/'stderr.txt').open('wb') as stderr:
            process=subprocess.run(command,cwd=HERE,env=env,stdout=stdout,stderr=stderr)
        native_exit=process.returncode;receipt['native_exit_code']=native_exit
        (execution/'execution_provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')
        build_gate(args.build_manifest);inputs.verify(read_declared_bytes=True)
        p.check_pin(reservation_pin)
        for pin in script_pins:p.check_pin(pin)
        p.require(native_exit==0,'Native stage incomplete; preserve all attempts and diagnostics')
        validation=validate_training(output,closure) if args.mode=='train' else validate_plan(output,closure,training)
        validation_path=output/('training_audit.json' if args.mode=='train' else 'plan_audit.json');validation_path.write_text(json.dumps(validation,indent=2)+'\n')
        files=[p.file_pin(q) for q in sorted(output.rglob('*')) if q.is_file() and q.name!='.gitignore']
        execution_files=[p.file_pin(q) for q in sorted(execution.iterdir()) if q.is_file()]
        if args.mode=='train':
            freeze=dict(version='rgb_dilated_mask_bank_freeze_v1',native_exit_zero=True,comparison_feasible=True,training_attempts_complete=True,
                        objects=OBJECTS,attempts=20736,successful_templates=validation['successful_templates'],summary=validation['summary'],
                        training_source='frozen grayscale RGB warp',feature_selection_mask='official warped mask; per-layer 3x3 dilation',
                        files=files,execution_files=execution_files,reservation=reservation_pin,runner_validation=p.file_pin(validation_path),independent_audit_required=True,
                        image_decodes=864,decode_count_definition='432 RGB plus 432 mask imread calls derived from fixed completed training loop',matcher_calls=0)
            name='BANK_FREEZE.json'
        else:
            freeze=dict(version='rgb_dilated_mask_common_padding_freeze_v1',passed=True,bank_freeze=train_freeze,plan=validation['plan'],
                        files=files,execution_files=execution_files,reservation=reservation_pin,independent_audit_required=True,image_decodes=0,matcher_calls=0)
            name='COMMON_PADDING_FREEZE.json'
        (output/name).write_text(json.dumps(freeze,indent=2)+'\n')
        print(json.dumps(dict(passed=True,mode=args.mode,matcher_calls=0)))
    except Exception as error:
        (execution/'failure.json').write_text(json.dumps(dict(incomplete=True,mode=args.mode,reason=str(error),native_exit_code=native_exit,matcher_calls=0,missing_frames_are_not_negatives=True),indent=2)+'\n')
        raise


if __name__=='__main__':main()
