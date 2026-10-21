"""Inventory explicit numeric/source evidence only; no staging or archiving."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = HERE/'SOURCE_ONLY_PUBLISH_SELECTION.json'


def main():
    if OUTPUT.exists():
        raise ValueError('Inventory must be new')
    top = ['DESIGN.md', 'PROTOCOL.json', 'SYNTHETIC_RESULTS.md', 'RESULTS.md',
           'EMPTY_FEATURE_MASK_SUCCESSOR_DESIGN.md', 'PRIVATE_SOURCE_FREEZE.json',
           'INPUT_CLOSURE.json', 'private_source_create.json', 'input_closure_create_v1.json',
           'test_private_source_isolation.py', 'freeze_private_sources.py', 'test_input_contract.py',
           'prepare_input_closure.py', 'silhouette_source.hpp', 'silhouette_source_test.cpp',
           'silhouette_eval.cpp', 'build_native.ps1', 'build_adapter.py', 'native_provenance.py',
           'run_stage.py', 'test_native_provenance.py', 'test_dependency_aliases.py',
           'prepare_publish_selection.py']
    directories = ['private_v11', 'frozen_helpers', 'frozen_inputs', 'private_source_test_red',
                   'private_source_test_green', 'input_contract_red', 'input_contract_green',
                   'build_source_test_red', 'build_source_test_red2', 'build_source_test_green',
                   'native_provenance_literals_v1', 'native_provenance_literals_v2',
                   'dependency_alias_red', 'dependency_alias_green', 'run_source_only_training_v1']
    files = {HERE/name for name in top}
    allowed = {'.py', '.ps1', '.cpp', '.h', '.hpp', '.hxx', '.json', '.csv', '.gz', '.txt', '.stdout', '.stderr', '.md'}
    for directory in directories:
        for path in (HERE/directory).rglob('*'):
            if path.is_file() and path.suffix in allowed and '__pycache__' not in path.parts:
                files.add(path)
    for version in ['build_adapter_v1', 'build_adapter_v2']:
        directory = HERE/version
        for path in directory.rglob('*'):
            if path.is_file() and (path.suffix in {'.json', '.stdout', '.stderr', '.d', '.py', '.cpp', '.hpp'}):
                files.add(path)
    rows = []
    for path in sorted(files):
        data = path.read_bytes()
        rows.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)))
    if any(Path(r['path']).suffix in ('.exe', '.o', '.png', '.jpg', '.dll') for r in rows):
        raise AssertionError('Non-numeric/source member selected')
    result = dict(kind='explicit numeric and source inventory only; no staging, archives, commits or promotion',
                  members=len(rows), bytes=sum(r['bytes'] for r in rows), files=rows,
                  preserved_failures=True, dataset_images_selected=0, compiled_executables_selected=0,
                  object_files_selected=0, protocol_sha256=hashlib.sha256((HERE/'PROTOCOL.json').read_bytes()).hexdigest())
    OUTPUT.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(members=result['members'], bytes=result['bytes'], inventory_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()
