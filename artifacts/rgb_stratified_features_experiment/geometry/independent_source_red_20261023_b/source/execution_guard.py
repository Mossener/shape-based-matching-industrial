"""Watch one foreground child process; preserve all partial outputs on failure."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

class Memory(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD),
              *[(name,ctypes.c_size_t) for name in ('peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]]

def directory_bytes(root):
    if not root.exists():return 0
    total=0
    for current,dirs,names in os.walk(root,followlinks=False):
        for name in dirs+names:
            path=Path(current)/name
            if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Output path escapes guarded directory')
        total+=sum((Path(current)/name).stat().st_size for name in names)
    return total

def run_guarded(command,env,cwd,native_output,execution,maximum_seconds=5400.,maximum_rss_bytes=1610612736,
                maximum_output_bytes=4294967296,minimum_free_bytes=0,maximum_execution_bytes=67108864):
    """One child, polled at 50ms; native preflight byte checks remain necessary.

    The process cannot spawn delegated worker executables under the frozen
    adapter contract. Threads are included in process-wide working-set data.
    This watchdog bounds observed RSS/wall/output; it is not an OS allocation
    sandbox and may observe a limit just after the offending allocation/write.
    """
    native_output=Path(native_output).resolve();execution=Path(execution).resolve();cwd=Path(cwd).resolve()
    if native_output.exists() or execution.exists():raise ValueError('Fresh native and execution paths required')
    if not native_output.parent.exists() or not execution.parent.exists():raise ValueError('Existing parent directories required')
    if native_output==execution or native_output.is_relative_to(execution) or execution.is_relative_to(native_output):raise ValueError('Separate output directories required')
    execution.mkdir();started=time.monotonic();process=None;handle=None;reason=None;peak=0;samples=0;size=0
    record=dict(command=list(map(str,command)),working_directory=str(cwd),started=False,passed=False,exit_code=None,
                maximum_seconds=maximum_seconds,maximum_rss_bytes=maximum_rss_bytes,maximum_output_bytes=maximum_output_bytes,
                minimum_free_bytes=minimum_free_bytes,maximum_execution_bytes=maximum_execution_bytes)
    (execution/'guard_reservation.json').write_text(json.dumps(record,indent=2)+'\n')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Memory),wintypes.DWORD];psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    try:
        if shutil.disk_usage(native_output.parent).free<minimum_free_bytes:
            reason='insufficient_free_disk'
        else:
            with (execution/'stdout.txt').open('wb') as stdout,(execution/'stderr.txt').open('wb') as stderr:
                process=subprocess.Popen(record['command'],cwd=cwd,env=env,stdout=stdout,stderr=stderr)
                record['started']=True;record['pid']=process.pid
                handle=kernel.OpenProcess(0x0400|0x0010,False,process.pid)
                if not handle:raise OSError(ctypes.get_last_error(),'Open child process for RSS')
                previous=-1.
                while True:
                    elapsed=time.monotonic()-started
                    memory=Memory();memory.cb=ctypes.sizeof(memory)
                    queried=psapi.GetProcessMemoryInfo(handle,ctypes.byref(memory),memory.cb)
                    code=process.poll()
                    if not queried and code is None:raise OSError(ctypes.get_last_error(),'Child peak RSS query')
                    if queried:peak=max(peak,memory.peak_working)
                    size=directory_bytes(native_output);execution_size=directory_bytes(execution);samples+=1
                    state=dict(elapsed_seconds=elapsed,peak_rss_bytes=peak,native_output_bytes=size,execution_bytes=execution_size,samples=samples,pid=process.pid)
                    if elapsed>=maximum_seconds:reason='wall_time_ceiling'
                    elif peak>maximum_rss_bytes:reason='peak_working_set_ceiling'
                    elif size>maximum_output_bytes:reason='native_output_ceiling'
                    elif size+execution_size>maximum_output_bytes:reason='combined_output_ceiling'
                    elif execution_size>maximum_execution_bytes:reason='execution_log_ceiling'
                    if elapsed-previous>=1.:
                        (execution/'guard_latest.json').write_text(json.dumps(state,indent=2)+'\n')
                        with (execution/'guard_telemetry.jsonl').open('a') as stream:stream.write(json.dumps(state,separators=(',',':'))+'\n')
                        previous=elapsed
                    if reason:
                        if code is None:process.kill()
                        process.wait(timeout=10);break
                    if code is not None:break
                    time.sleep(.05)
            record['exit_code']=process.returncode
            if reason is None and process.returncode!=0:reason='process_exit_nonzero'
            if reason is None:record['passed']=True
    except BaseException as error:
        reason='guard_exception';record['exception']=repr(error)
        if process is not None and process.poll() is None:process.kill();process.wait(timeout=10)
        if process is not None:record['exit_code']=process.returncode
    finally:
        if handle:kernel.CloseHandle(handle)
    try:final_bytes=directory_bytes(native_output)
    except BaseException as error:
        final_bytes=None;record['final_stat_exception']=repr(error)
        if reason is None:reason='final_stat_exception';record['passed']=False
    record.update(reason=reason,elapsed_seconds=time.monotonic()-started,peak_rss_bytes=peak,native_output_bytes=final_bytes,samples=samples)
    (execution/'guard_receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
