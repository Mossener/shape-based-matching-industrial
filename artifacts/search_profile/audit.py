"""Independent post-processing audit. Does not regenerate or modify the snapshot."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
import sys

HERE=Path(__file__).resolve().parent
STAGES=['coarse_similarity','coarse_collect','local_similarity','local_argmax','local_filter']
COUNT_FIELDS=['map_positions','accumulated_prefix','geometrically_valid','zero_tail_scanned',
              'wrapped_prefix_scanned','coarse_candidates','zero_tail_candidates','wrapped_candidates',
              'local_calls','matches_before_sort','matches_after_unique']

def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as handle:
        reader=csv.DictReader(handle)
        for row in reader:
            if None in row or None in row.values():raise AssertionError(f'CSV alignment: {path}')
            yield row

def close(a,b):
    if abs(float(a)-float(b))>max(1e-6,abs(float(b))*1e-8):
        raise AssertionError(f'Numeric mismatch: {a} != {b}')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def callkey(row):return row['dataset'],row['image'],int(row['round'])
def templatekey(row):return callkey(row)+(row['class_id'],int(row['template_id']))

def audit(run):
    environment=json.loads((run/'environment.json').read_text(encoding='utf-8-sig'))
    manifest=json.loads((HERE/'source_manifest.json').read_text(encoding='utf-8'))
    assert manifest['git_head']=='6b7be69f96cffc1a914674691c6f20d80ea09106'
    for name,digest in manifest['source_sha256'].items():
        assert environment['source_sha256'][name].lower()==digest.lower(),name
    for name,digest in manifest['generated_sha256'].items():assert sha(HERE/name)==digest,name
    for name in ['profile.cpp','profile.hpp','source_manifest.json']:
        assert sha(HERE/name)==environment['source_sha256']['artifacts/search_profile/'+name].lower(),name
    validation=list(rows(run/'validation.csv'));calls=list(rows(run/'calls.csv'))
    assert len(validation)==9 and len(calls)==90
    for row in validation+calls:
        assert all(row[name]=='1' for name in ['semantic_equal','strict_equal','count_equal'])
    phases=Counter(row['phase'] for row in calls)
    assert phases=={'cold':9,'warmup':18,'measured':63},phases
    measured={callkey(row):row for row in calls if row['phase']=='measured'}
    assert len(measured)==63
    aggregate=defaultdict(lambda:defaultdict(float));templates={};template_count=0
    per_template_counts=['map_positions','accumulated_prefix','geometrically_valid','zero_tail_scanned',
                         'wrapped_prefix_scanned','coarse_candidates','zero_tail_candidates','wrapped_candidates']
    for row in rows(run/'templates.csv'):
        template_count+=1;key=templatekey(row);assert key not in templates
        values={name:int(row[name]) for name in per_template_counts}
        assert values['map_positions']==values['accumulated_prefix']+values['zero_tail_scanned']
        assert values['accumulated_prefix']==values['geometrically_valid']+values['wrapped_prefix_scanned']
        assert values['zero_tail_candidates']==0 and values['wrapped_candidates']==0
        templates[key]={'coarse_level':int(row['coarse_level']),'coarse_candidates':values['coarse_candidates'],'levels':{}}
        target=aggregate[callkey(row)]
        for name,value in values.items():target[name]+=value
        for stage in ['coarse_similarity','coarse_collect']:target[stage+'_worker_sum_ms']+=float(row[stage+'_worker_ms'])
    assert template_count==(8*900+361)*7==52927,template_count
    localdetails=defaultdict(lambda:defaultdict(float));features=defaultdict(set);level_count=0
    for row in rows(run/'levels.csv'):
        level_count+=1;key=templatekey(row);assert key in templates
        level=int(row['level']);item=templates[key]
        assert level not in item['levels']
        incoming,outgoing,calls_=[int(row[name]) for name in ['candidates_in','candidates_out','local_calls']]
        assert incoming>=outgoing>=0
        item['levels'][level]=(row['kind'],incoming,outgoing,calls_)
        if row['kind']=='local':
            assert calls_==incoming
            target=aggregate[callkey(row)];target['local_calls']+=calls_
            target['local_similarity_worker_sum_ms']+=float(row['similarity_worker_ms'])
            target['local_argmax_worker_sum_ms']+=float(row['argmax_worker_ms'])
            target['local_filter_worker_sum_ms']+=float(row['filter_worker_ms'])
            dkey=(row['dataset'],row['image'],int(row['round']),level)
            for field in ['candidates_in','candidates_out','local_calls','x_clamped','y_clamped','similarity_worker_ms','argmax_worker_ms']:
                localdetails[dkey][field]+=float(row[field])
            assert int(row['x_clamped'])<=calls_ and int(row['y_clamped'])<=calls_
            features[row['dataset'],row['image'],level].add(int(row['features']))
    assert level_count==(8*900*3+361*2)*7==156254,level_count
    for key,item in templates.items():
        coarse=item['coarse_level'];levels=item['levels']
        assert set(levels)==set(range(coarse+1))
        assert levels[coarse][0]=='coarse' and levels[coarse][2]==item['coarse_candidates']
        for level in range(coarse-1,-1,-1):
            assert levels[level][0]=='local' and levels[level][1]==levels[level+1][2]
        aggregate[key[:3]]['matches_before_sort']+=levels[0][2]
    for key,row in measured.items():
        for field in COUNT_FIELDS:
            if field!='matches_after_unique':close(aggregate[key][field],row[field])
        for stage in STAGES:close(aggregate[key][stage+'_worker_sum_ms'],row[stage+'_worker_sum_ms'])
        expected=next(v for v in validation if (v['dataset'],v['image'])==key[:2])
        assert int(row['matches_after_unique'])==int(expected['current_count'])
    byimage=defaultdict(list)
    for row in measured.values():byimage[row['dataset'],row['image']].append(row)
    summary=list(rows(run/'summary_by_image.csv'))
    for result in summary:
        image_rows=byimage[result['dataset'],result['image']]
        for field,value in result.items():
            if field.startswith('median_') and field.endswith('_worker_share_pct'):
                stage=field[len('median_'):-len('_worker_share_pct')]
                close(value,median(100*float(r[stage+'_worker_sum_ms'])/sum(float(r[s+'_worker_sum_ms']) for s in STAGES) for r in image_rows))
            elif field.startswith('median_'):
                name=field[len('median_'):];close(value,median(float(r[name]) for r in image_rows))
            elif field in COUNT_FIELDS:
                observed={int(r[field]) for r in image_rows};assert len(observed)==1
                close(value,observed.pop())
        for field,base in [('zero_tail_scanned_pct','zero_tail_scanned'),('wrapped_prefix_scanned_pct','wrapped_prefix_scanned')]:
            close(result[field],100*float(result[base])/float(result['map_positions']))
    for result in rows(run/'summary_by_dataset.csv'):
        image_rows=[r for r in summary if r['dataset']==result['dataset']]
        assert int(result['images'])==len(image_rows)
        for field,value in result.items():
            if field not in ['dataset','images','weighting']:close(value,mean(float(r[field]) for r in image_rows))
    raw_grouped=defaultdict(list)
    for (d,i,r,l),values in localdetails.items():raw_grouped[d,i,l].append(values)
    distribution=[]
    for (dataset,image,level),values in sorted(raw_grouped.items()):
        result={'dataset':dataset,'image':image,'level':level,'features':','.join(str(x) for x in sorted(features[dataset,image,level]))}
        for field in values[0]:
            counts=[r[field] for r in values]
            if not field.endswith('_ms'):assert len(set(counts))==1
            result[field]=median(counts)
        result['retained_pct']=100*result['candidates_out']/result['candidates_in']
        result['x_clamped_pct']=100*result['x_clamped']/result['local_calls']
        result['y_clamped_pct']=100*result['y_clamped']/result['local_calls']
        distribution.append(result)
    with (run/'local_call_clamp_distribution.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(distribution[0]));writer.writeheader();writer.writerows(distribution)
    report=['# Local call and clamp distribution','',
        'Derived only from the completed run; no matching rerun or snapshot change. Counts are identical in all seven measured repetitions. X and Y clamping counts can overlap. Unique local centers and overlapping candidate windows were not recorded, so these values cannot establish cache hit rates.','',
        '| Dataset / image | Level | Features | Local calls | Retained | X clamped | Y clamped |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in distribution:
        report.append(f"| {r['dataset']}/{r['image']} | {r['level']} | {r['features']} | {r['local_calls']:.0f} | {r['retained_pct']:.2f}% | {r['x_clamped']:.0f} ({r['x_clamped_pct']:.2f}%) | {r['y_clamped']:.0f} ({r['y_clamped_pct']:.2f}%) |")
    led=[r for r in distribution if r['dataset']=='LED']
    report+=['','LED local accumulation, equal mean of image medians:']
    for level in [1,0]:
        items=[r for r in led if r['level']==level]
        report.append(f"- Level {level}: {mean(r['local_calls'] for r in items):.1f} local calls/image, {mean(r['similarity_worker_ms'] for r in items):.3f} ms summed worker accumulation/image; {mean(r['retained_pct'] for r in items):.2f}% candidates retained.")
    report+=['','These are worker elapsed intervals, not wall time. Level 0 uses 236-feature 16-bit accumulation; level 1 uses 111-feature 16-bit accumulation. LED coarse uses 46 features and the 8-bit kernel. The L0 candidate rejection occurs after its full 16×16 search; this is diagnostic evidence for targeting that kernel, not permission to alter thresholds.','']
    (run/'LOCAL_CALLS.md').write_text('\n'.join(report),encoding='utf-8')
    checks=['Snapshot source hashes match the original run environment; all five generated files match their immutable manifest.',
        'Driver/header hashes match the run environment. No production-source refresh or matching rerun was performed.',
        'Nine pre-profile current/instrumented comparisons passed semantic sets, strict sets, and raw counts.',
        'All 90 cold/warmup/measured calls passed semantic, strict, and raw-count checks; phase counts are 9/18/63.',
        f'All {template_count:,} template rows and {level_count:,} level rows have aligned CSV fields and unique expected keys.',
        'Every template has exactly its expected pyramid levels; coarse output equals next-level input and local output equals next-level input.',
        'Every local call count equals its candidate input count; clamping counts are bounded by calls.',
        'Per-template region census partitions map = accumulated prefix + zero tail and prefix = valid rectangle + wrapped positions.',
        'All measured call counts and all five worker stage sums reconcile independently with template/level CSVs.',
        'Sum of L0 outputs equals pre-sort count; post-unique count equals validated current count.',
        'Per-image medians, worker-share percentages, census percentages, and dataset equal-weight means were independently recalculated.']
    hashes={name:sha(run/name) for name in ['environment.json','config.json','validation.csv','calls.csv','templates.csv','levels.csv','summary_by_image.csv','summary_by_dataset.csv','summary_levels.csv']}
    data={'audited_at':datetime.now(timezone.utc).isoformat(),'passed':True,'snapshot_git_head':manifest['git_head'],
          'checks':checks,'csv_rows':{'validation':len(validation),'calls':len(calls),'templates':template_count,'levels':level_count},'sha256':hashes}
    (run/'audit.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    notes=['# Profile audit','',f"Passed {len(checks)} independent consistency checks. Snapshot: `{manifest['git_head']}`.",'']
    notes+=['- '+item for item in checks]
    notes+=['','Interpretation limits: worker elapsed sums are not process CPU or serial wall time; per-candidate clock overhead disproportionately affects argmax. Kernel intervals include map zeroing/allocation and any conversion. Equal-score ordering is not a detection-accuracy claim. Clamp counts are not unique-center counts. Production files may since have changed; provenance is checked against the run-time hash manifest, not the current working tree.','',
        'This audit does not independently verify every SIMD memory access or prove detection accuracy. The existing semantic/count comparison establishes equivalence only on these nine fixed fixtures. A low-level kernel change still needs its own kernel tests and the uninstrumented equivalence/benchmark workflow.','',
        'Raw evidence SHA256 values are saved in `audit.json`. `LOCAL_CALLS.md` and `local_call_clamp_distribution.csv` are post-processing only.','']
    (run/'AUDIT.md').write_text('\n'.join(notes),encoding='utf-8')
    print('\n'.join(notes));print('\n'.join(report))

if __name__=='__main__':audit(Path(sys.argv[1]))
