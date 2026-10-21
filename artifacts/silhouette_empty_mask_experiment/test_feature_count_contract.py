"""Literal static regression: requested feature counts are not actual caps.

The fixed six RGB attempt tables contain actual successful feature counts above
32/16. This test preserves that numeric evidence and catches the inherited
specific upper-bound assertions; it is not a general C++ semantic proof.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():
        raise ValueError('Output must be fresh')
    args.output.mkdir();records=[]
    try:
        for obj in [1,2,5,8,12,17]:
            path=HERE/f'frozen_inputs/obj{obj}/rgb_training/template_attempts.csv';data=path.read_bytes()
            rows=list(csv.DictReader(data.decode().splitlines()));successful=[r for r in rows if int(r['success'])]
            records.append(dict(object_id=obj,attempts=len(rows),successful=len(successful),
                                max_l0=max(int(r['features_l0']) for r in successful),max_l1=max(int(r['features_l1']) for r in successful),
                                above_requested=sum(int(r['features_l0'])>32 or int(r['features_l1'])>16 for r in successful),
                                source_sha256=hashlib.sha256(data).hexdigest()))
        if max(r['max_l0'] for r in records)!=44 or max(r['max_l1'] for r in records)!=23 or not all(r['above_requested']>0 for r in records):
            raise AssertionError('Fixed original successful-feature evidence changed')
        adapter=(HERE/'silhouette_eval.cpp').read_text()
        if re.search(r'n0\s*<=\s*32|n1\s*<=\s*16',adapter):
            raise AssertionError('Inherited adapter incorrectly caps actual V11 features at requested 32/16')
        result=dict(passed=True,scope='Numeric retained-bank evidence plus literal static upper-bound regression',
                    objects=records,adapter_sha256=hashlib.sha256(adapter.encode()).hexdigest(),dataset_image_reads=0,native_processes=0,matcher_calls=0)
        (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,objects=6,max_l0=44,max_l1=23)))
    except Exception as error:
        (args.output/'failure.json').write_text(json.dumps(dict(incomplete=True,reason=str(error),objects=records,dataset_image_reads=0,native_processes=0),indent=2)+'\n');raise


if __name__=='__main__':
    main()
