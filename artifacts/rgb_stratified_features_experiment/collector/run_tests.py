"""Build/run only literal C++14 collector tests with complete local receipts.

No datasets, image decoding, matcher, training or benchmark is invoked. The
local native_provenance.py is an unchanged copy of the V29 provenance helper;
the receipt pins both copies. OS static imports and actual loaded modules are
recorded separately; these records are evidence, not execution attestation.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import native_provenance as provenance

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE_NAMES = ('candidate_collector.hpp', 'candidate_collector.cpp',
                'test_candidate_collector.cpp', 'run_tests.py', 'native_provenance.py')


def dump(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def mutate(source, name):
    if name == 'none':
        return
    text = source.read_text(encoding='utf-8')
    changes = {
        'per-stratum-nms': [
            ('cv::Mat valid(magnitude.size(), CV_8U, cv::Scalar(255));',
             'cv::Mat valid_by_stratum[] = {cv::Mat(magnitude.size(), CV_8U, cv::Scalar(255)), '
             'cv::Mat(magnitude.size(), CV_8U, cv::Scalar(255))};'),
            ('if (!domain_row[x] || !valid.at<unsigned char>(y,x)) continue;',
             'cv::Mat& valid = valid_by_stratum[result.interior.at<unsigned char>(y,x) ? 1 : 0];\n'
             '            if (!domain_row[x] || !valid.at<unsigned char>(y,x)) continue;')],
        'threshold128': [('cv::compare(official_mask, 0, binary, cv::CMP_NE);',
                          'cv::compare(official_mask, 128, binary, cv::CMP_GE);')],
        'prefilter-invalid-angle': [
            ('if (!domain_row[x] || !valid.at<unsigned char>(y,x)) continue;',
             'if (!domain_row[x] || !valid.at<unsigned char>(y,x)) continue;\n'
             '            if (!valid_one_bit(quantized_angle.at<unsigned char>(y,x))) continue;')],
        'prefilter-low-strength': [
            ('if (!domain_row[x] || !valid.at<unsigned char>(y,x)) continue;',
             'if (!domain_row[x] || !valid.at<unsigned char>(y,x)) continue;\n'
             '            if (magnitude.at<float>(y,x) <= 1600.0f) continue;')],
        'accept-threshold-equality': [('if (score > 1600.0f && angle > 0)',
                                       'if (score >= 1600.0f && angle > 0)')],
    }
    for before, after in changes[name]:
        provenance.require(text.count(before) == 1, 'Mutation anchor must match once: '+before)
        text = text.replace(before, after)
    source.write_text(text, encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cpu-slot-granted', action='store_true')
    parser.add_argument('--compiler', type=Path, default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--opencv', type=Path, default=Path('D:/opencv-4.12.0'))
    parser.add_argument('--case')
    parser.add_argument('--expect', choices=('green','red'), default='green')
    parser.add_argument('--expected-failed-case')
    parser.add_argument('--expected-failure-text')
    parser.add_argument('--mutation', choices=('none','per-stratum-nms','threshold128',
        'prefilter-invalid-angle','prefilter-low-strength','accept-threshold-equality'), default='none')
    args=parser.parse_args()
    provenance.require(args.cpu_slot_granted, 'A coordinated literal native CPU slot is required')
    out=args.output.resolve()
    provenance.require(out.is_relative_to(HERE) and out!=HERE and not out.exists(),
                       'Output must be a fresh subdirectory of collector')
    provenance.require(args.expect!='red' or
        (args.expected_failed_case and args.expected_failure_text),
        'RED must name its intended failing case and exact message substring')
    out.mkdir();(out/'source').mkdir()
    receipt={'scope':'literal C++14 numeric Mats only', 'image_decodes':0,'matcher_calls':0,
             'dataset_files_read':0, 'mutation':args.mutation, 'expected':args.expect,
             'commands':[], 'passed':False}
    started=time.time()
    try:
        original_pins=[provenance.file_pin(HERE/n) for n in SOURCE_NAMES]
        for name in SOURCE_NAMES:
            shutil.copyfile(HERE/name,out/'source'/name)
        mutate(out/'source/candidate_collector.cpp',args.mutation)
        project=[out/'source'/n for n in SOURCE_NAMES]
        receipt['source_pins']=[provenance.file_pin(p) for p in project]
        receipt['original_source_pins']=original_pins
        origin=ROOT/'artifacts/rgb_dilated_mask_experiment/native_provenance.py'
        receipt['provenance_helper_origin']=provenance.file_pin(origin)
        provenance.require(receipt['provenance_helper_origin']['sha256']==
            provenance.file_pin(HERE/'native_provenance.py')['sha256'], 'Unchanged V29 helper copy differs')
        reference=ROOT/'artifacts/rgb_dilated_mask_experiment/control_v11/line2Dup.cpp'
        receipt['v11_reference_source']=provenance.file_pin(reference)
        reference_bytes=reference.read_bytes()
        start=reference_bytes.index(b'bool ColorGradientPyramid::extractTemplate(Template &templ) const')
        end=reference_bytes.index(b'    // We require a certain number of features',start)
        (out/'reference_v11_extract_prefix.txt').write_bytes(reference_bytes[start:end])
        receipt['v11_reference_nms_prefix']=provenance.file_pin(out/'reference_v11_extract_prefix.txt')
        receipt['reference_comparison_scope']='V11 mask-before-traversal row-major 5x5 NMS; V31 domain differs intentionally'
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
        flags=['-std=c++14','-O2','-Wall','-Wextra','-Werror','-DNOMINMAX',
            '-I'+str(out/'source'),'-I'+str(opencv/'build'),
            '-I'+str(opencv/'modules/core/include'),'-I'+str(opencv/'modules/imgproc/include')]

        def command(label,argv,expected=0):
            argv=list(map(str,argv))
            row={'label':label,'command':argv,'cwd':str(out)}
            receipt['commands'].append(row);dump(out/'receipt.json',receipt)
            process=subprocess.run(argv,cwd=out,env=env,capture_output=True,timeout=120)
            (out/(label+'.stdout.txt')).write_bytes(process.stdout)
            (out/(label+'.stderr.txt')).write_bytes(process.stderr)
            row['exit_code']=process.returncode
            dump(out/'receipt.json',receipt)
            provenance.require(process.returncode==expected,label+' unexpected exit '+str(process.returncode))
            return process.stdout

        receipt['dependency_units']=[]
        for name,source in [('core',out/'source/candidate_collector.cpp'),
                            ('adapter',out/'source/test_candidate_collector.cpp')]:
            target=name+'.o';depfile=out/(name+'.d')
            before=command(name+'_dependencies',[compiler,*flags,'-M','-MT',target,source])
            (out/(name+'_before.d')).write_bytes(before)
            pins=provenance.dependency_pins(before,target,out,ROOT,project)
            command(name+'_compile',[compiler,*flags,'-c',source,'-o',out/target,
                                    '-MD','-MF',depfile,'-MT',target])
            actual=provenance.dependency_pins(depfile.read_bytes(),target,out,ROOT,project)
            provenance.require(pins==actual, 'Precompile and actual dependencies differ: '+name)
            receipt['dependency_units'].append({'target':target,'dependencies':actual})
            for pin in pins:provenance.check_pin(pin)
        exe=out/'collector_tests.exe'
        command('link',[compiler,out/'core.o',out/'adapter.o',library,'-o',exe,'-Wl,-t'])
        receipt['executable']=provenance.file_pin(exe)
        receipt['executable_runtime_closure']=provenance.import_closure([exe],compiler,opencv,env)
        stdout=command('tests',[exe]+([args.case] if args.case else []),0 if args.expect=='green' else 1)
        text=stdout.decode('utf-8',errors='strict')
        failed=[line.split('\t',2) for line in text.splitlines() if line.startswith('FAIL\t')]
        if args.expect=='red':
            provenance.require(len(failed)==1 and failed[0][1]==args.expected_failed_case and
                len(failed[0])==3 and args.expected_failure_text in failed[0][2],
                'RED did not fail exactly for the intended assertion')
        else:
            provenance.require(not failed and 'failed=0' in text,'GREEN test assertions failed')
        receipt['summary']=[line for line in text.splitlines() if line.startswith('SUMMARY\t')]
        modules=[Path(line.split('\t',1)[1]) for line in text.splitlines() if line.startswith('MODULE\t')]
        provenance.require(modules,'Native actual loaded-module capture is empty')
        receipt['observed_loaded_modules']=[provenance.file_pin(p) for p in modules]
        for pin in original_pins+receipt['source_pins']+receipt['tools_and_link_libraries']:
            provenance.check_pin(pin)
        provenance.check_pin(receipt['v11_reference_source'])
        for unit in receipt['dependency_units']:
            for pin in unit['dependencies']:provenance.check_pin(pin)
        for key in ('compiler_runtime_closure','executable_runtime_closure'):
            for pin in receipt[key]['files']:provenance.check_pin(pin)
        for pin in receipt['observed_loaded_modules']:provenance.check_pin(pin)
        receipt['passed']=True
        print('\n'.join(receipt['summary']))
    except BaseException as exc:
        receipt['failure']=str(exc)
        raise
    finally:
        receipt['elapsed_seconds']=time.time()-started
        receipt['output_files']=[provenance.file_pin(p) for p in sorted(out.rglob('*'))
            if p.is_file() and p!=out/'receipt.json']
        dump(out/'receipt.json',receipt)
        print(str(out/'receipt.json'))


if __name__=='__main__':main()
