"""Exact V20 training/planning milestone selection; excludes unfinished quality."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DEST=HERE/'TRAINING_PUBLISH_SELECTION.json'
TOP=['DESIGN.md','PROTOCOL.json','PRIVATE_SOURCE_FREEZE.json','INPUT_CLOSURE.json','IMPLEMENTATION_ORIGIN.json',
     'README.md','STATIC_RESULTS.md','NATIVE_PRETRAIN_RESULTS.md','NATIVE_PRETRAIN_SUMMARY.json','TRAINING_RESULTS.md',
     'freeze_private_sources.py','native_provenance.py','silhouette_source.hpp','empty_mask_policy.hpp',
     'empty_mask_source_test.cpp','silhouette_eval.cpp','build_adapter.py','run_synthetic.py','run_stage.py',
     'prepare_input_closure.py','prepare_origin_manifest.py','summarize_pretraining.py','summarize_training.py',
     'test_successor_contract.py','test_private_source_isolation.py','test_native_provenance.py','test_feature_count_contract.py',
     'private_source_create_v1.json','input_closure_create_v1.json','input_verify_static_v1.json',
     'prepare_training_publish_selection.py']
DIRECTORIES=['private_v11','frozen_helpers','frozen_inputs','synthetic_fixtures',
             'input_contract_red_v1','input_contract_green_v1','private_source_test_green_v1','native_provenance_literals_v1',
             'actual_count_contract_red_v1','actual_count_contract_green_v1',
             'build_synthetic_red_v1','build_synthetic_green_v1','build_adapter_v1',
             'run_synthetic_red_v1','run_synthetic_green_v1','run_training_v1','run_plan_v1']
FORBIDDEN={'.exe','.o','.obj','.pyc','.pyo','.png','.bmp','.jpg','.jpeg','.webp','.tif','.tiff','.gif','.smd','.dll','.a','.lib'}


def need(value,message):
    if not value:
        raise ValueError(message)


def pin(path):
    path=Path(path).resolve(strict=True);need(path.is_relative_to(ROOT),'Publish path outside workspace');data=path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def main():
    need(not DEST.exists(),'Selection must be fresh')
    paths={HERE/name for name in TOP};excluded=[]
    for name in DIRECTORIES:
        directory=HERE/name;need(directory.is_dir(),'Missing completed milestone directory '+name)
        for path in directory.rglob('*'):
            if not path.is_file():
                continue
            if path.name=='.gitignore' or '__pycache__' in path.parts or path.suffix.lower() in FORBIDDEN:
                excluded.append(path.relative_to(ROOT).as_posix());continue
            paths.add(path)
    # Root-owned independent numeric parser, tests and immutable receipts are
    # part of this milestone. No images or runtime binaries belong here.
    independent=ROOT/'artifacts/independent_reviews/empty_mask_training_v1'
    need(independent.is_dir(),'Root independent training/planning evidence missing')
    for path in independent.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix.lower() not in FORBIDDEN:
            paths.add(path)
    for path in paths:
        need(path.is_file() and path.suffix.lower() not in FORBIDDEN and '__pycache__' not in path.parts,'Forbidden selected artifact '+str(path))
        need(not path.name.startswith(('quality_','test_quality_','prepare_quality_','build_quality','run_quality')),'Unfinished quality work must stay outside V20')
    selected={p.resolve() for p in paths}
    checked=[]
    for name in ['build_synthetic_red_v1','build_synthetic_green_v1','build_adapter_v1']:
        manifest=json.loads((HERE/name/'build_manifest.json').read_text());need(manifest['passed'] is True,'Incomplete build in milestone')
        # Actual -MD occurrences remain complete in the manifest/.d evidence.
        # SDK/compiler external dependencies stay pinned prerequisites; they
        # are not vendored into this repository or this publish selection.
        source_pins=list(manifest['project_sources'])
        source_pins += [pin for unit in manifest['dependency_units'] for pin in unit['dependencies']]
        for record in source_pins:
            path=Path(record['path']).resolve(strict=True)
            if path.is_relative_to(ROOT):
                need(path in selected,'Participating repo build source/dependency omitted '+str(path))
                actual=pin(path);need(actual['sha256']==record['sha256'] and actual['bytes']==record['bytes'],'Completed native build source changed')
        checked.append(dict(directory=name,actual_repo_source_and_dependency_occurrences=sum(Path(r['path']).resolve().is_relative_to(ROOT) for r in source_pins)))
    files=[pin(path) for path in sorted(paths,key=lambda p:p.relative_to(ROOT).as_posix())]
    need(len(files)==len({r['path'] for r in files}),'Duplicate publish member')
    result=dict(version='empty_mask_training_planning_v20_exact_selection_v1',milestone='Complete trainable binary-empty-selection-mask templates, independent serialized feature/pose audit and common union padding; no accuracy or speed claim',
                protocol_sha256=hashlib.sha256((HERE/'PROTOCOL.json').read_bytes()).hexdigest(),
                bank_freeze_sha256=hashlib.sha256((HERE/'run_training_v1/BANK_FREEZE.json').read_bytes()).hexdigest(),
                common_padding_freeze_sha256=hashlib.sha256((HERE/'run_plan_v1/COMMON_PADDING_FREEZE.json').read_bytes()).hexdigest(),
                files=files,file_count=len(files),selected_bytes=sum(r['bytes'] for r in files),checked_completed_builds=checked,
                explicitly_excluded_existing_artifacts=sorted(excluded),
                exclusion_policy='All unfinished quality-stage code/evidence; image/SMD/runtime/object/cache files; transient ignored outputs. Compiler/SDK dependency bytes are pinned external prerequisites, not vendored.',
                root_owns_staging_commits_and_push=True,dataset_image_decodes_by_selection=0,matcher_calls=0)
    DEST.write_text(json.dumps(result,indent=2)+'\n')
    # Verify selected bytes once more after selection assembly.
    for record in files:
        need(pin(ROOT/record['path'])==record,'Selected artifact changed during manifest assembly')
    print(json.dumps(dict(passed=True,file_count=len(files),selected_bytes=result['selected_bytes'],selection_sha256=hashlib.sha256(DEST.read_bytes()).hexdigest(),dataset_image_decodes=0,matcher_calls=0)))


if __name__=='__main__':
    main()
