"""Independent inert-byte review of Phase2 actual build/selftest receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN_SHA = '830a77d629ad766df998aa59fbd1b6cf6bc207c900263afd04b890560eb9215a'
seen = {}


def need(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_bytes())


def pin(path):
    path = Path(path)
    need(path.suffix.lower() not in ('.bmp','.png','.jpg','.jpeg','.smd'), 'No image/SMD content access')
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def check(value):
    actual = pin(value['path'])
    need(actual == value, 'Changed exact file pin: ' + value['path'])
    key = str(Path(value['path']).resolve())
    need(key not in seen or seen[key] == value, 'Conflicting pins')
    seen[key] = value


def build(path, red):
    result = load(path)
    need(result['passed'] is True and result['red_controls'] is red and
         result['core_revision'] == 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed', 'Build scope differs')
    commands = result['commands']
    need([row['label'] for row in commands] == ['dependency_before','compile','link'] and
         all(row['exit_code'] == 0 for row in commands), 'Actual build commands incomplete')
    for command in commands[:2]:
        need(('-DSCORE_PATH_RED_CONTROLS' in command['command']) is red, 'Wrong RED build flag')
    values = result['project_sources'] + result['phase1_project_sources'] + result['compiler_tools_and_link_libraries']
    values += result['compiler_runtime_closure']['files'] + result['executable_runtime_closure']['files']
    values += [result['executable'],result['preprocessing_extraction'],result['prior_phase1_receipt']]
    need(len(result['dependency_units']) == 1, 'One actual core translation unit required')
    unit = result['dependency_units'][0]
    need(Path(unit['source']) == HERE/'phase2.cpp', 'Unexpected translation unit')
    values += unit['dependencies'] + [unit['object'],unit['dependency_file'],unit['generated_preprocess_header']]
    for value in values:
        check(value)
    extraction = load(result['preprocessing_extraction']['path'])
    check(extraction['source']);check(extraction['generated_header'])
    source = Path(extraction['source']['path']).read_bytes()
    blocks = [row['utf8'].encode('utf-8') for row in extraction['components']]
    need(all(source.count(block) == 1 for block in blocks), 'Original exact source blocks differ')
    expected = b'#pragma once\nnamespace probe_v2 {\n' + b''.join(blocks) + b'\n}\n'
    need(Path(extraction['generated_header']['path']).read_bytes() == expected, 'Exact extracted header differs')
    return result, pin(path)


def stage(name, fault, build_pin):
    folder = HERE/name
    path = folder/'PHASE2_STAGE_FREEZE.json'
    result = load(path)
    need(result['completed'] is True and result['stage'] == 'selftest' and result['fault'] == fault and
         result['build_manifest'] == build_pin and result['input_plan']['sha256'] == PLAN_SHA,
         'Wrong completed synthetic stage')
    need(result['image_hash_operations'] == result['unique_dataset_image_files_opened'] == 0 and
         result['image_before'] == result['image_after'] == [] and result['accuracy_improvement_claim'] is False,
         'Synthetic stage read dataset or claimed accuracy')
    files = result['files']
    for value in files + result['execution_files'] + [build_pin,result['input_plan'],result['reservation']] + result['red_receipts']:
        check(value)
    need({p.resolve() for p in (folder/'native').rglob('*') if p.is_file()} ==
         {Path(v['path']).resolve() for v in files}, 'Native output membership differs')
    need({p.resolve() for p in folder.iterdir() if p.is_file()} ==
         {Path(v['path']).resolve() for v in result['execution_files']} | {path.resolve()},
         'Execution output membership differs')
    execution = load(folder/'execution_provenance.json')
    need(execution['build_manifest'] == build_pin and execution['mode'] == 'selftest' and
         execution['fault'] == fault and execution['maximum_dataset_kernel_calls'] == 0,
         'Actual invocation differs')
    need(load(folder/'watchdog.json')['stop_reason'] is None, 'Watchdog stopped synthetic fixture')
    if fault != 'none':
        failure = load(folder/'native/failure.json')
        need(result['expected_native_failure'] is True and result['native_exit_code'] == 1 and
             result['summary'] is None and result['native_failure'] == failure and
             failure['reason'] == 'Independent '+fault+' oracle mismatch' and
             failure['decoded_operations_started'] == failure['full_class_search_replays'] ==
             failure['public_detector_match_calls'] == 0, 'RED failed for a different reason')
        expected = {'coarse':(1,0,0),'local':(1,1,0),'winner':(1,1,1)}[fault]
        need(tuple(failure[key] for key in ('coarse_similarity_calls_started','local_map_calls_started',
                                          'local_fused_maximum_calls_started')) == expected,
             'Unexpected RED kernel path')
    else:
        summary = load(folder/'native/selftest_result.json')
        need(result['expected_native_failure'] is False and result['native_exit_code'] == 0 and
             result['native_failure'] is None and result['summary'] == summary, 'GREEN did not complete')
        expected = dict(passed=1,stage='selftest',coarse_cells=12,local_cells=256,scalar_native_oracles=1,
                        dataset_image_reads=0,full_class_search_replays=0,public_detector_match_calls=0)
        need(summary == expected, 'GREEN exact fixture budget differs')
        need(len(result['red_receipts']) == 3, 'Missing three RED gates')
    return pin(path)


def main():
    red, red_pin = build(HERE/'probe_build_red_v1/build_manifest.json', True)
    green, green_pin = build(HERE/'probe_build_green_v1/build_manifest.json', False)
    def normalized(value):
        header = value['dependency_units'][0]['generated_preprocess_header']
        need(value['project_sources'].count(header) == 1, 'Generated header source membership differs')
        return [row for row in value['project_sources'] if row != header], (header['bytes'],header['sha256'])
    need(normalized(red) == normalized(green) and red['compiler_tools_and_link_libraries'] ==
         green['compiler_tools_and_link_libraries'], 'RED/GREEN source/tool inputs differ')
    red_stages = [stage('probe_selftest_red_'+fault+'_v1',fault,red_pin) for fault in ('coarse','local','winner')]
    green_stage = stage('probe_selftest_green_v1','none',green_pin)
    need(load(green_stage['path'])['red_receipts'] == red_stages, 'GREEN bindings differ from reviewed REDs')
    result = dict(passed=True,read_only_inert_byte_audit=True,distinct_pins_checked=len(seen),
                  red_build=red_pin,green_build=green_pin,red_stages=red_stages,green_stage=green_stage,
                  exact_red_reasons=True,green_coarse_cells=12,green_local_cells=256,
                  native_processes_started_by_reader=0,image_smd_bytes_opened_by_reader=0,
                  project_implementation_imports=0,source=pin(Path(__file__)),
                  limitations=['Hashes runtime/build binaries as inert bytes; does not attest all actual Windows loader reads.',
                               'Synthetic gates only; no dataset result or accuracy/speed claim.'])
    target = HERE/'ROOT_SYNTHETIC_RECEIPT_20261022.json'
    need(not target.exists(), 'Preserve earlier root receipt')
    target.write_text(json.dumps(result,indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True,receipt=pin(target),distinct_pins_checked=len(seen))))


if __name__ == '__main__':
    main()
