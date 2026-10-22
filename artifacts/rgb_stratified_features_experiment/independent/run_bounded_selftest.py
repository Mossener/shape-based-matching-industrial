"""Fresh source-pinned bounded-v2 equivalence GREEN and discriminating RED."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
SOURCES=['numeric_oracle.py','bounded_classifier_v2.py','test_bounded_classifier.py','run_bounded_selftest.py']
ORIGINAL_BFS_SHA256='264a788493c05348d06db51de0aa6cec861e0e1547f2a7ffb039133473f70307'
MUTANTS=[
    ('radius3',[('range(y-4,y+5)','range(y-3,y+4)'),('range(x-4,x+5)','range(x-3,x+4)')]),
    ('threshold128',[('mask[neighbor_y*width+neighbor_x]!=0','mask[neighbor_y*width+neighbor_x]>=128')]),
    ('nonzero_exterior',[('inside=(0<=neighbor_x<width and 0<=neighbor_y<height and\n                        mask[neighbor_y*width+neighbor_x]!=0)',
                         'inside=(not (0<=neighbor_x<width and 0<=neighbor_y<height) or\n                        mask[neighbor_y*width+neighbor_x]!=0)')]),
    ('reversed_stratum',[("result.append('S' if found_opposite else 'I')","result.append('I' if found_opposite else 'S')")]),
]


def pin(path):
    data=path.read_bytes(); return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def run(directory,label,test=None):
    command=[sys.executable,'-B',str(directory/'test_bounded_classifier.py')]
    if test: command.append(test)
    result=subprocess.run(command,cwd=directory,capture_output=True,text=True,
                          env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    out,err=directory/(label+'.stdout.txt'),directory/(label+'.stderr.txt')
    out.write_text(result.stdout,encoding='utf-8');err.write_text(result.stderr,encoding='utf-8')
    return {'command':command,'cwd':str(directory),'exit_code':result.returncode,'stdout':pin(out),'stderr':pin(err)},result


def main():
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    folder=HERE/'evidence'/(stamp+'_bounded_v2');snapshot=folder/'source_snapshot';snapshot.mkdir(parents=True,exist_ok=False)
    before={name:pin(HERE/name) for name in SOURCES}
    if before['numeric_oracle.py']['sha256']!=ORIGINAL_BFS_SHA256: raise ValueError('original BFS source changed')
    for name in SOURCES:shutil.copyfile(HERE/name,snapshot/name)
    green,green_result=run(snapshot,'green')
    source=(snapshot/'bounded_classifier_v2.py').read_text(encoding='utf-8');reds=[]
    for name,replacements in MUTANTS:
        directory=folder/('mutant_'+name);directory.mkdir();changed=source
        for needle,replacement in replacements:
            if changed.count(needle)!=1:raise ValueError('nonunique mutation anchor '+name)
            changed=changed.replace(needle,replacement,1)
        (directory/'bounded_classifier_v2.py').write_text(changed,encoding='utf-8')
        for name_source in ['numeric_oracle.py','test_bounded_classifier.py']:shutil.copyfile(snapshot/name_source,directory/name_source)
        receipt,result=run(directory,'red','BoundedEquivalence.test_literals_more_than_nine_pixels_boundary_four_vs_five')
        receipt.update(name=name,source=pin(directory/'bounded_classifier_v2.py'),
                       detected=result.returncode==1 and 'FAIL:' in result.stderr and 'ERROR:' not in result.stderr)
        reds.append(receipt)
    after={name:pin(HERE/name) for name in SOURCES}
    passed=green_result.returncode==0 and all(r['detected'] for r in reds) and before==after
    receipt={'schema':'bounded_classifier_v2_equivalence_selftest_v1','all_checks_passed':passed,
             'synthetic_only':True,'native_calls':0,'image_reads':0,'real_bank_reads':0,
             'sources_before':before,'sources_after':after,'source_snapshot':[pin(snapshot/n) for n in SOURCES],
             'original_BFS_source_unchanged':after['numeric_oracle.py']['sha256']==ORIGINAL_BFS_SHA256,
             'green':green,'mutant_red':reds,
             'limitations':['Classifies frozen radius4 predicates only; not complete signed distance map',
                            'No reduction of candidate/mask/pairwise selection coverage','No real full audit performed']}
    target=folder/'RECEIPT.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':passed,'receipt':str(target),'mutants_detected':sum(r['detected'] for r in reds)}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
