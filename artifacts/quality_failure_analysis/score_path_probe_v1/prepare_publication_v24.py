"""Exact completed V24 numeric/source publication selection; no Git or images."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUDIT = ROOT/'artifacts/independent_reviews/score_path_probe_v1'
INVENTORY = HERE/'PUBLICATION_INVENTORY_V24.json'
SOURCES = '''build_probe.py contract_green.txt contract_red_assertions.txt contract_red.txt
DESIGN.md prepare_probe.py probe_contract.py PROBE_INPUTS_V1.json probe.cpp
RESULTS_PHASE1_V24.md root_check_phase1_totals.py root_check_synthetic.py
ROOT_PHASE1_TOTALS_20261022.json ROOT_STATIC_REVIEW_20261022.md
ROOT_SYNTHETIC_RECEIPT_20261022.json run_probe.py runner_gates_green.txt
runner_gates_red.txt runner_gates.py test_contract.py test_runner_gates.py
prepare_publication_v24.py'''.split()
AUDITOR_FILES = '''audit_main.py evidence_red.txt evidence.py numeric.py
phase1_audit_v1_console.txt README.md SOURCE_REVIEW.md synthetic_green.txt
synthetic_red.txt test_evidence.py test_numeric.py
run_phase1_audit_20261022_v1/.gitignore
run_phase1_audit_20261022_v1/result.json'''.split()
BUILD_FILES = '''adapter_before.d adapter.d attempts.json build_manifest.json
compile.stderr compile.stdout dependency_before.stderr dependency_before.stdout
link.stderr link.stdout'''.split()
FAILED_BUILD_FILES = '''adapter_before.d adapter.d attempted_probe.cpp.txt attempts.json
compile.stderr compile.stdout dependency_before.stderr dependency_before.stdout
FAILED_BUILD_RECEIPT.json failure.json'''.split()
STAGES = ['probe_selftest_red_v2', 'probe_selftest_green_v2', 'probe_phase1_v2']
SUFFIXES = {'.py', '.cpp', '.hpp', '.md', '.json', '.txt', '.csv', '.gz', '.d', '.stdout', '.stderr'}


def read(path):
    return json.loads(Path(path).read_bytes())


def selected():
    paths = [HERE/name for name in SOURCES] + [AUDIT/name for name in AUDITOR_FILES]
    paths += [HERE/'probe_build_red'/name for name in FAILED_BUILD_FILES]
    for build in ['probe_build_red_v2', 'probe_build_green_v2']:
        paths += [HERE/build/name for name in BUILD_FILES]
    for name in STAGES:
        directory = HERE/name
        freeze = read(directory/'PROBE_STAGE_FREEZE.json')
        assert freeze['completed'] is True
        for value in freeze['files'] + freeze['execution_files'] + [freeze['reservation']]:
            path = Path(value['path']).resolve(strict=True)
            data = path.read_bytes()
            assert len(data) == value['bytes'] and hashlib.sha256(data).hexdigest() == value['sha256']
            paths.append(path)
        paths.append(directory/'PROBE_STAGE_FREEZE.json')
    resolved = [p.resolve(strict=True) for p in paths]
    assert len(resolved) == len(set(resolved)), 'Duplicate publication member'
    for path in resolved:
        assert path.is_relative_to(HERE) or path.is_relative_to(AUDIT)
        assert path.suffix.lower() in SUFFIXES or path.name == '.gitignore'
        assert '__pycache__' not in path.parts
    return sorted(resolved, key=lambda p: p.relative_to(ROOT).as_posix())


def make_inventory():
    records = []
    for path in selected():
        data = path.read_bytes()
        records.append(dict(path=path.relative_to(ROOT).as_posix(), size_bytes=len(data),
                            sha256=hashlib.sha256(data).hexdigest()))
    return dict(version='V24', scope='Completed Phase1 diagnostics, failed build, synthetic gates and independent numeric audit only',
                file_count=len(records), total_bytes=sum(r['size_bytes'] for r in records),
                excluded='Dataset/private images and SMD, compiler/SDK/runtime files, exe/object, pending Phase2 and hash full-matcher experiments',
                files=records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = make_inventory()
    if args.verify:
        assert read(INVENTORY) == result, 'Published evidence selection/bytes changed'
    else:
        with INVENTORY.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}))


if __name__ == '__main__':
    main()
