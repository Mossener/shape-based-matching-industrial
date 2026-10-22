"""Independent five-case CSV routes and arithmetic, no benchmark imports/native."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

CASES = [('exact_v11', 'exact_v11', -1), ('linear16_off', 'linear16', 0),
         ('linear16_on', 'linear16', 1), ('direct16_off', 'direct16', 0),
         ('direct16_on', 'direct16', 1)]
METRICS = ['pyramid_ms', 'gradient_ms', 'spread_ms', 'response_ms', 'linearize_ms',
           'preprocess_ms', 'search_ms', 'total_ms', 'adapter_wall_ms']
PAIRS = [('direct16_on', 'direct16_off'), ('linear16_on', 'linear16_off'),
         ('direct16_on', 'linear16_on'), ('direct16_off', 'linear16_off'),
         ('linear16_off', 'exact_v11'), ('direct16_off', 'exact_v11')]
FIELDS = ['image', 'image_index', 'width', 'height', 'templates', 'threshold',
          'phase', 'round', 'order_position', 'case', 'variant', 'cache',
          *METRICS, 'result_count', 'full_ordered_equal']


def need(value, message):
    if not value:
        raise ValueError(message)


def stats(values):
    need(values and all(math.isfinite(v) and v >= 0 for v in values), 'Invalid observations')
    ordered = sorted(values)
    def percentile(p):
        index = p*(len(ordered)-1)
        low = math.floor(index)
        return ordered[low]+(ordered[math.ceil(index)]-ordered[low])*(index-low)
    return dict(count=len(values), median=statistics.median(values),
                geomean=0. if min(values) == 0 else math.exp(sum(map(math.log, values))/len(values)),
                p10=percentile(.1), p90=percentile(.9), min=min(values), max=max(values))


def compare(a, b):
    if isinstance(a, dict):
        need(isinstance(b, dict) and set(a) <= set(b), 'Missing summary fields')
        for key, value in a.items():
            compare(value, b[key])
    elif isinstance(a, list):
        need(isinstance(b, list) and len(a) == len(b), 'Summary list length differs')
        for x, y in zip(a, b):
            compare(x, y)
    elif isinstance(a, float):
        need(type(b) in (int, float) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15), 'Arithmetic differs')
    else:
        need(type(a) is type(b) and a == b, 'Summary identity/count differs')


def reconstruct(rows, names):
    need(len(names) == len(set(names)) == 25 and len(rows) == 2250, 'Wrong fixed scope')
    need(names[:9] == ['LED_'+str(i) for i in range(1, 9)]+['case1'], 'Wrong fixture order')
    measured, cursor = {}, 0
    for image, name in enumerate(names):
        count, geometry = None, None
        for phase, rounds, offset, parity in [('cold', 1, 0, 0), ('warm', 2, 1, 1), ('measured', 15, 3, 0)]:
            for iteration in range(rounds):
                rotation = (image+offset+iteration) % 5
                route = sorted(range(5), key=lambda v: (v-rotation) % 5)
                if (image+iteration//5+parity) % 2:
                    route.reverse()
                for position, case_id in enumerate(route):
                    row = rows[cursor]; cursor += 1
                    need(set(row) == set(FIELDS), 'Wrong CSV field set')
                    identity, variant, cache = CASES[case_id]
                    expected = dict(image=name, image_index=image, phase=phase, round=iteration,
                                    order_position=position, case=identity, variant=variant, cache=cache,
                                    templates=900 if image < 8 else 361 if image == 8 else 2212,
                                    threshold=75 if image < 8 else 90 if image == 8 else 85,
                                    full_ordered_equal=1)
                    need(all(row[k] == str(v) for k, v in expected.items()), 'Wrong sample route/identity')
                    shape = (int(row['width']), int(row['height']))
                    alignment = 32 if image < 8 else 16
                    need(min(shape) > 0 and all(v % alignment == 0 for v in shape) and
                         (geometry is None or shape == geometry), 'Changing or unaligned image shape')
                    geometry = shape
                    need(int(row['result_count']) >= 0 and
                         (count is None or int(row['result_count']) == count), 'Changing output count')
                    count = int(row['result_count'])
                    values = {m: float(row[m]) for m in METRICS}
                    need(all(math.isfinite(v) and v >= 0 for v in values.values()), 'Invalid timing')
                    # The core includes transient buffer destruction in total.
                    # Both inclusive clocks may exceed their named sub-stages.
                    need(values['preprocess_ms']+1e-8 >= sum(values[m] for m in METRICS[:5]) and
                         values['total_ms']+1e-8 >= values['preprocess_ms']+values['search_ms'],
                         'Inconsistent inclusive internal timing')
                    if phase == 'measured':
                        key = name, iteration, identity
                        need(key not in measured, 'Duplicate measured sample')
                        measured[key] = values
    need(len(measured) == 1875, 'Incomplete measured samples')
    group_names = {'LED': names[:8], 'case1': names[8:9], 'tiny': names[9:]}
    ratios, absolute = {}, {}
    for metric in ['preprocess_ms', 'search_ms', 'total_ms', 'adapter_wall_ms']:
        ratios[metric] = {}
        for numerator, denominator in PAIRS:
            per_image = {}
            for name in names:
                values = []
                for iteration in range(15):
                    den = measured[name, iteration, denominator][metric]
                    need(den > 0, 'Zero ratio denominator')
                    values.append(measured[name, iteration, numerator][metric]/den)
                per_image[name] = dict(stats(values), ratios=values)
            medians = [per_image[name]['median'] for name in names]
            records = [dict(image=name, median_ratio=per_image[name]['median']) for name in names]
            ratios[metric][numerator+'__over__'+denominator] = dict(
                numerator=numerator, denominator=denominator, per_image=per_image,
                equal_weight_image_medians=stats(medians),
                pooled_round_ratios=stats([v for name in names for v in per_image[name]['ratios']]),
                groups={label: stats([per_image[n]['median'] for n in subset]) for label, subset in group_names.items()},
                regressions=[r for r in records if r['median_ratio'] > 1],
                all_images_by_descending_ratio=sorted(records, key=lambda r: (-r['median_ratio'], r['image'])))
    descriptive = {}
    for metric in METRICS:
        absolute[metric] = {}
        for identity, _, _ in CASES:
            per_image = {name: stats([measured[name, i, identity][metric] for i in range(15)]) for name in names}
            absolute[metric][identity] = dict(per_image=per_image,
                equal_weight_image_medians=stats([per_image[name]['median'] for name in names]),
                pooled_round_observations=stats([measured[name, i, identity][metric] for name in names for i in range(15)]))
    for label, subset in group_names.items():
        descriptive[label] = {metric: {identity: statistics.mean(absolute[metric][identity]['per_image'][name]['median']
                                                               for name in subset)
                                      for identity, _, _ in CASES}
                              for metric in ['search_ms', 'total_ms', 'adapter_wall_ms']}
    return dict(image_names=names, measured_rounds=15, ratios=ratios, absolute_ms=absolute), descriptive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', required=True, type=Path); parser.add_argument('--summary', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path); args = parser.parse_args()
    need(not args.output.exists(), 'Output must be fresh')
    source_path = Path(__file__).resolve()
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    pins = {}
    def read(path):
        path = Path(path).resolve(strict=True); data = path.read_bytes()
        need(path.is_relative_to(Path.cwd()) and path.suffix in ('.json', '.csv'), 'Contained numeric evidence only')
        pin = dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
        need(str(path) not in pins or pins[str(path)] == pin, 'Input changed')
        pins[str(path)] = pin; return data
    result = json.loads(read(args.result)); summary = json.loads(read(args.summary))
    need(result['passed'] is True and result['actual_matcher_calls'] ==
         dict(exact_v11=450, linear16=900, direct16=900, total=2250), 'Incomplete native run')
    data = read(result['csv']['path'])
    need(pins[str(Path(result['csv']['path']).resolve())] == {k: result['csv'][k] for k in ('sha256', 'size_bytes')}, 'CSV pin differs')
    need(summary['run_evidence']['sha256'] == pins[str(args.result.resolve())]['sha256'], 'Summary result differs')
    calculated, descriptive = reconstruct(list(csv.DictReader(data.decode('utf-8-sig').splitlines())), result['image_names'])
    compare(calculated, summary)
    for path, pin in pins.items():
        data = Path(path).read_bytes(); need(pin == dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data)), 'Input changed')
    need(hashlib.sha256(source_path.read_bytes()).hexdigest() == source_sha256, 'Audit source changed')
    report = dict(passed=True, rows=2250, measured_rows=1875, images=25, input_pins=pins,
                  audit_source_sha256=source_sha256,
                  descriptive_mean_of_image_medians_ms=descriptive, matcher_calls=0, image_decodes=0,
                  limitation='Independent saved routes and descriptive arithmetic only; native comparator supplies complete output equality, no universal speed or accuracy conclusion')
    with args.output.open('x') as stream:
        stream.write(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'input_pins'}))


if __name__ == '__main__':
    main()
