"""Numeric-only summary of completed native builds and two synthetic runs."""
import hashlib
import json
from pathlib import Path

import native_provenance as p
import run_stage

HERE=Path(__file__).resolve().parent


def main():
    output=HERE/'NATIVE_PRETRAIN_SUMMARY.json';p.require(not output.exists(),'Summary must be fresh')
    builds=[]
    for name,target in [('build_synthetic_red_v1','source-test-red'),('build_synthetic_green_v1','source-test-green'),('build_adapter_v1','adapter')]:
        directory=HERE/name;file=directory/'build_manifest.json';manifest=json.loads(file.read_text())
        p.require(manifest['passed'] is True and manifest['target']==target and len(manifest['commands'])==5 and
                  all(c['exit_code']==0 for c in manifest['commands']),'Incomplete actual build')
        pins=manifest['project_sources']+manifest['compiler_tools_and_link_libraries']+manifest['compiler_runtime_closure']['files']+manifest['executable_runtime_closure']['files']+[manifest['executable']]
        dependencies=[]
        for unit in manifest['dependency_units']:
            for pin in unit['dependencies']+[unit['object'],unit['dependency_file']]:
                p.check_pin(pin)
            stem=Path(unit['target']).stem
            before=(directory/(stem+'_before.d')).read_bytes();actual=Path(unit['dependency_file']['path']).read_bytes()
            p.require(p.parse_dependencies(before,unit['target'],directory)==p.parse_dependencies(actual,unit['target'],directory),'Ordered GCC dependency content differs')
            dependencies.append(dict(target=unit['target'],source=unit['source'],ordered_occurrences=len(unit['dependencies']),
                                     unique_files=len({r['path'] for r in unit['dependencies']}),
                                     raw_pre_actual_depfile_bytes_equal=before==actual,
                                     pre_depfile=p.file_pin(directory/(stem+'_before.d')),actual_depfile=unit['dependency_file']))
        for pin in pins:
            p.check_pin(pin)
        record=dict(build_directory=name,target=target,build_manifest=p.file_pin(file),executable=manifest['executable'],
                    commands=[dict(label=c['label'],exit_code=c['exit_code']) for c in manifest['commands']],dependency_units=dependencies,
                    compiler_tools_and_libraries=len(manifest['compiler_tools_and_link_libraries']),
                    compiler_runtime_files=len(manifest['compiler_runtime_closure']['files']),
                    executable_runtime_files=len(manifest['executable_runtime_closure']['files']),
                    dataset_image_reads=0,matcher_calls=0)
        summary=directory/'build_summary.json';p.require(not summary.exists(),'Build summary must be fresh')
        summary.write_text(json.dumps(record,indent=2)+'\n');builds.append(record)
    run_stage.build_gate(HERE/'build_adapter_v1/build_manifest.json')
    tests=[]
    for name,red,exit_code in [('run_synthetic_red_v1',True,1),('run_synthetic_green_v1',False,0)]:
        directory=HERE/name;result=json.loads((directory/'results.json').read_text())
        p.require(result['passed'] is True and result['expected_red'] is red and result['native_exit_code']==exit_code,'Native RED/GREEN result differs')
        for pin in result['files']:
            p.check_pin(pin)
        tests.append(dict(directory=name,expected_red=red,native_exit_code=exit_code,results=p.file_pin(directory/'results.json')))
    native_file=HERE/'run_synthetic_green_v1/native_result.json';native=json.loads(native_file.read_text())
    p.require(native['passed']==1 and native['clone_ownership_passed']==1 and native['selection_mask_empty_spy_passed']==1 and
              native['invalid_masks_rejected']==4 and native['dataset_image_reads']==0 and native['matcher_calls']==0,'Native literal invariants differ')
    p.require([r['toy'] for r in native['toys']]==['rectangle','diagonal_polygon'] and
              all(r['success']==1 and r['template_id']==0 and r['error']=='' for r in native['toys']),'Fixed toy outcome differs')
    result=dict(passed=True,builds=builds,synthetic_runs=tests,native_green_result=p.file_pin(native_file),native_toys=native['toys'],
                protocol=p.file_pin(HERE/'PROTOCOL.json'),private_source_freeze=p.file_pin(HERE/'PRIVATE_SOURCE_FREEZE.json'),
                input_closure=p.file_pin(HERE/'INPUT_CLOSURE.json'),origin_manifest=p.file_pin(HERE/'IMPLEMENTATION_ORIGIN.json'),
                summarizer=p.file_pin(Path(__file__)),
                actual_synthetic_extraction_calls=2,real_training_attempts=0,development_image_decodes=0,dataset_image_reads=0,matcher_calls=0,
                scope='Actual private native builds and unchanged generated toys only; no real-bank feasibility, accuracy or timing result')
    output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,builds=3,synthetic_runs=2,real_training_attempts=0,dataset_image_reads=0,matcher_calls=0)))


if __name__=='__main__':
    main()
