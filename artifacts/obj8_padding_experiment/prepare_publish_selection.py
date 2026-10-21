"""Inventory pure numeric/source publication candidates, without staging Git.

Existing run provenance is read without modification. Binaries, input images,
Python caches and compiler scratch checks are excluded. Selected build evidence
is explicit, rather than including the build directory wholesale.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ALLOWED = {'.h', '.hxx', '.hpp', '.cpp', '.py', '.ps1', '.md', '.json', '.csv', '.gz', '.txt'}
BUILD_FILES = {
    'build_manifest.json', 'provenance_selftest.json',
    'adapter_compiler_stdout.txt', 'adapter_compiler_stderr.txt',
    'adapter_compiler_stdout_recheck.txt', 'adapter_compiler_stderr_recheck.txt',
    'adapter_compiler_stdout_parent_review.txt', 'adapter_compiler_stderr_parent_review.txt',
}
BUILD_DIRS = {'planner_red', 'planner_red_final', 'planner_green_and_mutations',
              'planner_green_and_mutations_recheck'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Selection output must be new')
    files, excluded = [], []
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or path.resolve() == args.output.resolve():
            continue
        relative = path.relative_to(HERE)
        name = relative.as_posix()
        selected_build = relative.parts[0] == 'build' and (
            name[6:] in BUILD_FILES or len(relative.parts) > 2 and relative.parts[1] in BUILD_DIRS)
        selected = '__pycache__' not in relative.parts and (path.suffix in ALLOWED or path.name == '.gitignore')
        if relative.parts[0] == 'build' and not selected_build:
            selected = False
        if not selected:
            excluded.append(name)
            continue
        files.append(dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size,
                          sha256=digest(path), role='selected_build_evidence' if selected_build else
                          'run_numeric_and_snapshots' if relative.parts[0].startswith('run_') else
                          'numeric_fixture' if relative.parts[0] == 'audit_mutation_fixtures' else 'source_plan_report'))
    # List external numeric dependencies for the integration owner's existing
    # preservation packages. Never copy or hash input image members here.
    verified = json.loads((HERE/'run_obj8_full400/verified_inputs.json').read_text())
    external = []
    for item in verified['input_sha256']:
        path = Path(item['path'])
        if path.is_relative_to(HERE) or path.suffix.lower() not in ALLOWED | {'.yml'}:
            continue
        if path.suffix == '.gz' and not (path.name.endswith('_raw.csv.gz') or path.name.startswith('templates_')):
            continue
        external.append(dict(path=path.relative_to(ROOT).as_posix(), bytes=item['bytes'],
                             sha256=item['sha256'], source='Original verified input record; retained in prior packages or required for replay'))
    result = dict(schema_version=1, purpose='V16 reviewable selection only; no git staging, archive creation or source/provenance mutation',
                  members=len(files), total_bytes=sum(f['bytes'] for f in files), files=files,
                  excluded_local_members=excluded, external_numeric_dependencies=external,
                  input_image_members_selected=0, executables_selected=0, compiler_objects_selected=0,
                  do_not_rewrite_original_run_provenance=True,
                  integration_note='Directly track top-level source/plans/reports. Numeric runs and selected build evidence may be archived with exact repository paths and per-member SHA values. .gitignore files inside runs are part of attested output sets. This inventory itself has no self hash.')
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(members=result['members'], total_bytes=result['total_bytes'], external_numeric_dependencies=len(external), excluded_local_members=len(excluded))))


if __name__ == '__main__':
    main()
