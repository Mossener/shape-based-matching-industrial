"""Independent replay CSV routes, batching and paired arithmetic; no native run."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

from audit_trace import parse, numeric_v11, require

METHODS = ['v11_sort_unique', 'owning_hash_reserve', 'owning_hash_no_reserve',
           'index_hash_reserve', 'index_hash_no_reserve']
FIELDS = ['trace_index', 'case', 'scenario', 'phase', 'round', 'order', 'method',
          'input_count', 'output_count', 'batch', 'copy_ms', 'consolidation_ms',
          'bucket_count', 'zero_score_fallback']


def distribution(values):
    ordered = sorted(values)
    require(ordered and all(math.isfinite(v) and v >= 0 for v in ordered), 'Invalid timings')
    def q(p):
        at = (len(ordered)-1)*p
        return ordered[math.floor(at)]*(math.ceil(at)-at)+ordered[math.ceil(at)]*(at-math.floor(at)) if at % 1 else ordered[int(at)]
    return dict(median=statistics.median(ordered), p10=q(.1), p90=q(.9))


def paired(numerator, denominator):
    require(len(numerator) == len(denominator) and numerator and all(v > 0 for v in denominator), 'Invalid pairs')
    ratios = [a/b for a, b in zip(numerator, denominator)]
    require(all(math.isfinite(v) and v > 0 for v in ratios), 'Invalid paired ratios')
    return ratios, statistics.median(ratios)


def reconstruct(rows, cases, sizeof_match):
    require(len(rows) == 170*len(cases), 'Wrong row count')
    output, cursor = [], 0
    for index, case in enumerate(cases):
        n, u = case['input_count'], case['output_count']
        estimated = sum(sizeof_match+64+length for length in case['class_lengths'])
        batch = min(10000 if n < 64 else 128 if n < 4096 else 1,
                    max(1, 67108864//max(1, estimated)))
        latency, copies, diagnostic = {m: [] for m in METHODS}, {m: [] for m in METHODS}, {}
        for phase, rounds in [('warmup', 3), ('measured', 31)]:
            for iteration in range(rounds):
                offset = (index+iteration) % 5
                route = sorted(range(5), key=lambda value: (value-offset) % 5)
                if (index+iteration) % 2:
                    route = route[::-1]
                for position, method_id in enumerate(route):
                    row = rows[cursor]; cursor += 1
                    require(set(row) == set(FIELDS), 'Wrong CSV fields')
                    method = METHODS[method_id]
                    values = dict(trace_index=index, case=case['case_id'], scenario=case['scenario'],
                                  phase=phase, round=iteration, order=position, method=method,
                                  input_count=n, output_count=u, batch=batch)
                    require(all(row[k] == str(v) for k, v in values.items()), 'Wrong route/count/batch')
                    elapsed, copy = float(row['consolidation_ms']), float(row['copy_ms'])
                    require(math.isfinite(elapsed) and elapsed > 0 and math.isfinite(copy) and copy >= 0,
                            'Nonfinite/nonpositive timing')
                    buckets, fallback = int(row['bucket_count']), int(row['zero_score_fallback'])
                    expected_fallback = int(method_id != 0 and case['has_zero'])
                    require(fallback == expected_fallback and
                            (buckets == 0 if method_id == 0 or case['has_zero'] else buckets >= u),
                            'Wrong hash diagnostic')
                    require(method not in diagnostic or diagnostic[method] == (buckets, fallback),
                            'Unstable bucket/fallback diagnostic')
                    diagnostic[method] = (buckets, fallback)
                    if phase == 'measured':
                        latency[method].append(elapsed); copies[method].append(copy)
        methods = {}
        for i, method in enumerate(METHODS):
            ratios, median = paired(latency[method], latency[METHODS[0]])
            methods[method] = dict(consolidation_ms=distribution(latency[method]),
                                   copy_ms=distribution(copies[method]), paired_ratios=ratios,
                                   paired_ratio_median=median, reserve_input=None if i == 0 else i in (1, 3),
                                   bucket_count=diagnostic[method][0], zero_score_fallback=bool(diagnostic[method][1]))
        output.append(dict(trace_index=index, case_id=case['case_id'], scenario=case['scenario'],
                           input_count=n, output_count=u, batch=batch, methods=methods))
    scenarios = {}
    for scenario in dict.fromkeys(c['scenario'] for c in cases):
        selected = [c for c in output if c['scenario'] == scenario]
        methods = {}
        for method in METHODS:
            ratios = [c['methods'][method]['paired_ratio_median'] for c in selected]
            methods[method] = dict(traces=len(selected), median=statistics.median(ratios),
                                   geometric_mean=math.exp(sum(map(math.log, ratios))/len(ratios)),
                                   regressions=[c['case_id'] for c in selected if c['methods'][method]['paired_ratio_median'] > 1])
        scenarios[scenario] = methods
    return dict(rows=len(rows), measured_rows=155*len(cases), traces=output, scenarios=scenarios)


def compare(expected, actual):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) <= set(actual), 'Missing summary fields')
        for k, value in expected.items():
            compare(value, actual[k])
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(expected) == len(actual), 'Summary list length differs')
        for a, b in zip(expected, actual):
            compare(a, b)
    elif isinstance(expected, float):
        require(type(actual) in (int, float) and math.isclose(expected, actual, rel_tol=1e-12, abs_tol=1e-15),
                'Summary arithmetic differs')
    else:
        require(type(expected) is type(actual) and expected == actual, 'Summary value differs')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--result', type=Path, required=True); p.add_argument('--summary', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); args = p.parse_args()
    root = Path.cwd().resolve(); pins = {}
    sources = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in [Path(__file__), Path(__file__).with_name('audit_trace.py')]}
    def read(path):
        path = Path(path).resolve(strict=True)
        require(path.is_relative_to(root) and path.suffix in ('.json', '.csv', '.bin'), 'Numeric evidence only')
        data = path.read_bytes(); pin = dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
        require(str(path) not in pins or pins[str(path)] == pin, 'Input changed')
        pins[str(path)] = pin; return data
    result_data = read(args.result); result = json.loads(result_data); summary = json.loads(read(args.summary))
    require(result['passed'] is True and result['mode'] == 'measure' and result['performance_measurement'] is True,
            'Successful isolated replay measurement required')
    require(summary['result_sha256'] == hashlib.sha256(result_data).hexdigest(), 'Summary result binding differs')
    native = json.loads(read(result['native']['path']))
    require(native['passed'] is True and native['traces'] == 25 and native['timing_rows'] == 4250 and
            native['matcher_calls'] == native['image_decodes'] == 0 and native['verify_only'] is False,
            'Wrong native measurement scope')
    cases = []
    for case in result['cases']:
        data = read(case['trace']); require(hashlib.sha256(data).hexdigest() == case['trace_sha256'], 'Trace SHA differs')
        before, after = parse(data); require(numeric_v11(before) == after, 'Independent trace grouping differs')
        require((len(before), len(after)) == (case['input_count'], case['output_count']), 'Trace counts differ')
        cases.append(dict(case, class_lengths=[len(r[4]) for r in before],
                          has_zero=any(r[3] & 0x7fffffff == 0 for r in before)))
    require(len(cases) == 25, 'All25 cases required')
    table = csv.DictReader(read(result['timings']['path']).decode().splitlines())
    require(table.fieldnames == FIELDS, 'CSV schema differs')
    calculated = reconstruct(list(table), cases, native['sizeof_match']); compare(calculated, summary)
    for pin in [result['native'], result['timings']]:
        require(pins[str(Path(pin['path']).resolve())] == {k: pin[k] for k in ('sha256', 'size_bytes')}, 'Measured output pin differs')
    for path, pin in pins.items():
        data = Path(path).read_bytes(); require(pin == dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data)), 'Input changed')
    for path, pin in sources.items():
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == pin, 'Audit source changed')
    audit = dict(passed=True, rows=4250, formal_rows=3875, traces=25, input_pins=pins, source_pins=sources,
                 matcher_calls=0, image_decodes=0, scope='Independent trace grouping, complete CSV routes/batching and paired descriptive arithmetic; no whole-matcher or accuracy result')
    with args.output.open('x') as stream:
        stream.write(json.dumps(audit, indent=2)+'\n')
    print(json.dumps({k: v for k, v in audit.items() if k not in ('input_pins', 'source_pins')}))


if __name__ == '__main__':
    main()
