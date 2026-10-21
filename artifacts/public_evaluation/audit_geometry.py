#!/usr/bin/env python3
"""Attach source-aware metadata/header checks to an existing template geometry report."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    data = load(args.report); index = load(args.dataset/'index.json'); config = load(args.training/'training_config.json')
    object_id = config.get('target_objects', [1])[0]
    meta = {m['template_id']: m for m in load(args.training/'template_metadata.json')['templates']}
    dimensions, headers = set(), []
    for frame in index['test']:
        if frame['split'] != 'development':
            continue
        path = args.dataset/frame['rgb']
        with path.open('rb') as stream:
            header = stream.read(24)
        assert header[:8] == b'\x89PNG\r\n\x1a\n'
        size = struct.unpack('>II', header[16:24]); dimensions.add(size)
        assert size == (frame['width'], frame['height'])
        headers.append({'rgb': frame['rgb'], 'png_header_sha256': hashlib.sha256(header).hexdigest()})
    assert len(dimensions) == 1
    width, height = next(iter(dimensions)); padding = config['input_padding']
    assert padding == 64 and config['pyramid_T'] == [4, 8]
    padded = [((n+2*padding+15)//16)*16 for n in [width, height]]
    assert data['raw_input_size'] == [width, height] and data['input_size'] == padded
    invalid, width_equals_max, max_support_exceeds_level, by_scale = 0, 0, 0, Counter()
    for template in data['levels']:
        for level in template['levels']:
            W, H = [n >> level['pyramid_level'] for n in padded]; T = config['pyramid_T'][level['level']]
            assert level['input_level_size'] == [W, H] and level['T'] == T
            assert W % T == H % T == 0
            low_x, low_y, max_x, max_y = level['feature_extent']
            assert level['feature_extent_max_plus_one'] == [max_x+1, max_y+1]
            width_equals_max += level['width'] == max_x
            max_support_exceeds_level += low_x < 0 or low_y < 0 or max_x+1 > W or max_y+1 > H
            center = [8*T, W-level['width']-8*T, 8*T, H-level['height']-8*T]
            assert level['refinement_center_interval'] == center
            coarse_fit = W//T-((level['width']-1)//T+1) >= 0 and H//T-((level['height']-1)//T+1) >= 0
            refine_fit = not level['refinement_level'] or center[0] <= center[1] and center[2] <= center[3]
            assert level['coarse_fit'] == coarse_fit and level['refinement_interval_valid'] == refine_fit
            if not level['declared_geometry_fit']:
                invalid += 1
                by_scale[str(meta[template['template_id']]['scale'])] += 1
    assert invalid == data['invalid_template_levels']
    data['source_audit'] = {'passed': True, 'raw_png_header_size': [width, height], 'development_rgb_headers_verified': len(headers),
                            'pixel_decode_performed': False, 'heldout_png_headers_inspected_by_this_audit': False,
                            'training_directory': str(args.training), 'training_config_sha256': digest(args.training/'training_config.json'),
                            'bank_sha256': digest(args.training/f'templates_tless_object_{object_id}.yml.gz'),
                            'template_metadata_sha256': digest(args.training/'template_metadata.json'),
                            'reporter_source_sha256': digest(Path('artifacts/public_evaluation/template_geometry_report.cpp')),
                            'audit_script_sha256': digest(Path(__file__)),
                            'T_divisibility_verified': True, 'invalid_levels_by_scale': dict(by_scale),
                            'levels_with_width_equal_feature_max': width_equals_max, 'actual_feature_max_plus_one_exceeds_level': max_support_exceeds_level,
                            'full_physical_load_safety_proven': False,
                            'limitation': 'Declared extent, actual feature max+1 and logical refinement interval are different quantities. Width==feature max is historical core behavior, not a format failure. These metadata checks are not a proof of physical fallback SIMD reads (the word path can load beyond 16 logical columns). No templates or parameters were changed.',
                            'headers': headers}
    args.report.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: data['source_audit'][k] for k in ['passed', 'raw_png_header_size', 'development_rgb_headers_verified', 'invalid_levels_by_scale', 'actual_feature_max_plus_one_exceeds_level', 'full_physical_load_safety_proven']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--training', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    main(parser.parse_args())
