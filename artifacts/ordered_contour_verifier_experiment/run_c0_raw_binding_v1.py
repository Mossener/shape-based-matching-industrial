"""One guarded full C0 numeric replay; never launches a matcher or compiler."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
OTHER = HERE.parent/'rgb_stratified_features_experiment'
GUARD = OTHER/'execution_guard.py'


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    if len(sys.argv) != 2 or not re.fullmatch('[a-z][a-z0-9_]{0,59}',sys.argv[1]):
        raise SystemExit('usage: run_c0_raw_binding_v1.py fresh_name')
    name = sys.argv[1]
    out,payload = HERE/name,HERE/(name+'_payload')
    if out.exists() or payload.exists():
        raise ValueError('Fresh guard/payload directories required')
    out.mkdir()
    archive = out/'source_archive'; archive.mkdir()
    paths = [HERE/'prepare_c0_raw_binding_v1.py',HERE/'c0_numeric_binding_v1.py',
             HERE/'prepare_c0_payload_inventory_v2.py',OTHER/'independent_quality/evidence.py',
             OTHER/'independent_quality/numeric.py',GUARD,Path(__file__),Path(sys.executable),
             HERE/'C0_INPUT_PLAN_V1.json',HERE/'c0_inventory_hash_v2_payload/inventory.json']
    before = [pin(path) for path in paths]
    archived = []
    for index,path in enumerate(paths[:-3]):
        target = archive/f'{index:02d}_{path.name}'
        target.write_bytes(path.read_bytes()); archived.append((path,target))
    command = [sys.executable,'-E','-B',str(HERE/'prepare_c0_raw_binding_v1.py'),payload.name]
    invocation = dict(schema='c0_raw_binding_guard_invocation_v1',command=command,cwd=str(HERE),
        source_and_bootstrap_pins=before,
        source_archive_semantics='Before-execution copies; actual sources execute in workspace and are rechecked.',
        maximum_seconds=900,maximum_observed_peak_working_set_bytes=536870912,
        maximum_output_bytes=16777216,minimum_free_disk_bytes=100663296,
        payload_scope='4809 exact C0 numeric payloads; datasets, images, bank payloads and native calls forbidden')
    (out/'invocation.json').write_text(json.dumps(invocation,indent=2)+'\n',encoding='utf-8')
    spec = importlib.util.spec_from_file_location('_c0_raw_binding_guard_v1',GUARD)
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    result = guard.run_guarded(command,dict(os.environ),HERE,payload,out/'execution',
        maximum_seconds=900,maximum_rss_bytes=536870912,maximum_output_bytes=16777216,
        minimum_free_bytes=100663296)
    accepted = bool(result['passed']); observed = None
    if accepted:
        observed = json.loads((payload/'result.json').read_bytes())
        accepted = (observed['passed'] is True and observed['frames'] == 400 and
            observed['object_frame_combinations'] == 2400 and observed['raw_rows'] == 457279 and
            observed['zero_raw_combinations'] == 390 and observed['original_allGT_identity_count'] == 215 and
            observed['payload_unique_files_read'] == observed['payload_end_hash_rechecks'] == 4809 and
            observed['original_allGT_identities_exact'] is True and
            observed['python_flags'] == dict(optimize=0,ignore_environment=1,debug=True) and
            observed['dataset_files_opened'] == observed['image_reads'] == observed['native_calls'] == 0 and
            observed['real_pixel_input_freeze'] is False and observed['production_promotion'] is False)
    stable = before == [pin(path) for path in paths]
    archive_equal = all(source.read_bytes() == target.read_bytes() for source,target in archived)
    accepted = bool(accepted and stable and archive_equal)
    receipt = dict(schema='c0_raw_binding_guard_receipt_v1',passed=accepted,
        source_and_bootstrap_pins=before,sources_stable=stable,source_archive_equal=archive_equal,guard=result,
        result=pin(payload/'result.json') if observed is not None else None,
        inherited_GT_projection_only=True,real_pixel_input_freeze=False,
        quality_improvement_claim=False,performance_claim=False,production_promotion=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=accepted,elapsed_seconds=result['elapsed_seconds'],
        peak_working_set_bytes=result['peak_rss_bytes'],result=receipt['result'])))
    return 0 if accepted else 1


if __name__ == '__main__':
    raise SystemExit(main())
