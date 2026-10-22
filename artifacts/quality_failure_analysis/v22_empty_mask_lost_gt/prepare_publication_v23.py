"""Select completed numeric diagnosis evidence by explicit path, without Git."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
NAMES=['diagnostic.py','run_analysis.py','test_diagnostic.py','PROTOCOL.json',
       'RESULTS.md','NEXT_SINGLE_POINT_DESIGN.md','green_tests.txt','red_tests.txt',
       'root_review_saved.py','root_review_saved_20261022.json','prepare_publication_v23.py',
       'run_20261022_v1/lost_gt_details.json','run_20261022_v1/per_gt.csv',
       'run_20261022_v1/per_positive_frame.csv','run_20261022_v1/result.json',
       'run_20261022_v1/source/diagnostic.py','run_20261022_v1/source/run_analysis.py',
       'run_20261022_v1/source/test_diagnostic.py','run_20261022_v1/source/PROTOCOL.json']

def main():
    records=[]
    for name in NAMES:
        path=(HERE/name).resolve(strict=True)
        assert path.is_relative_to(HERE) and path.suffix in {'.py','.json','.csv','.md','.txt'}
        data=path.read_bytes()
        records.append(dict(path=path.relative_to(ROOT).as_posix(),size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    result=dict(file_count=len(records),total_bytes=sum(r['size_bytes'] for r in records),files=records,scope='V23 completed V22 lost-GT numeric diagnosis; pending native probe excluded',matcher_calls=0,image_decodes=0)
    with (HERE/'PUBLICATION_INVENTORY_V23.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))

if __name__=='__main__':
    main()
