"""Preserve isolated source-only GREEN and deliberately weakened-source RED."""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
SOURCES=['numeric.py','evidence.py','contract.py','quality_audit.py','test_quality_audit.py',
         'run_audit.py','test_run_audit.py','run_selftest.py','SOURCE_ORIGINS.json','README.md','MIGRATION_PLAN.md','SOURCE_VALIDATION.md',
         'SOURCE_ORIGINS_V1.json','test_shared_numeric.py','run_successor_tests.py','SUCCESSOR_V2.md']
MUTANTS=[
    ('ignore_shared_pin_conflict','contract.py',"need(pin==shared,'shared inherited closure pin conflicts')",'pass',
     'SharedNumericTests.test_conflicting_hash_or_size_is_rejected'),
    ('allow_other_numeric_duplicates','contract.py',"else:need(path not in result,'duplicate declared numeric pin')",'else:pass',
     'SharedNumericTests.test_only_exact_inherited_role_is_shared'),
    ('reset_shared_role_counter','contract.py','shared_count+=1','shared_count=1',
     'SharedNumericTests.test_three_occurrences_are_rejected'),
    ('ignore_fixed_shared_hash','contract.py',"shared['sha256']==INHERITED_CLOSURE_SHA",'True',
     'SharedNumericTests.test_only_exact_inherited_role_is_shared'),
    ('ignore_raw_equality','quality_audit.py',"need(left==right,'full ordered raw fields/score bits differ')",'None',
     'test_raw_order_and_each_selected_field'),
    ('ignore_own_origin','quality_audit.py',"x-64+sx-m['tl_x']","x-64+sx",
     'test_metadata_box_uses_each_arms_own_origin'),
    ('ignore_retention_arm','quality_audit.py',"need(values==expected,'P/C0 or B/C0 GT retention/pose differs')",'pass',
     'test_retention_P_and_B_separate_with_pose_identity'),
    ('ignore_raw_order','quality_audit.py',"need(result==sorted(result,key=candidate_order),'raw canonical order differs')",'pass',
     'test_full_raw_archive_manifest_order_metadata_and_score_bits'),
    ('unbounded_decode','quality_audit.py','decoded=archive.read(expected+1)','decoded=archive.read()',
     'test_gzip_decoder_caps_expansion_before_materializing_payload'),
    ('ignore_bank_origin','contract.py',"need(path==str(directory/filename),'accepted bank metadata/payload origin differs')",'pass',
     'test_bank_pins_bind_all_18_own_directories_and_counts'),
    ('ignore_common_original_closure','contract.py',"need(references==required,'complete C0 raw reference allowlist differs')",'pass',
     'test_inherited_C0_bank_common_and_original_raw_source_closures'),
    ('ignore_physical_summary','contract.py',"need(reader.json(native/'stage_summary.json')==summary,'embedded/native stage summary differs')",'pass',
     'test_stage_complete_inventory_physical_summary_and_parent_bindings'),
    ('substitute_P_primary','contract.py',"b=pooled[ARMS[2]]['allGT']","b=pooled[ARMS[1]]['allGT']",
     'test_quality_gate_uses_B_and_keeps_P_diagnostic'),
    ('nms_strict_boundary','numeric.py','overlap(candidate[5], old[5]) <= threshold','overlap(candidate[5], old[5]) < threshold',
     'test_nms_gt_ignore_and_threshold_boundaries'),
    ('reuse_ignore_GT','numeric.py','used.add(identity)','pass',
     'test_nms_gt_ignore_and_threshold_boundaries'),
    ('ignore_cpu_grant','run_audit.py',"need(cpu_slot_granted is True,'root exclusive quality-audit CPU grant required')",'pass',
     'RunnerTests.test_execute_one_guarded_child_and_no_retry'),
    ('ignore_source_freeze','run_audit.py',"need(source_pins()==record['source_pins'],'quality audit sources/interpreter changed before execution')",'pass',
     'RunnerTests.test_source_change_consumes_attempt_without_running_child'),
    ('ignore_guard_result','run_audit.py',"need(guard.get('passed') is True and guard.get('exit_code')==0,'guarded quality child failed')",'pass',
     'RunnerTests.test_child_failure_or_wrong_stage_preserved'),
]


