"""Required before/after gate for real training or numeric bank planning."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

import freeze_private_sources as frozen
import native_provenance as provenance
import prepare_input_closure as inputs

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_gate(path):
    manifest = json.loads(Path(path).read_text())
    provenance.require(manifest['passed'] is True and manifest['target']=='adapter' and manifest['core_revision'] == frozen.REV and
                       manifest['actual_private_core'] == str(HERE/'private_v11/line2Dup.cpp'), 'Actual frozen private build required')
    pins = list(manifest['project_sources'])+list(manifest['compiler_tools_and_link_libraries'])
    pins += manifest['compiler_runtime_closure']['files']+manifest['executable_runtime_closure']['files']+[manifest['executable']]
    for unit in manifest['dependency_units']:
        pins += unit['dependencies']+[unit['object'], unit['dependency_file']]
    provenance.require(len(manifest['dependency_units']) == 2 and all(c['exit_code'] == 0 for c in manifest['commands']) and len(manifest['commands']) == 5,
                       'Both dependency compiles and link must complete')
    provenance.require([u['source'] for u in manifest['dependency_units']]==[str(HERE/'private_v11/line2Dup.cpp'),str(HERE/'silhouette_eval.cpp')],
                       'Actual adapter/core translation unit pair changed')
    provenance.require(all('-DEMPTY_MASK_POLICY_RED_TEST' not in c['command'] for c in manifest['commands']),
                       'RED fixture must never be used for real training/planning')
    for pin in pins:
        provenance.check_pin(pin)
    provenance.require(Path(manifest['executable']['path']).name == 'silhouette_eval.exe', 'Unexpected native executable')
    return manifest, provenance.file_pin(path)


def bank_freeze(native, run, build_pin, complete):
    summary_file = native/'training_summary.json'
    summary = json.loads(summary_file.read_text()) if summary_file.exists() else None
    members = [provenance.file_pin(path) for path in sorted(native.rglob('*')) if path.is_file() and path.name != '.gitignore']
    result = dict(stage='all_six_binary_empty_mask_training', native_exit_zero=complete,
                  comparison_feasible=bool(complete and summary and summary['comparison_feasible'] == 1),
                  training_attempts_complete=bool(summary and summary['training_attempts_complete'] == 1),
                  summary=summary, files=members, build_manifest=build_pin,
                  input_closure=provenance.file_pin(HERE/'INPUT_CLOSURE.json'),
                  protocol=provenance.file_pin(HERE/'PROTOCOL.json'), matcher_calls=0,
                  missing_objects_or_poses_are_not_negatives=True)
    (run/'BANK_FREEZE.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['train', 'plan'], required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--build-manifest', required=True, type=Path)
    parser.add_argument('--training-run', type=Path)
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    provenance.require(args.cpu_slot_granted, 'Await coordinated actual-stage CPU slot')
    run = args.output.resolve()
    provenance.require(run.is_relative_to(HERE) and not run.exists(), 'Run directory must be fresh inside experiment')
    run.mkdir();native = run/'native'
    native_exit, post_valid = None, False
    script_pins = [provenance.file_pin(HERE/name) for name in ('run_stage.py', 'native_provenance.py', 'prepare_input_closure.py')]
    try:
        build, build_pin = build_gate(args.build_manifest)
        closure_pin = provenance.file_pin(HERE/'INPUT_CLOSURE.json')
        before = inputs.verify('training' if args.mode == 'train' else None)
        (run/'verified_before.json').write_text(json.dumps(before, indent=2)+'\n')
        frozen_manifest = json.loads((HERE/'PRIVATE_SOURCE_FREEZE.json').read_text())
        frozen.verify(HERE/'private_v11', frozen_manifest)
        command = [build['executable']['path'], '--mode', args.mode, '--output', str(native), '--closure', str(HERE/'INPUT_CLOSURE.json')]
        prior = None
        if args.mode == 'plan':
            provenance.require(args.training_run is not None, 'Plan requires a complete frozen training run')
            training_run = args.training_run.resolve(strict=True)
            prior = provenance.file_pin(training_run/'BANK_FREEZE.json')
            bank = json.loads((training_run/'BANK_FREEZE.json').read_text())
            provenance.require(bank['comparison_feasible'] is True and bank['training_attempts_complete'] is True and bank['native_exit_zero'] is True,
                               'Planning an incomplete/zero-success/exception bank is forbidden')
            for pin in bank['files']:
                provenance.check_pin(pin)
            command += ['--training', str(training_run/'native')]
        env = dict(os.environ)
        env['PATH'] = str(Path(build['compiler']).parent)+';'+str(Path(build['opencv'])/'build/bin')+';'+env.get('PATH', '')
        execution = dict(command=command, build_manifest=build_pin, input_closure=closure_pin,
                         native_exit_code=None, mode=args.mode, training_run=prior, script_pins=script_pins,
                         runtime_path_prefix=[str(Path(build['compiler']).parent), str(Path(build['opencv'])/'build/bin')])
        (run/'execution_provenance.json').write_text(json.dumps(execution, indent=2)+'\n')
        # Output is streamed to disk. The fixed native checkpoints occur after
        # calls/poses; no single native call is claimed to be interruptible.
        with (run/'native.stdout').open('wb') as stdout,(run/'native.stderr').open('wb') as stderr:
            process = subprocess.run(command, cwd=HERE, env=env, stdout=stdout, stderr=stderr)
        native_exit = process.returncode
        execution['native_exit_code'] = native_exit
        (run/'execution_provenance.json').write_text(json.dumps(execution, indent=2)+'\n')
        after = inputs.verify('training' if args.mode == 'train' else None)
        provenance.require(before == after, 'Input verification scope changed during stage')
        build_gate(args.build_manifest);provenance.check_pin(build_pin);provenance.check_pin(closure_pin)
        for pin in script_pins:
            provenance.check_pin(pin)
        if prior:
            provenance.check_pin(prior)
            for pin in bank['files']:
                provenance.check_pin(pin)
        (run/'verified_after.json').write_text(json.dumps(after, indent=2)+'\n');post_valid = True
        if args.mode == 'train':
            bank_freeze(native, run, build_pin, native_exit == 0)
        else:
            (run/'COMMON_PADDING_FREEZE.json').write_text(json.dumps(dict(passed=native_exit == 0, bank_freeze=prior,
                build_manifest=build_pin, files=[provenance.file_pin(p) for p in sorted(native.iterdir()) if p.is_file() and p.name != '.gitignore'],
                development_images_decoded=0, matcher_calls=0), indent=2)+'\n')
        provenance.require(native_exit == 0, 'Native stage incomplete; exit '+str(native_exit)+' and all failure evidence preserved')
        (run/'stage_complete.json').write_text(json.dumps(dict(passed=True, mode=args.mode, post_verification_passed=True, matcher_calls=0), indent=2)+'\n')
        print(json.dumps(dict(passed=True, mode=args.mode, matcher_calls=0)))
    except Exception as error:
        (run/'failure.json').write_text(json.dumps(dict(incomplete=True, reason=str(error), native_exit_code=native_exit,
            post_verification_passed=post_valid, missing_frames_are_not_negatives=True), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
