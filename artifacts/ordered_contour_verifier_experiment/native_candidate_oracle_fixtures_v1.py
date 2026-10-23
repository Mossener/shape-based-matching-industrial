"""Exact independent expected records for 6,144 supplied-label candidates.

The mask/profile/template/transform order is the frozen exhaustive loop in
test_independent_candidate_oracle.py. Expected scene and score values come only
from independent_candidate_oracle.reference_scene/reference_candidate. Their
dependency path uses independent edge decomposition and partial injections;
no optimized Python implementation supplies an expectation or work counter.

Full JSON scene and candidate fields are audited, omitting solver work only.
Counter behavior is not independently verified here. No image is opened.
Run with -E -B, active assertions and the parent process watchdog.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

import independent_candidate_oracle as reference


COMPARISONS = 6144
LOOP_ORDER = ['scene_occupancy', 'direction_profile', 'template', 'transform']


def require(value, message):
    if not value:
        raise ValueError(message)


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def grid(width, height, foreground, label=0):
    foreground = dict(foreground) if isinstance(foreground, dict) else {
        pixel: label for pixel in foreground}
    return tuple(tuple(foreground.get(y * width + x, 255)
                       for x in range(width)) for y in range(height))


def cases():
    """Reproduce the frozen exhaustive test without pruning any occupancy."""
    templates = (grid(3, 3, (4,)), ((0, 0, 0, 0, 0),),
                 grid(3, 3, (1, 3, 5, 7)))
    transforms = (((0, 0), (0, 0), (0, 0, 0, 0)),
                  ((2, 1), (1, 2), (1, 0, 0, 1)))
    label_profiles = ((0,) * 9, (0, 7, 2, 6, 4, 1, 5, 3, 0))
    for mask in range(512):
        for labels in label_profiles:
            scene_grid = grid(3, 3, {pixel: labels[pixel]
                                    for pixel in range(9) if mask & (1 << pixel)})
            for template_grid in templates:
                for tl, match, padding in transforms:
                    yield template_grid, scene_grid, tl, match, padding


def request_line(request_id, template, scene, tl, match, padding):
    tokens = ['C1', request_id, len(template[0]), len(template), len(scene[0]), len(scene)]
    tokens += list(tl) + list(match) + list(padding)
    tokens += [label for row in template for label in row]
    tokens += [label for row in scene for label in row]
    return ' '.join(map(str, tokens)) + '\n'


def expected(request_id, template, scene, tl, match, padding):
    return dict(request_id=request_id,
                scene=asdict(reference.reference_scene(scene)),
                score=asdict(reference.reference_candidate(template, scene, tl, match, padding)))


def fresh_counts():
    return dict(candidate_comparisons=0, chain_brute_force_comparisons=0,
                maximum_owned_template_samples=0, maximum_scene_chain_points=0,
                empty_scene_records=0, outside_padded_records=0,
                outside_original_records=0, negative_relative_sample_rows=0,
                cross_chain_reuse_records=0)


def observe(counts, record):
    scene, score = record['scene'], record['score']
    # Every one of the three frozen templates has exactly one original chain;
    # its support-row count is therefore also its owned-chain point count.
    require(len(score['chains']) == 1, 'Frozen template chain domain changed')
    counts['candidate_comparisons'] += 1
    counts['chain_brute_force_comparisons'] += len(score['chains'])
    counts['maximum_owned_template_samples'] = max(
        counts['maximum_owned_template_samples'], len(score['samples']))
    scene_maximum = max((len(chain['pixel_ids']) for chain in scene['chains']), default=0)
    require(scene_maximum <= 8, 'Scene chain exceeds tiny reference domain; no skip permitted')
    counts['maximum_scene_chain_points'] = max(counts['maximum_scene_chain_points'], scene_maximum)
    counts['empty_scene_records'] += not scene['chains']
    counts['outside_padded_records'] += bool(score['outside_padded_sample_ids'])
    counts['outside_original_records'] += bool(score['outside_original_sample_ids'])
    counts['negative_relative_sample_rows'] += sum(
        any(coordinate < 0 for coordinate in sample['relative']) for sample in score['samples'])
    counts['cross_chain_reuse_records'] += bool(score['cross_chain_reused_pixel_ids'])


def validate_counts(counts):
    require(counts['candidate_comparisons'] == COMPARISONS, 'Incomplete candidate fixture domain')
    require(counts['chain_brute_force_comparisons'] == COMPARISONS,
            'Incomplete original template-chain domain')
    require(counts['maximum_owned_template_samples'] == 3, 'Wrong frozen template sample domain')
    require(0 < counts['maximum_scene_chain_points'] <= 8, 'Wrong tiny scene-chain domain')
    require(counts['empty_scene_records'] > 0 and counts['outside_padded_records'] > 0 and
            counts['outside_original_records'] > 0 and counts['negative_relative_sample_rows'] > 0,
            'Empty-scene or coordinate-frame coverage was lost')


def domain_counts(counts):
    return dict(scene_occupancies=512, direction_profiles=2, templates=3, transforms=2,
                scene_profile_combinations=1024, skipped_cases=0, **counts)


def generate(output):
    output.mkdir()
    counts = fresh_counts()
    with (output / 'requests.txt').open('w', encoding='ascii', newline='\n') as requests, \
            (output / 'expected.jsonl').open('w', encoding='ascii', newline='\n') as records:
        for request_id, supplied in enumerate(cases()):
            record = expected(request_id, *supplied)
            observe(counts, record)
            requests.write(request_line(request_id, *supplied))
            records.write(json.dumps(record, separators=(',', ':'), allow_nan=False) + '\n')
    validate_counts(counts)
    result = dict(schema='native_candidate_oracle_fixture_v1', comparisons=COMPARISONS,
        domain_counts=domain_counts(counts), loop_order=LOOP_ORDER,
        expected_algorithms=['independent_candidate_oracle.reference_scene',
                             'independent_candidate_oracle.reference_candidate'],
        independent_ordered_objective='Partial injective correspondences with original circular order',
        full_scene_fields=True, full_candidate_fields_except_work=True,
        optimized_python_expectations_used=False, work_counters_independently_verified=False,
        image_count=0, inputs=[pin(output / name) for name in ('requests.txt', 'expected.jsonl')],
        python_flags=dict(optimize=sys.flags.optimize, ignore_environment=sys.flags.ignore_environment,
                          debug=__debug__))
    (output / 'generation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def reject_number(token):
    raise ValueError('Float/nonfinite token is outside exact JSON evidence: ' + token)


def exact_json(line):
    return json.loads(line, object_pairs_hook=unique, parse_float=reject_number,
                      parse_constant=reject_number)


def same_type_value(actual, target, path):
    # JSON bool compares equal to Python int; equality alone is insufficient.
    require(type(actual) is type(target), 'JSON type mismatch at ' + path)
    if isinstance(target, dict):
        require(actual.keys() == target.keys(), 'JSON key mismatch at ' + path)
        for key in target:
            same_type_value(actual[key], target[key], path + '.' + key)
    elif isinstance(target, list):
        require(len(actual) == len(target), 'JSON length mismatch at ' + path)
        for index, (left, right) in enumerate(zip(actual, target)):
            same_type_value(left, right, path + '[' + str(index) + ']')
    else:
        require(actual == target, 'JSON field mismatch at ' + path)


def audit(fixtures, response, output):
    output.mkdir()
    generation = exact_json((fixtures / 'generation.json').read_text(encoding='utf-8'))
    require(type(generation['comparisons']) is int and generation['comparisons'] == COMPARISONS,
            'Wrong generated candidate comparison count')
    require(generation['loop_order'] == LOOP_ORDER, 'Fixture loop order changed')
    for declared in generation['inputs']:
        require(pin(Path(declared['path'])) == declared, 'Fixture pin mismatch')
    counts = fresh_counts()
    with (fixtures / 'requests.txt').open(encoding='ascii', newline='') as requests, \
            (fixtures / 'expected.jsonl').open(encoding='ascii') as expected_records, \
            response.open(encoding='ascii') as native_records:
        for request_id, supplied in enumerate(cases()):
            require(next(requests, None) == request_line(request_id, *supplied),
                    'Request skipped/reordered or outside frozen domain at ' + str(request_id))
            expected_line, native_line = next(expected_records, None), next(native_records, None)
            require(expected_line is not None, 'Missing independent candidate record')
            require(native_line is not None, 'Missing native candidate result')
            target, actual = exact_json(expected_line), exact_json(native_line)
            require(type(target) is dict and type(actual) is dict, 'Candidate result must be an object')
            require(type(target.get('request_id')) is int and target['request_id'] == request_id,
                    'Wrong independent request association')
            require(type(actual.get('request_id')) is int and actual['request_id'] == request_id,
                    'Wrong native request association')
            same_type_value(actual, target, 'record[' + str(request_id) + ']')
            observe(counts, target)
        require(next(requests, None) is None, 'Extra candidate request')
        require(next(expected_records, None) is None, 'Extra independent candidate record')
        require(next(native_records, None) is None, 'Extra native candidate record')
    validate_counts(counts)
    same_type_value(domain_counts(counts), generation['domain_counts'], 'domain_counts')
    for declared in generation['inputs']:
        require(pin(Path(declared['path'])) == declared, 'Fixture changed during audit')
    result = dict(schema='native_candidate_oracle_audit_v1', passed=True, comparisons=COMPARISONS,
        domain_counts=domain_counts(counts), loop_order=LOOP_ORDER, zero_skips=True,
        independent_all_scene_fields=True, independent_all_candidate_fields_except_work=True,
        optimized_python_expectations_used=False, work_counters_independently_verified=False,
        exact_json_types=True, duplicate_keys_rejected=True, floats_and_constants_rejected=True,
        inputs=[pin(fixtures / 'generation.json'), pin(response)],
        python_flags=dict(optimize=sys.flags.optimize, ignore_environment=sys.flags.ignore_environment,
                          debug=__debug__), image_decodes=0, quality_claim=False, performance_claim=False)
    (output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    require(__debug__ and sys.flags.optimize == 0 and sys.flags.ignore_environment == 1,
            'Use -E -B with active assertions')
    if len(sys.argv) == 3 and sys.argv[1] == 'generate':
        generate(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 5 and sys.argv[1] == 'audit':
        audit(*(Path(value).resolve() for value in sys.argv[2:]))
    else:
        raise SystemExit('usage: native_candidate_oracle_fixtures_v1.py generate fresh_output | audit fixtures responses fresh_output')
