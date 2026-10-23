"""Bind completed component evidence and prepare an explicit public selection.

Reads retained source/receipt/numeric evidence only. Does not reopen original
images, raw candidates, banks or GT; does not run a matcher or mutate Git.
All actual pixel/attempt replay successors remain outside this checkpoint.
"""
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = '7214a3e7a8ff9f8599aee7cd9e676b0f83be81a0'
PRODUCTION = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
NATIVE_RUNS = (
    'native_candidate_red_v1', 'native_candidate_green_v1',
    'native_candidate_oracle_green_v1',
    'native_pixel_operator_red_v1', 'native_pixel_operator_green_v1',
    'native_compiled_scene_red_v2', 'native_compiled_scene_green_v2',
    'native_compiled_scene_benchmark_v2',
    'native_c0_replay_geometry_red_v1', 'native_c0_replay_geometry_green_v1',
)
C0_RUNS = (
    'c0_inventory_whitelist_green_v1', 'c0_inventory_whitelist_green_v2',
    'c0_inventory_whitelist_green_v3', 'c0_inventory_estimate_v1',
    'c0_inventory_windows_red_v2', 'c0_inventory_windows_green_v2',
    'c0_inventory_estimate_v2', 'c0_inventory_hash_v2',
    'c0_numeric_binding_red_v1', 'c0_numeric_binding_green_v1',
    'c0_raw_binding_green_v1',
)
SOURCES = (
    '.gitattributes',
    'native_candidate_compatibility.hpp', 'native_candidate_compatibility_test.cpp',
    'NATIVE_CANDIDATE_DECISIONS_V1.json', 'run_native_candidate_checks_v1.py',
    'native_candidate_batch_v1.cpp', 'NATIVE_CANDIDATE_BATCH_PROTOCOL_V1.json',
    'native_candidate_oracle_fixtures_v1.py', 'run_native_candidate_oracle_checks_v1.py',
    'NATIVE_CANDIDATE_RESULTS_V1.md', 'STATIC_NATIVE_CANDIDATE_REVIEW_V1.md',
    'native_pixel_operator.hpp', 'native_pixel_operator.cpp', 'native_pixel_operator_test.cpp',
    'NATIVE_PIXEL_OPERATOR_DECISIONS_V1.json', 'run_native_pixel_operator_checks_v1.py',
    'NATIVE_PIXEL_OPERATOR_RESULTS_V1.md', 'STATIC_NATIVE_PIXEL_OPERATOR_FINAL_REVIEW_V1.md',
    'native_candidate_compiled_scene_v2.hpp', 'native_candidate_compiled_scene_v2_test.cpp',
    'NATIVE_COMPILED_SCENE_DECISIONS_V2.json', 'run_native_compiled_scene_checks_v2.py',
    'native_compiled_scene_benchmark_v2.cpp', 'run_native_compiled_scene_benchmark_v2.py',
    'NATIVE_COMPILED_SCENE_RESULTS_V2.md', 'NATIVE_COMPILED_SCENE_BENCHMARK_RESULTS_V2.md',
    'STATIC_NATIVE_COMPILED_SCENE_RED_REVIEW_V2.md',
    'STATIC_NATIVE_COMPILED_SCENE_FINAL_REVIEW_V2.md',
    'STATIC_NATIVE_COMPILED_SCENE_REVIEW_V2.md', 'STATIC_NATIVE_BENCHMARK_METADATA_REVIEW_V2.md',
    'native_c0_replay_geometry.hpp', 'native_c0_replay_geometry_test.cpp',
    'NATIVE_C0_REPLAY_GEOMETRY_DECISIONS_V1.json', 'run_native_c0_replay_geometry_checks_v1.py',
    'NATIVE_C0_REPLAY_GEOMETRY_RESULTS_V1.md', 'STATIC_C0_REPLAY_GEOMETRY_RED_REVIEW_V1.md',
    'prepare_c0_payload_inventory_v1.py', 'prepare_c0_payload_inventory_v2.py',
    'INPUT_INVENTORY_DECISIONS_V1.json', 'INPUT_INVENTORY_DECISIONS_V2.json',
    'run_c0_inventory_checks_v1.py', 'run_c0_inventory_checks_v2.py',
    'run_c0_inventory_whitelist_checks_v2.py', 'test_c0_inventory_whitelist_v1.py',
    'test_c0_inventory_whitelist_v2.py', 'test_c0_inventory_windows_stat_v2.py',
    'C0_PAYLOAD_INVENTORY_RESULTS_V2.md', 'c0_numeric_binding_v1.py',
    'test_c0_numeric_binding_v1.py', 'DECISIONS_c0_numeric_binding_v1.json',
    'run_c0_numeric_binding_v1.py', 'prepare_c0_raw_binding_v1.py', 'run_c0_raw_binding_v1.py',
    'C0_RAW_BINDING_RESULTS_V1.md', 'C0_RAW_BINDING_ACCEPTANCE_V1.json',
    'NATIVE_COMPONENT_CHECKPOINT_V35.md', 'prepare_native_candidate_checkpoint_v35.py',
    'STATIC_CHECKPOINT_REVIEW_V35.md', 'V35_RETAINED_EVIDENCE_MANIFEST.json',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def pin(path, relative=False):
    require(path.is_file() and not path.is_symlink(), 'Missing/linked selected file: ' + str(path))
    data = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix() if relative else str(path),
                bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def check_pin(row):
    require(pin(Path(row['path'])) == row, 'Current verified source/evidence differs: ' + row['path'])


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def main():
    require(sys.argv[1:] in ([], ['--check']), 'usage: prepare_native_candidate_checkpoint_v35.py [--check]')
    require(git('rev-parse', 'HEAD').decode().strip() == BASE, 'Unexpected checkpoint parent')
    require(not git('diff', '--cached', '--name-only'), 'Unrelated staged files present')
    receipts = {name: read(HERE / name / 'receipt.json') for name in NATIVE_RUNS + C0_RUNS}
    require(all(row['passed'] is True for name, row in receipts.items()
                if name != 'c0_inventory_estimate_v1'), 'A required actual run did not pass')
    require(receipts['c0_inventory_estimate_v1']['passed'] is False,
            'Historical failed V1 estimate was rewritten')
    require(receipts['c0_inventory_windows_red_v2']['guard']['exit_code'] == 1
            and receipts['c0_inventory_windows_green_v2']['guard']['passed'] is True,
            'Windows timestamp actual RED/GREEN differs')
    for name in ('c0_inventory_windows_green_v2', 'c0_inventory_estimate_v2',
                 'c0_inventory_hash_v2', 'c0_numeric_binding_green_v1'):
        receipt = receipts[name]
        require(receipt['sources_stable'] and receipt['source_archive_equal'],
                'Final C0 source stability failed')
        for row in receipt['source_pins']:
            check_pin(row)
    for row in receipts['c0_inventory_whitelist_green_v3']['source_pins_after']:
        check_pin(row)
    require(receipts['c0_inventory_whitelist_green_v3']['summary']['tests_run'] == 9,
            'Final whitelist test count differs')
    for name, count in (('c0_numeric_binding_red_v1', 35), ('c0_numeric_binding_green_v1', 0)):
        require(receipts[name]['expected_test_methods'] == 28
                and receipts[name]['observed_failure_count'] == count,
                'C0 numeric fixed-test phase differs')
    for prefix, version, test in (
            ('c0_inventory_windows', 'v2', 'test_c0_inventory_windows_stat_v2.py'),
            ('c0_numeric_binding', 'v1', 'test_c0_numeric_binding_v1.py')):
        for phase in ('red', 'green'):
            require((HERE / (prefix + '_' + phase + '_' + version) / 'source_archive' / test).read_bytes()
                    == (HERE / test).read_bytes(), 'Fixed C0 regression test changed')
    pairs = (
        ('native_candidate', 'v1', 35, 307, 204, 611, 'native_candidate_compatibility_test.cpp'),
        ('native_pixel_operator', 'v1', 22, 970, 338, 8452, 'native_pixel_operator_test.cpp'),
        ('native_compiled_scene', 'v2', 28, 8556, 8437, 8557, 'native_candidate_compiled_scene_v2_test.cpp'),
        ('native_c0_replay_geometry', 'v1', 7, 35, 24, 4660, 'native_c0_replay_geometry_test.cpp'),
    )
    for prefix, version, tests, red_checks, failures, green_checks, test in pairs:
        red_name, green_name = (prefix + '_' + phase + '_' + version for phase in ('red', 'green'))
        red, green = receipts[red_name], receipts[green_name]
        require(red['summary'] == dict(tests=tests, checks=red_checks, failures=failures, errors=0),
                'RED summary differs: ' + prefix)
        require(green['summary'] == dict(tests=tests, checks=green_checks, failures=0, errors=0),
                'GREEN summary differs: ' + prefix)
        require(red['test_guard']['exit_code'] == 1 and green['test_guard']['passed'] is True,
                'Actual RED/GREEN execution differs')
        for name in (red_name, green_name):
            require((HERE / name / 'source' / test).read_bytes() == (HERE / test).read_bytes(),
                    'Fixed test changed: ' + test)
        for row in green['source_pins_after']:
            check_pin(row)
    oracle = receipts['native_candidate_oracle_green_v1']
    require(oracle['sources_stable'] and oracle['audit']['passed']
            and oracle['audit']['comparisons'] == 6144 and oracle['audit']['zero_skips']
            and oracle['audit']['domain_counts']['chain_brute_force_comparisons'] == 6144
            and oracle['optimized_python_expectations_used'] is False
            and oracle['work_counters_independently_verified'] is False,
            'Complete independent candidate oracle differs')
    expected = HERE / 'native_candidate_oracle_green_v1/fixtures/expected.jsonl'
    response = HERE / 'native_candidate_oracle_green_v1/native_execution/stdout.txt'
    require(expected.read_bytes() == response.read_bytes(), 'Full independent native candidate records differ')
    for row in oracle['fixture_pins'] + read(HERE / 'native_candidate_oracle_green_v1/invocation.json')['source_pins']:
        check_pin(row)
    benchmark = receipts['native_compiled_scene_benchmark_v2']
    benchmark_rows = benchmark['measurements']
    require(len(benchmark_rows) == 6 and benchmark['benchmark_guard']['passed'], 'Incomplete paired benchmark')
    for index, row in enumerate(benchmark_rows):
        require(row['round'] == index and row['order'] == ('baseline_first' if index % 2 == 0 else 'cached_first'),
                'Paired execution order differs')
        for key, multiplier in (('baseline', 256), ('cached', 1)):
            counters = row[key]
            require(counters['index_pairs'] == multiplier and counters['maps_constructed'] == 2 * multiplier
                    and counters['membership_rows'] == 5120 * multiplier
                    and counters['members'] == 6144 * multiplier and counters['chains'] == 2048 * multiplier,
                    'Actual scene index operations differ')
    for row in benchmark['source_pins_after']:
        check_pin(row)
    inventory = HERE / 'c0_inventory_hash_v2_payload/inventory.json'
    inventory_pin = pin(inventory)
    require((inventory_pin['bytes'], inventory_pin['sha256']) ==
            (6349773, '59edd80d4c6083286d14044326a665daa41ce999ef11414fb5c9da9cb9ab2ec4'),
            'Accepted hash inventory changed')
    binding = read(HERE / 'c0_raw_binding_green_v1_payload/result.json')
    require(binding['passed'] and binding['raw_rows'] == 457279
            and binding['object_frame_combinations'] == 2400 and binding['zero_raw_combinations'] == 390
            and binding['selected_rows'] == 42327 and binding['original_allGT_identities_exact']
            and binding['original_allGT_identity_count'] == 215
            and [binding['allGT'][key] for key in ('tp', 'fp', 'fn', 'gt')] == [215,42112,185,400]
            and binding['payload_unique_files_read'] == binding['payload_end_hash_rechecks'] == 4809
            and binding['geometry'] == dict(width=848,height=848,padding_ltrb=[64,64,64,244])
            and binding['gt_projection_independently_reconstructed'] is False
            and binding['quality_improvement_claim'] is False and binding['performance_claim'] is False,
            'Complete C0 numeric positive control differs')
    for row in binding['source_pins']:
        check_pin(row)
    binding_acceptance = read(HERE / 'C0_RAW_BINDING_ACCEPTANCE_V1.json')
    require(binding_acceptance['passed'] is True, 'C0 binding acceptance missing')
    for row in [binding_acceptance['mapping_red']['receipt'],
                binding_acceptance['mapping_green']['receipt']] + binding_acceptance['evidence']:
        path = HERE / row['path']
        require(path.resolve().is_relative_to(HERE), 'C0 evidence escapes experiment')
        observed = pin(path)
        require((observed['bytes'], observed['sha256']) == (row['bytes'], row['sha256']),
                'Accepted C0 numeric evidence changed')
    production = []
    for name in git('ls-tree', '-r', '--name-only', PRODUCTION).decode().splitlines():
        if Path(name).parent == Path('.') and Path(name).name.startswith('line2Dup'):
            path = ROOT / name
            require(path.read_bytes() == git('show', PRODUCTION + ':' + name), 'Production source changed')
            production.append(pin(path))
    require(len(production) == 7, 'Authoritative production set differs')
    acceptance = HERE / 'NATIVE_COMPONENT_ACCEPTANCE_V35.json'
    selected = [HERE / name for name in SOURCES] + [ROOT / 'docs/optimization_versions.md']
    allowed = {'.py', '.hpp', '.h', '.hxx', '.cpp', '.json', '.jsonl', '.txt', '.md'}
    runs = NATIVE_RUNS + C0_RUNS + (
        'c0_inventory_estimate_v2_payload', 'c0_inventory_hash_v2_payload', 'c0_raw_binding_green_v1_payload')
    members_path = HERE / 'V35_RETAINED_EVIDENCE_MANIFEST.json'
    members_pin = pin(members_path)
    require((members_pin['bytes'], members_pin['sha256']) ==
            (72645, '9602d4a9b7139f7a1fe9751e4685be10d289f4115324b1b8fddc5b09a9427d4b'),
            'Frozen retained evidence manifest changed')
    members = read(members_path)
    require(members['schema'] == 'v35_retained_nonbuild_members_v1'
            and set(members['runs']) == set(runs), 'Retained evidence scope differs')
    for run in runs:
        directory = HERE / run
        require(directory.is_dir() and not directory.is_symlink(), 'Missing/linked evidence directory')
        actual = set()
        for path in sorted(directory.rglob('*')):
            require(not path.is_symlink(), 'Linked evidence member')
            if not path.is_file() or 'build' in path.relative_to(directory).parts:
                continue
            require(path.suffix in allowed, 'Unexpected public run suffix: ' + str(path))
            actual.add(path.relative_to(ROOT).as_posix())
        expected_rows = members['runs'][run]
        expected_names = {row['path'] for row in expected_rows}
        require(len(expected_names) == len(expected_rows) and actual == expected_names,
                'Retained evidence directory members changed: ' + run)
        for row in expected_rows:
            path = ROOT / row['path']
            require(path.resolve().is_relative_to(directory), 'Member escapes declared run')
            require(pin(path, relative=True) == row, 'Retained evidence bytes changed')
            selected.append(path)
    selected = sorted(set(selected), key=lambda path: path.relative_to(ROOT).as_posix())
    selection_rows = [pin(path, relative=True) for path in selected]
    if sys.argv[1:] == ['--check']:
        print(json.dumps(dict(check_only=True, passed=True, file_count_before_acceptance=len(selection_rows),
                              selected_bytes_before_acceptance=sum(row['bytes'] for row in selection_rows))))
        return
    write_new(acceptance, dict(schema='ordered_contour_native_component_acceptance_v35',
        component_correctness_accepted=True, production_baseline=PRODUCTION,
        checks=[pin(HERE / name / 'receipt.json') for name in NATIVE_RUNS + C0_RUNS],
        fixed_tests_red_green=True, independent_candidate_comparisons=6144,
        compiled_scene_full_score_and_work_parity_comparisons=6144,
        benchmark_complete_comparisons=1536, benchmark_scope='One supplied-label 256x256 scene; 6 alternating rounds of 256 queries',
        paired_cached_over_baseline_total_median=statistics.median(
            row['cached']['total_ms'] / row['baseline']['total_ms'] for row in benchmark_rows),
        benchmark_timing_includes_preparation=True, timed_baseline_is_uninstrumented_v1=True,
        original_C0_numeric_positive_control=True, original_allGT_identities_exact=215,
        original_raw_rows=457279, original_zero_combinations=390,
        original_GT_independently_reconstructed=False,
        production_files_unchanged=production, real_image_new_verifier_quality_tested=False,
        real_image_end_to_end_speed_improvement=False, real_pixel_attempt_replay_complete=False,
        heldout_remains_sealed=True, production_promotion=False))
    selected.append(acceptance)
    selected = sorted(set(selected), key=lambda path: path.relative_to(ROOT).as_posix())
    selection_rows = [pin(path, relative=True) for path in selected]
    selection = HERE / 'PUBLISH_SELECTION_V35.json'
    write_new(selection, dict(schema='ordered_contour_native_component_checkpoint_v35',
        base_commit=BASE, scope='Verified native candidate/pixel/geometry components, compiled-scene synthetic speed and original C0 numeric control.',
        host_metadata='Retained receipts disclose workspace/toolchain absolute paths and versions as in V33/V34.',
        excluded='All build subdirectories/binaries, images, private magnet/SMD derivatives, real raw/bank/GT input payloads, all pending real pixel replay sources/outputs.',
        file_count=len(selection_rows), selected_bytes=sum(row['bytes'] for row in selection_rows), files=selection_rows))
    pathspec = HERE / 'PUBLISH_PATHSPEC_V35.nul'
    with pathspec.open('xb') as stream:
        stream.write(b'\0'.join([row['path'].encode() for row in selection_rows]
                               + [selection.relative_to(ROOT).as_posix().encode()]) + b'\0')
    print(json.dumps(dict(accepted=True, selection=pin(selection), file_count=len(selection_rows),
                          selected_bytes=sum(row['bytes'] for row in selection_rows))))


if __name__ == '__main__':
    main()
