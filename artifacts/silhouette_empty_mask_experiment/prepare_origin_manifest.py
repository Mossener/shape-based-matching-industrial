"""Record predecessor/helper origins without modifying predecessor evidence."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PARENT=ROOT/'artifacts/silhouette_template_experiment'
DEST=HERE/'IMPLEMENTATION_ORIGIN.json'


def pin(path):
    path=Path(path).resolve(strict=True);data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def main():
    if DEST.exists():
        raise ValueError('Origin manifest must be fresh')
    identical=['native_provenance.py','silhouette_source.hpp','test_native_provenance.py','test_private_source_isolation.py']
    derived=['freeze_private_sources.py','silhouette_eval.cpp','build_adapter.py','run_stage.py']
    records=[]
    for name in identical+derived:
        old,new=pin(PARENT/name),pin(HERE/name)
        if name in identical and old['sha256']!=new['sha256']:
            raise ValueError('Unchanged inherited helper differs: '+name)
        records.append(dict(name=name,predecessor=old,successor_initial=new,
                            relationship='byte-identical helper' if name in identical else 'successor-specific adaptation; final build manifest pins actual bytes'))
    result=dict(predecessor_git_revision='922428c',frozen_matcher_git_revision='b25df46f6ddf9c24fb43f5836f1414dc38c8caed',
                parent_source_freeze=pin(PARENT/'PRIVATE_SOURCE_FREEZE.json'),
                parent_input_closure=pin(PARENT/'INPUT_CLOSURE.json'),
                parent_protocol=pin(PARENT/'PROTOCOL.json'),
                parent_bank_freeze=pin(PARENT/'run_source_only_training_v1/BANK_FREEZE.json'),
                successor_protocol=pin(HERE/'PROTOCOL.json'),successor_source_freeze=pin(HERE/'PRIVATE_SOURCE_FREEZE.json'),
                successor_input_closure=pin(HERE/'INPUT_CLOSURE.json'),records=records,
                scope='Origins only. A completed native build/runner separately pins actual final successor source, tool and dependency bytes.',
                dataset_image_reads=0,matcher_calls=0)
    DEST.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,origin_records=len(records),dataset_image_reads=0,matcher_calls=0)))


if __name__=='__main__':
    main()
