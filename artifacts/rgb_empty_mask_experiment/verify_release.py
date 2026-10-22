"""Verify V27 frozen evidence, inventory public files, and check index bytes.

No image reads, native execution, staging, commits, or network operations.
Keep historical manifests immutable; report current status in a separate file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVIEW_ROOTS = [ROOT / 'artifacts/independent_reviews' / name for name in (
    'rgb_empty_mask_quality_v1', 'rgb_empty_mask_training_v1', 'rgb_empty_mask_timing_v1')]
INVENTORY = HERE / 'PUBLISH_SELECTION_V27.json'
FORBIDDEN = {'.exe', '.o', '.obj', '.dll', '.a', '.lib', '.pyc', '.pyo',
             '.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp', '.gif', '.smd'}


def need(value, message):
    if not value:
        raise ValueError(message)


def permitted(path):
    path = Path(path).resolve()
    need(path.is_relative_to(ROOT), 'Outside repository: ' + str(path))
    need(path.suffix.lower() not in FORBIDDEN and '__pycache__' not in path.parts,
         'Non-public evidence member: ' + str(path))
    return path


def pin(path):
    path = permitted(path)
    data = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def load(path):
    return json.loads(permitted(path).read_text(encoding='utf-8-sig'))


def check(record):
    path = Path(record['path'])
    path = path if path.is_absolute() else ROOT / path
    actual = pin(path)
    need(actual['sha256'] == record['sha256'] and
         ('bytes' not in record or actual['bytes'] == record['bytes']),
         'Frozen SHA/size mismatch: ' + str(path))


def verify_evidence():
    # Existing build/stage gates verify external tool/runtime prerequisites too.
    # Their exact bytes are prerequisites, never selected for publication.
    import run_quality
    import prepare_quality_inputs
    import freeze_private_sources
    prepare_quality_inputs.verify()
    freeze_private_sources.verify(HERE / 'private_v11', load(HERE / 'PRIVATE_SOURCE_FREEZE.json'))
    builds = []
    for name in ('build_source_test_v2', 'build_training_v2', 'build_quality_v1', 'build_quality_v2'):
        manifest = load(HERE / name / 'build_manifest.json')
        need(manifest['passed'] is True and len(manifest['commands']) == 5 and
             all(row['exit_code'] == 0 for row in manifest['commands']), 'Incomplete build: ' + name)
        for record in manifest['project_sources']:
            check(record)
        # Check actual -MD dependency pins with the established read-only pin checker.
        for unit in manifest['dependency_units']:
            for record in unit['dependencies'] + [unit['object'], unit['dependency_file']]:
                run_quality.p.check_pin(record)
        for key in ('compiler_tools_and_link_libraries',):
            for record in manifest[key]:
                run_quality.p.check_pin(record)
        for key in ('compiler_runtime_closure', 'executable_runtime_closure'):
            for record in manifest[key]['files']:
                run_quality.p.check_pin(record)
        builds.append(pin(HERE / name / 'build_manifest.json'))
    stage_counts = {}
    for name in ('run_quality_selftest_v1', 'run_quality_selftest_v3', 'run_quality_old_gate_v1',
                 'run_quality_pilot_v1', 'run_quality_development_v1', 'run_quality_timing_v2'):
        manifest = load(HERE / name / 'QUALITY_STAGE_FREEZE.json')
        stage = manifest['stage']
        check(manifest['build_manifest']); check(manifest['quality_inputs'])
        for key in ('previous_stage', 'selftest', 'reservation'):
            if manifest[key]:
                check(manifest[key])
        for record in manifest['files'] + manifest['execution_files']:
            check(record)
        expected = {Path(record['path']).resolve() for record in manifest['files']}
        actual = {p.resolve() for p in (HERE / name / 'native').rglob('*')
                  if p.is_file() and p.name != '.gitignore'}
        need(actual == expected, 'Stage member set changed: ' + name)
        need(manifest['completed'] and manifest['native_exit_code'] == 0 and
             manifest['actual_matcher_calls'] == manifest['maximum_matcher_calls'],
             'Stage incomplete: ' + name)
        if stage != 'selftest':
            stage_counts[stage] = int(manifest['actual_matcher_calls'])
    need(stage_counts == dict(old_gate=96, pilot=192, development=9600, timing=12288), 'Stage budgets differ')
    for name, basename in (('run_training_v1', 'BANK_FREEZE.json'),
                           ('run_plan_v1', 'COMMON_PADDING_FREEZE.json')):
        manifest = load(HERE / name / basename)
        for record in manifest['files']:
            check(record)
    return dict(passed=True, successful_builds=builds, matcher_calls_in_frozen_runs=22176,
                source_files_unchanged=True, stage_member_sets_unchanged=True,
                matcher_calls_by_this_verifier=0, image_reads_by_this_verifier=0)


def create_inventory():
    need(not INVENTORY.exists(), 'Inventory already exists; verify rather than overwrite it')
    verification = verify_evidence()
    paths = set()
    for root in [HERE] + REVIEW_ROOTS:
        need(root.is_dir(), 'Independent evidence missing: ' + str(root))
        for p in root.rglob('*'):
            if p.is_file() and p != INVENTORY and p.name != '.gitignore' and not any(
                    part == '__pycache__' for part in p.parts) and p.suffix.lower() not in FORBIDDEN:
                paths.add(p)
    files = [pin(p) for p in sorted(paths, key=lambda p: p.relative_to(ROOT).as_posix())]
    result = dict(version='v27_public_evidence_selection_v1', files=files, file_count=len(files),
                  selected_bytes=sum(p['bytes'] for p in files), verification=verification,
                  exclusion_policy='Private images/SMD, all raster images, binaries, objects, caches and .gitignore files excluded; external runtime/SDK prerequisites remain pinned, not vendored',
                  root_owned_staging=True, image_reads=0, matcher_calls=0)
    INVENTORY.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def verify_inventory(staged=False):
    result = load(INVENTORY)
    files = result['files']
    need(result['file_count'] == len(files) == len({r['path'] for r in files}), 'Inventory count/duplicates')
    for record in files:
        check(record)
    need(sum(r['bytes'] for r in files) == result['selected_bytes'], 'Inventory bytes differ')
    if staged:
        index = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=ROOT)
        lookup = {}
        for line in index.split(b'\0'):
            if line:
                meta, path = line.split(b'\t', 1)
                mode, oid, stage = meta.decode().split()
                need(stage == '0', 'Unmerged index')
                lookup[path.decode('utf-8')] = oid
        for record in files + [pin(INVENTORY)]:
            data = (ROOT / record['path']).read_bytes()
            oid = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            need(lookup.get(record['path']) == oid, 'Index bytes differ: ' + record['path'])
    return dict(passed=True, files=len(files), selected_bytes=result['selected_bytes'],
                staged_bytes_equal=staged, image_reads=0, matcher_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create-inventory', action='store_true')
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    if args.create_inventory:
        create_inventory()
    else:
        verify_evidence()
    print(json.dumps(verify_inventory(staged=args.staged)))


if __name__ == '__main__':
    main()
