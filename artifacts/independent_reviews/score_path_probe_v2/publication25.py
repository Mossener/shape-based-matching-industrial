"""Bounded V25 publication preparation. Standard library, no Git or images."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PROBE=ROOT/'artifacts/quality_failure_analysis/score_path_probe_v2'
SCOPES=(PROBE,HERE)
PROBE_SOURCES='''build_probe.py DESIGN.md geometry.py geometry_green_boundaries.txt
geometry_green_v2.txt geometry_red.txt geometry_red_boundaries.txt geometry_red_v2.txt
phase2.cpp PHASE2_BUDGET_PROPOSAL_V1.json PHASE2_BUDGET_PROPOSAL_V2.json
PHASE2_INPUTS_V1.json prepare_budget.py pure_sources_green_v3.txt root_check_synthetic.py
ROOT_STATIC_REVIEW_20261022.md ROOT_SYNTHETIC_RECEIPT_20261022.json RESULTS_PHASE2_V25.md run_probe.py
source_contract.py source_contract_green.txt source_contract_green_build_inputs.txt
source_contract_red.txt source_contract_red_assertions.txt source_contract_red_build_inputs.txt
test_geometry.py test_source_contract.py source_check_v1/result.json'''.split()
AUDIT_SOURCES='''all_green_v1.txt all_green_v2.txt all_green_v3.txt all_green_v4.txt
audit_main.py bank_declarations_red.txt DESIGN.md evidence2.py evidence_red.txt
fullframe_red.txt map_stream_red.txt numeric2.py numeric_green_v1.txt numeric_red.txt
numeric_trace_green_v2.txt numeric_trace_green_v3.txt README.md
run_numeric_audit_20261022_v1_console.txt run_numeric_audit_20261022_v2_console.txt
SOURCE_REVIEW.md test_driver.py test_evidence2.py test_numeric2.py test_traces.py
trace_green_v1.txt trace_red.txt traces.py publication25.py test_publication25.py
publication_red.txt publication_green.txt PUBLICATION_SCOPE.md
run_numeric_audit_20261022_v1/.gitignore run_numeric_audit_20261022_v1/failure.json
run_numeric_audit_20261022_v2/.gitignore run_numeric_audit_20261022_v2/result.json
run_numeric_audit_20261022_v2/diagnostics.csv'''.split()
BUILD_FILES='''adapter_before.d adapter.d attempts.json build_manifest.json
compile.stderr compile.stdout dependency_before.stderr dependency_before.stdout
link.stderr link.stdout generated_preprocess.hpp PREPROCESS_EXTRACTION.json'''.split()
STAGES=(('probe_selftest_red_coarse_v1','selftest','coarse'),('probe_selftest_red_local_v1','selftest','local'),('probe_selftest_red_winner_v1','selftest','winner'),('probe_selftest_green_v1','selftest','none'),('probe_phase2_v1','phase2','none'))
ALLOWED={'.py','.cpp','.hpp','.md','.json','.txt','.csv','.gz','.d','.stdout','.stderr'}
ARCHIVES={name+'.csv.gz' for name in ('jobs','feature_vectors','native_cells','local_maxima','physical_anchors','parent_links','occurrences','fullclass_nms_assignment')}


def need(condition,message):
    if not condition:raise ValueError(message)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def member(path,root,scope_roots):
    root=Path(root).resolve();scopes=tuple(Path(value).resolve() for value in scope_roots);path=Path(path).resolve(strict=True)
    need(all(scope.is_relative_to(root) for scope in scopes) and any(path.is_relative_to(scope) for scope in scopes),'Publication member outside approved roots')
    parts={part.lower() for part in path.relative_to(root).parts}
    need(not(parts&{'__pycache__','.git','dataset','datasets','private'}) and not any(part.startswith('private_') for part in parts),'Dataset/private/cache publication member forbidden')
    need(path.is_file() and (path.suffix.lower() in ALLOWED or path.name=='.gitignore'),'Binary/image/template publication member forbidden')
    if path.suffix.lower()=='.gz':need(path.name in ARCHIVES and path.parent.name=='native' and path.parent.parent.name=='probe_phase2_v1','Only fixed audited numeric CSV gzip streams may be published')
    return path


def verify_pin(value,root,scope_roots):
    need(set(value)=={'path','bytes','sha256'},'Publication stage pin schema differs');path=member(value['path'],root,scope_roots);data=path.read_bytes()
    need(len(data)==value['bytes'] and hashlib.sha256(data).hexdigest()==value['sha256'],'Frozen publication bytes differ');return path


def records(paths,root,scope_roots):
    root=Path(root).resolve();paths=[member(path,root,scope_roots) for path in paths]
    need(len(paths)==len(set(paths)),'Duplicate publication member')
    result=[]
    for path in sorted(paths,key=lambda value:value.relative_to(root).as_posix()):
        data=path.read_bytes();result.append(dict(path=path.relative_to(root).as_posix(),size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    return result


def selected(extras=()):
    paths=[PROBE/name for name in PROBE_SOURCES]+[HERE/name for name in AUDIT_SOURCES]
    for name in ('probe_build_red_v1','probe_build_green_v1'):paths.extend(PROBE/name/file for file in BUILD_FILES)
    for name,mode,fault in STAGES:
        directory=PROBE/name;freeze_path=directory/'PHASE2_STAGE_FREEZE.json';freeze=read(freeze_path)
        need(freeze.get('completed') is True and freeze.get('stage')==mode and freeze.get('fault')==fault,'Publication includes incomplete/wrong native stage')
        verify_pin(freeze['build_manifest'],ROOT,SCOPES);verify_pin(freeze['input_plan'],ROOT,SCOPES)
        for value in freeze['files']+freeze['execution_files']+[freeze['reservation']]:paths.append(verify_pin(value,ROOT,SCOPES))
        paths.append(freeze_path)
    completed=HERE/'run_numeric_audit_20261022_v2/result.json';data=completed.read_bytes()
    need(hashlib.sha256(data).hexdigest()=='1710a1b3fe934ad73b8484b24527a99c2dddcdc6c20cca82aa2c3860ba724ea8','Immutable independent audit result differs')
    result=json.loads(data);need(result.get('passed') is True and result.get('dataset_image_bytes_opened')==0 and result.get('serialized_template_bytes_opened')==0,'Independent audit scope differs')
    for value in result['source_pins']+[result['diagnostics']]:verify_pin(value,ROOT,SCOPES)
    for value in extras:
        path=Path(value);need(not path.is_absolute() and '..' not in path.parts,'Extra publication member must be explicit repository-relative path')
        paths.append(ROOT/path)
    return paths


def make_inventory(extras=()):
    values=records(selected(extras),ROOT,SCOPES)
    return dict(version='V25',scope='Completed fixed Phase2 native traces, all synthetic gates and independent numeric audit; explicit two-root base before separately reviewed classifier additions',file_count=len(values),total_bytes=sum(value['size_bytes'] for value in values),excluded='Dataset/private images/SMD/template banks, compiler/SDK/runtime and exe/object/dll/cache files, all existing V24 members, adjacent unpublished hash/full-matcher experiments; external provenance references are not recursively copied',files=values)


def boundary(inventory,inventory_path):
    included={ROOT/value['path'] for value in inventory['files']};excluded=[];pending=[]
    for scope in SCOPES:
        for path in sorted(scope.rglob('*')):
            if not path.is_file() or path in included:continue
            if path.name.startswith(('PUBLICATION_INVENTORY_V25','PUBLICATION_BOUNDARY_V25')):continue
            try:member(path,ROOT,SCOPES)
            except ValueError:excluded.append(dict(path=path.relative_to(ROOT).as_posix(),size_bytes=path.stat().st_size))
            else:pending.append(path.relative_to(ROOT).as_posix())
    data=inventory_path.read_bytes()
    documents=[]
    for path in (ROOT/'README.md',ROOT/'docs/optimization_versions.md'):
        contents=path.read_bytes();documents.append(dict(path=str(path),bytes=len(contents),sha256=hashlib.sha256(contents).hexdigest()))
    return dict(passed=True,kind='V25 base publication boundary',inventory=dict(path=inventory_path.relative_to(ROOT).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()),member_count=inventory['file_count'],member_bytes=inventory['total_bytes'],scope_roots=[value.relative_to(ROOT).as_posix() for value in SCOPES],by_root={scope.relative_to(ROOT).as_posix():dict(files=sum(path.is_relative_to(scope) for path in included),bytes=sum(value['size_bytes'] for value in inventory['files'] if (ROOT/value['path']).is_relative_to(scope))) for scope in SCOPES},numeric_gzip_members=sum(value['path'].endswith('.csv.gz') for value in inventory['files']),excluded_known_local_files=excluded,excluded_known_local_bytes=sum(value['size_bytes'] for value in excluded),pending_explicit_scope_review=pending,input_dependency_method='Retain path/hash declarations in completed receipts and manifests; never recursively follow them into V24/private/SDK/runtime/adjacent experimental trees.',root_document_pins_separate_from_inventory=documents,external_members_added=[],inventory_excludes_itself=True,inventory_excludes_boundary_receipt=True,git_commands=0,native_processes_started=0,image_bytes_opened=0,serialized_template_bytes_opened=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--verify',action='store_true');parser.add_argument('--extra-member',action='append',default=[]);parser.add_argument('--inventory',type=Path,default=PROBE/'PUBLICATION_INVENTORY_V25_BASE.json');parser.add_argument('--boundary',type=Path,default=PROBE/'PUBLICATION_BOUNDARY_V25_BASE.json');args=parser.parse_args()
    inventory_path=args.inventory.resolve();boundary_path=args.boundary.resolve();need(inventory_path.parent==PROBE and boundary_path.parent==PROBE and inventory_path!=boundary_path,'Publication metadata must remain in Phase2 probe root')
    value=make_inventory(args.extra_member)
    if args.verify:need(read(inventory_path)==value,'Publication member list/bytes changed');need(read(boundary_path)==boundary(value,inventory_path),'Publication boundary changed')
    else:
        for path in (inventory_path,boundary_path):need(not path.exists(),'Fresh publication metadata required')
        inventory_path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');boundary_path.write_text(json.dumps(boundary(value,inventory_path),indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:item for key,item in value.items() if key!='files'}))


if __name__=='__main__':main()
