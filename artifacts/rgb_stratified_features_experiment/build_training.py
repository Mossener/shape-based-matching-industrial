"""Build the shared-pool adapter with the unmodified V11 core, without images."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import native_provenance as p

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def read(path):return json.loads(path.read_text())
def source_gate():
    manifest=read(HERE/'TRAINING_SOURCE_FREEZE.json')
    p.require(manifest['git_revision']=='b25df46f6ddf9c24fb43f5836f1414dc38c8caed' and manifest['sole_core_delta'] is None,'Exact original V11 required')
    result=[]
    for directory,key in [('control_v11','files'),('frozen_helpers','helpers')]:
        expected=manifest[key];actual={f.relative_to(HERE/directory).as_posix() for f in (HERE/directory).rglob('*') if f.is_file()}
        p.require(actual==set(expected),'Snapshot member set changed')
        for name,pin in expected.items():
            full=p.file_pin(HERE/directory/name)
            p.require({k:full[k] for k in ('bytes','sha256')}==pin,'Snapshot source changed: '+name)
            result.append(Path(full['path']))
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--cpu-slot-granted',action='store_true')
    args=ap.parse_args();p.require(args.cpu_slot_granted,'Coordinated compiler slot required')
    out=args.output.resolve();p.require(out.is_relative_to(HERE) and not out.exists(),'Fresh contained build required');out.mkdir()
    commands=[]
    try:
        project=source_gate()+[HERE/n for n in ('train_shared_features.cpp','integration/shared_training.hpp','collector/candidate_collector.hpp','collector/candidate_collector.cpp','sampler/v2/stratified_sampler.hpp','packing/numeric_pack.hpp')]
        supporting=[HERE/n for n in ('build_training.py','native_provenance.py','prepare_training_sources.py','prepare_training_inputs.py','TRAINING_SOURCE_FREEZE.json','TRAINING_INPUT_FREEZE.json','PROTOCOL.json','DESIGN_ERRATA_1.md','PACK_FORMAT_V1.md')]
        project_pins=[p.file_pin(path) for path in project+supporting]
        compiler=Path('F:/mysys2/ucrt64/bin/g++.exe');opencv=Path('D:/opencv-4.12.0');env=dict(os.environ)
        env['PATH']=str(compiler.parent)+';'+str(opencv/'build/bin')+';'+env.get('PATH','')
        tools,queries=p.compiler_tools(compiler,env)
        libraries=[opencv/'build/lib/libopencv_world4120.dll.a',compiler.parent.parent/'lib/libz.dll.a',compiler.parent.parent/'lib/libpsapi.a',compiler.parent.parent/'lib/libbcrypt.a']
        tool_pins=[p.file_pin(path) for path in tools+libraries]
        runtime_before=p.import_closure(tools+[opencv/'build/bin/libopencv_world4120.dll',compiler.parent/'zlib1.dll'],compiler,opencv,env)
        private=HERE/'control_v11'
        flags=['-std=c++17','-O3','-mssse3','-msse4.1','-fopenmp','-Wall','-Wextra','-Wno-sign-compare','-Wno-unused-function','-I'+str(private),'-I'+str(private/'MIPP'),'-I'+str(opencv/'build')]
        flags+=['-I'+str(opencv/'modules'/name/'include') for name in ('core','imgproc','highgui','imgcodecs','videoio')]
        def run(label,command):
            item=dict(label=label,command=list(map(str,command)),working_directory=str(out));commands.append(item)
            (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
            result=subprocess.run(item['command'],cwd=out,env=env,capture_output=True,timeout=300)
            (out/(label+'.stdout')).write_bytes(result.stdout);(out/(label+'.stderr')).write_bytes(result.stderr)
            item['exit_code']=result.returncode;(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
            p.require(result.returncode==0,label+' failed; diagnostics preserved');return result.stdout
        units=[]
        for name,source in [('core',private/'line2Dup.cpp'),('adapter',HERE/'train_shared_features.cpp')]:
            target=name+'.o';before_data=run(name+'_dependency_before',[compiler,*flags,'-M','-MT',target,source])
            (out/(name+'_before.d')).write_bytes(before_data);before=p.dependency_pins(before_data,target,out,ROOT,project)
            run(name+'_compile',[compiler,*flags,'-c',source,'-o',out/target,'-MD','-MF',out/(name+'.d'),'-MT',target])
            actual=p.dependency_pins((out/(name+'.d')).read_bytes(),target,out,ROOT,project)
            p.require(before==actual,'Actual compiler dependency list/bytes changed')
            units.append(dict(source=str(source),target=target,object=p.file_pin(out/target),dependency_file=p.file_pin(out/(name+'.d')),dependencies=actual))
        exe=out/'train_shared_features.exe';run('link',[compiler,'-fopenmp',out/'core.o',out/'adapter.o',*libraries,'-o',exe])
        runtime=p.import_closure([exe],compiler,opencv,env)
        for pin in project_pins+tool_pins+runtime_before['files']+runtime['files']:p.check_pin(pin)
        for unit in units:
            for pin in unit['dependencies']+[unit['object'],unit['dependency_file']]:p.check_pin(pin)
        source_gate()
        result=dict(passed=True,compiler=str(compiler),opencv=str(opencv),executable=p.file_pin(exe),project_sources=project_pins,
                    compiler_tools_and_link_libraries=tool_pins,compiler_tool_queries=queries,compiler_runtime_closure=runtime_before,
                    executable_runtime_closure=runtime,dependency_units=units,commands=commands,image_decodes=0,matcher_calls=0,training_poses=0)
        (out/'build_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(passed=True,translation_units=2,compiler_commands=len(commands),image_decodes=0,matcher_calls=0)))
    except Exception as error:
        (out/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),commands=commands,image_decodes=0,matcher_calls=0),indent=2)+'\n');raise
if __name__=='__main__':main()
