"""Operational compiler child: a Windows job bounds this process and its children.

The caller supplies its own frozen command reservation, never external content.
The parent watchdog bounds wall/output; this job's memory limit includes GCC's
cc1plus/assembler/linker children. No dataset or image API is used.
"""
import ctypes
from ctypes import wintypes
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import time


class BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', wintypes.DWORD), ('minimum_working', ctypes.c_size_t),
                ('maximum_working', ctypes.c_size_t), ('active_limit', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                ('scheduling', wintypes.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', BasicLimits), ('io', IoCounters),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


def main():
    reservation = json.loads(Path(sys.argv[1]).read_bytes())
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    limits.basic.flags = 0x200 | 0x2000  # JOB_MEMORY | KILL_ON_JOB_CLOSE
    limits.job_memory = reservation['job_memory_limit_bytes']
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    # Keep this handle open until process termination, so compiler children
    # inherit the job and parent watchdog termination also closes the job.
    output = Path(reservation['output'])
    output.mkdir()
    attempts = []
    spec = importlib.util.spec_from_file_location('_native_build_provenance', reservation['provenance_source'])
    provenance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provenance)
    declared = None
    code = 0
    for index, command in enumerate(reservation['commands']):
        started = time.monotonic()
        with (output / f'command_{index}_stdout.txt').open('wb') as stdout, \
                (output / f'command_{index}_stderr.txt').open('wb') as stderr:
            run = subprocess.run(command, cwd=reservation['cwd'], stdout=stdout, stderr=stderr)
        attempts.append(dict(command=command, returncode=run.returncode,
                             elapsed_seconds=time.monotonic() - started))
        if run.returncode:
            code = run.returncode
            break
        if index == 0:
            declared = provenance.dependency_pins(
                (output / 'declared.d').read_bytes(), 'adapter.o', reservation['cwd'],
                reservation['repository'], reservation['allowed_project_sources'])
        elif index == 1:
            actual = provenance.dependency_pins(
                (output / 'actual.d').read_bytes(), 'adapter.o', reservation['cwd'],
                reservation['repository'], reservation['allowed_project_sources'])
            if actual != declared:
                raise ValueError('Declared and actual compiler dependency pins differ')
    if declared is not None:
        for dependency in declared:
            provenance.check_pin(dependency)
    observed = ExtendedLimits()
    if not kernel.QueryInformationJobObject(job, 9, ctypes.byref(observed), ctypes.sizeof(observed), None):
        raise ctypes.WinError(ctypes.get_last_error())
    result = dict(attempts=attempts, job_memory_limit_bytes=limits.job_memory,
                  peak_job_committed_memory_bytes=observed.peak_job_memory,
                  peak_process_committed_memory_bytes=observed.peak_process_memory,
                  all_compiler_children_in_job=True,
                  compiler_dependency_pins=declared,
                  memory_semantics='Windows job committed-memory limit; distinct from RSS/working set',
                  passed=code == 0)
    (output / 'compiler_child_result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
