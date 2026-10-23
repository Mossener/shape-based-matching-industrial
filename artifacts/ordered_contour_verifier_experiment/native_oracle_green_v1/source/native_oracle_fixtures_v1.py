"""Independent expected values and complete audit for bounded native Q1/R1.

Generate and audit are separate externally guarded child invocations. Expected
scores, cases and witnesses use only the independent partial-injection oracle.
The optimized Python solver is consulted by audit only for work counters.
No elapsed time here is a matching performance benchmark.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import independent_tiny_oracle as oracle
from weighted_ordered_match import SceneChain, TemplateChain

LIMIT = 67108864
COUNTERS = ('case_count', 'edge_states', 'fenwick_queries', 'fenwick_updates',
            'fenwick_query_visits', 'fenwick_update_visits', 'maximum_integer_bits')


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def carrier(template_id, reference):
    case = reference.case
    return SimpleNamespace(template_chain_id=template_id,
        numerator=reference.numerator, independent_numerator=reference.independent_numerator,
        total_weight=reference.total_weight, witness=reference.witness,
        case=None if case is None else SimpleNamespace(scene_chain_id=case[0],
            direction=case[1], template_cut=case[2], scene_cut=case[3]))


def encode(request_id, template, scenes):
    tokens = ['Q1', request_id, template.chain_id, int(template.closed),
              len(template.sample_ids), len(scenes)]
    for sample, weight in zip(template.sample_ids, template.weights):
        tokens.extend((sample, weight))
    for scene in scenes:
        tokens.extend((scene.chain_id, int(scene.closed), len(scene.pixel_ids), len(scene.edges)))
        tokens.extend(scene.pixel_ids)
        for edge in scene.edges:
            tokens.extend(edge)
    return ' '.join(map(str, tokens)) + '\n'


def decode(line):
    tokens = iter(line.split())
    assert next(tokens) == 'Q1'
    request_id, template_id, closed, n, count = (int(next(tokens)) for _ in range(5))
    samples, weights = [], []
    for _ in range(n):
        samples.append(int(next(tokens)))
        weights.append(int(next(tokens)))
    template = TemplateChain(template_id, tuple(samples), tuple(weights), bool(closed))
    scenes = []
    for _ in range(count):
        identity, closed, m, e = (int(next(tokens)) for _ in range(4))
        pixels = tuple(int(next(tokens)) for _ in range(m))
        edges = tuple((int(next(tokens)), int(next(tokens))) for _ in range(e))
        scenes.append(SceneChain(identity, pixels, edges, bool(closed)))
    assert next(tokens, None) is None
    return request_id, template, tuple(scenes)


def special_cases():
    # Arbitrary scoring weights exercise the typed mathematical API. They are
    # expressly additional abstract supplied-graph cases, not bbox geometries.
    maximum = (1 << 64) - 1
    for template_closed in (False, True):
        for scene_closed in (False, True):
            template = TemplateChain(maximum, (maximum, 0, 19),
                                     ((1 << 1100) + 3, (1 << 1099) + 7, 5), template_closed)
            scenes = (SceneChain(maximum, (0, maximum, 31),
                        ((maximum, 31), (0, maximum), (19, 0)), scene_closed),
                      SceneChain(0, (31, maximum, 0),
                        ((maximum, 31), (0, maximum), (19, 0)), scene_closed),
                      SceneChain(12, (), (), scene_closed))
            yield template, scenes
            yield template, tuple(reversed(scenes))
    yield TemplateChain(0, (), (), True), ()
    yield TemplateChain(maximum, (maximum,), (1 << 1100,), False), ()
    yield TemplateChain(0, (4,), (7,), False), (SceneChain(2, (3,), (), True),)
    yield TemplateChain(0, (), (), False), (SceneChain(maximum, (3, 2), (), True),)


def generate(output):
    output.mkdir()
    count = 0
    requests_path, expected_path = output / 'requests.txt', output / 'expected.jsonl'
    with requests_path.open('w', encoding='ascii', newline='\n') as requests, \
            expected_path.open('w', encoding='ascii', newline='\n') as expectations:
        def capture(template, scenes):
            nonlocal count
            reference = oracle.brute_force(template, scenes)
            requests.write(encode(count, template, scenes))
            expectations.write(json.dumps(dict(request_id=count, template_chain_id=template.chain_id,
                                               **asdict(reference)), separators=(',', ':')) + '\n')
            count += 1
            return carrier(template.chain_id, reference)
        exhaustive = oracle.run_exhaustive(capture, seconds=45)
        seeded = oracle.run_seeded(capture, seed=20261023, seconds=8)
        extra = 0
        for template, scenes in special_cases():
            result = capture(template, scenes)
            oracle.audit_result(template, scenes, result)
            extra += 1
    assert count == 24912 + 100 + 12
    assert requests_path.stat().st_size + expected_path.stat().st_size < LIMIT
    result = dict(schema='native_ordered_oracle_fixture_v1', comparisons=count,
        exhaustive=exhaustive, seeded=seeded, special_abstract_cases=extra,
        expected_algorithm='independent partial injective enumeration and original cyclic-order predicate',
        expected_numeric_fields='B, A, total, full canonical case and original-ID witness',
        optimized_solver_used_for_expected=False,
        inputs=[pin(requests_path), pin(expected_path)], images=0, quality_claim=False,
        performance_claim=False)
    (output / 'generation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


def parse_response(line):
    tokens = iter(line.split())
    assert next(tokens) == 'R1', 'native returned non-result record'
    identity, template_id, b, a, total, has_case = (int(next(tokens)) for _ in range(6))
    assert has_case in (0, 1)
    case = tuple(int(next(tokens)) for _ in range(4)) if has_case else None
    length = int(next(tokens))
    assert 0 <= length <= 8
    witness = tuple((int(next(tokens)), int(next(tokens))) for _ in range(length))
    counters = tuple(int(next(tokens)) for _ in COUNTERS)
    assert all(0 <= value <= (1 << 64) - 1 for value in counters)
    assert next(tokens, None) is None, 'native output has extra fields'
    reference = oracle.OracleResult(b, a, total, case, witness, 0)
    return identity, template_id, reference, dict(zip(COUNTERS, counters))


def audit(fixtures, responses, output):
    # This import cannot supply any expected score/case/witness. Those fields
    # are compared against frozen independent expectations before this call.
    from weighted_ordered_match import solve
    output.mkdir()
    generation = json.loads((fixtures / 'generation.json').read_bytes())
    for declared in generation['inputs']:
        assert pin(Path(declared['path'])) == declared
    assert responses.stat().st_size < LIMIT
    count = 0
    with (fixtures / 'requests.txt').open(encoding='ascii') as requests, \
            (fixtures / 'expected.jsonl').open(encoding='ascii') as expectations, \
            responses.open(encoding='ascii') as actuals:
        for line in requests:
            expected_line, actual_line = next(expectations, None), next(actuals, None)
            assert expected_line is not None and actual_line is not None, ('missing record', count)
            request_id, template, scenes = decode(line)
            expected = json.loads(expected_line)
            identity, template_id, actual, counters = parse_response(actual_line)
            assert identity == request_id == expected['request_id'] == count
            assert template_id == template.chain_id == expected['template_chain_id']
            expected_reference = oracle.OracleResult(expected['numerator'], expected['independent_numerator'],
                expected['total_weight'], None if expected['case'] is None else tuple(expected['case']),
                tuple(tuple(edge) for edge in expected['witness']), expected['partial_injections_checked'])
            oracle.audit_result(template, scenes, carrier(template_id, actual), reference=expected_reference)
            python_counters = asdict(solve(template, scenes).work)
            assert counters == python_counters, ('work counters differ', count, counters, python_counters)
            count += 1
        assert next(expectations, None) is None and next(actuals, None) is None, 'extra records'
    assert count == generation['comparisons'] == 25024
    result = dict(schema='native_ordered_oracle_audit_v1', passed=True, comparisons=count,
        all_exact_scores_cases_witnesses=True, independent_expected_values=True,
        counters_compared_against_optimized_python=True, independent_counter_oracle=False,
        complete_no_skips=True, inputs=[pin(fixtures / 'generation.json'), pin(responses)],
        quality_claim=False, performance_claim=False)
    (output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'generate':
        generate(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 5 and sys.argv[1] == 'audit':
        audit(*(Path(value).resolve() for value in sys.argv[2:]))
    else:
        raise SystemExit('usage: native_oracle_fixtures_v1.py generate fresh_output | audit fixtures responses fresh_output')
