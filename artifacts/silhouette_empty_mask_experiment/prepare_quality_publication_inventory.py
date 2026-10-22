"""Create an exact, byte-pinned V22 quality publication selection.

This is a source/evidence inventory only. It never stages, commits, decodes
images, compiles or calls the matcher. Numeric gzip archives are eligible;
executables, object files, caches and image formats are rejected.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = HERE / "V22_QUALITY_PUBLICATION_INVENTORY.json"

ROOT_FILES = (
    "PADDING_BASELINE_COMPARISON_PLAN.md", "QUALITY_INPUT_FREEZE.json",
    "QUALITY_RESULTS_V22.md", "QUALITY_SOURCE_ORIGIN.json",
    "QUALITY_STAGE_README.md", "build_quality.py", "prepare_quality_inputs.py",
    "quality_build_selftest_receipt_v1.json", "quality_contract.py",
    "quality_eval.cpp", "quality_input_create_v1.json",
    "quality_input_verify_static_v1.json", "quality_input_verify_static_v2.json",
    "quality_old_gate_receipt_v1.json", "quality_pilot_receipt_v1.json",
    "quality_static_review_v1.json", "quality_support.hpp", "run_quality.py",
    "test_quality_contract.py", "native_provenance.py", "freeze_private_sources.py",
    "prepare_input_closure.py", "PRIVATE_SOURCE_FREEZE.json", "INPUT_CLOSURE.json",
    "PROTOCOL.json", "prepare_quality_publication_inventory.py",
    "test_quality_publication_inventory.py",
)
STAGE_DIRS = (
    "build_quality_v1", "run_quality_selftest_v1", "run_quality_old_gate_v1",
    "run_quality_pilot_v1", "run_quality_development_v1",
    "quality_stage_reservations", "quality_contract_red_v1",
    "quality_contract_green_v1", "quality_contract_green_v2",
)
REVIEW_ROOT = ROOT / "artifacts/independent_reviews/empty_mask_quality_v1"
REVIEW_DIRS = (
    "run_development_audit_20261022", "run_development_audit_20261022_v2",
    "run_development_audit_20261022_v3", "run_pilot_audit_20261022",
    "run_20261022_analysis_green", "run_20261022_analysis_red",
    "run_20261022_contract_green", "run_20261022_contract_red",
    "run_20261022_evidence_green", "run_20261022_evidence_red",
    "run_20261022_numeric_green", "run_20261022_numeric_red",
    "run_20261022_source_review_green",
)
REVIEW_FILES = (
    "ORIGIN.json", "DESIGN.md", "analysis_core.py", "audit_quality.py",
    "checked.py", "evidence.py", "numeric.py", "root_build_selftest_20261022.json",
    "root_build_selftest_review.py", "root_old_gate_completion_20261022.json",
    "root_pilot_completion_20261022.json", "root_development_completion_20261022.json",
    "root_stage_gate_review.py", "run_synthetic.py", "test_analysis_core.py",
    "test_checked.py", "test_evidence.py", "test_numeric.py", "test_report.py",
)
ALLOWED_SUFFIXES = {'.cpp', '.d', '.csv', '.gz', '.h', '.hpp', '.json', '.md',
                   '.py', '.stderr', '.stdout', '.txt', '.yml'}
FORBIDDEN_SUFFIXES = {'.a', '.bmp', '.dll', '.exe', '.gif', '.jpg', '.jpeg',
                      '.o', '.obj', '.png', '.pyc', '.pyo', '.tif', '.tiff',
                      '.webp'}


def relative(path):
    path = path.resolve(strict=True)
    if not path.is_relative_to(ROOT):
        raise ValueError('Path escaped repository: '+str(path))
    return path.relative_to(ROOT).as_posix()


def safe(path):
    if not path.is_file() or path.name == '.gitignore' or '__pycache__' in path.parts:
        return False
    if path.resolve(strict=True) != path.absolute():
        return False
    suffix = path.suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES or suffix not in ALLOWED_SUFFIXES:
        return False
    # Do not publish any raw image or private magnet/SMD material even if a
    # future run adds one under a selected tree.
    name = path.name.lower()
    if suffix == '.gz' and not name.endswith('.csv.gz'):
        return False
    if name.endswith(('.smd', '.bmp', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.webp')):
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--refresh', action='store_true',
                      help='Explicitly replace an existing candidate inventory')
    mode.add_argument('--verify', action='store_true',
                      help='Check an existing inventory and every selected byte without writing')
    args = parser.parse_args()
    selected = {}

    def add(path, category):
        path = Path(path)
        if not path.is_file() or not safe(path):
            raise ValueError('Missing or forbidden publication file: '+str(path))
        name = relative(path)
        if name in selected:
            raise ValueError('Duplicate publication path: '+name)
        data = path.read_bytes()
        selected[name] = dict(path=name, size_bytes=len(data),
                              sha256=hashlib.sha256(data).hexdigest(), category=category)

    for name in ROOT_FILES:
        add(HERE/name, 'quality_sources_and_receipts')
    for name in STAGE_DIRS:
        directory = HERE/name
        if not directory.is_dir():
            raise ValueError('Missing completed quality directory: '+name)
        for path in sorted(directory.rglob('*')):
            if path.is_file() and safe(path):
                add(path, 'native_quality_evidence')
    for name in REVIEW_FILES:
        path = REVIEW_ROOT/name
        if path.is_file():
            add(path, 'independent_quality_source_or_receipt')
        else:
            raise ValueError('Missing independent review file: '+str(path))
    for name in REVIEW_DIRS:
        directory = REVIEW_ROOT/name
        if not directory.is_dir():
            raise ValueError('Missing independent audit directory: '+name)
        for path in sorted(directory.rglob('*')):
            if path.is_file() and safe(path):
                add(path, 'independent_quality_audit_evidence')

    files = [selected[name] for name in sorted(selected)]
    forbidden = [item['path'] for item in files if Path(item['path']).suffix.lower() in FORBIDDEN_SUFFIXES]
    if forbidden:
        raise ValueError('Forbidden selection member: '+forbidden[0])
    result = dict(schema_version=1,
                  status='Exact V22 quality source/numeric evidence candidate; no Git mutation',
                  decision='Binary empty-mask arm remains an isolated quality experiment; production default unchanged',
                  native_matcher_calls=9888, independent_audit_matcher_calls=0,
                  image_decodes_in_independent_audit=0, object_frame_pairs=2400,
                  file_count=len(files), total_bytes=sum(item['size_bytes'] for item in files),
                  failed_audit_preserved=True,
                  exclusions=['executables', 'object files', 'image pixels', 'private SMD/magnet files',
                              'heldout image data', 'Python bytecode', 'unexecuted timing stage'],
                  limitation='Numeric archives are review evidence; no heldout or industrial acceptance claim',
                  files=files)
    if args.verify:
        if not OUTPUT.is_file():
            raise ValueError('No existing inventory to verify')
        existing = json.loads(OUTPUT.read_text(encoding='utf-8'))
        if existing != result:
            raise ValueError('Inventory differs from current selection, metadata or selected bytes')
    else:
        if OUTPUT.exists() and not args.refresh:
            raise ValueError('Existing inventory requires --refresh')
        OUTPUT.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    # Re-read every selected byte after writing the inventory. The inventory
    # intentionally does not include itself, avoiding a circular self-hash.
    for item in files:
        path = ROOT/item['path']
        data = path.read_bytes()
        if len(data) != item['size_bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Selected bytes changed: '+item['path'])
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}))
    print('mode='+('verify_only' if args.verify else 'generate_and_verify'))
    print('inventory_sha256='+hashlib.sha256(OUTPUT.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
