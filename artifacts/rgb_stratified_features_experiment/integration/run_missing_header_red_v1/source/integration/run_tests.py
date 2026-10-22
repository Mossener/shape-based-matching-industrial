"""Isolated two-TU V11 integration literal build/run; no datasets or matcher calls."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(EXPERIMENT))
import native_provenance as provenance


def dump(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')


def mutate(header, mode):
    replacements = {
        'early-l0-return-red': (
            'if (level == 0) pyramid.pyrDown();',
            'if (level == 0 && pooled.status != industrial_stratified::Status::ok) break;\n'
            '        if (level == 0) pyramid.pyrDown();'),
        'copied-pool-red': (
            'auto balanced = sample(pool, budget, industrial_stratified::Mode::balanced);',
            'const auto copied_pool = pool;\n'
            '        auto balanced = sample(copied_pool, budget, industrial_stratified::Mode::balanced);'),
        'wrong-crop-red': (
            'int x = templ.features[j].x << templ.pyramid_level;',
            'int x = templ.features[j].x;'),
    }
    if mode not in replacements:
        return None
    text=header.read_text(encoding='utf-8')
    before,after=replacements[mode]
    provenance.require(text.count(before)==1,'Unique mutation seam differs')
    pin=provenance.file_pin(header)
    header.write_text(text.replace(before,after),encoding='utf-8',newline='\n')
    return dict(mode=mode,before=pin,after=provenance.file_pin(header),replacements=1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--cpu-slot-granted',action='store_true')
    parser.add_argument('--compiler',type=Path,default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--opencv',type=Path,default=Path('D:/opencv-4.12.0'))
    parser.add_argument('--mode',choices=('missing-header-red','green','early-l0-return-red',
        'copied-pool-red','wrong-crop-red'),required=True)
    args=parser.parse_args()
    provenance.require(args.cpu_slot_granted,'Root-coordinated literal CPU slot required')
    out=args.output.resolve()
    provenance.require(out.is_relative_to(HERE) and out!=HERE and not out.exists(),
                       'Output must be a fresh integration child directory')
    out.mkdir();source=out/'source';source.mkdir()
    receipt=dict(scope='numeric cv::Mat integration literals, frozen V11 core separate TU',
        mode=args.mode,passed=False,image_decodes=0,matcher_calls=0,dataset_files_read=0,
        commands=[],expected_red=args.mode!='green')
    started=time.time()
    try:
        freeze_path=EXPERIMENT/'TRAINING_SOURCE_FREEZE.json'
        freeze=json.loads(freeze_path.read_text(encoding='utf-8'))
        provenance.require(len(freeze['files'])==23 and freeze['sole_core_delta'] is None,
                           'Expected exact unchanged 23-file V11 source snapshot')
        for name,pin in freeze['files'].items():
            observed=provenance.file_pin(EXPERIMENT/'control_v11'/name)
            provenance.require({k:observed[k] for k in ('bytes','sha256')}==pin,
                               'Frozen core file changed: '+name)
        names=['integration/test_shared_training.cpp','integration/run_tests.py',
               'collector/candidate_collector.hpp','collector/candidate_collector.cpp',
               'sampler/v2/stratified_sampler.hpp','native_provenance.py','TRAINING_SOURCE_FREEZE.json']
        names+=['control_v11/'+name for name in freeze['files']]
        if args.mode!='missing-header-red':names+=['integration/shared_training.hpp']
        original=[provenance.file_pin(EXPERIMENT/name) for name in names]
        for name in names:
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(EXPERIMENT/name,dest)
        receipt['original_source_pins']=original
        receipt['mutation']=None if args.mode=='missing-header-red' else mutate(source/'integration/shared_training.hpp',args.mode)
        if args.mode!='missing-header-red':
            core_text=(source/'control_v11/line2Dup.cpp').read_text(encoding='utf-8')
            start=core_text.index('static Rect cropTemplates(std::vector<Template> &templates)')
            end=core_text.index('\nbool ColorGradientPyramid::selectScatteredFeatures',start)
            inherited=core_text[start:end].replace('static Rect cropTemplates(',
                                                   'inline Rect crop_templates(',1).strip()
            header_text=(source/'integration/shared_training.hpp').read_text(encoding='utf-8')
            provenance.require(args.mode=='wrong-crop-red' or inherited in header_text,
                               'Cross-layer crop body differs from frozen V11 original')
            receipt['unchanged_crop_source_text_gate']=args.mode!='wrong-crop-red'
        project=[source/name for name in names]
        receipt['source_pins']=[provenance.file_pin(path) for path in project]
        receipt['training_source_freeze']=provenance.file_pin(freeze_path)
        compiler=args.compiler.resolve(strict=True);opencv=args.opencv.resolve(strict=True)
        env=dict(os.environ)
        env['PATH']=str(compiler.parent)+';'+str(opencv/'build/bin')+';'+env.get('PATH','')
        env['OMP_NUM_THREADS']='1';env['OPENBLAS_NUM_THREADS']='1';env['OPENCV_FOR_THREADS_NUM']='1'
        receipt['environment_overrides']={k:env[k] for k in ('PATH','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','OPENCV_FOR_THREADS_NUM')}
        tools,queries=provenance.compiler_tools(compiler,env)
        receipt['compiler_queries']=queries
        library=opencv/'build/lib/libopencv_world4120.dll.a'
        receipt['tools_and_link_libraries']=[provenance.file_pin(p) for p in tools+[library]]
        receipt['compiler_runtime_closure']=provenance.import_closure(tools,compiler,opencv,env)
        receipt['python_executable']=provenance.file_pin(sys.executable)
        receipt['python_version']=sys.version
        flags=['-std=c++14','-O2','-mssse3','-msse4.1','-fopenmp','-DNOMINMAX',
               '-Wall','-Wextra','-Wno-sign-compare','-Wno-unused-function',
               '-I'+str(source/'integration'),'-I'+str(source/'control_v11'),
               '-I'+str(source/'control_v11/MIPP'),'-I'+str(opencv/'build')]
        flags+=['-I'+str(opencv/'modules'/module/'include')
                for module in ('core','imgproc','highgui','imgcodecs','videoio')]
        receipt['compile_flags']=flags

        def command(label,argv,expected=0):
            argv=list(map(str,argv));row=dict(label=label,command=argv,cwd=str(out))
            receipt['commands'].append(row);dump(out/'receipt.json',receipt)
            process=subprocess.run(argv,cwd=out,env=env,capture_output=True,timeout=120)
            (out/(label+'.stdout.txt')).write_bytes(process.stdout)
            (out/(label+'.stderr.txt')).write_bytes(process.stderr)
            row['exit_code']=process.returncode;dump(out/'receipt.json',receipt)
            if expected is not None:
                provenance.require(process.returncode==expected,label+' unexpected exit '+str(process.returncode))
            return process

        if args.mode=='missing-header-red':
            process=command('missing_header_compile',[compiler,*flags,'-fsyntax-only',
                source/'integration/test_shared_training.cpp'],None)
            provenance.require(process.returncode!=0 and
                b'shared_training.hpp: No such file or directory' in process.stderr,
                'Expected missing integration header compile RED not observed')
            receipt['passed']=True
        else:
            receipt['dependency_units']=[]
            for label,unit in [('core',source/'control_v11/line2Dup.cpp'),
                               ('adapter',source/'integration/test_shared_training.cpp')]:
                target=label+'.o';depfile=out/(label+'.d')
                before=command(label+'_dependencies',[compiler,*flags,'-M','-MT',target,unit]).stdout
                (out/(label+'_before.d')).write_bytes(before)
                pins=provenance.dependency_pins(before,target,out,ROOT,project)
                command(label+'_compile',[compiler,*flags,'-c',unit,'-o',out/target,
                                         '-MD','-MF',depfile,'-MT',target])
                actual=provenance.dependency_pins(depfile.read_bytes(),target,out,ROOT,project)
                provenance.require(pins==actual,'Precompile/actual dependencies differ: '+label)
                receipt['dependency_units'].append(dict(target=target,dependencies=actual))
                for pin in actual:provenance.check_pin(pin)
            exe=out/'integration_tests.exe'
            command('link',[compiler,'-fopenmp',out/'core.o',out/'adapter.o',library,'-o',exe,'-Wl,-t'])
            receipt['executable']=provenance.file_pin(exe)
            receipt['executable_runtime_closure']=provenance.import_closure([exe],compiler,opencv,env)
            red_cases={
                'early-l0-return-red':('failed_l0_still_l1_and_shared_pool',
                                      'failed L0 must still collect/sample/hook L1'),
                'copied-pool-red':('failed_l0_still_l1_and_shared_pool',
                                   'P/B and serialization hook must share the identical immutable vector'),
                'wrong-crop-red':('copied_crop_literal_bounds','cross-layer literal crop differs')}
            case=[] if args.mode=='green' else [red_cases[args.mode][0]]
            process=command('tests',[exe,*case],0 if args.mode=='green' else 1)
            text=process.stdout.decode('utf-8',errors='strict')
            failed=[line.split('\t',2) for line in text.splitlines() if line.startswith('FAIL\t')]
            if args.mode=='green':
                provenance.require(not failed and 'failed=0' in text,'GREEN assertions failed')
            else:
                expected=red_cases[args.mode]
                provenance.require(len(failed)==1 and len(failed[0])==3 and failed[0][1]==expected[0]
                    and expected[1] in failed[0][2],'RED did not fail for the intended assertion')
            receipt['summary']=[line for line in text.splitlines() if line.startswith('SUMMARY\t')]
            modules=[Path(line.split('\t',1)[1]) for line in text.splitlines() if line.startswith('MODULE\t')]
            provenance.require(modules,'Native actual loaded-module capture is empty')
            receipt['observed_loaded_modules']=[provenance.file_pin(path) for path in modules]
            for pin in receipt['observed_loaded_modules']:provenance.check_pin(pin)
            receipt['passed']=True
            print('\n'.join(receipt['summary']))
        for pin in original+receipt['source_pins']+receipt['tools_and_link_libraries']:
            provenance.check_pin(pin)
        for unit in receipt.get('dependency_units',[]):
            for pin in unit['dependencies']:provenance.check_pin(pin)
        for key in ('compiler_runtime_closure','executable_runtime_closure'):
            for pin in receipt.get(key,{}).get('files',[]):provenance.check_pin(pin)
    except BaseException as exc:
        receipt['passed']=False;receipt['failure']=str(exc)
        raise
    finally:
        receipt['elapsed_seconds']=time.time()-started
        receipt['output_files']=[provenance.file_pin(path) for path in sorted(out.rglob('*'))
                                if path.is_file() and path!=out/'receipt.json']
        dump(out/'receipt.json',receipt)
        print(str(out/'receipt.json'))


if __name__=='__main__':main()
