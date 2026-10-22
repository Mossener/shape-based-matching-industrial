"""Preserve isolated synthetic training-core GREEN and deliberate mutant RED."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
SOURCES=['numeric_oracle.py','pool_stream.py','strict_bank_reader.py','training_audit.py',
         'test_numeric_oracle.py','test_pool_stream.py','test_training_audit.py','BANK_READER_ORIGIN.json',
         'run_training_selftest.py','TRAINING_SCHEMA.md','TRAINING_AUDIT_ORIGINS.json','README.md',
         'bounded_classifier_v2.py','test_bounded_classifier.py']
MUTANTS=[
    ('crop_plus_one','crop=[min_x,min_y,max_x-min_x,max_y-min_y]',
     'crop=[min_x,min_y,max_x-min_x+1,max_y-min_y+1]',
     'TrainingLiterals.test_cross_layer_crop_even_origin_no_plus_one_and_order'),
    ('crop_odd_origin','if min_x%2==1: min_x-=1','if False: min_x-=1',
     'TrainingLiterals.test_cross_layer_crop_even_origin_no_plus_one_and_order'),
    ('ignore_L1_bytes','actual==mask1','len(actual)==len(mask1)',
     'TrainingLiterals.test_mask_bbox_nonzero_and_layer_exact_bytes'),
    ('ignore_full_claim','same(row,expected_row,"full ordered layer selection differs")','pass',
     'TrainingLiterals.test_training_claim_tamper_omission_order_hash_geometry_and_status'),
    ('ignore_serialized_features','require(layer_digest(layers)==entry["sha256"],"complete serialized bank feature/order/crop digest differs")','pass',
     'TrainingLiterals.test_strict_serialized_bank_and_metadata_full_order_fields'),
    ('ignore_official_metadata','same(_canonical_metadata(observed),_canonical_metadata(entry["metadata"]),"complete serialized metadata differs")','pass',
     'TrainingLiterals.test_strict_serialized_bank_and_metadata_full_order_fields'),
    ('ignore_extra_artifacts','require(actual_inventory==expected_inventory,"missing/extra bank artifact inventory")','pass',
     'TrainingLiterals.test_all_artifact_inventory_rejects_extra_missing_bank_and_config'),
    ('ignore_raw_dilation_hash','require(hashlib.sha256(dilation).hexdigest()==observation[\'dilated_mask_sha256\'],"full raw dilated mask SHA differs")','pass',
     'TrainingLiterals.test_dilation_sidecar_target_raw_map_hash_and_scan_validation'),
    ('ignore_extra_pool_observation',"if observations is not None: _end(observations,'pool observation')",'pass',
     'TrainingLiterals.test_sidecar_stream_requires_all_pools_and_keeps_native_observations_limited'),
    ('ignore_original_CSV_pin',"same(observed,{'bytes':pin['bytes'],'sha256':pin['sha256']},\"numeric evidence pin differs\")",'pass',
     'TrainingLiterals.test_numeric_input_freeze_csv_pins_and_strict_stream_jsonl'),
    ('ignore_summary_contract',"same(summary,expected,'complete training summary observed counters differ')",'pass',
     'TrainingLiterals.test_inherited_config_builder_and_full_observed_summary_contract'),
]


def pin(path):
    data=path.read_bytes()
    return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def run(directory,label,tests):
    command=[sys.executable,'-B','-m','unittest','-v']+tests
    result=subprocess.run(command,cwd=directory,capture_output=True,text=True,
                          env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    out,err=directory/(label+'.stdout.txt'),directory/(label+'.stderr.txt')
    out.write_text(result.stdout,encoding='utf-8'); err.write_text(result.stderr,encoding='utf-8')
    return {'command':command,'cwd':str(directory),'exit_code':result.returncode,
            'stdout':pin(out),'stderr':pin(err)},result


def main():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    evidence=HERE/'evidence'/(stamp+'_training_core')
    snapshot=evidence/'source_snapshot'; snapshot.mkdir(parents=True,exist_ok=False)
    before={name:pin(HERE/name) for name in SOURCES}
    for name in SOURCES: shutil.copyfile(HERE/name,snapshot/name)
    green,green_run=run(snapshot,'green',['test_numeric_oracle','test_pool_stream','test_training_audit','test_bounded_classifier'])
    source=(snapshot/'training_audit.py').read_text(encoding='utf-8')
    reds=[]
    for name,needle,replacement,test in MUTANTS:
        if source.count(needle)!=1: raise RuntimeError('mutation anchor not unique: '+name)
        target=evidence/('mutant_'+name); target.mkdir()
        for filename in SOURCES:
            if filename!='training_audit.py': shutil.copyfile(snapshot/filename,target/filename)
        (target/'training_audit.py').write_text(source.replace(needle,replacement,1),encoding='utf-8')
        receipt,result=run(target,'red',['test_training_audit.'+test])
        receipt.update(name=name,mutated_source=pin(target/'training_audit.py'),
                       detected=result.returncode==1 and 'FAIL:' in result.stderr and 'ERROR:' not in result.stderr)
        reds.append(receipt)
    after={name:pin(HERE/name) for name in SOURCES}
    passed=green_run.returncode==0 and all(row['detected'] for row in reds) and before==after
    receipt={'schema':'independent_training_core_selftest_v1','utc':stamp,'all_checks_passed':passed,
             'synthetic_only':True,'native_calls':0,'image_reads':0,'real_bank_reads':0,
             'sources_before':before,'sources_after':after,'source_snapshot':[pin(snapshot/n) for n in SOURCES],
             'interpreter':{'path':sys.executable,'version':sys.version,'pin':pin(Path(sys.executable))},
             'green':green,'mutant_red':reds,'sources_unchanged':before==after,
             'limitations':['No real training or heavy audit','Actual native synthetic fullCLI audit is retained separately',
                            'No real RGB gradient or NMS regeneration','Input/source closure belongs to root runner']}
    target=evidence/'RECEIPT.json'; target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':passed,'receipt':str(target),'mutants_detected':sum(row['detected'] for row in reds)}))
    return 0 if passed else 1


if __name__=='__main__': raise SystemExit(main())
