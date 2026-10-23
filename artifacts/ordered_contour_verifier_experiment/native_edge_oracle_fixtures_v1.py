"""Complete independent expected records for native supplied-label chains.

No optimized edge helpers are imported. Source labels are artificial, not
images. Full native JSON values are compared, including all topology, points,
deletion rounds, ownership and exact weights; empty templates remain null.
Run with -E, active assertions and the parent process watchdog.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import sys

import independent_edge_oracle as oracle


def require(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def grids():
    for mask in range(512):
        yield tuple(tuple((mask + 3 * (3 * y + x)) % 8
                          if mask & (1 << (3 * y + x)) else 255
                          for x in range(3)) for y in range(3))
    rng = random.Random(20261023)
    for index in range(100):
        size = 4 + index % 2
        yield tuple(tuple(rng.randrange(8) if rng.randrange(2) else 255
                          for _ in range(size)) for _ in range(size))
    # Large isolated-point grids add exact LCM arithmetic absent from tiny
    # occupancy graphs. Each block occupies one of its global 4x4 bbox cells.
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53]
    grid = [[255] * 160 for _ in range(160)]
    for cell, count in enumerate(primes):
        cx, cy = 40 * (cell % 4), 40 * (cell // 4)
        for index in range(count):
            x, y = cx + 3 * (index % 13), cy + 3 * (index // 13)
            grid[y][x] = (cell + index) % 8
    yield tuple(tuple(row) for row in grid)
    # Nonmonotonic open path and returning-cycle patterns are already present
    # in exhaustive 3x3 graphs; explicit larger paths retain longer witnesses.
    for size in (9, 31):
        yield tuple(tuple(x % 8 if y == 1 else 255 for x in range(size)) for y in range(3))


def expected(request_id, grid):
    thin = oracle.reference_thinning(grid)
    chains = oracle.reference_chains(grid)
    samplings = [oracle.reference_sampling(chain, len(grid[0])) for chain in chains]
    if any(label != 255 for row in thin.labels for label in row):
        template = asdict(oracle.reference_template(grid))
    else:
        try:
            oracle.reference_template(grid)
        except ValueError:
            template = None
        else:
            raise ValueError('Independent oracle accepted a wholly empty template')
    return dict(request_id=request_id, thinning=asdict(thin),
                raw_chains=[asdict(chain) for chain in chains],
                raw_samplings=[asdict(sampling) for sampling in samplings], template=template)


def generate(output):
    output.mkdir()
    count, empty = 0, 0
    with (output / 'requests.txt').open('w', encoding='ascii', newline='\n') as requests, \
            (output / 'expected.jsonl').open('w', encoding='ascii', newline='\n') as records:
        for count, grid in enumerate(grids(), start=1):
            record = expected(count - 1, grid)
            empty += record['template'] is None
            tokens = ['G1', count - 1, len(grid[0]), len(grid)]
            tokens += [label for row in grid for label in row]
            requests.write(' '.join(map(str, tokens)) + '\n')
            records.write(json.dumps(record, separators=(',', ':')) + '\n')
    require(count == 615, 'Incomplete grid fixture set')
    result = dict(schema='native_edge_oracle_fixture_v1', comparisons=count,
        exhaustive_3x3_occupancies=512, seeded_4x4_5x5=100, seed=20261023,
        additional_large_synthetic_grids=3, null_templates=empty,
        expected_algorithm='Independent degree-two component decomposition, bisect arc sampling and Fraction cell mass',
        full_fields=True, optimized_edge_helpers_used=False, image_count=0,
        inputs=[pin(output / name) for name in ('requests.txt', 'expected.jsonl')])
    (output / 'generation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def reject_float(token):
    raise ValueError('Float is outside exact native JSON evidence: ' + token)


def audit(fixtures, response, output):
    output.mkdir()
    generation = json.loads((fixtures / 'generation.json').read_bytes())
    for declared in generation['inputs']:
        require(pin(Path(declared['path'])) == declared, 'Fixture pin mismatch')
    count, empty, saw_large = 0, 0, False
    with (fixtures / 'expected.jsonl').open(encoding='ascii') as expected_records, \
            response.open(encoding='ascii') as native_records:
        for expected_line in expected_records:
            native_line = next(native_records, None)
            require(native_line is not None, 'Missing native edge result')
            target = json.loads(expected_line, object_pairs_hook=unique)
            actual = json.loads(native_line, object_pairs_hook=unique, parse_float=reject_float,
                                parse_constant=reject_float)
            require(type(actual.get('request_id')) is int and actual['request_id'] == count,
                    'Wrong native request association')
            # JSON bool compares equal to Python ints, so require matching
            # complete value types recursively as well as exact numerical data.
            def same_type_value(left, right):
                require(type(left) is type(right), 'Native JSON type mismatch')
                if isinstance(left, dict):
                    require(left.keys() == right.keys(), 'Native JSON key mismatch')
                    for key in left:
                        same_type_value(left[key], right[key])
                elif isinstance(left, list):
                    require(len(left) == len(right), 'Native JSON length mismatch')
                    for a, b in zip(left, right):
                        same_type_value(a, b)
                else:
                    require(left == right, 'Native JSON field mismatch at record ' + str(count))
            same_type_value(actual, target)
            empty += target['template'] is None
            if count == 612:
                require(target['template'] is not None and target['template']['lcm'] > (1 << 64),
                        'Special fixture failed to exercise GMP LCM')
                saw_large = True
            count += 1
        require(next(native_records, None) is None, 'Extra native edge records')
    require(count == generation['comparisons'] == 615 and empty == generation['null_templates'] and saw_large,
            'Incomplete edge audit')
    result = dict(schema='native_edge_oracle_audit_v1', passed=True, comparisons=count,
        independent_all_fields=True, zero_skips=True, null_templates=empty,
        maximum_lcm_exceeds_uint64=True,
        inputs=[pin(fixtures / 'generation.json'), pin(response)],
        python_flags=dict(optimize=sys.flags.optimize, ignore_environment=sys.flags.ignore_environment,
                          debug=__debug__), image_decodes=0, quality_claim=False, performance_claim=False)
    (output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    require(__debug__ and sys.flags.optimize == 0 and sys.flags.ignore_environment == 1,
            'Use -E with active assertions')
    if len(sys.argv) == 3 and sys.argv[1] == 'generate':
        generate(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 5 and sys.argv[1] == 'audit':
        audit(*(Path(value).resolve() for value in sys.argv[2:]))
    else:
        raise SystemExit('usage: native_edge_oracle_fixtures_v1.py generate fresh_output | audit fixtures responses fresh_output')
