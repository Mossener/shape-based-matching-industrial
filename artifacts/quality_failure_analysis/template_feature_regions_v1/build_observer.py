"""Build only after root grants the coordinated native CPU slot."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import input_contract as c
import native_provenance as p


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--cpu-slot-granted',action='store_true')
    parser.add_argument('--compiler',type=Path,default=Path('F:/mysys2/ucrt64/bin/g++.exe'))
    parser.add_argument('--opencv',type=Path,default=Path('D:/opencv-4.12.0'))
    args=parser.parse_args();c.need(args.cpu_slot_granted,'Await root native CPU-slot grant')
    out=args.output.resolve();c.need(out.is_relative_to(c.HERE) and not out.exists(),'Fresh build directory inside experiment required')
    out.mkdir();commands=[]
    try:
        c.specification();compiler=args.compiler.resolve(strict=True);opencv=args.opencv.resolve(strict=True)
        env=dict(os.environ);env['PATH']=str(compiler.parent)+';'+str(opencv/'build/bin')+';'+env.get('PATH','')
        sources=[q for q in c.HERE.iterdir() if q.is_file() and q.suffix.lower() in ('.py','.cpp','.hpp','.json','.md')]
        pins=[p.file_pin(q) for q in sources]
        tools,queries=p.compiler_tools(compiler,env)
        libraries=[opencv/'build/lib/libopencv_world4120.dll.a',compiler.parent.parent/'lib/libz.dll.a',
                   compiler.parent.parent/'lib/libpsapi.a',compiler.parent.parent/'lib/libbcrypt.a']
        toolpins=[p.file_pin(q) for q in tools+libraries]
        runtime=p.import_closure(tools+[opencv/'build/bin/libopencv_world4120.dll',compiler.parent/'zlib1.dll'],compiler,opencv,env)
        flags=['-O3','-std=c++17','-DNDEBUG','-I'+str(opencv/'build')]
        flags+=['-I'+str(opencv/'modules'/m/'include') for m in ('core','imgproc','imgcodecs')]
        def command(label,args):
            rec=dict(label=label,command=list(map(str,args)),working_directory=str(out));commands.append(rec)
            (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
            run=subprocess.run(rec['command'],cwd=out,env=env,capture_output=True)
            (out/(label+'.stdout.txt')).write_bytes(run.stdout);(out/(label+'.stderr.txt')).write_bytes(run.stderr)
            rec['exit_code']=run.returncode;(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
            c.need(run.returncode==0,label+' failed; diagnostics retained');return run.stdout
        source=c.HERE/'observer.cpp'
        before=command('dependency_before',[compiler,*flags,'-M','-MT','adapter.o',source])
        (out/'before.d').write_bytes(before)
        dependencies=p.dependency_pins(before,'adapter.o',out,c.ROOT,[source])
        command('compile',[compiler,*flags,'-c',source,'-o',out/'adapter.o','-MD','-MF',out/'adapter.d','-MT','adapter.o'])
        actual=(out/'adapter.d').read_bytes()
        actual_deps=p.dependency_pins(actual,'adapter.o',out,c.ROOT,[source])
        c.need(actual==before and actual_deps==dependencies,'Actual dependency bytes/list differ')
        executable=out/'observer.exe';command('link',[compiler,out/'adapter.o',*libraries,'-o',executable])
        exe_runtime=p.import_closure([executable],compiler,opencv,env)
        for record in pins+toolpins+runtime['files']+exe_runtime['files']+actual_deps:p.check_pin(record)
        c.specification()
        result=dict(passed=True,compiler=str(compiler),opencv=str(opencv),sources=pins,tools_libraries=toolpins,
                    compiler_tool_queries=queries,compiler_runtime=runtime,executable_runtime=exe_runtime,
                    executable=p.file_pin(executable),object=p.file_pin(out/'adapter.o'),dependency_file=p.file_pin(out/'adapter.d'),
                    dependencies=actual_deps,commands=commands,image_decodes=0,matcher_calls=0,native_observer_runs=0)
        (out/'BUILD_FREEZE.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(passed=True,compiler_commands=len(commands),image_decodes=0,matcher_calls=0)))
    except Exception as error:
        (out/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),commands=commands,image_decodes=0,matcher_calls=0),indent=2)+'\n')
        raise


if __name__=='__main__':main()
