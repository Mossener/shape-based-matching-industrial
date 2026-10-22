"""Freeze successor-owned actual V11 Git bytes and verified parent helpers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REV = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
CORE = ['line2Dup.cpp', 'line2Dup.h', 'line2Dup_local.hpp', 'line2Dup_matches.hpp',
        'line2Dup_response.hpp', 'line2Dup_search.hpp', 'line2Dup_spread.hpp']
HELPERS = {
    'artifacts/public_evaluation/tless_eval.cpp': 'c9e4016d1cd7ad6ce37d49bc04f49f1f3d496573a0047a9d1b8da951eb7204ef',
    'artifacts/public_evaluation/eval_metrics.hpp': '1339092b5fbf2f5283dced01fc0b74eea467074223943d8248b89b6e48249de3',
    'artifacts/obj8_padding_experiment/padding_plan.hpp': '8310a76c3e2b167c94f083337d77979485d6bc3174a5fa656015efac2e12f361',
}
PARENT = ROOT/'artifacts/silhouette_template_experiment'
PARENT_FREEZE_SHA = '5a6512dfe187ee66312935de1df26fb6eac99dd06ea1113d497c7e3de1ee2de2'


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def source_bytes():
    mipp = git('ls-tree', '-r', '--name-only', REV, '--', 'MIPP').decode().splitlines()
    require(len(mipp) == len(set(mipp)) == 16 and all(p.startswith('MIPP/') and '..' not in Path(p).parts for p in mipp), 'Frozen MIPP member set')
    return {name: git('show', REV+':'+name) for name in CORE+mipp}


def private_flags(private):
    return ['-std=c++17', '-O3', '-mssse3', '-msse4.1', '-fopenmp', '-Wall', '-Wextra',
            '-Wno-sign-compare', '-Wno-unused-function', '-I'+str(private), '-I'+str(private/'MIPP')]


def verify(private, manifest):
    require(manifest['git_revision'] == REV, 'Frozen private Git revision changed')
    committed = source_bytes()
    require(set(manifest['files']) == set(committed), 'Frozen source manifest member set changed')
    observed = {p.relative_to(private).as_posix() for p in private.rglob('*') if p.is_file()}
    require(observed == set(manifest['files']), 'Frozen private file member set changed')
    for name, expected in manifest['files'].items():
        data = (private/name).read_bytes()
        require(data == committed[name] and digest(data) == expected['sha256'] and len(data) == expected['bytes'], 'Frozen private source SHA/size changed: '+name)
    helpers = HERE/'frozen_helpers'
    require({p.name for p in helpers.iterdir() if p.is_file()} == set(manifest['helpers']), 'Frozen helper member set changed')
    for name, expected in manifest['helpers'].items():
        data = (helpers/name).read_bytes()
        require(digest(data) == expected['sha256'] == HELPERS[expected['source']] and len(data) == expected['bytes'], 'Frozen helper SHA/size changed: '+name)
    require(manifest['compile_flags'] == private_flags(private), 'Private compile include flags changed')
    require(manifest['core_translation_unit'] == str(private/'line2Dup.cpp'), 'Private translation unit changed')
    return dict(manifest, passed=True, image_files_opened=0, image_decodes=0, matcher_calls=0)


def create():
    private = HERE/'private_v11'
    helpers = HERE/'frozen_helpers'
    require(not private.exists() and not helpers.exists() and not (HERE/'PRIVATE_SOURCE_FREEZE.json').exists(), 'Source freeze must be new')
    encoded = source_bytes()
    helper_bytes = {}
    parent_data = (PARENT/'PRIVATE_SOURCE_FREEZE.json').read_bytes()
    require(digest(parent_data) == PARENT_FREEZE_SHA, 'Frozen parent source manifest changed')
    parent = json.loads(parent_data)
    for path, expected in HELPERS.items():
        data = (PARENT/'frozen_helpers'/Path(path).name).read_bytes()
        require(digest(data) == expected == parent['helpers'][Path(path).name]['sha256'], 'Frozen parent helper pin changed: '+path)
        helper_bytes[Path(path).name] = (path, data)
    require(set(encoded) == set(parent['files']) and all(digest(data) == parent['files'][name]['sha256'] for name,data in encoded.items()),
            'Actual Git V11 bytes differ from frozen source-only pins')
    for name, data in encoded.items():
        path = private/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    helpers.mkdir()
    for name, (_, data) in helper_bytes.items():
        (helpers/name).write_bytes(data)
    files = {n: dict(sha256=digest(b), bytes=len(b)) for n, b in encoded.items()}
    helper_records = {n: dict(source=p, sha256=digest(b), bytes=len(b)) for n, (p, b) in helper_bytes.items()}
    manifest = dict(git_revision=REV, file_count=len(files), files=files, helpers=helper_records,
                    private_sha256=digest(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()),
                    core_translation_unit=str(private/'line2Dup.cpp'), compile_flags=private_flags(private),
                    adapter_include='frozen_helpers/tless_eval.cpp',
                    source_policy='Successor-owned actual Git V11 bytes and transitive MIPP; unchanged helpers copied from SHA-verified source-only freeze; no mutable root core',
                    parent_source_freeze_sha256=PARENT_FREEZE_SHA,
                    image_files_opened=0, matcher_calls=0)
    (HERE/'PRIVATE_SOURCE_FREEZE.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return verify(private, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--create', action='store_true')
    group.add_argument('--verify', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Output must be new')
    try:
        result = create() if args.create else verify(HERE/'private_v11', json.loads((HERE/'PRIVATE_SOURCE_FREEZE.json').read_text()))
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(dict(passed=True, file_count=result['file_count'], image_decodes=0, matcher_calls=0)))
    except Exception as error:
        args.output.write_text(json.dumps(dict(incomplete=True, reason=str(error), image_decodes=0, matcher_calls=0), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
