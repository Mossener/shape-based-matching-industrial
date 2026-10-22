"""Bounded timing-only evidence reader and independent execution pin gates."""
import hashlib
import json
from pathlib import Path
import timing_audit as a

MAX_BYTES=64*1024**2
HERE=Path(__file__).resolve().parent
EXPERIMENT=HERE.parent
ROOT=EXPERIMENT.parents[1]


def loads(data):
    def unique(pairs):
        result={}
        for k,v in pairs:a.need(k not in result,'duplicate JSON key');result[k]=v
        return result
    def nonfinite(value):raise a.AuditError('nonfinite JSON constant: '+value)
    return json.loads(data.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=nonfinite)


def pin_schema(pin):
    a.need(isinstance(pin,dict) and set(pin)=={'path','bytes','sha256'} and isinstance(pin['path'],str) and
        Path(pin['path']).is_absolute() and str(Path(pin['path']).resolve())==pin['path'] and
        type(pin['bytes']) is int and pin['bytes']>=0 and isinstance(pin['sha256'],str) and len(pin['sha256'])==64 and
        all(c in '0123456789abcdef' for c in pin['sha256']),'complete canonical numeric pin required')


def pin_map(pins):
    a.need(isinstance(pins,list),'numeric pin list required');result={}
    for pin in pins:
        pin_schema(pin);a.need(pin['path'] not in result,'duplicate numeric pin');result[pin['path']]=pin
    return result


class Reader:
    def __init__(self,root):self.root=Path(root).resolve();self.seen={};self.indexes={}

    def allowed(self,path):
        path=Path(path);a.need(not path.is_symlink(),'numeric symlink refused');resolved=path.resolve(strict=True)
        a.need(resolved.is_relative_to(self.root),'numeric path escaped audit root')
        a.need(not resolved.is_relative_to(self.root/'datasets'),'all dataset bytes refused')
        a.need(resolved.suffix.lower() in ('.json','.jsonl','.csv','.py','.md','.txt','.cpp','.hpp'),
               'image/bank/gzip/executable byte access refused')
        return resolved

    def read(self,path):
        path=self.allowed(path);a.need(path.stat().st_size<=MAX_BYTES,'numeric read bound exceeded')
        with path.open('rb') as stream:data=stream.read(MAX_BYTES+1)
        a.need(len(data)<=MAX_BYTES,'numeric file grew beyond bound')
        pin=dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        a.need(self.seen.setdefault(str(path),pin)==pin,'numeric file changed during audit');return data

    def check(self,pin):
        pin_schema(pin);a.need(pin['bytes']<=MAX_BYTES,'pinned numeric size exceeds bound')
        data=self.read(pin['path']);a.need(self.seen[pin['path']]==pin,'frozen numeric SHA/size mismatch');return data

    def json(self,path):return loads(self.read(path))
    def recheck(self):
        for pin in list(self.seen.values()):self.check(pin)

    def index(self,pins):
        if id(pins) not in self.indexes:self.indexes[id(pins)]=pin_map(pins)
        return self.indexes[id(pins)]


def stage_gate(reader,pin,mode,calls,verify_payloads=False):
    data=loads(reader.check(pin));root=Path(pin['path']).parent;native=root/'native'
    a.need(data.get('completed') is True and data.get('stage')==mode and data.get('native_exit_code')==0 and
        data.get('actual_matcher_calls')==data.get('maximum_matcher_calls')==calls and
        data.get('post_verification_passed') is True and data.get('heldout_images_allowed') is False and
        data.get('missing_frames_are_not_negatives') is True,'completed native stage closure differs')
    files=reader.index(data.get('files'));execution=reader.index(data.get('execution_files'))
    a.need(all(Path(p).is_relative_to(native) for p in files),'native output pin escaped stage')
    a.need(all(Path(p).is_relative_to(root) and not Path(p).is_relative_to(native) for p in execution),
        'execution pin escaped separate stage scope')
    actual={str(p.resolve()) for p in native.rglob('*') if p.is_file() and p.name!='.gitignore'}
    a.need(actual==set(files),'native output inventory differs')
    actual_exec={str(p.resolve()) for p in root.rglob('*') if p.is_file() and not p.is_relative_to(native)
                 and str(p.resolve())!=pin['path'] and p.name!='.gitignore'}
    a.need(actual_exec==set(execution),'execution evidence inventory differs')
    if mode=='timing':
        a.need({str(Path(p).relative_to(native)) for p in files}==
            {'bank_load_timings.csv','stage_summary.json','timing_samples.csv','timing_pairs.csv'},'exact four numeric timing files required')
        wanted={'execution_provenance.json','verified_before.json','verified_after.json'}
        wanted|={str(Path('guard')/name) for name in ('stdout.txt','stderr.txt','guard_reservation.json',
            'guard_latest.json','guard_telemetry.jsonl','guard_receipt.json')}
        a.need({str(Path(p).relative_to(root)) for p in execution}==wanted,'exact timing execution/watchdog inventory required')
    for item in execution.values():reader.check(item)
    if verify_payloads:
        for item in files.values():reader.check(item)
    return data,native


