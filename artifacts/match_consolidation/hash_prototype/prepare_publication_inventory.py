"""Exact completed numerical/source publication selection; no images or native."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNS = (
    'build_20261022_capture_v1', 'build_20261022_replay_v1',
    'run_20261021_dependency_red', 'run_20261021_hash_green',
    'run_20261021_hash_red', 'run_20261021_hash_red_semantic',
    'run_20261021_hook_green', 'run_20261021_hook_red',
    'run_20261021_manifest_source_green', 'run_20261021_manifest_source_red',
    'run_20261021_mutant_maximum', 'run_20261021_mutant_no_finite',
    'run_20261021_mutant_no_sort', 'run_20261021_mutant_no_zero_fallback',
    'run_20261021_mutant_omit_x', 'run_20261021_mutant_trace_trailing',
    'run_20261021_real_closure_green', 'run_20261021_real_closure_red',
    'run_20261021_trace_green', 'run_20261021_trace_red',
    'run_20261022_capture_actual85', 'run_20261022_dependency_alias_green',
    'run_20261022_dependency_green', 'run_20261022_real_adapter_green',
    'run_20261022_real_dependency_green', 'run_20261022_replay_measure_v1',
    'run_20261022_replay_summary_green', 'run_20261022_replay_summary_green_final',
    'run_20261022_replay_summary_red', 'run_20261022_replay_verify_v1',
    'run_20261022_scope_smoke')
TEXT = {'.cpp','.h','.hpp','.hxx','.py','.ps1','.txt','.json','.md','.csv','.tsv','.d','.sha256'}
DEST = HERE/'PUBLICATION_INVENTORY_V21.json'


def choose(path):
    if not path.is_file() or '__pycache__' in path.parts or path==DEST:
        return False
    if path.suffix=='.bin':
        return (path.parent.parent==HERE/'run_20261022_capture_actual85' and
                path.name in ('capture.bin','reference.bin'))
    return path.suffix in TEXT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-candidate',action='store_true')
    args=parser.parse_args()
    if DEST.exists() and not args.refresh_candidate:
        raise ValueError('Existing inventory requires explicit candidate refresh')
    candidates = list(HERE.iterdir())
    for name in RUNS:
        directory=HERE/name
        if not directory.is_dir():
            raise ValueError('Missing completed evidence '+name)
        candidates += list(directory.rglob('*'))
    candidates += list((ROOT/'artifacts/independent_reviews/consolidation_trace_v1').iterdir())
    candidates += [ROOT/'docs/superpowers/plans'/name for name in
                   ('2026-10-21-hash-consolidation-prototype.md','2026-10-21-immutable-consolidation-capture.md')]
    records=[]
    for path in sorted({p.resolve() for p in candidates if choose(p)}):
        data=path.read_bytes()
        records.append(dict(path=path.relative_to(ROOT).as_posix(),size_bytes=len(data),
                            sha256=hashlib.sha256(data).hexdigest()))
    if sum(r['path'].endswith('.bin') for r in records)!=50:
        raise ValueError('Exactly 25 numeric capture/reference pairs required')
    output=dict(schema_version=1,status='Exact completed source/numeric candidates; parent owns staging',
                production_changed=False,matcher_calls_in_selection=0,image_decodes=0,
                file_count=len(records),total_bytes=sum(r['size_bytes'] for r in records),files=records,
                exclusions=['compiler binaries','objects','image pixels','private magnet inputs','Python bytecode'],
                limitation='Local executable/tool/header pins retained in receipts; external build cache not redistributed')
    with DEST.open('w' if args.refresh_candidate else 'x') as stream:
        stream.write(json.dumps(output,indent=2)+'\n')
    for record in records:
        data=(ROOT/record['path']).read_bytes()
        if len(data)!=record['size_bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
            raise ValueError('Selected bytes changed')
    print(json.dumps({k:v for k,v in output.items() if k!='files'}))


if __name__=='__main__':
    main()
