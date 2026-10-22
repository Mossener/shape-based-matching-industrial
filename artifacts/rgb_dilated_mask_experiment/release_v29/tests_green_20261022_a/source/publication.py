"""V29 public training-evidence selection and read-only Git index verification.

This tool never stages, commits, imports the experiment, opens images, executes
native code or attests external compiler/runtime bytes. Run prepare only after
the root freezes the release. A subsequent verifier rejects extra staged paths.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
ROOT = EXPERIMENT.parents[1]
REVIEW = ROOT / 'artifacts/independent_reviews/rgb_dilated_mask_training_v1'
INVENTORY = EXPERIMENT / 'PUBLISH_SELECTION_V29.json'
BASE_REVISION = '94239caf522173cf1d6027fa54dc45cdec2163fe'
EXTERNAL = ('.gitattributes', 'docs/optimization_versions.md')
ROOT_FILES = '''accept_training_audit.py bank_reader.py build_quality.py
build_training_v2.py build_training.py DESIGN.md EXECUTION_STATUS_PRE_QUALITY.json
FAILURE_HISTORY.md freeze_private_sources.py IMPLEMENTATION_PLAN.md INPUT_CLOSURE.json
literal_mask_test.cpp native_provenance.py prepare_input_closure.py
prepare_quality_inputs.py prepare_sources.py PRIVATE_SOURCE_FREEZE.json PROTOCOL.json
quality_contract.py quality_eval.cpp quality_execution_inputs.py quality_support.hpp
README.md RESULTS_PRE_QUALITY.md rgb_dilated_mask_policy.hpp
rgb_dilated_mask_source_test.cpp run_native_test.py run_quality.py run_static_tests.py
run_training.py source_contract.py SOURCE_ORIGINS.json SOURCE_REVIEW.md source_status.json
test_audit_acceptance.py test_source_contract.py TOY_TEST_EXPECTATIONS.json
toy_verification_20261022_a.json toy_verification_20261022_b.json
toy_verification_root_20261022.json train_rgb_dilated_mask.cpp TRAINING_BUILD_V2_ORIGIN.json
training_numeric.py TRAINING_VALIDATOR_ORIGIN.json verify_toy_receipts.py
AUDIT_ACCEPTANCE.json QUALITY_INPUT_FREEZE.json quality_inputs_verified_root_20261022_a.json
ROOT_REVIEW_PRE_QUALITY.md'''.split()
EXPERIMENT_DIRS = '''build_literal_control_red_v1 build_literal_control_v1
build_literal_treatment_v1 build_source_test_v1 build_training_v1 control_v11
frozen_helpers private_v11 run_literal_control_red_v1 run_literal_control_v1
run_literal_treatment_v1 run_plan_v1 run_plan_v1_execution run_source_test_v1
run_training_v1 run_training_v1_execution tests_acceptance_green_20261022_a
tests_acceptance_red_20261022_a tests_all_20261022_a tests_all_20261022_b
tests_all_20261022_c tests_all_20261022_d tests_all_20261022_e tests_all_20261022_f
tests_red_20261022_a tests_root_20261022_a tests_source_20261022_a
tests_source_20261022_b training_stage_reservations release_v29'''.split()
REVIEW_FILES = '''audit_v2.py audit.py bank_reader.py ORIGIN_V2.json ORIGIN.json
README.md test_bank.py test_numeric.py test_scope_and_seam.py test_v2_schema.py
training_numeric.py quality_source_review_v1.md'''.split()
REVIEW_DIRS = '''run_real_v2_root_20261022_a tests_green_20261022_a
tests_green_20261022_b tests_green_20261022_c tests_red_20261022 tests_red_20261022_b
tests_v2_green_20261022_a tests_v2_red_20261022_a'''.split()
FORBIDDEN = {'.exe', '.o', '.obj', '.dll', '.a', '.lib', '.pyc', '.pyo', '.smd',
             '.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp', '.gif',
             '.mp4', '.avi', '.wav', '.mp3', '.zip', '.tar', '.7z'}
PUBLIC_SUFFIXES = {'.py', '.cpp', '.h', '.hpp', '.hxx', '.md', '.json', '.csv',
                   '.d', '.stdout', '.stderr', '.txt'}


def need(value, message):
    if not value:
        raise ValueError(message)


def permitted(path):
    """Reject before read: only the two selected roots or two fixed extras."""
    path = Path(path).resolve()
    need(path.is_relative_to(EXPERIMENT) or path.is_relative_to(REVIEW) or
         path in {ROOT / name for name in EXTERNAL}, 'Outside V29 scope: ' + str(path))
    need(path.is_relative_to(ROOT), 'Outside repository')
    need('__pycache__' not in path.parts and path.name != '.gitignore' and
         path.suffix.lower() not in FORBIDDEN, 'Excluded member: ' + str(path))
    need(path.name == '.gitattributes' or path.suffix.lower() in PUBLIC_SUFFIXES or
         path.name.endswith(('.yml.gz', '.csv.gz')), 'Unknown public type: ' + str(path))
    return path


def pin(path):
    path = permitted(path)
    data = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def load(path):
    return json.loads(permitted(path).read_text(encoding='utf-8-sig'))


def path_for(record):
    path = Path(record['path'])
    return permitted(path if path.is_absolute() else ROOT / path)


def check(record):
    actual = pin(path_for(record))
    need(actual['sha256'] == record['sha256'] and actual['bytes'] == record['bytes'],
         'SHA/size mismatch: ' + record['path'])


def collect():
    """Never descend into unknown top-level experiment/review directories."""
    selected, excluded = set(), []
    for root, names, dirs in ((EXPERIMENT, ROOT_FILES, EXPERIMENT_DIRS),
                              (REVIEW, REVIEW_FILES, REVIEW_DIRS)):
        for name in names:
            path = root / name
            if path.exists():
                selected.add(permitted(path))
        for name in dirs:
            directory = root / name
            if not directory.exists():
                continue
            need(directory.resolve().is_relative_to(root.resolve()), 'Directory escapes selection root')
            for path in directory.rglob('*'):
                if not path.is_file():
                    continue
                if path.name == '.gitignore' or '__pycache__' in path.parts or path.suffix.lower() in FORBIDDEN:
                    excluded.append(path.relative_to(ROOT).as_posix())
                    continue
                selected.add(permitted(path))
    selected.update(permitted(ROOT / name) for name in EXTERNAL)
    selected.discard(INVENTORY)
    return sorted(selected, key=lambda p: p.relative_to(ROOT).as_posix()), sorted(excluded)


def verify_members(freeze, directory, basename):
    records = freeze['files']
    paths = [path_for(p) for p in records]
    need(len(paths) == len(set(paths)) and all(p.is_relative_to(directory) for p in paths),
         'Unsafe/duplicate freeze member')
    actual = {p.resolve() for p in directory.rglob('*') if p.is_file() and
              p.name != '.gitignore' and p != directory / basename}
    need(set(paths) == actual, 'Frozen complete native member set differs')
    for record in records + freeze['execution_files'] + [freeze['reservation']]:
        check(record)


def verify_evidence(audit_path):
    """Recheck local public closures; the independent audit owns interpretation."""
    audit_path = permitted(audit_path)
    need(audit_path.is_relative_to(REVIEW) and audit_path.name == 'receipt.json',
         'Select the independent review receipt explicitly')
    bank_path = EXPERIMENT / 'run_training_v1/BANK_FREEZE.json'
    plan_path = EXPERIMENT / 'run_plan_v1/COMMON_PADDING_FREEZE.json'
    bank, plan, audit = load(bank_path), load(plan_path), load(audit_path)
    need(bank['native_exit_zero'] is True and bank['comparison_feasible'] is True and
         bank['training_attempts_complete'] is True and bank['attempts'] == 20736 and
         bank['matcher_calls'] == 0 and bank['image_decodes'] == 864,
         'Incomplete training evidence')
    need(bank['successful_templates'] == {'1':3432,'2':3456,'5':3456,'8':3456,'12':3456,'17':3456},
         'Recorded training result differs')
    need(plan['passed'] is True and plan['image_decodes'] == plan['matcher_calls'] == 0 and
         plan['plan']['width'] == 848 and plan['plan']['height'] == 832 and
         plan['plan']['padding_ltrb'] == [64,64,64,228] and
         plan['plan']['banks'] == 12 and plan['plan']['loaded_layers'] == 77822,
         'Fixed full-bank plan differs')
    check(plan['bank_freeze'])
    need(path_for(plan['bank_freeze']) == bank_path, 'Plan binds another training freeze')
    verify_members(bank, bank_path.parent, bank_path.name)
    verify_members(plan, plan_path.parent, plan_path.name)
    need(audit['passed'] is True and audit['training_attempts'] == 20736 and
         audit['plan'] == plan['plan'] and audit['image_decodes'] == audit['matcher_calls'] == 0 and
         audit['inputs_unchanged_before_after'] is True and
         audit['input_pins'] == audit['input_pins_after'], 'Independent audit gate differs')
    for path in (bank_path, plan_path):
        expected = pin(path)
        observed = audit['input_pins'].get(str(path.resolve()))
        need(observed is not None and all(observed[k] == expected[k] for k in ('bytes','sha256')),
             'Audit did not bind exact original freezes')
    for name, expected in audit['audit_source_pins'].items():
        need(Path(name).name == name, 'Unsafe audit source member')
        check(dict(path=str(REVIEW / name), **expected))
    acceptance = load(EXPERIMENT / 'AUDIT_ACCEPTANCE.json')
    need(acceptance['accepted_independent_audit'] is True and
         acceptance['scope'] == 'training_and_exact_geometry', 'Independent acceptance missing')
    for name, path in (('training_freeze', bank_path), ('plan_freeze', plan_path),
                       ('independent_audit', audit_path)):
        check(acceptance[name])
        need(path_for(acceptance[name]) == path, 'Acceptance binds another ' + name)
    build = load(EXPERIMENT / 'build_training_v1/build_manifest.json')
    need(build['passed'] and build['target'] == 'training' and build['core_arm'] == 'treatment' and
         len(build['commands']) == 5 and all(p['exit_code'] == 0 for p in build['commands']),
         'Actual training build gate differs')
    for record in build['project_sources']:
        check(record)
    # Runtime/SDK/objects and original image pins stay declarations here.
    # Root's actual native-run verification checked them separately.
    for name in ('run_training_v1_execution', 'run_plan_v1_execution'):
        execution = load(EXPERIMENT / name / 'execution_provenance.json')
        need(execution['native_exit_code'] == 0, 'Native stage exit differs')
        for record in execution['script_pins'] + [execution['build_manifest'], execution['input_closure']]:
            check(record)
    toy = load(EXPERIMENT / 'toy_verification_root_20261022.json')
    need(toy['passed'] is True and len(toy['cases']) == 4 and
         [c['actual_exit'] for c in toy['cases']] == [0,1,0,0], 'Native toy gate differs')
    check(toy['oracle']); check(toy['verifier'])
    for case in toy['cases']:
        for key in ('build_manifest','receipt','stdout','stderr'):
            check(case[key])
    return dict(passed=True, audit=pin(audit_path), attempts=20736,
                successful_templates=bank['successful_templates'], loaded_layers=77822,
                local_public_freezes_rechecked=True, image_reads=0, matcher_calls=0,
                limitation='Rechecks selected public bytes and critical audit bindings; does not rerun numeric interpretation, native processes, external SDK/runtime checks, image hashes or historical inherited inputs.')


def object_id(data, algorithm='sha1'):
    need(algorithm in ('sha1', 'sha256'), 'Unknown Git object format')
    return hashlib.new(algorithm, b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def verify_index_records(records, lookup, changed, algorithm='sha1'):
    paths = {r['path'] for r in records}
    need(set(changed).issubset(paths), 'Extra staged path(s): ' + ', '.join(sorted(set(changed)-paths)))
    for record in records:
        data = path_for(record).read_bytes()
        need(lookup.get(record['path']) == object_id(data, algorithm),
             'Git index bytes differ: ' + record['path'])


def prepare(audit_path):
    need(not INVENTORY.exists(), 'Inventory already exists; never overwrite')
    verification = verify_evidence(audit_path)
    need((EXPERIMENT / 'ROOT_REVIEW_PRE_QUALITY.md').is_file(), 'Root release review is not frozen yet')
    paths, excluded = collect()
    files = [pin(p) for p in paths]
    need(pin(audit_path)['path'] in {p['path'] for p in files}, 'Audit receipt not selected')
    result = dict(version='v29_public_training_evidence_selection_v1', base_revision=BASE_REVISION,
                  files=files, file_count=len(files), selected_bytes=sum(p['bytes'] for p in files),
                  verification=verification, excluded_files=excluded,
                  scope='Official-mask dilation training/geometry and source preparation only; no quality/timing outcome',
                  exclusion_policy='Explicit root filenames/directories only; images/SMD, binaries, objects, archives and caches excluded. SDK/runtime prerequisites remain pinned but are not vendored.',
                  image_reads=0, matcher_calls=0)
    with INVENTORY.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    return result


def verify(staged=False):
    result = load(INVENTORY)
    files = result['files']
    need(result['version'] == 'v29_public_training_evidence_selection_v1' and
         result['base_revision'] == BASE_REVISION and
         result['file_count'] == len(files) == len({p['path'] for p in files}),
         'Inventory identity/count/duplicates differ')
    paths, _ = collect()
    need({p.relative_to(ROOT).as_posix() for p in paths} == {r['path'] for r in files},
         'Explicit selection changed after inventory freeze')
    for record in files:
        check(record)
    need(result['selected_bytes'] == sum(p['bytes'] for p in files), 'Inventory byte total differs')
    verification = verify_evidence(path_for(result['verification']['audit']))
    need(verification == result['verification'], 'Release evidence status changed')
    changed = []
    if staged:
        index = subprocess.check_output(['git','ls-files','--stage','-z'], cwd=ROOT)
        lookup = {}
        for row in index.split(b'\0'):
            if row:
                meta, name = row.split(b'\t',1)
                mode, oid, stage = meta.decode().split()
                need(stage == '0', 'Unmerged Git index')
                lookup[name.decode('utf-8')] = oid
        changed = subprocess.check_output(['git','diff','--cached','--name-only','--no-renames','-z'], cwd=ROOT).decode('utf-8').split('\0')
        changed = [p for p in changed if p]
        algorithm = subprocess.check_output(['git','rev-parse','--show-object-format'], cwd=ROOT).decode().strip()
        verify_index_records(files+[pin(INVENTORY)], lookup, changed, algorithm)
    return dict(passed=True, file_count=len(files), selected_bytes=result['selected_bytes'],
                staged_bytes_equal=staged, extra_staged_paths_rejected=staged,
                changed_staged_paths=len(changed), image_reads=0, matcher_calls=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--check-evidence', action='store_true')
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    need(not (args.prepare or args.check_evidence) or args.audit is not None,
         'Evidence check/prepare requires explicit independent audit receipt')
    if args.check_evidence:
        need(not args.staged, 'Index verification requires the frozen inventory')
        print(json.dumps(verify_evidence(args.audit)))
        return
    if args.prepare:
        prepare(args.audit)
    else:
        need(args.audit is None, 'Verify uses the audit frozen in the inventory')
    print(json.dumps(verify(staged=args.staged)))


if __name__ == '__main__':
    main()
