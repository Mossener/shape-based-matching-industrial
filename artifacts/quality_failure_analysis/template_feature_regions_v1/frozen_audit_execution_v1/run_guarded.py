"""Prepare-to-run single-process guard for the unchanged complete numeric audit."""
import ctypes
import json
import os
from pathlib import Path
import runpy
import sys
import threading
import time
import traceback

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
sys.path.insert(0,str(BASE))
import input_contract as c


class Memory(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong),
              *[(name,ctypes.c_size_t) for name in ('peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]]


def directory_bytes(root):
    total=0;files=0
    for current,dirs,names in os.walk(root,followlinks=False):
        c.need(Path(current).resolve().is_relative_to(root),'Output directory escaped experiment execution root')
        for name in dirs:
            path=Path(current)/name
            c.need(not path.is_symlink() and path.resolve().is_relative_to(root),'Output directory symlink or escape forbidden')
        for name in names:
            path=Path(current)/name
            c.need(not path.is_symlink() and path.resolve().is_relative_to(root),'Output file symlink or escape forbidden')
            total+=path.stat().st_size;files+=1
    return total,files


def visible_progress(main_ident,audit_path):
    frame=sys._current_frames().get(main_ident)
    chain=[];progress={};phase='guard_preflight_or_cleanup'
    while frame is not None:
        source=Path(frame.f_code.co_filename)
        if source.parent==BASE and source.suffix=='.py':
            name=frame.f_code.co_name;chain.append(dict(source=source.name,function=name,line=frame.f_lineno))
            if source==audit_path:
                local=frame.f_locals
                if name=='main':
                    for key in ('feature_count',):
                        value=local.get(key)
                        if type(value) is int:progress[key]=value
                    for key in ('seen','descriptor_keys','descriptors'):
                        value=local.get(key)
                        if isinstance(value,(dict,set,list,tuple)):progress[key+'_count']=len(value)
                if name=='usage_replay':
                    for key in ('events','expected_frames','gt_links','rgb_signatures'):
                        value=local.get(key)
                        if isinstance(value,(dict,set,list,tuple)):progress[key+'_count']=len(value)
                    phase='complete_usage_replay'
                elif name=='load_banks':phase='load_all_18_banks'
                elif name=='verify_attempt_layers':phase='verify_all_attempt_layers'
                elif name=='main' and phase=='guard_preflight_or_cleanup' and 'feature_count' in local:phase='complete_map_feature_replay_or_final_checks'
        frame=frame.f_back
    return dict(phase=phase,python_stack=chain[:12],counters=progress)


def main():
    parameters=c.load(HERE/'PARAMETERS.json');parameter_pin=c.pin(HERE/'PARAMETERS.json')
    c.need(parameters['schema']=='complete_numeric_audit_guard_v1','Guard parameter schema')
    c.need(parameters['scope']==dict(poses=20736,maps=103680,features=2905834,serialized_layers=119294,attempt_layers=124416,quality_frames=7200,selected_events=64618),'Complete frozen audit scope')
    c.need(parameters['maximum_seconds']==1800 and parameters['maximum_rss_bytes']==1610612736 and parameters['maximum_output_bytes']==2147483648,'Frozen guard ceilings')
    run=Path(parameters['execution_directory']).resolve();audit=Path(parameters['audit_directory']).resolve()
    c.need(run==HERE/'run_v1' and run.is_relative_to(BASE) and not run.exists(),'Fresh experiment-local execution directory required')
    c.need(audit==run/'audit' and not audit.exists(),'Fresh audit output directory required')
    c.need(Path(parameters['audit_source']).resolve()==BASE/'audit_numeric.py','Only unchanged frozen numeric audit may execute')
    run.mkdir();guard=run/'guard';guard.mkdir()
    sys.stdout=(guard/'stdout.txt').open('w',buffering=1)
    sys.stderr=(guard/'stderr.txt').open('w',buffering=1)
    start=time.monotonic();stop=threading.Event();main_ident=threading.get_ident();state=dict(phase='verify_complete_closure')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Memory),ctypes.c_ulong];psapi.GetProcessMemoryInfo.restype=ctypes.c_int
    process=kernel.GetCurrentProcess();cached=dict(output_bytes=0,output_files=0)
    def sample(scan_output=True):
        mem=Memory();mem.cb=ctypes.sizeof(mem)
        if not psapi.GetProcessMemoryInfo(process,ctypes.byref(mem),mem.cb):raise OSError(ctypes.get_last_error(),'RSS query')
        if scan_output:cached['output_bytes'],cached['output_files']=directory_bytes(run)
        progress=visible_progress(main_ident,BASE/'audit_numeric.py') if state['phase']=='run_original_audit' else dict(phase=state['phase'],python_stack=[],counters={})
        return dict(elapsed_seconds=time.monotonic()-start,peak_rss_bytes=mem.peak_working,working_rss_bytes=mem.working,**cached,**progress)
    def violation(status):
        if status['elapsed_seconds']>=parameters['maximum_seconds']:return 'wall_time_ceiling'
        if status['peak_rss_bytes']>parameters['maximum_rss_bytes']:return 'peak_working_set_ceiling'
        if status['output_bytes']>parameters['maximum_output_bytes']:return 'numeric_output_ceiling'
        return None
    def watchdog():
        last_scan=last_saved=-1.
        while not stop.wait(.25):
            try:
                now=time.monotonic()-start;scan=now-last_scan>=1.
                status=sample(scan)
                if scan:last_scan=now
                reason=violation(status)
                if reason:
                    (guard/'failure.json').write_text(json.dumps(dict(status,incomplete=True,reason=reason,parameters=parameter_pin),indent=2)+'\n')
                    print('AUDIT_GUARD_LIMIT '+reason,file=sys.stderr,flush=True)
                    os._exit(124)
                if now-last_saved>=2.:
                    (guard/'latest.json').write_text(json.dumps(status,indent=2)+'\n')
                    with (guard/'telemetry.jsonl').open('a') as stream:stream.write(json.dumps(status,separators=(',',':'))+'\n')
                    last_saved=now
            except BaseException as error:
                (guard/'watchdog_failure.json').write_text(json.dumps(dict(incomplete=True,reason=repr(error),elapsed_seconds=time.monotonic()-start),indent=2)+'\n')
                os._exit(125)
    monitor=threading.Thread(target=watchdog,daemon=True);monitor.start()
    command=[parameters['audit_source'],'--observation',parameters['observation'],'--output',str(audit)]
    try:
        (guard/'reservation.json').write_text(json.dumps(dict(command=command,parameters=parameter_pin,scope=parameters['scope'],
            maximum_seconds=1800,maximum_rss_bytes=1610612736,maximum_output_bytes=2147483648,python_executable=sys.executable,python_version=sys.version,
            image_bytes_opened=0,native_executable_launches=0,matcher_calls=0),indent=2)+'\n')
        for record in parameters['sources']+parameters['numeric_inputs']:c.check(record)
        state['phase']='run_original_audit';sys.argv=command
        runpy.run_path(parameters['audit_source'],run_name='__main__')
        state['phase']='verify_complete_outputs_and_closure'
        summary=c.load(audit/'summary.json')
        c.need(summary['passed'] and summary['poses']==20736 and summary['features']==2905834 and summary['serialized_layers']==119294 and summary['attempt_layers']==124416,'Full audit receipt coverage')
        for record in parameters['sources']+parameters['numeric_inputs']+[parameter_pin]:c.check(record)
        status=sample();reason=violation(status);c.need(reason is None,'Final resource limit: '+str(reason))
        result=dict(status,passed=True,parameters=parameter_pin,command=command,audit_summary=c.pin(audit/'summary.json'),scope=parameters['scope'],
                    numeric_input_members=len(parameters['numeric_inputs']),image_bytes_opened=0,native_executable_launches=0,matcher_calls=0,
                    limitation='Complete frozen numeric replay with process-wide resource guard; no native real-image pixel regeneration or causal accuracy claim')
        (guard/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(passed=True,elapsed_seconds=result['elapsed_seconds'],peak_rss_bytes=result['peak_rss_bytes'],output_bytes=result['output_bytes'])),flush=True)
    except BaseException as error:
        status=sample();(guard/'failure.json').write_text(json.dumps(dict(status,incomplete=True,reason=repr(error),parameters=parameter_pin),indent=2)+'\n')
        traceback.print_exc();raise
    finally:
        stop.set();monitor.join(timeout=1);sys.stdout.flush();sys.stderr.flush()


if __name__=='__main__':main()