def stage_read(reader,stage,path,prior=None):
    pin=reader.index(stage['files']).get(str(Path(path).resolve()));a.need(pin is not None,'numeric file absent from stage inventory')
    if prior is not None:a.need(reader.index(prior['input_pins']).get(pin['path'])==pin,'development file absent from independent audit pins')
    return reader.check(pin)


def validate_execution(reader,stage,stage_pin,native,pins,build):
    for field,target in [('build_manifest','build_manifest'),('quality_inputs','quality_inputs'),('selftest','selftest'),('previous_stage','development_stage')]:
        a.need(stage[field]==pins[target],'timing accepted reference binding differs')
    root=Path(stage_pin['path']).parent;execution=reader.json(root/'execution_provenance.json')
    command=[build['executable']['path'],'--mode','timing','--output',str(native),'--inputs',pins['quality_inputs']['path'],
        '--previous',str(Path(pins['development_stage']['path']).parent/'native')]
    a.need(execution['command']==command and execution['mode']=='timing' and execution['native_exit_code']==0 and
        execution['maximum_matcher_calls']==29952,'timing execution command/count differs')
    for field in ('build_manifest','quality_inputs','selftest','previous_stage','reservation'):
        a.need(execution[field]==stage[field],'execution/stage reference differs')
    script_paths=[EXPERIMENT/'quality'/name for name in ('run_quality.py','quality_contract.py','prepare_quality_inputs.py',
        'quality_execution_inputs.py','build_quality.py','quality_eval.cpp','quality_support.hpp','EXECUTION_RESOURCES.md')]
    script_paths += [EXPERIMENT/'native_provenance.py',EXPERIMENT/'execution_guard.py']
    a.need([p['path'] for p in execution['script_pins']]==list(map(str,script_paths)),'timing script closure differs')
    for pin in execution['script_pins']:reader.check(pin)
    reservation=loads(reader.check(stage['reservation']))
    a.need(reservation==dict(stage='timing',run=str(root),maximum_calls=29952,previous_stage='development',
        previous_freeze=pins['development_stage'],total_protocol_maximum=44736,
        policy='One attempt per fixed stage; preserve reservation and partial evidence; missing frames are never negatives'),
        'one-shot timing reservation differs')
    before=reader.json(root/'verified_before.json');after=reader.json(root/'verified_after.json')
    a.need(before==after and before['inputs']['passed'] is True and before['inputs']['quality_input_freeze']==pins['quality_inputs'] and
        before['images']['passed'] is True and before['images']['stage']=='timing' and before['images']['image_byte_files_checked']==64 and
        all(before['images'][k]==0 for k in ('image_decodes','matcher_calls','training_image_files_checked','heldout_images_checked')),
        'timing pre/post verification differs')
    guard=loads(reader.check(execution['watchdog']))
    a.need(guard==stage['watchdog'] and guard.get('passed') is True and guard.get('started') is True and
        guard.get('exit_code')==0 and guard.get('reason') is None and guard.get('command')==command,'timing watchdog completion differs')
    for key,value in dict(maximum_seconds=5400,maximum_rss_bytes=1610612736,maximum_output_bytes=4294967296,
            maximum_execution_bytes=67108864,minimum_free_bytes=0).items():
        a.need(type(guard[key]) is type(value) and guard[key]==value,'timing watchdog resource limit differs')
    a.need(0<=a.finite(guard['elapsed_seconds'])<5400 and 0<a.integer(guard['peak_rss_bytes'])<=1610612736,
        'timing watchdog observed resource ceiling differs')
