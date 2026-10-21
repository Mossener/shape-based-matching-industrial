"""Summarize diagnostic composition without conflating worker sums and wall time."""
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
import sys

STAGES = ['coarse_similarity', 'coarse_collect', 'local_similarity', 'local_argmax', 'local_filter']
COUNTS = ['map_positions', 'accumulated_prefix', 'geometrically_valid', 'zero_tail_scanned',
          'wrapped_prefix_scanned', 'coarse_candidates', 'zero_tail_candidates', 'wrapped_candidates',
          'local_calls', 'matches_before_sort', 'matches_after_unique']

def read(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f, fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def percentile(values, q):
    ordered=sorted(values);index=(len(ordered)-1)*q;lo=int(index);hi=min(lo+1,len(ordered)-1)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(index-lo)

def summarize(path):
    calls=read(path/'calls.csv')
    if not calls or any(r[k]!='1' for r in calls for k in ('semantic_equal','count_equal')):
        raise RuntimeError('Missing calls or failed correctness checks')
    grouped=defaultdict(list)
    for r in calls:
        if r['phase']=='measured':grouped[r['dataset'],r['image']].append(r)
    summary=[]
    for (dataset,image),rows in sorted(grouped.items()):
        result={'dataset':dataset,'image':image,'samples':len(rows)}
        for field in ['wall_ms','api_total_ms','preprocess_ms','search_wall_ms','final_sort_wall_ms','final_unique_wall_ms']:
            result['median_'+field]=median(float(r[field]) for r in rows)
        result['p95_search_wall_ms']=percentile([float(r['search_wall_ms']) for r in rows],.95)
        for stage in STAGES:
            result['median_'+stage+'_worker_sum_ms']=median(float(r[stage+'_worker_sum_ms']) for r in rows)
            result['median_'+stage+'_worker_share_pct']=median(
                100*float(r[stage+'_worker_sum_ms'])/sum(float(r[s+'_worker_sum_ms']) for s in STAGES) for r in rows)
        for field in COUNTS:
            values=[int(r[field]) for r in rows]
            if len(set(values))!=1:raise RuntimeError(f'Unstable count {dataset}/{image}/{field}: {values}')
            result[field]=values[0]
        result['zero_tail_scanned_pct']=100*result['zero_tail_scanned']/result['map_positions']
        result['wrapped_prefix_scanned_pct']=100*result['wrapped_prefix_scanned']/result['map_positions']
        summary.append(result)
    if not summary:raise RuntimeError('No measured rows')
    write(path/'summary_by_image.csv',summary)
    datasets=defaultdict(list)
    for r in summary:datasets[r['dataset']].append(r)
    rollup=[]
    for dataset,rows in sorted(datasets.items()):
        result={'dataset':dataset,'images':len(rows),'weighting':'arithmetic mean of per-image medians/counts'}
        for field in summary[0]:
            if field not in ('dataset','image','samples'):result[field]=mean(r[field] for r in rows)
        rollup.append(result)
    write(path/'summary_by_dataset.csv',rollup)
    levels=defaultdict(lambda:defaultdict(float))
    for r in read(path/'levels.csv'):
        key=(r['dataset'],r['image'],int(r['round']),int(r['level']),r['kind'])
        for field in ['candidates_in','candidates_out','local_calls','x_clamped','y_clamped',
                      'similarity_worker_ms','argmax_worker_ms','filter_worker_ms']:
            levels[key][field]+=float(r[field])
    bylevel=defaultdict(list)
    for (d,i,round_,l,k),v in levels.items():bylevel[d,i,l,k].append(v)
    levelsummary=[]
    for (d,i,l,k),rows in sorted(bylevel.items()):
        result={'dataset':d,'image':i,'level':l,'kind':k,'samples':len(rows)}
        for field in rows[0]:result['median_'+field]=median(r[field] for r in rows)
        levelsummary.append(result)
    write(path/'summary_levels.csv',levelsummary)
    report=['# Search composition profile','',
        'This is an instrumented composition diagnostic. All stage intervals inside template workers are summed elapsed intervals; they are neither serial wall time nor process CPU time. Percentages use only the five worker stages as their denominator. Final sort/unique and search wall use serial elapsed time and are reported separately.','',
        'All fixtures passed exact semantic-set and raw-count checks against current production code before profiling; every collected call rechecked those comparisons. Strict sets are retained separately for equal-score template tie review.','',
        '| Dataset | Coarse similarity | Candidate collect | Local similarity | Local argmax | Local filter | Search wall median | Sort median |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rollup:
        cells=[r['dataset']]+[f"{r['median_'+s+'_worker_share_pct']:.2f}%" for s in STAGES]
        cells += [f"{r['median_search_wall_ms']:.3f} ms",f"{r['median_final_sort_wall_ms']:.3f} ms"]
        report.append('| '+' | '.join(cells)+' |')
    report+=['','Dataset rows equally weight image-level medians; LED and case1 are kept separate. These descriptive summaries do not estimate confidence intervals.','',
        '| Dataset / image | Coarse candidates | Local calls | Zero tail scanned | Wrapped prefix scanned | Zero-tail candidates | Wrapped candidates |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in summary:
        report.append(f"| {r['dataset']}/{r['image']} | {r['coarse_candidates']} | {r['local_calls']} | {r['zero_tail_scanned_pct']:.2f}% | {r['wrapped_prefix_scanned_pct']:.2f}% | {r['zero_tail_candidates']} | {r['wrapped_candidates']} |")
    report+=['','The coarse scan covers H×W entries. Kernels zero that whole map but accumulate only the prefix `span_y*W + span_x + 1`. Tail entries therefore remain zero; geometrically invalid row-wrapped origins occur inside the accumulated prefix. Removing the latter can change existing output and needs a separate correctness decision.','',
        'Timer calls, per-template vectors, counter bookkeeping and candidate-region census add overhead. Kernel timings include map allocation/zeroing and any conversion, not just SIMD adds. Per-candidate timings perturb short argmax operations proportionally more. Instrumented search wall is not an optimization speedup result. Validate any proposed kernel change with the uninstrumented benchmark and existing equivalence suites.','']
    (path/'REPORT.md').write_text('\n'.join(report),encoding='utf-8')
    print('\n'.join(report))

if __name__=='__main__':
    summarize(Path(sys.argv[1]))
