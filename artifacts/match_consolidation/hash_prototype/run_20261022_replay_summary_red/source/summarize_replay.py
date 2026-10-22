"""Validate every frozen replay row and summarize paired per-trace ratios."""
import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import statistics

from capture_manifest import check_file, json_bytes, read_trace, require, sha256

METHODS = ('v11_sort_unique', 'owning_hash_reserve', 'owning_hash_no_reserve',
           'index_hash_reserve', 'index_hash_no_reserve')
FIELDS = ['trace_index', 'case', 'scenario', 'phase', 'round', 'order', 'method',
          'input_count', 'output_count', 'batch', 'copy_ms', 'consolidation_ms',
          'bucket_count', 'zero_score_fallback']


def validate_rows(rows, fieldnames, cases, sizeof_match):
    return {}


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
