"""Native config-scope smoke only: no image decode, template build or matcher."""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from capture_manifest import check_file, json_bytes, relative_path, require, sha256, validate_case
from run_capture import fixed_cases

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    require(args.cpu_slot_granted, 'Parent native scope-smoke CPU slot required')
    output = args.output.resolve()
    require(output.is_relative_to(ROOT) and not output.exists(), 'Scope smoke output must be new')
    receipt_path = args.build_receipt.resolve(strict=True)
    require(receipt_path.is_relative_to(ROOT), 'Build receipt outside repository')
    receipt = json_bytes(receipt_path.read_bytes())
    require(receipt['passed'] is True, 'Successful complete native build required')
    toolchain = receipt['toolchain']
    before = {str(receipt_path): sha256(receipt_path), str(Path(__file__).resolve()): sha256(Path(__file__))}
    for item in receipt['source_pins']:
        path = relative_path(ROOT, item['path'])
        check_file(path, item, 'scope smoke source')
        before[str(path)] = item['sha256']
    for item in [toolchain['compiler'], toolchain['import_library'], *toolchain['runtimes']]:
        check_file(Path(item['path']), item, 'scope smoke toolchain')
        before[item['path']] = item['sha256']
    environment = dict(os.environ, PATH=str(Path(toolchain['opencv_root'])/'build/bin')+os.pathsep+
                       str(Path(toolchain['compiler']['path']).parent)+os.pathsep+os.environ.get('PATH', ''),
                       OMP_WAIT_POLICY='PASSIVE', OMP_NUM_THREADS='4', OMP_DYNAMIC='FALSE', OMP_MAX_ACTIVE_LEVELS='1')
    cases, _ = fixed_cases('quality_actual85')
    configs = []
    for case in (cases[0], cases[8], cases[9]):
        value = dict(case)
        tiny_image = value.pop('image', None)
        image, bank = validate_case(value)
        value.update(schema_version=1, flags=127, cv_threads=1, omp_threads=4,
                     repo_root=str(ROOT), image=image or tiny_image, bank=bank)
        configs.append((value['case_id'], value, True))
    base = configs[2][1]
    for name, changes in (
            ('heldout_split', dict(split='heldout', image='datasets/tless_tiny/heldout_never_opened.png')),
            ('reserved_object', dict(object_id=25)), ('wrong_bank', dict(bank='LED/ku.smd')),
            ('wrong_flags', dict(flags=63))):
        value = copy.deepcopy(base)
        value.update(changes)
        configs.append((name, value, False))
    output.mkdir(parents=True)
    result = dict(passed=False, started_at=datetime.now(timezone.utc).isoformat(), cases=[],
                  image_decodes=0, matcher_calls=0, performance_measurement=False,
                  limitation='Native scope validation only; no template training, matching or accuracy/speed result')
    try:
        for role in ('capture', 'reference'):
            built = relative_path(ROOT, receipt['builds'][role]['path'])
            check_file(built, receipt['builds'][role], 'scope smoke build')
            before[str(built)] = receipt['builds'][role]['sha256']
            build = json_bytes(built.read_bytes())
            executable = relative_path(ROOT, build['executable']['path'])
            check_file(executable, build['executable'], 'scope smoke executable')
            before[str(executable)] = build['executable']['sha256']
            for name, config, valid in configs:
                path = output/(role+'_'+name+'.json')
                with path.open('x', encoding='utf-8') as stream:
                    stream.write(json.dumps(config, indent=2)+'\n')
                command = [str(executable), '--validate-config', str(path)]
                process = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True)
                (output/(role+'_'+name+'_stdout.txt')).write_bytes(process.stdout)
                (output/(role+'_'+name+'_stderr.txt')).write_bytes(process.stderr)
                require(process.returncode == (0 if valid else 1), 'Native scope acceptance differs')
                if valid:
                    native = json_bytes(process.stdout.strip())
                    require(native['passed'] is True and native['scope_validation_only'] is True
                            and native['image_decodes'] == native['matcher_calls'] == 0,
                            'Scope-smoke native receipt differs')
                result['cases'].append(dict(role=role, name=name, expected_valid=valid,
                                           exit_code=process.returncode, command=command))
        require(len(result['cases']) == 14, 'Incomplete two-build native scope matrix')
        for name, expected in before.items():
            require(sha256(Path(name)) == expected, 'Scope smoke source/build/runtime changed')
        result.update(passed=True, before_after_sha256=before)
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        with (output/'scope_smoke.json').open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, cases=14, image_decodes=0, matcher_calls=0,
                         receipt=str(output/'scope_smoke.json'))))


if __name__ == '__main__':
    main()
