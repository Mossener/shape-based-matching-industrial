"""Single-process, bounded numeric-only performance probe; no quality claims."""
import ctypes
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
sys.path.insert(0,str(BASE))
import input_contract as c
import audit_numeric as a
import independent_numeric as n


class Memory(ctypes.Structure):
    _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong),
              *[(name,ctypes.c_size_t) for name in ('peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]]


def main():
    parameters=c.load(HERE/'PARAMETERS.json')
    out=HERE/'run_v1';out.mkdir()
    sys.stdout=(out/'stdout.txt').open('w',buffering=1)
    sys.stderr=(out/'stderr.txt').open('w',buffering=1)
    start=time.monotonic();state=dict(phase='verify_pins',poses=0,maps=0,features=0,descriptors=0)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Memory),ctypes.c_ulong]
    psapi.GetProcessMemoryInfo.restype=ctypes.c_int
    process=kernel.GetCurrentProcess();stop=threading.Event()
    def sample():
        mem=Memory();mem.cb=ctypes.sizeof(mem)
        if not psapi.GetProcessMemoryInfo(process,ctypes.byref(mem),mem.cb):raise OSError(ctypes.get_last_error(),'RSS query')
        return dict(state,elapsed_seconds=time.monotonic()-start,peak_rss_bytes=mem.peak_working,working_rss_bytes=mem.working)
    def watchdog():
        while not stop.wait(.1):
            try:
                status=sample();(out/'latest.json').write_text(json.dumps(status,indent=2)+'\n')
                if status['elapsed_seconds']>=parameters['maximum_seconds'] or status['peak_rss_bytes']>parameters['maximum_rss_bytes']:
                    reason='wall_time_ceiling' if status['elapsed_seconds']>=parameters['maximum_seconds'] else 'rss_ceiling'
                    (out/'failure.json').write_text(json.dumps(dict(status,incomplete=True,reason=reason),indent=2)+'\n')
                    print('PROBE_LIMIT '+reason,file=sys.stderr,flush=True)
                    os._exit(124)
            except BaseException as error:
                (out/'watchdog_failure.txt').write_text(repr(error)+'\n');os._exit(125)
    guard=threading.Thread(target=watchdog,daemon=True);guard.start()
    try:
        for record in parameters['inputs']+parameters['sources']:c.check(record)
        observer=c.load(parameters['observer_input'])
        target=parameters['target'];poses={a.pose_key(q):q for q in observer['poses'] if q['object_id']==target['object_id'] and q['image']==target['image']}
        c.need(len(poses)==48,'Fixed target pose scope')
        state['phase']='load_18_banks'
        before=time.monotonic();banks,metadata,attempts=a.load_banks(observer)
        load_end=sample();load_seconds=time.monotonic()-before
        bank_templates=sum(len(v) for v in banks.values())
        bank_layers=sum(len(t) for v in banks.values() for t in v)
        bank_features=sum(len(layer['features']) for v in banks.values() for t in v for layer in t)
        c.need((bank_templates,bank_layers,bank_features)==(59647,119294,2905834),'Whole bank coverage')
        state.update(phase='fixed_48_pose_geometry',bank_templates=bank_templates,bank_layers=bank_layers,bank_features=bank_features)
        before=time.monotonic();seen=set();descriptors={};timings=dict(parse_and_hash=0.,nearest_and_boxes=0.,feature_observation=0.,descriptor_summary=0.)
        with gzip.open(c.numeric_path(parameters['map_pack']),'rt',encoding='utf-8') as stream:
            lines=iter(stream)
            while True:
                first=next(lines,None)
                if first is None:break
                begin=time.monotonic();records=[json.loads(first)]+[json.loads(next(lines)) for _ in range(4)]
                key=a.pose_key(records[0]);c.need(key in poses and key not in seen,'Probe pose scope/duplicate');seen.add(key)
                c.need(all(a.pose_key(q)==key for q in records) and [q['name'] for q in records]==['M0','M1','B1','A0','A1'],'Five-map group')
                maps={q['name']:n.read_map(q['map']) for q in records};timings['parse_and_hash']+=time.monotonic()-begin
                pose=poses[key];begin=time.monotonic()
                c.need(a.map_box(maps['M0'])==tuple(pose['geometry'][5:9]),'Official bbox')
                a.validate_nearest_pyramid(maps['M0'],maps['M1']);timings['nearest_and_boxes']+=time.monotonic()-begin
                for fi,family in enumerate(observer['families']):
                    tid=pose['template_ids'][fi]
                    if tid<0:continue
                    for level,layer in enumerate(banks[family,key[0]][tid]):
                        current={'M':maps['M1' if level else 'M0'],'A':maps['A1' if level else 'A0'],'B':maps['B1' if level else 'M0']}
                        begin=time.monotonic();box=a.map_box(current['M']);timings['nearest_and_boxes']+=time.monotonic()-begin
                        begin=time.monotonic();observations=[]
                        for feature in layer['features']:
                            observations.append(n.feature_observation(current,layer,feature,box));state['features']+=1
                        timings['feature_observation']+=time.monotonic()-begin
                        begin=time.monotonic();descriptors[family,key[0],tid,level]=n.descriptor_summary(observations,32 if level==0 else 16)
                        timings['descriptor_summary']+=time.monotonic()-begin;state['descriptors']+=1
                state['poses']+=1;state['maps']+=5
        pose_seconds=time.monotonic()-before
        c.need(set(poses)==seen and state['poses']==48 and state['maps']==240,'Complete fixed probe poses/maps')
        c.need(state['features']==parameters['target_feature_rows'] and state['descriptors']==parameters['target_serialized_layers'],'Complete fixed probe features/layers')
        state['phase']='verify_after'
        for record in parameters['inputs']+parameters['sources']:c.check(record)
        result=dict(sample(),passed=True,load_banks_seconds=load_seconds,load_banks_end=load_end,pose_geometry_seconds=pose_seconds,timings_seconds=timings,
                    sources=parameters['sources'],inputs=parameters['inputs'],parameters=c.pin(HERE/'PARAMETERS.json'),
                    image_bytes_opened=0,native_executables=0,matcher_calls=0,
                    limitation='Numeric performance probe for fixed obj1/image0 only; no quality inference or full-audit scope reduction; full usage replay and full descriptor-memory growth unmeasured')
        c.need(result['elapsed_seconds']<parameters['maximum_seconds'] and result['peak_rss_bytes']<=parameters['maximum_rss_bytes'],'Final resource ceiling')
        (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    except BaseException as error:
        failure=dict(sample(),incomplete=True,reason=str(error));(out/'failure.json').write_text(json.dumps(failure,indent=2)+'\n')
        import traceback
        traceback.print_exc();raise
    finally:
        stop.set();guard.join(timeout=1);sys.stdout.flush();sys.stderr.flush()


if __name__=='__main__':main()
