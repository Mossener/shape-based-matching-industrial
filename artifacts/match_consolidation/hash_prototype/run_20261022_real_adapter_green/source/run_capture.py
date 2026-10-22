"""Capture/reference exact ordered traces for the fixed 25-case development matrix."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from capture_manifest import (CORE_REVISION, check_file, json_bytes, read_trace,
                              relative_path, require, sha256, validate_case)
from dependency_closure import audit_build_dependencies
from real_capture_audit import audit_real_capture

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def metadata(path, role=None, direct=False):
    path = Path(path).resolve(strict=True)
    value = dict(path=path.name if direct else path.relative_to(ROOT).as_posix(),
                 size_bytes=path.stat().st_size, sha256=sha256(path))
    if role:
        value['role'] = role
    return value


def write_new(path, data):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(data, indent=2)+'\n')


def fixed_cases(scenario):
    frozen = json_bytes((HERE/'CAPTURE_PROTOCOL.json').read_bytes())
    require(scenario == frozen['tiny_scenario'] == 'quality_actual85',
            'Threshold50 stress needs a later separately frozen protocol')
    cases = [dict(case_id='LED_'+str(i), dataset='LED', split='legacy',
                  scenario='legacy', matcher_threshold=75) for i in range(1, 9)]
    cases.append(dict(case_id='case1', dataset='case1', split='legacy', scenario='legacy', matcher_threshold=90))
    index_path = ROOT/'datasets/tless_tiny/index.json'
    index_pin = metadata(index_path, 'index')
    require(index_pin['sha256'] == frozen['tiny_index_sha256'], 'Frozen tiny metadata index differs')
    index = json_bytes(index_path.read_bytes())
    development = [frame for frame in index['test'] if frame['split'] == 'development']
    require(len(development) == 16, 'Fixed sixteen-frame development matrix differs')
    seen = set()
    for frame in development:
        identity = (frame['scene_id'], frame['image_id'])
        require(all(type(n) is int and n >= 0 for n in identity) and identity not in seen,
                'Development frame identity invalid/duplicated')
        seen.add(identity)
        # Only development metadata is allowed to become an image path.
        image = 'datasets/tless_tiny/'+frame['rgb']
        relative_path(ROOT, image)
        cases.append(dict(case_id='tiny_s%d_i%d' % identity, dataset='tless_tiny',
                          split='development', scenario=scenario, object_id=1,
                          matcher_threshold=85 if scenario == 'quality_actual85' else 50,
                          image=image))
    require([case['case_id'] for case in cases] == frozen['case_order'] and len(cases) == frozen['case_count'],
            'Frozen25-case identity/order differs')
    return cases, index_pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tiny-scenario', choices=('quality_actual85', 'stress_coarse50'), default='quality_actual85')
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    require(args.cpu_slot_granted, 'Parent must explicitly grant native matcher CPU')
    output = args.output.resolve()
    require(output.is_relative_to(ROOT) and not output.exists(), 'Capture output must be new in repository')
    receipt_path = args.build_receipt.resolve(strict=True)
    require(receipt_path.is_relative_to(ROOT), 'Build receipt must stay in repository')
    receipt_pin = metadata(receipt_path, 'config')
    receipt = json_bytes(receipt_path.read_bytes())
    require(receipt['passed'] is True, 'Complete successful build receipt required')
    frozen_path = HERE/'CAPTURE_PROTOCOL.json'
    frozen_pin = metadata(frozen_path)
    frozen = json_bytes(frozen_path.read_bytes())
    require(frozen['core_revision'] == CORE_REVISION and frozen['flags'] == 127
            and frozen['cv_threads'] == 1 and frozen['omp_threads'] == 4
            and frozen['omp_dynamic'] is False and frozen['omp_max_active_levels'] == 1
            and frozen['omp_wait_policy'] == 'PASSIVE' and frozen['expected_matcher_calls'] == 50,
            'Frozen capture execution constants differ')
    sources = receipt['source_pins']
    require(len(sources) == len({item['path'] for item in sources}), 'Duplicate source receipt pin')
    builds = {}
    toolchain = receipt['toolchain']
    snapshot = relative_path(ROOT, receipt['snapshot']['path']).parent
    for item in sources:
        check_file(relative_path(ROOT, item['path']), item, 'before capture source')
    for role in ('capture', 'reference'):
        item = receipt['builds'][role]
        path = relative_path(ROOT, item['path'])
        check_file(path, item, 'bound build manifest')
        built = json_bytes(path.read_bytes())
        require(built['passed'] is True and built['role'] == role, 'Build role/status differs')
        audit_build_dependencies(ROOT, snapshot, toolchain, built,
                                 {p['path'] for p in built['source_files']})
        check_file(relative_path(ROOT, built['executable']['path']), built['executable'], 'before capture executable')
        builds[role] = built
    cases, index_pin = fixed_cases(args.tiny_scenario)
    require(len(cases) == 25, 'Expected all 25 cases')
    output.mkdir(parents=True)
    environment = dict(os.environ, PATH=str(Path(toolchain['opencv_root'])/'build/bin')+os.pathsep+
                       str(Path(toolchain['compiler']['path']).parent)+os.pathsep+os.environ.get('PATH', ''),
                       OMP_WAIT_POLICY='PASSIVE', OMP_NUM_THREADS='4', OMP_DYNAMIC='FALSE', OMP_MAX_ACTIVE_LEVELS='1')
    result = dict(passed=False, started_at=datetime.now(timezone.utc).isoformat(),
                  tiny_scenario=args.tiny_scenario, build_receipt=receipt_pin, verified_cases=[],
                  frozen_capture_protocol=frozen_pin,
                  matcher_calls=0, adapter_invocations=0, performance_measurement=False,
                  limitation='Trace provenance/exact-output equality only; capture overhead excludes all speed claims')
    try:
        for declared in cases:
            case = dict(declared)
            tiny_image = case.pop('image', None)
            image, bank = validate_case(case)
            if image is None:
                image = tiny_image
            check_file(frozen_path, frozen_pin, 'frozen protocol before case')
            require(sha256(ROOT/bank) == frozen['fixtures'][case['dataset']]['bank_sha256'],
                    'Frozen fixture bank bytes differ')
            require(case['matcher_threshold'] == frozen['fixtures'][case['dataset']]['threshold'],
                    'Frozen fixture threshold differs')
            directory = output/case['case_id']
            directory.mkdir()
            config = dict(case, schema_version=1, flags=127, cv_threads=1, omp_threads=4,
                          repo_root=str(ROOT), image=image, bank=bank)
            config_path = directory/'config.json'
            write_new(config_path, config)
            pins = list(sources)+[metadata(ROOT/image, 'image'), metadata(ROOT/bank, 'bank'),
                    metadata(config_path, 'config'), receipt_pin]
            pins += [dict(receipt['builds'][role], role=role+'_build') for role in ('capture', 'reference')]
            if case['dataset'] == 'tless_tiny':
                pins.append(index_pin)
            protocol = dict(schema_version=1, core_revision=CORE_REVISION,
                            capture_kind='exact_pre_consolidation_v11', reference_kind='uninstrumented_same_core',
                            case=case, pins=pins, real_build_closure=dict(
                                source_manifest=receipt['snapshot'], toolchain=toolchain))
            protocol_path = directory/'protocol.json'
            write_new(protocol_path, protocol)
            trace_metadata = {}
            for role in ('capture', 'reference'):
                for item in pins:
                    check_file(relative_path(ROOT, item['path']), item, 'case pin before call')
                for item in [toolchain['compiler'], toolchain['import_library'], *toolchain['runtimes']]:
                    check_file(Path(item['path']), item, 'toolchain before call')
                built = builds[role]
                executable = relative_path(ROOT, built['executable']['path'])
                check_file(executable, built['executable'], 'executable before call')
                trace_path = directory/(role+'.bin')
                command = [str(executable), '--config', str(config_path), '--output', str(trace_path)]
                process = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True)
                result['adapter_invocations'] += 1
                (directory/(role+'_stdout.txt')).write_bytes(process.stdout)
                (directory/(role+'_stderr.txt')).write_bytes(process.stderr)
                native = [json_bytes(line) for line in process.stdout.splitlines() if line.startswith(b'{')]
                require(process.returncode == 0 and len(native) == 1 and native[0]['passed'] is True
                        and native[0]['capture'] is (role == 'capture') and native[0]['matcher_calls'] == 1,
                        'Native capture/reference failed: '+case['case_id']+'/'+role)
                result['matcher_calls'] += native[0]['matcher_calls']
                trace = read_trace(trace_path.read_bytes())
                require((len(trace['input']), len(trace['output'])) ==
                        (native[0]['input_count'], native[0]['output_count']), 'Native count identity differs')
                record = metadata(trace_path, direct=True)
                record.update(input_count=len(trace['input']), output_count=len(trace['output']))
                trace_metadata['trace' if role == 'capture' else 'reference'] = record
                write_new(directory/(role+'_receipt.json'), dict(
                    passed=True, command=command, native=native[0], executable=built['executable'],
                    trace=record, exit_code=process.returncode))
                check_file(executable, built['executable'], 'executable after call')
                for item in [toolchain['compiler'], toolchain['import_library'], *toolchain['runtimes']]:
                    check_file(Path(item['path']), item, 'toolchain after call')
            manifest = dict(schema_version=1, core_revision=CORE_REVISION, protocol_sha256=sha256(protocol_path),
                            case=case, **trace_metadata)
            manifest_path = directory/'manifest.json'
            write_new(manifest_path, manifest)
            verification = audit_real_capture(manifest_path, protocol_path, ROOT)
            write_new(directory/'verification.json', verification)
            result['verified_cases'].append(metadata(manifest_path))
            print(json.dumps(dict(case=case['case_id'], verified=True,
                                  input_count=verification['input_count'], output_count=verification['output_count'])), flush=True)
        require(len(result['verified_cases']) == 25 and result['matcher_calls'] == 50,
                'Incomplete native capture/reference matrix')
        check_file(receipt_path, receipt_pin, 'build receipt after matrix')
        check_file(frozen_path, frozen_pin, 'frozen protocol after matrix')
        result['passed'] = True
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        write_new(output/'capture_result.json', result)
    print(json.dumps(dict(passed=True, cases=25, matcher_calls=50,
                         output=str(output/'capture_result.json'), performance_measurement=False)))


if __name__ == '__main__':
    main()
