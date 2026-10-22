"""Isolated Phase2 single-TU build. Requires explicit root native CPU grant."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import source_contract
import prepare_budget

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXPERIMENT = ROOT/'artifacts/silhouette_empty_mask_experiment'
V1 = HERE.parent/'score_path_probe_v1'
sys.path.insert(0, str(EXPERIMENT))
import freeze_private_sources as frozen
import native_provenance as p


def build(output, compiler, opencv, red):
    receipt, receipt_pin = prepare_budget.load_pinned(prepare_budget.RECEIPT, prepare_budget.RECEIPT_SHA)
    p.check_pin(receipt['build_manifest'])
    previous = json.loads(Path(receipt['build_manifest']['path']).read_bytes())
    for value in previous['project_sources']:
        p.check_pin(value)
    source = V1/'probe.cpp'
    expected = next(value for value in previous['project_sources'] if Path(value['path']) == source)
    p.check_pin(expected)
    extracted = source_contract.extract(source.read_bytes())
    header = output/'generated_preprocess.hpp'
    header.write_bytes(extracted['header'])
    extraction = dict(source=expected, rule='Unique literal markers; exact Memories alias, Maps struct and preprocess block; namespace wrapper only',
                      markers=['using Memories = ', 'struct Maps { ', 'static Maps preprocess(', '// Independent oracle:'],
                      components=[dict(utf8=value.decode('utf-8'), sha256=hashlib.sha256(value).hexdigest(), bytes=len(value))
                                  for value in extracted['components']],
                      generated_header=p.file_pin(header), original_source_edited=False, generated_file_is_transformed=True)
    (output/'PREPROCESS_EXTRACTION.json').write_text(json.dumps(extraction, indent=2)+'\n', encoding='utf-8')
    freeze=json.loads((EXPERIMENT/'PRIVATE_SOURCE_FREEZE.json').read_bytes())
    frozen.verify(EXPERIMENT/'private_v11',freeze)
    project = [EXPERIMENT/'private_v11'/name for name in freeze['files']]
    project += [EXPERIMENT/'frozen_helpers'/name for name in freeze['helpers']]
    project += [EXPERIMENT/'quality_support.hpp', HERE/'phase2.cpp', source, header]
    supporting = [HERE/name for name in ('build_probe.py','run_probe.py','source_contract.py','prepare_budget.py','geometry.py','DESIGN.md')]
    supporting += [EXPERIMENT/name for name in ('PRIVATE_SOURCE_FREEZE.json','freeze_private_sources.py','native_provenance.py')]
    project_pins = [p.file_pin(path) for path in project+supporting]
    environment=dict(os.environ);environment['PATH']=str(compiler.parent)+';'+str(opencv/'build/bin')+';'+environment.get('PATH','')
    tools,queries=p.compiler_tools(compiler,environment)
    libraries=[opencv/'build/lib/libopencv_world4120.dll.a',compiler.parent.parent/'lib/libz.dll.a',compiler.parent.parent/'lib/libpsapi.a']
    tool_pins=[p.file_pin(path) for path in tools+libraries]
    before_runtime=p.import_closure(tools+[opencv/'build/bin/libopencv_world4120.dll',compiler.parent/'zlib1.dll'],compiler,opencv,environment)
    flags=freeze['compile_flags']+['-I'+str(output),'-I'+str(EXPERIMENT/'frozen_helpers'),'-I'+str(opencv/'build')]
    flags+=['-I'+str(opencv/'modules'/module/'include') for module in ('core','imgproc','highgui','imgcodecs','videoio')]
    if red:
        flags.append('-DSCORE_PATH_RED_CONTROLS')
    attempts=[]

    def execute(label,command):
        record=dict(label=label,command=list(map(str,command)),working_directory=str(output));attempts.append(record)
        (output/'attempts.json').write_text(json.dumps(attempts,indent=2)+'\n')
        process=subprocess.run(record['command'],cwd=output,env=environment,capture_output=True)
        (output/(label+'.stdout')).write_bytes(process.stdout);(output/(label+'.stderr')).write_bytes(process.stderr)
        record['exit_code']=process.returncode
        (output/'attempts.json').write_text(json.dumps(attempts,indent=2)+'\n')
        p.require(process.returncode==0,label+' failed; full diagnostics retained')
        return process.stdout

    cpp=HERE/'phase2.cpp'
    before=execute('dependency_before',[compiler,*flags,'-M','-MT','adapter.o',cpp])
    (output/'adapter_before.d').write_bytes(before)
    before_pins=p.dependency_pins(before,'adapter.o',output,ROOT,project)
    actual_paths={Path(value['path']) for value in before_pins}
    p.require({cpp,header,EXPERIMENT/'private_v11/line2Dup.cpp'}<=actual_paths,'Actual Phase2 single TU/core/extracted header missing')
    execute('compile',[compiler,*flags,'-c',cpp,'-o',output/'adapter.o','-MD','-MF',output/'adapter.d','-MT','adapter.o'])
    actual=p.dependency_pins((output/'adapter.d').read_bytes(),'adapter.o',output,ROOT,project)
    p.require(actual==before_pins,'Actual Phase2 dependencies changed')
    executable=output/'score_probe_v2.exe'
    execute('link',[compiler,'-fopenmp',output/'adapter.o',*libraries,'-o',executable])
    after_runtime=p.import_closure([executable],compiler,opencv,environment)
    for value in project_pins+tool_pins+before_runtime['files']+after_runtime['files']+actual+[receipt_pin,expected]:
        p.check_pin(value)
    result=dict(passed=True,target='score_path_probe_phase2',core_revision=frozen.REV,red_controls=red,
                prior_phase1_receipt=receipt_pin,phase1_project_sources=previous['project_sources'],
                compiler=str(compiler),opencv=str(opencv),executable=p.file_pin(executable),project_sources=project_pins,
                compiler_tools_and_link_libraries=tool_pins,compiler_tool_queries=queries,
                compiler_runtime_closure=before_runtime,executable_runtime_closure=after_runtime,
                preprocessing_extraction=p.file_pin(output/'PREPROCESS_EXTRACTION.json'),
                dependency_units=[dict(source=str(cpp),included_private_core=str(EXPERIMENT/'private_v11/line2Dup.cpp'),
                    generated_preprocess_header=p.file_pin(header),object=p.file_pin(output/'adapter.o'),
                    dependency_file=p.file_pin(output/'adapter.d'),dependencies=actual)],
                commands=attempts,image_decodes=0,full_class_search_replays=0,public_detector_match_calls=0)
    (output/'build_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compiler',type=Path,default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--opencv',type=Path,default=Path('D:/opencv-4.12.0'))
    parser.add_argument('--red-negative-controls',action='store_true')
    parser.add_argument('--cpu-slot-granted',action='store_true')
    args=parser.parse_args();p.require(args.cpu_slot_granted,'Await explicit root native build CPU slot')
    output=args.output.resolve();p.require(output.is_relative_to(HERE) and not output.exists(),'Fresh contained Phase2 build required')
    output.mkdir()
    try:
        result=build(output,args.compiler.resolve(strict=True),args.opencv.resolve(strict=True),args.red_negative_controls)
        print(json.dumps(dict(passed=True,target=result['target'],red_controls=result['red_controls'])))
    except Exception as error:
        (output/'failure.json').write_text(json.dumps(dict(passed=False,error=str(error),image_decodes=0),indent=2)+'\n')
        raise


if __name__=='__main__':
    main()
