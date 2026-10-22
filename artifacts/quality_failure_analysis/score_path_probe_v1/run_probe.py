"""One-shot, separately gated runner for the score-path probe."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import time

from probe_contract import check, pin, require, reserve
import runner_gates

HERE = Path(__file__).resolve().parent
CORE_REVISION = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
INPUT_SHA = '353615a753a0be27a2665997488301259fe99989858068895870d16fe32de91c'
ROOT = HERE.parents[2]
EXPERIMENT = ROOT/'artifacts/silhouette_empty_mask_experiment'
OBJECTS = {1, 2, 5, 8, 12, 17}
SCENES = {1, 4, 6, 7, 8, 10, 12, 13}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def check_manifest(manifest_path, red):
    manifest_path = Path(manifest_path).resolve(strict=True)
    require(manifest_path.is_relative_to(HERE), 'Build manifest must belong to this probe')
    manifest = read(manifest_path)
    require(manifest.get('passed') is True and manifest.get('target') == 'score_path_probe_phase1' and
            manifest.get('core_revision') == CORE_REVISION and manifest.get('red_negative_control') is red,
            'Wrong or incomplete score probe build manifest')
    require(Path(manifest['executable']['path']).resolve() == manifest_path.parent/'score_probe.exe',
            'Unexpected executable location')
    units = manifest.get('dependency_units', [])
    commands = manifest.get('commands', [])
    require(len(units) == 1 and Path(units[0]['source']).resolve() == HERE/'probe.cpp' and
            Path(units[0]['included_private_core']).resolve() == EXPERIMENT/'private_v11/line2Dup.cpp',
            'Actual single-TU source/core differs')
    require(len(commands) == 3 and [value['label'] for value in commands] == ['dependency_before', 'compile', 'link'] and
            all(value['exit_code'] == 0 for value in commands), 'Actual build command sequence differs')
    for value in commands[:2]:
        require(('-DSCORE_PROBE_ORACLE_RED' in value['command']) is red,
                'Build RED macro provenance differs')
    values = list(manifest.get('project_sources', [])) + list(manifest.get('compiler_tools_and_link_libraries', []))
    values += list(manifest.get('compiler_runtime_closure', {}).get('files', []))
    values += list(manifest.get('executable_runtime_closure', {}).get('files', []))
    values.append(manifest['executable'])
    for unit in manifest.get('dependency_units', []):
        require(Path(unit['source']).name == 'probe.cpp' and
                Path(unit['included_private_core']).name == 'line2Dup.cpp', 'Unexpected score probe dependency unit')
        values.extend(unit.get('dependencies', []))
        values.extend([unit['object'], unit['dependency_file']])
    require(values, 'Empty score probe build closure')
    for value in values:
        check(value)
    return manifest, pin(manifest_path)


def check_plan(plan_path):
    plan_path = Path(plan_path).resolve(strict=True)
    require(plan_path == HERE/'PROBE_INPUTS_V1.json', 'Only the fixed contained input plan may be opened')
    plan_pin = pin(plan_path)
    require(plan_pin['sha256'] == INPUT_SHA, 'Input plan is not the exact prepared numeric allowlist')
    plan = read(plan_path)
    require(plan.get('version') == 'score_path_probe_v1' and plan.get('stage') == 'phase1' and
            plan.get('rgb_tp_identities') == 215 and plan.get('object_frames') == 213 and
            plan.get('image_frames') == 175 and plan.get('full_class_search_replays') == 426 and
            plan.get('public_detector_match_calls') == 0 and plan.get('phase2_authorized') is False,
            'Wrong score probe input plan scope')
    require(len(plan.get('frames', [])) == 213 and len(plan.get('permitted_image_pins', [])) == 175,
            'Input plan member count differs')
    for value in plan.get('numeric_pins', []) + [plan['audit']]:
        check(value)
    image_pins = plan['permitted_image_pins']
    image_paths = {str(Path(value['path']).resolve()) for value in image_pins}
    require(len(image_paths) == 175, 'Duplicate permitted image path')
    frame_paths = set()
    for frame in plan['frames']:
        obj, scene = int(frame['object_id']), int(frame['scene'])
        require(obj in OBJECTS and scene in SCENES and int(frame['image']) >= 0, 'Frame outside fixed image scope')
        relative = Path(frame['rgb_relative'])
        require(not relative.is_absolute() and '..' not in relative.parts and
                len(relative.parts) >= 2 and relative.parts[0] == 'test_primesense' and
                relative.parts[1] == f'{scene:06d}', 'Unsafe or held-out image relative path')
        image_path = str(Path(frame['image_path']).resolve())
        require(image_path in image_paths, 'Frame image is absent from permitted pin closure')
        frame_paths.add(image_path)
    require(frame_paths == image_paths, 'Permitted image closure contains an unused image')
    return plan, plan_pin


def verify_images(plan):
    """Validate the allowlist before opening any image bytes, then hash exactly it."""
    values = plan['permitted_image_pins']
    paths = [Path(value['path']).resolve() for value in values]
    require(len(paths) == len(set(paths)) == 175, 'Image allowlist cardinality differs')
    actual = []
    for value, path in zip(values, paths):
        require(path.is_file(), 'Permitted image is missing: ' + str(path))
        observed = pin(path)
        require(observed == value, 'Permitted image bytes changed: '+str(path))
        actual.append(observed)
    return actual


def verify_numeric(plan):
    for value in plan['numeric_pins'] + [plan['audit']]:
        check(value)


def native_files(native):
    require(native.is_dir(), 'Native output directory missing')
    files = [path for path in sorted(native.rglob('*')) if path.is_file()]
    require(all(path.name == '.gitignore' or path.suffix.lower() in ('.csv', '.gz', '.json') for path in files),
            'Native stage wrote output outside the numeric-only member types')
    return [pin(path) for path in files]


def stage_gate(run, expected_red, input_pin, expected_build=None):
    run = Path(run).resolve(strict=True)
    require(run.is_relative_to(HERE), 'Selftest run must belong to this probe')
    path = run/'PROBE_STAGE_FREEZE.json'
    manifest = read(path)
    require(manifest.get('completed') is True and manifest.get('stage') == 'selftest' and
            manifest.get('expected_native_failure') is expected_red and manifest.get('input_plan') == input_pin and
            manifest.get('actual_full_class_search_replays') == 0 and manifest.get('image_hash_operations') == 0,
            'Required synthetic selftest completion receipt differs')
    if expected_build is not None:
        require(manifest['build_manifest'] == expected_build, 'GREEN selftest is not bound to this build')
    inherited = [manifest['negative_control']] if manifest.get('negative_control') else []
    for value in manifest['execution_files']+[manifest['build_manifest'], manifest['input_plan'], manifest['reservation']]+inherited:
        check(value)
    runner_gates.verify_output(run/'native', manifest['files'])
    expected = {Path(value['path']).resolve() for value in manifest['execution_files']} | {path}
    actual = {value.resolve() for value in run.iterdir() if value.is_file()}
    require(actual == expected, 'Selftest execution output member set changed')
    return manifest, pin(path)


def run_native(command, environment, run):
    """One process, file-streamed logs, and Windows RSS/output/time watchdog."""
    class MemoryCounters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong)]+[
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
                'PagefileUsage', 'PeakPagefileUsage')]
    require(os.name == 'nt', 'This fixed native runner requires Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(MemoryCounters), ctypes.c_ulong]
    maximum_rss = 0
    maximum_output = 0
    stop_reason = None
    began = time.monotonic()
    with (run/'native.stdout').open('wb') as stdout, (run/'native.stderr').open('wb') as stderr:
        with subprocess.Popen(command, cwd=HERE, env=environment, stdout=stdout, stderr=stderr) as process:
            handle = kernel.OpenProcess(0x1000 | 0x0010, 0, process.pid)
            if not handle:
                process.kill()
                process.wait()
                raise ValueError('Cannot open native process for RSS watchdog')
            try:
                while process.poll() is None:
                    counters = MemoryCounters(); counters.cb = ctypes.sizeof(counters)
                    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                        stop_reason = 'Native RSS watchdog query failed'
                    maximum_rss = max(maximum_rss, counters.PeakWorkingSetSize)
                    output_bytes = sum(path.stat().st_size for path in run.rglob('*') if path.is_file())
                    maximum_output = max(maximum_output, output_bytes)
                    if maximum_rss > 1610612736:
                        stop_reason = 'Native peak RSS exceeded 1.5 GiB'
                    if maximum_output > 1073741824:
                        stop_reason = 'Complete run output exceeded one GiB'
                    if time.monotonic()-began > 3600:
                        stop_reason = 'Native stage exceeded 60 minutes'
                    if stop_reason:
                        process.kill()
                        break
                    time.sleep(.25)
                exit_code = process.wait()
            finally:
                kernel.CloseHandle(handle)
    return dict(native_exit_code=exit_code, elapsed_seconds=time.monotonic()-began,
                maximum_observed_rss_bytes=maximum_rss, maximum_observed_output_bytes=maximum_output,
                stop_reason=stop_reason, observation_interval_seconds=.25,
                limitation='Sampled process watchdog; native checks run at every class replay and streamed CSV flush')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('selftest', 'phase1'), required=True)
    parser.add_argument('--build-manifest', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--selftest-run', type=Path)
    parser.add_argument('--negative-control-run', type=Path)
    parser.add_argument('--red-negative-control', action='store_true')
    parser.add_argument('--cpu-slot-granted', action='store_true')
    args = parser.parse_args()
    require(args.cpu_slot_granted, 'Await coordinated native probe CPU slot')
    require(not args.red_negative_control or args.mode == 'selftest', 'RED is allowed only for synthetic selftest')
    run = args.output.resolve()
    require(run.is_relative_to(HERE) and not run.exists() and run.parent.is_dir(), 'Fresh contained probe run required')
    run.mkdir()
    native = run/'native'
    reservation_pin = None
    native_exit = None
    try:
        build, build_pin = check_manifest(args.build_manifest, args.red_negative_control)
        plan, plan_pin = check_plan(args.plan)
        red_pin = None
        if args.mode == 'phase1':
            require(not args.red_negative_control, 'Phase1 cannot use the RED build')
            require(args.selftest_run is not None, 'Passed GREEN selftest is required')
            _, selftest_pin = stage_gate(args.selftest_run, False, plan_pin, build_pin)
            require(args.negative_control_run is None, 'Phase1 consumes the bound GREEN selftest receipt')
        else:
            require(args.selftest_run is None, 'Selftest cannot depend on a prior stage')
            selftest_pin = None
            if args.red_negative_control:
                require(args.negative_control_run is None, 'RED negative control cannot depend on a prior run')
            else:
                require(args.negative_control_run is not None, 'GREEN requires the deliberate RED score failure first')
                red_stage, red_pin = stage_gate(args.negative_control_run, True, plan_pin)
                red_build, _ = check_manifest(red_stage['build_manifest']['path'], True)
                require(red_build['project_sources'] == build['project_sources'] and
                        red_build['compiler_tools_and_link_libraries'] == build['compiler_tools_and_link_libraries'],
                        'RED/GREEN source and compiler/library closures differ')
        reservation_stage = 'selftest_red' if args.red_negative_control else 'selftest_green' if args.mode == 'selftest' else 'phase1'
        reservation_path = reserve(HERE/'probe_stage_reservations', reservation_stage, run,
                                   dict(build=build_pin, input_plan=plan_pin, selftest=selftest_pin, negative_control=red_pin))
        reservation_pin = pin(reservation_path)
        verify_numeric(plan)
        image_before = image_after = []
        if args.mode == 'phase1':
            image_before = verify_images(plan)
        execution = dict(mode=args.mode, command=[build['executable']['path'], '--mode', args.mode,
                         '--output', str(native), '--plan', plan_pin['path']], build_manifest=build_pin,
                         input_plan=plan_pin, selftest=selftest_pin, reservation=reservation_pin,
                         negative_control=red_pin,
                         maximum_full_class_search_replays=0 if args.mode == 'selftest' else 426,
                         public_detector_match_calls=0, native_exit_code=None,
                         runtime_path_prefix=[str(Path(build['compiler']).parent), str(Path(build['opencv'])/'build/bin')],
                         started_utc=time.time())
        (run/'execution_provenance.json').write_text(json.dumps(execution, indent=2)+'\n', encoding='utf-8')
        environment = dict(os.environ)
        compiler = Path(build['compiler']).resolve()
        opencv = Path(build['opencv']).resolve()
        environment['PATH'] = str(compiler.parent)+';'+str(opencv/'build/bin')+';'+environment.get('PATH', '')
        watchdog = run_native(execution['command'], environment, run)
        native_exit = watchdog['native_exit_code']
        (run/'watchdog.json').write_text(json.dumps(watchdog, indent=2)+'\n')
        execution['native_exit_code'] = native_exit
        execution['finished_utc'] = time.time()
        (run/'execution_provenance.json').write_text(json.dumps(execution, indent=2)+'\n', encoding='utf-8')
        verify_numeric(plan)
        if args.mode == 'phase1':
            image_after = verify_images(plan)
            require(image_before == image_after, 'Permitted image bytes changed during native stage')
        _, latest_build_pin = check_manifest(args.build_manifest, args.red_negative_control)
        require(latest_build_pin == build_pin, 'Build manifest changed during native stage')
        _, latest_plan_pin = check_plan(args.plan)
        require(latest_plan_pin == plan_pin, 'Input plan changed during native stage')
        check(reservation_pin)
        if selftest_pin:
            stage_gate(args.selftest_run, False, plan_pin, build_pin)
            check(selftest_pin)
        if red_pin:
            stage_gate(args.negative_control_run, True, plan_pin)
            check(red_pin)
        summary_path = native/('selftest_result.json' if args.mode == 'selftest' else 'stage_summary.json')
        summary = read(summary_path) if summary_path.is_file() else None
        failure_path = native/'failure.json'
        failure = read(failure_path) if failure_path.is_file() else None
        require(watchdog['stop_reason'] is None, 'Native watchdog stopped stage: '+str(watchdog['stop_reason']))
        gate = runner_gates.validate_native(args.mode, args.red_negative_control, native_exit, summary, failure)
        files = native_files(native)
        runner_gates.verify_output(native, files)
        execution_files = [pin(path) for path in sorted(run.iterdir()) if path.is_file()]
        require(sum(value['bytes'] for value in files+execution_files) <= 1073741824, 'Complete numeric run exceeds one GiB')
        freeze = dict(stage=args.mode, completed=True, native_exit_code=native_exit,
                      expected_native_failure=gate['expected_native_failure'],
                      actual_full_class_search_replays=gate['actual_full_class_search_replays'],
                      build_manifest=build_pin, input_plan=plan_pin, selftest=selftest_pin,
                      negative_control=red_pin,
                      reservation=reservation_pin, files=files, execution_files=execution_files, summary=summary,
                      image_before=image_before, image_after=image_after,
                      image_hash_operations=0 if args.mode == 'selftest' else 350,
                      unique_dataset_image_files_opened=0 if args.mode == 'selftest' else 175,
                      partial_results_are_not_negatives=False, phase2_started=False)
        (run/'PROBE_STAGE_FREEZE.json').write_text(json.dumps(freeze, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(dict(passed=True, stage=args.mode, red_negative_control=args.red_negative_control,
                              full_class_search_replays=gate['actual_full_class_search_replays'])))
    except Exception as error:
        record = dict(incomplete=True, stage=args.mode, reason=str(error), native_exit_code=native_exit,
                      build_manifest=pin(args.build_manifest) if args.build_manifest.exists() else None,
                      input_plan=pin(args.plan) if args.plan.exists() else None, reservation=reservation_pin,
                      partial_results_are_not_negatives=True, phase2_started=False)
        (run/'failure.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
