"""Validate every frozen replay row and summarize paired per-trace ratios."""
import argparse
import csv
import json
import math
from pathlib import Path
import re
import statistics

from capture_manifest import check_file, json_bytes, read_trace, require, sha256

METHODS = ('v11_sort_unique', 'owning_hash_reserve', 'owning_hash_no_reserve',
           'index_hash_reserve', 'index_hash_no_reserve')
FIELDS = ['trace_index', 'case', 'scenario', 'phase', 'round', 'order', 'method',
          'input_count', 'output_count', 'batch', 'copy_ms', 'consolidation_ms',
          'bucket_count', 'zero_score_fallback']


def validate_rows(rows, fieldnames, cases, sizeof_match):
    require(fieldnames == FIELDS, 'Replay CSV columns/order differ')
    require(type(sizeof_match) is int and 0 < sizeof_match < (1 << 64), 'Invalid sizeof(Match)')
    require(isinstance(cases, list) and cases, 'Replay cases required')
    require(len(rows) == len(cases)*170, 'Replay row count differs')

    def uint(value):
        require(isinstance(value, str) and re.fullmatch(r'0|[1-9][0-9]*', value),
                'Replay unsigned integer required')
        number = int(value)
        require(number < (1 << 64), 'Replay unsigned integer overflow')
        return number

    def latency(value, positive):
        require(isinstance(value, str), 'Replay numeric string required')
        try:
            number = float(value)
        except ValueError as error:
            raise ValueError('Replay numeric timing required') from error
        require(math.isfinite(number) and (number > 0 if positive else number >= 0),
                'Replay timing must be finite and positive/nonnegative')
        return number

    def distribution(values):
        ordered = sorted(values)

        def quantile(fraction):
            position = (len(ordered)-1)*fraction
            index = math.floor(position)
            return ordered[index] if index == len(ordered)-1 else (
                ordered[index]+(ordered[index+1]-ordered[index])*(position-index))

        return dict(median=statistics.median(values), p10=quantile(.1), p90=quantile(.9))

    traces, seen = [], set()
    offset = 0
    for index, case in enumerate(cases):
        require(isinstance(case, dict), 'Replay case object required')
        identity, scenario = case['case_id'], case['scenario']
        require(all(isinstance(value, str) and value and not any(c in value for c in ',\t\r\n')
                    for value in (identity, scenario)) and identity not in seen, 'Invalid/duplicate case identity')
        seen.add(identity)
        count, unique = case['input_count'], case['output_count']
        require(type(count) is int and type(unique) is int and 0 <= unique <= count < (1 << 64),
                'Replay case counts differ')
        lengths, has_zero = case['class_bytes'], case['has_zero']
        require(isinstance(lengths, list) and len(lengths) == count and
                all(type(value) is int and 0 <= value < (1 << 64) for value in lengths),
                'Replay class-byte counts differ')
        require(type(has_zero) is bool and (not has_zero or count > 0), 'Invalid zero-score case flag')
        estimated = sum(sizeof_match+64+length for length in lengths)
        require(estimated < (1 << 64), 'Replay batch estimate overflow')
        base = 10000 if count < 64 else 128 if count < 4096 else 1
        batch = min(base, max(1, 67108864//max(1, estimated)))
        timings = {method: [] for method in METHODS}
        copies = {method: [] for method in METHODS}
        diagnostics = {}
        for phase, rounds in (('warmup', 3), ('measured', 31)):
            for round_index in range(rounds):
                rotation = (index+round_index) % 5
                order = list(range(rotation, 5))+list(range(rotation))
                if (index+round_index) % 2:
                    order.reverse()
                for position, method_index in enumerate(order):
                    method = METHODS[method_index]
                    row = rows[offset]
                    offset += 1
                    require(isinstance(row, dict) and set(row) == set(FIELDS), 'Replay row fields differ')
                    expected = dict(trace_index=index, round=round_index, order=position,
                                    input_count=count, output_count=unique, batch=batch)
                    require(all(uint(row[field]) == value for field, value in expected.items()),
                            'Replay route/count/batch differs')
                    require(row['case'] == identity and row['scenario'] == scenario and
                            row['phase'] == phase and row['method'] == method,
                            'Replay case/phase/method/order differs')
                    copy_ms = latency(row['copy_ms'], False)
                    consolidation_ms = latency(row['consolidation_ms'], True)
                    buckets, fallback = uint(row['bucket_count']), uint(row['zero_score_fallback'])
                    expected_fallback = int(method_index != 0 and has_zero)
                    require(fallback == expected_fallback, 'Replay zero-score fallback differs')
                    require((buckets == 0) if method_index == 0 or has_zero else buckets >= unique,
                            'Replay bucket diagnostic differs')
                    diagnostic = (buckets, fallback)
                    require(method not in diagnostics or diagnostics[method] == diagnostic,
                            'Replay diagnostic changed across rounds')
                    diagnostics[method] = diagnostic
                    if phase == 'measured':
                        timings[method].append(consolidation_ms)
                        copies[method].append(copy_ms)
        methods = {}
        for method in METHODS:
            ratios = [candidate/baseline for candidate, baseline in zip(timings[method], timings[METHODS[0]])]
            require(all(math.isfinite(value) and value > 0 for value in ratios), 'Invalid paired latency ratio')
            buckets, fallback = diagnostics[method]
            methods[method] = dict(consolidation_ms=distribution(timings[method]),
                                   copy_ms=distribution(copies[method]), paired_ratios=ratios,
                                   paired_ratio_median=statistics.median(ratios),
                                   reserve_input=None if method == METHODS[0] else method in (METHODS[1], METHODS[3]),
                                   bucket_count=buckets, zero_score_fallback=bool(fallback))
        traces.append(dict(trace_index=index, case_id=identity, scenario=scenario, input_count=count,
                           output_count=unique, batch=batch, methods=methods))
    scenarios = {}
    for scenario in dict.fromkeys(trace['scenario'] for trace in traces):
        selected = [trace for trace in traces if trace['scenario'] == scenario]
        scenarios[scenario] = {}
        for method in METHODS:
            ratios = [trace['methods'][method]['paired_ratio_median'] for trace in selected]
            geometric_mean = math.exp(math.fsum(math.log(value) for value in ratios)/len(ratios))
            scenarios[scenario][method] = dict(traces=len(selected),
                median=statistics.median(ratios), geometric_mean=geometric_mean,
                regressions=[trace['case_id'] for trace in selected
                             if trace['methods'][method]['paired_ratio_median'] > 1])
    return dict(rows=len(rows), measured_rows=len(cases)*155, traces=traces, scenarios=scenarios,
                ratio_direction='Candidate/V11; lower is faster',
                quantiles='Linear interpolation at (n-1)*p; descriptive only')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result_path = args.result.resolve(strict=True)
    before = sha256(result_path)
    result = json_bytes(result_path.read_bytes())
    require(result['passed'] is True and result['mode'] == 'measure', 'Successful replay measurement required')
    for item in result['input_pins']+[result['native'], result['timings']]:
        check_file(Path(item['path']), item, 'replay summary input before')
    native = json_bytes(Path(result['native']['path']).read_bytes())
    cases = []
    for case in result['cases']:
        trace = read_trace(Path(case['trace']).read_bytes())
        cases.append(dict(case, class_bytes=[len(record[3]) for record in trace['input']],
                          has_zero=any((record[2] & 0x7fffffff) == 0 for record in trace['input'])))
    with Path(result['timings']['path']).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        summary = validate_rows(list(reader), reader.fieldnames, cases, native['sizeof_match'])
    for item in result['input_pins']+[result['native'], result['timings']]:
        check_file(Path(item['path']), item, 'replay summary input after')
    require(sha256(result_path) == before, 'Replay result changed during summary')
    summary.update(result_sha256=before, performance_scope='Isolated consolidation replay only',
                   limitation='No whole-matcher, accuracy, industrial deployment or measured-memory gain follows; '
                              'all actual85 traces have positive duplicates and N21..2695, no historical486k pressure')
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(dict(passed=True, output=str(args.output), rows=summary['rows'])))


if __name__ == '__main__':
    main()
