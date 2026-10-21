"""Audit a one-call center census and report exact count-only reuse potential."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent

def read(path):
    with path.open(newline='',encoding='utf-8-sig') as handle:
        result=list(csv.DictReader(handle))
    assert all(None not in r and None not in r.values() for r in result),path
    return result

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def key(row):return row['dataset'],row['image'],int(row['level'])

def summarize(run):
    manifest=json.loads((HERE/'source_manifest.json').read_text(encoding='utf-8'))
    environment=json.loads((run/'environment.json').read_text(encoding='utf-8-sig'))
    for name,digest in manifest['generated_sha256'].items():assert sha(HERE/name)==digest,name
    assert sha(HERE/'source_manifest.json')==environment['source_sha256']['artifacts/local_center_profile/source_manifest.json'].lower()
    validation=read(run/'validation.csv');summary=read(run/'centers_by_level.csv');frequency=read(run/'center_frequency.csv');templates=read(run/'centers_by_template.csv')
    assert len(validation)==9 and len(summary)==17 and len(templates)==14761
    assert all(r['semantic_equal']=='1' and r['count_equal']=='1' for r in validation)
    strict_differences=sum(r['strict_equal']!='1' for r in validation)
    status=json.loads((run/'status.json').read_text(encoding='utf-8'))
    assert status['semantic_or_count_failures']==0 and status['completed_images']==9
    assert strict_differences==status['strict_set_differences']
    histogram=defaultdict(dict)
    for r in frequency:
        group=histogram[key(r)];f=int(r['frequency']);n=int(r['unique_centers'])
        assert f>0 and n>0 and f not in group and int(r['calls'])==f*n
        group[f]=n
    aggregate=defaultdict(lambda:defaultdict(int));seen=set()
    for r in templates:
        k=key(r);unique_key=k+(r['class_id'],int(r['template_id']));assert unique_key not in seen;seen.add(unique_key)
        calls,unique,redundant,maxf=[int(r[n]) for n in ['total_calls','unique_centers','redundant_calls','max_frequency']]
        assert calls>=unique>=0 and calls-unique==redundant
        assert (calls==0 and maxf==0) or 1<=maxf<=calls
        for field in ['total_calls','unique_centers','redundant_calls']:aggregate[k][field]+=int(r[field])
        aggregate[k]['max_frequency']=max(aggregate[k]['max_frequency'],maxf)
    old=read(HERE.parent/'search_profile'/'run_v9'/'local_call_clamp_distribution.csv')
    old_by_key={key(r):r for r in old}
    dataset=defaultdict(lambda:defaultdict(int))
    for r in summary:
        k=key(r);h=histogram[k];a=aggregate[k]
        for field in ['total_calls','unique_centers','redundant_calls','max_frequency']:assert int(r[field])==a[field],(k,field)
        assert int(r['total_calls'])==sum(f*n for f,n in h.items())
        assert int(r['unique_centers'])==sum(h.values())
        assert int(r['duplicate_centers'])==sum(n for f,n in h.items() if f>1)
        assert int(r['max_frequency'])==max(h,default=0)
        assert abs(float(r['redundant_pct'])-100*int(r['redundant_calls'])/int(r['total_calls']))<1e-8
        assert int(r['total_calls'])==int(float(old_by_key[k]['local_calls']))
        assert int(r['x_clamped'])==int(float(old_by_key[k]['x_clamped']))
        assert int(r['y_clamped'])==int(float(old_by_key[k]['y_clamped']))
        roll=dataset[r['dataset'],int(r['level'])]
        for field in ['total_calls','unique_centers','redundant_calls','duplicate_centers']:roll[field]+=int(r[field])
        roll['images']+=1;roll['max_frequency']=max(roll['max_frequency'],int(r['max_frequency']))
    rollup=[]
    for (d,l),counts in sorted(dataset.items()):
        r={'dataset':d,'level':l,**counts};r['redundant_pct']=100*r['redundant_calls']/r['total_calls'];rollup.append(r)
    with (run/'dataset_rollup.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rollup[0]));writer.writeheader();writer.writerows(rollup)
    report=['# Exact local-center repetition census','',
        'One instrumented V9 call per image, with one independent V4 call per image for exact semantic-set/raw-count validation. All nine checks passed. '+f'Strict-set differences: {strict_differences}.','',
        'Center identity is `(image, class, template_id, pyramid level, x/T, y/T)` after clamping. Each template/level owns its frequency dictionary. The key therefore records the exact patch used by local accumulation, including integer division. Images, templates and levels are never merged into one cache key.','',
        '| Dataset / image | Level | Total local calls | Unique centers | Repeated calls | Repeated % | Max frequency |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in summary:
        report.append(f"| {r['dataset']}/{r['image']} | {r['level']} | {r['total_calls']} | {r['unique_centers']} | {r['redundant_calls']} | {float(r['redundant_pct']):.2f}% | {r['max_frequency']} |")
    report+=['','| Dataset | Level | Images | Total calls | Unique centers | Repeated calls | Repeated % | Max frequency |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rollup:
        report.append(f"| {r['dataset']} | {r['level']} | {r['images']} | {r['total_calls']} | {r['unique_centers']} | {r['redundant_calls']} | {r['redundant_pct']:.2f}% | {r['max_frequency']} |")
    report+=['','`center_frequency.csv` contains the full distribution: frequency k, number of unique scoped centers occurring k times, and k × count calls. `centers_by_template.csv` retains all template/level totals, including those with no candidates. The post-processing audit reconciles both with every image/level summary and verifies total/clamp counts against the previous V9 profile.','',
        'Repeated calls are the exact count of already-evaluated identical local windows within a template/level. A result cache may reuse their maximum and relative winner coordinates while retaining all candidates and their existing threshold checks. This count is an upper bound on local evaluations avoided by a full-lifetime cache, not a speedup estimate. Cache lookup/storage/allocation costs, memory footprint, and altered cache behavior require an uninstrumented paired benchmark. No production API, pose bank, thresholds, candidate multiplicity, or matcher semantics were changed.','',
        'This executable uses a copy of the saved 6b7be69 V9 diagnostic source. Its fixture builder is compiled against that private namespace; no current production matcher object is linked. The prior `search_profile/source`, manifest, and `run_v9` remain unchanged. Old stage clocks remain in the copied code, but no timing results are used or published.','']
    (run/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
    audit={'passed':True,'v4_semantic_count_checks':9,'strict_set_differences':strict_differences,
           'center_level_rows':len(summary),'template_level_rows':len(templates),'histogram_rows':len(frequency),
           'checks':['private snapshot hashes','V4 semantic/raw-count equivalence','template unique keys',
                     'per-template totals','histogram total/unique/duplicate/max consistency',
                     'V9 local call and clamp counts unchanged'],
           'sha256':{name:sha(run/name) for name in ['environment.json','config.json','validation.csv','centers_by_level.csv','center_frequency.csv','centers_by_template.csv','status.json']}}
    (run/'audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    print('\n'.join(report))

if __name__=='__main__':summarize(Path(sys.argv[1]))
