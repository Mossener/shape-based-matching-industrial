"""Verify all four preregistered native toy receipts and complete pin closure."""
import argparse
import json
from pathlib import Path
import native_provenance as p

HERE=Path(__file__).resolve().parent


def read(path): return json.loads(Path(path).read_text())


def verify():
    oracle=read(HERE/'TOY_TEST_EXPECTATIONS.json')
    p.require(oracle['schema']=='rgb_dilated_mask_toy_expectations_v1' and len(oracle['cases'])==4,'Wrong fixed toy oracle')
    p.require(oracle['recorded_before_expected_red_run'] is True,'RED expectations were not declared')
    for pin in oracle['source_pins']: p.check_pin(pin)
    results=[]
    for case in oracle['cases']:
        build_path=HERE/case['build']/'build_manifest.json';build=read(build_path)
        p.require(build['passed'] is True,'Expected RED requires successful compilation')
        p.require(all(build[k]==case[k] for k in ('target','core_arm','expected_morphology')),'Build is not the fixed case')
        p.require(len(build['commands'])==5 and [r['label'] for r in build['commands']]==['core_dependency_before','core_compile','adapter_dependency_before','adapter_compile','link'] and all(r['exit_code']==0 for r in build['commands']),'Actual two-TU build incomplete')
        private=HERE/('private_v11' if case['core_arm']=='treatment' else 'control_v11')
        adapter=HERE/('literal_mask_test.cpp' if case['target']=='literal-test' else 'rgb_dilated_mask_source_test.cpp')
        p.require(build['actual_private_core']==str(private/'line2Dup.cpp') and
                  [u['source'] for u in build['dependency_units']]==[str(private/'line2Dup.cpp'),str(adapter)],'Wrong core or literal translation unit')
        if case['target']=='literal-test':
            macro='-DEXPECT_DILATION='+str(int(case['expected_morphology']=='dilate'))
            p.require(all(macro in r['command'] for r in build['commands'][:4]),'Literal expected semantics were not compiled')
        pins=build['project_sources']+build['compiler_tools_and_link_libraries']+build['compiler_runtime_closure']['files']+build['executable_runtime_closure']['files']+[build['executable']]
        for unit in build['dependency_units']: pins+=unit['dependencies']+[unit['object'],unit['dependency_file']]
        for pin in pins:p.check_pin(pin)
        run=HERE/case['run'];receipt=read(run/'execution_provenance.json')
        p.require(receipt['build']==p.file_pin(build_path),'Run binds another build')
        p.require(receipt['command']==[build['executable']['path']],'Run used a different executable')
        p.require(receipt['native_exit_code']==case['native_exit_code'],'Native exit is not the preregistered expectation')
        p.require(receipt['passed']==(case['native_exit_code']==0),'Toy runner pass state differs')
        p.require(all(receipt[k]==0 for k in ('image_decodes','matcher_calls','dataset_files_opened')),'Toy unexpectedly reports dataset/matcher use')
        p.check_pin(receipt['runner'])
        stderr=(run/'stderr.txt').read_text().replace('\r\n','\n')
        stdout=(run/'stdout.txt').read_text().replace('\r\n','\n')
        p.require(stderr==case['stderr_exact'],'RED must fail on exact morphology assertion; GREEN must have clean stderr')
        if case['native_exit_code']==0:
            p.require(stdout.endswith(case['stdout_suffix']) and not (run/'failure.json').exists(),'GREEN/old sanity did not finish the exact literal/spy path')
        else:
            failure=read(run/'failure.json')
            p.require(failure['native_exit_code']==1 and failure['reason']=='Native toy test failed; all diagnostics retained','RED was a preflight/compile failure')
            p.require('PASS literal mask tests' not in stdout,'RED unexpectedly finished all literal cases')
        results.append(dict(case=case['run'],expected_exit=case['native_exit_code'],actual_exit=receipt['native_exit_code'],
                            target=case['target'],build_manifest=p.file_pin(build_path),receipt=p.file_pin(run/'execution_provenance.json'),
                            stdout=p.file_pin(run/'stdout.txt'),stderr=p.file_pin(run/'stderr.txt'),complete_build_pin_records_checked=len(pins)))
    return dict(passed=True,oracle=p.file_pin(HERE/'TOY_TEST_EXPECTATIONS.json'),verifier=p.file_pin(Path(__file__)),cases=results,
                native_builds=4,native_toy_runs=4,expected_red_runs=1,image_decodes=0,matcher_calls=0,
                limitation='Literal synthetic extractor mask behavior and interface only; no accuracy, speed, training coverage or SIMD safety claim')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    p.require(not args.output.exists() and args.output.resolve().is_relative_to(HERE),'Fresh toy verification output required')
    result=verify();args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=4,expected_red_runs=1,image_decodes=0,matcher_calls=0)))
