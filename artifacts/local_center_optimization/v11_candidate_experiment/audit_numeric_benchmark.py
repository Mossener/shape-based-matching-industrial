"""Independent CSV arithmetic check, without importing the benchmark summary."""
import argparse
import csv
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    need(not args.output.exists(), 'Output must be new')
    encoded = args.csv.read_bytes()
    summary_bytes = args.summary.read_bytes()
    summary = json.loads(summary_bytes)
    need(digest(encoded) == summary['csv_sha256'], 'CSV identity')
    rows = list(csv.DictReader(encoded.decode('utf-8-sig').splitlines()))
    need(len(rows) == summary['all_rows'] == 1350, 'Raw sample count')
    cases = ['exact_v11', 'candidate_off', 'candidate_on']
    metrics = ['search_ms', 'total_ms', 'adapter_wall_ms']
    groups = defaultdict(dict)
    for row in rows:
        image, phase, index = int(row['image_index']), row['phase'], int(row['round'])
        need(row['full_ordered_equal'] == '1', 'Output equality')
        key = (phase, index, row['case'])
        need(key not in groups[image], 'Duplicate sample')
        call_round = index+dict(cold=0, warm=1, measured=3)[phase]
        offset = (image+call_round) % 3
        order = cases[offset:]+cases[:offset]
        if (image+call_round) % 2:
            order = order[::-1]
        need(order[int(row['order_position'])] == row['case'], 'Pair order')
        need(all(math.isfinite(float(row[m])) and float(row[m]) > 0 for m in metrics),
             'Timing domain')
        groups[image][key] = row
    expected = {(p, r, c) for p, count in [('cold', 1), ('warm', 2), ('measured', 15)]
                for r in range(count) for c in cases}
    need(set(groups) == set(range(25)), 'Image coverage')
    absolute = {}
    for image, records in sorted(groups.items()):
        need(set(records) == expected, 'Complete phase/round/case pairing')
        reported = summary['per_image'][image]
        need(reported['image_index'] == image, 'Summary image index')
        names = {r['image'] for r in records.values()}
        need(names == {reported['image']}, 'Summary image identity')
        absolute[image] = {}
        for metric in metrics:
            medians = {}
            for case in cases:
                values = [float(records[('measured', r, case)][metric]) for r in range(15)]
                medians[case] = statistics.median(values)
                need(medians[case] == reported['metrics'][metric]['case_median_ms'][case],
                     'Absolute median')
            for label, numerator, denominator in [('on_over_off', cases[2], cases[1]),
                    ('off_over_v11', cases[1], cases[0]), ('on_over_v11', cases[2], cases[0])]:
                ratios = [float(records[('measured', r, numerator)][metric]) /
                          float(records[('measured', r, denominator)][metric]) for r in range(15)]
                existing = reported['metrics'][metric]['paired_ratios'][label]
                need(ratios == existing['all_ratios'] and statistics.median(ratios) == existing['median'],
                     'Paired ratios')
            absolute[image][metric] = medians
    for metric in metrics:
        for label in ('on_over_off', 'off_over_v11', 'on_over_v11'):
            values = [r['metrics'][metric]['paired_ratios'][label]['median'] for r in summary['per_image']]
            rollup = summary['equal_weight_rollups'][metric][label]
            need(statistics.median(values) == rollup['equal_weight_image_median_ratios']['median'], 'Pooled median')
            geo = math.exp(sum(math.log(v) for v in values)/len(values))
            need(math.isclose(geo, rollup['equal_weight_image_median_ratios']['geometric_mean'], rel_tol=1e-14),
                 'Pooled geometric mean')
            need([r['image'] for r, v in zip(summary['per_image'], values) if v > 1] == rollup['regression_images'],
                 'Regression list')
    descriptive = {}
    for label, indices in [('LED8', range(8)), ('case1', [8]), ('tiny16', range(9, 25))]:
        descriptive[label] = {metric: {
            'equal_weight_mean_of_image_medians_ms': {case: statistics.mean(absolute[i][metric][case] for i in indices)
                                                    for case in cases},
            'median_of_image_paired_on_off_medians': statistics.median(
                summary['per_image'][i]['metrics'][metric]['paired_ratios']['on_over_off']['median'] for i in indices),
        } for metric in metrics}
    need(args.csv.read_bytes() == encoded and args.summary.read_bytes() == summary_bytes, 'Input changed')
    result = dict(passed=True, image_decodes=0, matcher_calls=0, rows=1350,
                  csv_sha256=digest(encoded), summary_sha256=digest(summary_bytes),
                  auditor_sha256=digest(Path(__file__).read_bytes()),
                  descriptive_dataset_groups=descriptive,
                  limitation='Arithmetic and sample pairing audit only; native pinned comparator supplies ordered-output '
                             'equality. Dataset group summaries are descriptive, not a new predeclared acceptance rule. '
                             'No memory, accuracy, universal speed or production-promotion conclusion.')
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(passed=True, descriptive_dataset_groups=descriptive)))


if __name__ == '__main__':
    main()
