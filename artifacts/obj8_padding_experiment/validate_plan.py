"""Read-only static validation of the declared object-8 padding experiment.

Reads numeric plans and serialized-bank bytes only. Never decodes images,
loads OpenCV, compiles code, trains or invokes a matcher.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

U64_MAX = (1 << 64) - 1


def checked(value):
    if not isinstance(value, int) or value < 0 or value > U64_MAX:
        raise ValueError('Unsigned 64-bit arithmetic bound')
    return value


def align(value, multiple):
    if multiple <= 0:
        raise ValueError('Positive alignment required')
    return checked(checked(value + multiple - 1) // multiple * multiple)


def plan(original, base_padding, layers, budget_pixels=1048576):
    if not layers or len(original) != 2 or len(base_padding) != 4:
        raise ValueError('Missing dimensions/layers')
    if any(v <= 0 for v in original) or any(v < 0 for v in base_padding):
        raise ValueError('Invalid source or padding')
    required = [checked(original[0] + base_padding[0] + base_padding[2]),
                checked(original[1] + base_padding[1] + base_padding[3])]
    alignment = 1
    for level, layer in enumerate(layers):
        t, width, height, maxx, maxy = layer
        if t <= 0 or min(width, height) <= 0 or min(maxx, maxy) < 0 or maxx > width or maxy > height:
            raise ValueError('Malformed loaded template geometry')
        factor = checked(1 << level)
        term = checked(factor * t)
        alignment = checked(alignment // math.gcd(alignment, term) * term)
        for axis, extent, maximum in ((0, width, maxx), (1, height, maxy)):
            if level < len(layers)-1:
                bound = checked(factor * checked(extent + checked(16*t)))
            else:
                bound = checked(factor * max(extent, checked(maximum+1)))
            required[axis] = max(required[axis], bound)
    size = [align(value, alignment) for value in required]
    area = checked(size[0] * size[1])
    if area > budget_pixels:
        raise ValueError('Declared pixel budget exceeded')
    if max(size) > 2048:
        raise ValueError('Declared axis budget exceeded')
    padding = [base_padding[0], base_padding[1],
               size[0]-original[0]-base_padding[0],
               size[1]-original[1]-base_padding[1]]
    return size, padding, alignment


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite evidence')
    root = Path(__file__).resolve().parents[2]
    folder = Path(__file__).resolve().parent
    protocol = json.loads((folder/'PROTOCOL.json').read_text())
    schedule = json.loads((folder/'frame_schedule.json').read_text())
    static = json.loads((folder/'preflight_plan.json').read_text())
    for pin in protocol['input_sha256']:
        assert sha(root/pin['path']) == pin['sha256'], pin['path']
    assert sha(folder/'frame_schedule.json') == protocol['frame_schedule_sha256']
    assert sha(folder/'preflight_plan.json') == protocol['preflight_plan_sha256']
    geometry = json.loads((root/'artifacts/public_evaluation/obj8_geometry_actual_input.json').read_text())
    assert geometry['template_count'] == protocol['template_count'] == 3456
    layers = []
    for level in range(2):
        records = [v['levels'][level] for v in geometry['levels']]
        assert all(v['level'] == level and v['T'] == [4, 8][level] for v in records)
        assert all(min(v['feature_extent'][:2]) >= 0 for v in records)
        assert all(v['feature_extent'][2] <= v['width'] and v['feature_extent'][3] <= v['height'] for v in records)
        layers.append(([4, 8][level], max(v['width'] for v in records),
                       max(v['height'] for v in records),
                       max(v['feature_extent'][2] for v in records),
                       max(v['feature_extent'][3] for v in records)))
    result = plan([720, 540], [64, 64, 64, 68], layers)
    assert result == ([848, 800], [64, 64, 64, 196], 16)
    expected = protocol['expected_current_shape']
    assert result[0] == static['planned_auto_size'] == expected['auto_size']
    assert result[1] == static['planned_padding_ltrb'] == expected['auto_padding_ltrb']
    failures_before, failures_after = [], []
    for item in geometry['levels']:
        for value in item['levels']:
            level, t = value['level'], value['T']
            for size, failures in (([848, 672], failures_before), ([848, 800], failures_after)):
                dims = [v >> level for v in size]
                legal = all(d % t == 0 for d in dims)
                if level == 0:
                    legal &= dims[0] >= value['width']+16*t and dims[1] >= value['height']+16*t
                else:
                    legal &= all(dims[a] >= max(value[['width', 'height'][a]], value['feature_extent_max_plus_one'][a]) for a in range(2))
                if not legal:
                    failures.append([item['template_id'], level])
    assert geometry['invalid_template_levels'] == 630
    assert len(failures_before) == 634 and not failures_after
    extra_boundary_ids = []
    for item in geometry['levels']:
        value = item['levels'][1]
        if value['coarse_fit'] and (value['feature_extent_max_plus_one'][0] > 424 or value['feature_extent_max_plus_one'][1] > 336):
            extra_boundary_ids.append(item['template_id'])
    assert extra_boundary_ids == [566, 951, 999, 1005]
    # Minimality is conditional on retaining at least the baseline total size.
    assert 848-16 < 848 and 800-16 < max(v[2]+16*v[0] for v in layers[:1])
    keys = [(v['scene_id'], v['image_id']) for v in schedule['frames']]
    assert len(keys) == len(set(keys)) == 400
    assert sum(v['pilot'] for v in schedule['frames']) == 8
    assert sum(v['timing'] for v in schedule['frames']) == 64
    assert all(v['width'] == 720 and v['height'] == 540 for v in schedule['frames'])
    assert sum(protocol[k]['match_calls'] for k in ('pilot', 'full_quality', 'timing')) == protocol['resource_budget']['max_match_calls_all_stages'] == 2880
    assertions = 0
    for extent in (1, 100, 734):
        for t in (1, 4, 8):
            bound = extent+16*t
            for delta in (-1, 0, 1):
                size = bound+delta
                assert (size-extent-8*t >= 8*t) == (delta >= 0)
                assertions += 1
    for extent, maximum in ((1, 0), (100, 99), (100, 100)):
        bound = max(extent, maximum+1)
        for delta in (-1, 0, 1):
            assert (bound+delta >= extent and bound+delta >= maximum+1) == (delta >= 0)
            assertions += 1
    assert plan([641, 479], [64, 64, 64, 64], [(3, 100, 90, 100, 90), (5, 60, 50, 60, 50), (7, 30, 25, 30, 25)]) == ([840, 840], [64, 64, 135, 297], 420)
    assertions += 1
    rejected = []
    cases = {
        'empty_layers': lambda: plan([1, 1], [0, 0, 0, 0], []),
        'negative_feature': lambda: plan([1, 1], [0, 0, 0, 0], [(4, 1, 1, -1, 0)]),
        'feature_above_extent': lambda: plan([1, 1], [0, 0, 0, 0], [(4, 1, 1, 2, 0)]),
        'zero_T': lambda: plan([1, 1], [0, 0, 0, 0], [(0, 1, 1, 1, 1)]),
        'pixel_budget': lambda: plan([720, 540], [64, 64, 64, 68], layers, budget_pixels=678399),
        'axis_budget': lambda: plan([2049, 1], [0, 0, 0, 0], [(1, 1, 1, 0, 0)], budget_pixels=10000000),
        'uint64_sum': lambda: plan([U64_MAX, 1], [64, 0, 64, 0], [(1, 1, 1, 0, 0)]),
        'uint64_align': lambda: align(U64_MAX, 16),
        'uint64_shift': lambda: checked(1 << 64),
        'uint64_product': lambda: checked((1 << 40)*(1 << 40)),
        'negative_padding': lambda: plan([1, 1], [0, -1, 0, 0], [(1, 1, 1, 0, 0)])}
    for name, call in cases.items():
        try:
            call()
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError('Expected rejection: '+name)
    # Coordinate transform depends on left/top, not the additional bottom.
    for x, y, tlx, tly, sx, sy in ((0, 0, 48, 44, 42, 42), (773, 601, 0, 0, 0, 0), (-5, -7, 13, 19, 2, 3)):
        baseline = (x-64+sx-tlx, y-64+sy-tly)
        auto = (x-result[1][0]+sx-tlx, y-result[1][1]+sy-tly)
        assert baseline == auto
        assertions += 1
    evidence = dict(passed=1, protocol_sha256=sha(folder/'PROTOCOL.json'), script_sha256=sha(Path(__file__)), templates_scanned=3456, levels_scanned=6912, historical_reported_infeasible_template_levels=630, recomputed_baseline_infeasible_template_levels=len(failures_before), additional_actual_feature_boundary_template_ids=extra_boundary_ids, proposed_infeasible_template_levels=len(failures_after), planned_size=result[0], planned_padding_ltrb=result[1], hand_derived_boundary_and_coordinate_assertions=assertions, rejected_invalid_cases=rejected, frames=400, pilot=8, timing=64, max_match_calls=2880, dataset_image_files_opened=0, image_decodes=0, compiler_calls=0, matcher_calls=0, limitation='Static constraints from frozen numeric geometry; runtime must revalidate the actual loaded bank, image dimensions, allocation/stride bounds and outputs before any empirical claim.')
    args.output.write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
