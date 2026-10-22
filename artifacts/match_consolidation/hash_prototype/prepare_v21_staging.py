import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path.cwd().resolve()
HERE=ROOT/'artifacts/match_consolidation/hash_prototype'
OUTPUT=HERE/'build'
INVENTORIES=[ROOT/'artifacts/match_consolidation/hash_prototype/PUBLICATION_INVENTORY_V21.json',
             ROOT/'artifacts/local_center_optimization/v11_candidate_experiment_v2/PUBLICATION_INVENTORY_V2.json']
TEXT_DOCS=['.gitattributes','README.md','docs/optimization_versions.md']


def git(*args,check=True,data=None):
    result=subprocess.run(['git',*args],cwd=ROOT,input=data,capture_output=True)
    if check and result.returncode:
        raise ValueError(result.stderr.decode(errors='replace')+result.stdout.decode(errors='replace'))
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',action='store_true')
    args=parser.parse_args()
    files={}
    inventory_pins=[]
    for manifest in INVENTORIES:
        value=json.loads(manifest.read_bytes())
        if len(value['files'])!=value['file_count']:
            raise ValueError('Wrong inventory count')
        for record in value['files']:
            if record['path'] in files:
                raise ValueError('Duplicate selection')
            files[record['path']]=record
        data=manifest.read_bytes()
        inventory_pins.append(dict(path=manifest.relative_to(ROOT).as_posix(),
                                   sha256=hashlib.sha256(data).hexdigest()))
        files[manifest.relative_to(ROOT).as_posix()]=dict(path=manifest.relative_to(ROOT).as_posix(),
            size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    review=ROOT/'artifacts/independent_reviews/direct16_correctness_v2/review_publication_scope_v21.json'
    if not review.is_file():
        raise ValueError('Separate publication scope review required')
    receipt=json.loads(review.read_bytes())
    if (receipt.get('passed') is not True or receipt.get('inventories')!=inventory_pins or
            receipt.get('stage_script_sha256')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
        raise ValueError('Separate publication scope review does not bind current inventories/helper')
    data=review.read_bytes()
    files[review.relative_to(ROOT).as_posix()]=dict(path=review.relative_to(ROOT).as_posix(),
        size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    for name,record in files.items():
        path=(ROOT/name).resolve(strict=True)
        if not path.is_relative_to(ROOT) or path.suffix.lower() in (
                '.exe','.o','.obj','.png','.jpg','.jpeg','.bmp','.gif','.smd','.pyc','.dll','.a'):
            raise ValueError('Unsafe publication selection '+name)
        data=path.read_bytes()
        if len(data)!=record['size_bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
            raise ValueError('Stale selected source '+name)
    paths=sorted(set(files)|set(TEXT_DOCS))
    selection=dict(files=list(files.values()),text_docs=TEXT_DOCS,total_paths=len(paths),
                   total_evidence_bytes=sum(r['size_bytes'] for r in files.values()),
                   stage_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT/'v21_selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    if not args.stage:
        print(json.dumps({k:v for k,v in selection.items() if k!='files'}));return
    staged=git('diff','--cached','--name-only','-z').stdout
    if staged:
        raise ValueError('Refuse to mix preexisting staged changes')
    listfile=OUTPUT/'v21_paths.nul'
    listfile.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0')
    git('add','-f','--pathspec-from-file='+str(listfile),'--pathspec-file-nul')
    actual=git('diff','--cached','--name-only','-z').stdout.decode().rstrip('\0').split('\0')
    if set(actual)!=set(paths):
        raise ValueError('Unexpected staged path set')
    request=''.join(':'+name+'\n' for name in files).encode()
    batch=git('cat-file','--batch',data=request).stdout
    at=0
    for name,record in files.items():
        end=batch.index(b'\n',at)
        header=batch[at:end].decode().split()
        if len(header)!=3 or header[1]!='blob':
            raise ValueError('Invalid staged blob '+name)
        length=int(header[2]);data=batch[end+1:end+1+length]
        if len(data)!=record['size_bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
            raise ValueError('Staged bytes differ '+name)
        at=end+length+2
    if at!=len(batch):
        raise ValueError('Trailing staged blob data')
    check=git('diff','--cached','--check',check=False)
    (OUTPUT/'v21_diff_check.txt').write_bytes(check.stdout+check.stderr)
    if check.returncode:
        raise ValueError('Staged whitespace check failed; see v21_diff_check.txt')
    git('diff','--exit-code','b25df46f6ddf9c24fb43f5836f1414dc38c8caed','--',
        'line2Dup.cpp','line2Dup.h','line2Dup_local.hpp','line2Dup_matches.hpp',
        'line2Dup_response.hpp','line2Dup_search.hpp','line2Dup_spread.hpp','MIPP')
    result=dict(passed=True,staged_paths=len(paths),exact_evidence_blobs=len(files),
                evidence_bytes=selection['total_evidence_bytes'],whitespace_passed=True,
                production_v11_unchanged=True,selection_sha256=hashlib.sha256((OUTPUT/'v21_selection.json').read_bytes()).hexdigest())
    (OUTPUT/'v21_staged_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
