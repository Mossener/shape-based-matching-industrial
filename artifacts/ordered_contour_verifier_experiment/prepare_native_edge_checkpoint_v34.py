"""Bind retained native-edge checks and select their finite public text evidence.

Does not rerun the solver, open real input payloads, or mutate the Git index.
The complete native build receipts remain in the retained run receipts, while
all build subdirectories (including compiler products) are excluded publicly.
"""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = 'bf0c402556e2c71a6ad9c9fc69f4222dcc631f79'
PRODUCTION = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
RUNS = ('native_edge_red_v1', 'native_edge_green_v1', 'native_edge_oracle_green_v1')
SOURCES = (
    '.gitattributes', 'native_edge_chains.hpp', 'native_edge_chains_test.cpp',
    'NATIVE_EDGE_DECISIONS_V1.json', 'run_native_edge_checks_v1.py',
    'native_edge_batch_v1.cpp', 'NATIVE_EDGE_BATCH_PROTOCOL_V1.json',
    'native_edge_oracle_fixtures_v1.py', 'run_native_edge_oracle_checks_v1.py',
    'independent_edge_oracle.py', 'native_compile_child_v1.py',
    'STATIC_NATIVE_EDGE_REVIEW_V1.md', 'NATIVE_EDGE_RESULTS_V1.md',
    'NATIVE_RESOURCE_SCOPE_SUPPLEMENT_V1.md', 'prepare_native_edge_checkpoint_v34.py',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(path, relative=False):
    data = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix() if relative else str(path),
                bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def read(path):
    return json.loads(path.read_bytes())


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def main():
    require(git('rev-parse', 'HEAD').decode().strip() == BASE, 'Unexpected checkpoint parent')
    require(not git('diff', '--cached', '--name-only'), 'Unrelated staged files present')
    receipts = {name: read(HERE / name / 'receipt.json') for name in RUNS}
    require(all(row['passed'] is True for row in receipts.values()), 'An actual run failed')
    red, green, oracle = (receipts[name] for name in RUNS)
    require(red['summary'] == dict(tests=36, checks=121, failures=114, errors=0), 'RED summary differs')
    require(green['summary'] == dict(tests=36, checks=229, failures=0, errors=0), 'GREEN summary differs')
    for name in RUNS[:2]:
        require((HERE / name / 'source/native_edge_chains_test.cpp').read_bytes()
                == (HERE / 'native_edge_chains_test.cpp').read_bytes(), 'Frozen test changed')
    require((HERE / RUNS[1] / 'source/native_edge_chains.hpp').read_bytes()
            == (HERE / 'native_edge_chains.hpp').read_bytes(), 'GREEN header changed')
    require(oracle['sources_stable'] is True, 'Oracle source stability failed')
    for row in green['source_pins_after'] + read(HERE / RUNS[2] / 'invocation.json')['source_pins']:
        require(pin(Path(row['path'])) == row, 'A current verified source changed')
    audit = read(HERE / RUNS[2] / 'audit/audit.json')
    require(audit['passed'] and audit['comparisons'] == 615 and audit['zero_skips']
            and audit['null_templates'] == 5 and audit['maximum_lcm_exceeds_uint64']
            and audit['independent_all_fields'], 'Incomplete independent comparison')
    require(audit['python_flags'] == dict(optimize=0, ignore_environment=1, debug=True), 'Audit flags differ')
    expected = HERE / RUNS[2] / 'fixtures/expected.jsonl'
    response = HERE / RUNS[2] / 'native_execution/stdout.txt'
    require(expected.read_bytes() == response.read_bytes(), 'Complete native records differ')
    for row in oracle['fixture_pins']:
        require(pin(Path(row['path'])) == row, 'Retained oracle fixture changed')
    production = []
    for name in git('ls-tree', '-r', '--name-only', PRODUCTION).decode().splitlines():
        if Path(name).parent == Path('.') and Path(name).name.startswith('line2Dup'):
            path = ROOT / name
            require(path.read_bytes() == git('show', PRODUCTION + ':' + name), 'Production source changed')
            production.append(pin(path))
    require(len(production) == 7, 'Production source set changed')
    acceptance = HERE / 'SYNTHETIC_NATIVE_EDGE_ACCEPTANCE_V1.json'
    write_new(acceptance, dict(schema='ordered_contour_native_edge_acceptance_v1',
        synthetic_correctness_accepted=True, production_baseline=PRODUCTION,
        checks=[pin(HERE / name / 'receipt.json') for name in RUNS],
        independent_audit=pin(HERE / RUNS[2] / 'audit/audit.json'),
        same_tests_red_green=True, literal_tests=36, independent_grids=615,
        complete_expected=pin(expected), complete_response=pin(response),
        production_files_unchanged=production, real_image_quality_tested=False,
        native_speed_benchmarked=False, real_pixel_input_freeze=False,
        production_promotion=False, heldout_remains_sealed=True))
    selected = [HERE / name for name in SOURCES] + [acceptance, ROOT / 'docs/optimization_versions.md']
    allowed = {'.py', '.hpp', '.cpp', '.json', '.jsonl', '.txt'}
    for run in RUNS:
        for path in sorted((HERE / run).rglob('*')):
            require(not path.is_symlink(), 'Run contains symlink')
            if not path.is_file() or 'build' in path.relative_to(HERE / run).parts:
                continue
            require(path.suffix in allowed, 'Unexpected public run suffix')
            selected.append(path)
    selected = sorted(set(selected), key=lambda path: path.relative_to(ROOT).as_posix())
    rows = [pin(path, relative=True) for path in selected]
    selection = HERE / 'PUBLISH_SELECTION_V34.json'
    write_new(selection, dict(schema='ordered_contour_native_edge_checkpoint_v34',
        base_commit=BASE, scope='Supplied-label native chains; synthetic correctness only.',
        host_metadata='Retained receipts include workspace/toolchain absolute paths and versions, as in V33.',
        excluded='All build subdirectories; binaries; private images; real raw/bank payloads; inventory/candidate successors.',
        file_count=len(rows), selected_bytes=sum(row['bytes'] for row in rows), files=rows))
    pathspec = HERE / 'PUBLISH_PATHSPEC_V34.nul'
    with pathspec.open('xb') as stream:
        stream.write(b'\0'.join([row['path'].encode() for row in rows]
                               + [selection.relative_to(ROOT).as_posix().encode()]) + b'\0')
    print(json.dumps(dict(accepted=True, selection=pin(selection), file_count=len(rows),
                          selected_bytes=sum(row['bytes'] for row in rows))))


if __name__ == '__main__':
    main()