def pin(path):
    data=path.read_bytes()
    return dict(path=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def run(directory,label,tests):
    command=[sys.executable,'-B','-m','unittest','-v']+tests
    result=subprocess.run(command,cwd=directory,capture_output=True,text=True,
                          env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    out,err=directory/(label+'.stdout.txt'),directory/(label+'.stderr.txt')
    out.write_text(result.stdout,encoding='utf-8'); err.write_text(result.stderr,encoding='utf-8')
    return dict(command=command,cwd=str(directory),exit_code=result.returncode,stdout=pin(out),stderr=pin(err)),result


def import_closure():
    standard={'collections','argparse','ast','copy','csv','datetime','gzip','hashlib','importlib','io','json','math','os',
              'pathlib','re','shutil','struct','subprocess','sys','tempfile','unittest'}
    local={'numeric','evidence','contract','quality_audit','run_audit'}
    imports={}
    for name in SOURCES:
        if not name.endswith('.py'): continue
        tree=ast.parse((HERE/name).read_bytes(),filename=name); modules=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import): modules.extend(alias.name.split('.')[0] for alias in node.names)
            if isinstance(node,ast.ImportFrom): modules.append(node.module.split('.')[0])
        if not set(modules)<=standard|local: raise ValueError('unapproved source import: '+name)
        imports[name]=sorted(set(modules))
    return imports


def main():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    evidence=HERE/'evidence'/(stamp+'_quality_source'); snapshot=evidence/'source_snapshot'
    snapshot.mkdir(parents=True,exist_ok=False)
    before={name:pin(HERE/name) for name in SOURCES}; imports=import_closure()
    origins=json.loads((HERE/'SOURCE_ORIGINS.json').read_text(encoding='utf-8')); origin=origins['numeric_core']
    if any(before['numeric.py'][key]!=origin[key] for key in ('bytes','sha256')):
        raise ValueError('numeric.py differs from byte-identical V30 core')
    for name in SOURCES: shutil.copyfile(HERE/name,snapshot/name)
    green,green_run=run(snapshot,'green',['test_quality_audit','test_run_audit','test_shared_numeric']); reds=[]
    for name,filename,needle,replacement,test in MUTANTS:
        source=(snapshot/filename).read_text(encoding='utf-8')
        if source.count(needle)!=1: raise ValueError('nonunique mutant anchor: '+name)
        target=evidence/('mutant_'+name); target.mkdir()
        for member in SOURCES: shutil.copyfile(snapshot/member,target/member)
        (target/filename).write_text(source.replace(needle,replacement,1),encoding='utf-8')
        test_name=('test_run_audit.'+test if test.startswith('RunnerTests.') else
                   'test_shared_numeric.'+test if test.startswith('SharedNumericTests.') else
                   'test_quality_audit.NumericTests.'+test)
        receipt,result=run(target,'red',[test_name])
        receipt.update(name=name,mutated_source=pin(target/filename),
                       detected=result.returncode==1 and 'FAIL:' in result.stderr and 'ERROR:' not in result.stderr)
        reds.append(receipt)
    after={name:pin(HERE/name) for name in SOURCES}
    passed=green_run.returncode==0 and all(row['detected'] for row in reds) and before==after
    receipt=dict(schema='independent_three_arm_quality_source_selftest_v2',passed=passed,synthetic_only=True,
                 sources_before=before,sources_after=after,source_snapshot=[pin(snapshot/n) for n in SOURCES],
                 sources_unchanged=before==after,imports=imports,green=green,mutant_red=reds,
                 interpreter=dict(path=sys.executable,version=sys.version,pin=pin(Path(sys.executable))),
                 matcher_calls=0,image_reads=0,image_decodes=0,real_bank_reads=0,real_raw_archive_reads=0,
                 production_promotion=False,limitations=origins['limitations'])
    target=evidence/'RECEIPT.json'; target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=passed,receipt=str(target),mutants_detected=sum(r['detected'] for r in reds))))
    return 0 if passed else 1


if __name__=='__main__': raise SystemExit(main())
