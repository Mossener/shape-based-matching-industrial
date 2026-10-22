"""Create or verify the exact V23 timing publication selection.

Only known source/doc/numeric evidence paths are selected.  This never stages,
commits, compiles, runs native code, decodes images or scans datasets.  The V22
inventory remains an unchanged historical artifact at its own Git tag.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REVIEW = ROOT / 'artifacts/independent_reviews/empty_mask_timing_v1'
OUTPUT = HERE / 'V23_TIMING_PUBLICATION_INVENTORY.json'
ROOT_FILES = (
    'TIMING_RESULTS_V23.md', 'QUALITY_STAGE_README.md',
    'prepare_timing_publication_inventory.py', 'test_timing_publication_inventory.py',
    'quality_stage_reservations/timing.json',
)
REVIEW_FILES = (
    'timing_audit.py', 'test_timing_audit.py', 'test_timing_provenance.py',
    'run_synthetic.py', 'ORIGIN.json', 'README.md', 'source_review_20261022.json',
    'root_arithmetic_review.py', 'root_arithmetic_review_20261022.json',
)
REVIEW_DIRS = ('run_synthetic_20261022_b', 'run_20261022_timing_audit_v1')
STAGE = HERE / 'run_quality_timing_v1'
STAGE_NAMES = {
    'QUALITY_STAGE_FREEZE.json', 'execution_provenance.json', 'native.stderr', 'native.stdout',
    'verified_before.json', 'verified_after.json', 'native/bank_load_timings.csv',
    'native/stage_summary.json', 'native/timing_samples.csv',
}
ALLOWED_SUFFIXES = {'.cpp', '.csv', '.gz', '.h', '.hpp', '.json', '.md', '.py', '.stderr', '.stdout', '.txt'}
PINS = {
    'timing_stage': ('run_quality_timing_v1/QUALITY_STAGE_FREEZE.json',
                     'e7585e22bfe29d398cd344ab14c9c72923c27fbeb093b3a8df98f7062bc1dfa4'),
    'previous_v22_inventory': ('V22_QUALITY_PUBLICATION_INVENTORY.json',
                               '3d3d3a52a9a947d028c4f873fc7bf970b9c6e9e45eb198593b5fe66a45cde814'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe(path):
    if not path.is_file() or path.name == '.gitignore' or '__pycache__' in path.parts:
        return False
    if path.resolve(strict=True) != path.absolute():
        return False
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False
    return path.suffix.lower() != '.gz' or path.name.lower().endswith('.csv.gz')


def select():
    selected = {}

    def add(path, category):
        if not safe(path):
            raise ValueError('Missing or forbidden V23 publication file: ' + str(path))
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(ROOT):
            raise ValueError('Publication path escaped repository')
        relative = resolved.relative_to(ROOT).as_posix()
        if relative in selected:
            raise ValueError('Duplicate publication path: ' + relative)
        data = resolved.read_bytes()
        selected[relative] = dict(path=relative, size_bytes=len(data), sha256=digest(data), category=category)

    for name in ROOT_FILES:
        add(HERE / name, 'timing_documentation_and_publication_source')
    for name in REVIEW_FILES:
        add(REVIEW / name, 'independent_timing_source_or_review')
    actual_names = {p.relative_to(STAGE).as_posix() for p in STAGE.rglob('*')
                    if p.is_file() and p.name != '.gitignore'}
    if actual_names != STAGE_NAMES:
        raise ValueError('Timing stage exact nine-file evidence inventory differs')
    for name in sorted(STAGE_NAMES):
        add(STAGE / name, 'native_timing_evidence_and_execution_closure')
    for name in REVIEW_DIRS:
        directory = REVIEW / name
        if not directory.is_dir():
            raise ValueError('Missing completed timing review directory: ' + name)
        for path in sorted(directory.rglob('*')):
            if path.is_file() and safe(path):
                add(path, 'independent_timing_audit_or_synthetic_evidence')
    pinned = {}
    for key, (name, expected) in PINS.items():
        path = HERE / name
        data = path.read_bytes()
        if digest(data) != expected:
            raise ValueError('Reviewed historical/stage pin differs: ' + key)
        pinned[key] = dict(path=path.relative_to(ROOT).as_posix(), size_bytes=len(data), sha256=expected)
    return [selected[key] for key in sorted(selected)], pinned


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--refresh', action='store_true')
    mode.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    files, pins = select()
    result = dict(schema_version=1, scope='Exact V23 timing source/numeric publication selection',
                  native_matcher_calls=12288, formal_timing_rows=10752,
                  independent_audit_matcher_calls=0, independent_audit_image_decodes=0,
                  production_core='V11 unchanged', source_and_evidence_only=True,
                  file_count=len(files), total_bytes=sum(item['size_bytes'] for item in files),
                  frozen_reference_pins=pins,
                  exclusions=['images', 'executables', 'object files', 'Python bytecode',
                              'unrelated diagnostics', 'synthetic_a prior source snapshots',
                              'pending probes', 'separately published lost-GT analysis'],
                  files=files)
    if args.verify:
        if not OUTPUT.is_file() or json.loads(OUTPUT.read_text(encoding='utf-8')) != result:
            raise ValueError('V23 inventory differs from selected files or metadata')
    else:
        if OUTPUT.exists() and not args.refresh:
            raise ValueError('Existing V23 inventory requires --refresh')
        OUTPUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    for item in files:
        data = (ROOT / item['path']).read_bytes()
        if len(data) != item['size_bytes'] or digest(data) != item['sha256']:
            raise ValueError('Selected V23 bytes changed: ' + item['path'])
    for key, pin in pins.items():
        data = (ROOT / pin['path']).read_bytes()
        if len(data) != pin['size_bytes'] or digest(data) != pin['sha256']:
            raise ValueError('Frozen historical/stage bytes changed: ' + key)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}))
    print('mode=' + ('verify_only' if args.verify else 'generate_and_verify'))
    print('inventory_sha256=' + digest(OUTPUT.read_bytes()))


if __name__ == '__main__':
    main()
