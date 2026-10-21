"""Prepare frozen padding-experiment provenance; no image decoding/matching.

Delegates baseline-raw attestation to the independently reviewed verifier,
then applies the separately frozen padding protocol and frame schedule.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE_VERIFIER = ROOT/'artifacts/quality_coverage/verify_raw_provenance.py'
BASE_VERIFIER_SHA = '8e213217adf01f582d2d90427f27d46c8687292e00a6a16ebfaaa225474276ed'
PROTOCOL_SHA = 'ab9207f2dd492622aed8f563997b00ca6d137d5c93fa0f2c99b67f7ec756573d'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_hash(path, expected):
    require(sha(path) == expected.lower(), 'Fixed source/input SHA changed: '+str(path))


def validate_protocol():
    require(sha(HERE/'PROTOCOL.json') == PROTOCOL_SHA, 'Padding protocol changed')
    protocol = json.loads((HERE/'PROTOCOL.json').read_text())
    require(sha(BASE_VERIFIER) == BASE_VERIFIER_SHA, 'Baseline verifier changed')
    require(protocol['target_objects'] == [8] and protocol['split'] == 'development', 'Padding scope changed')
    for pin in protocol['input_sha256']:
        require_hash(ROOT/pin['path'], pin['sha256'])
    for name in ('frame_schedule', 'preflight_plan'):
        require(sha(HERE/(name+'.json')) == protocol[name+'_sha256'], 'Frozen plan changed: '+name)
    return protocol


def validate_sources():
    protocol = validate_protocol()
    public = json.loads((ROOT/'artifacts/public_evaluation/build/build_manifest.json').read_text(encoding='utf-8-sig'))
    for path, expected in public['source_sha256'].items():
        require_hash(ROOT/path, expected)
    revision = protocol['core_revision']
    committed = subprocess.run(['git', 'ls-tree', '-r', '--name-only', revision, '--', 'MIPP'], cwd=ROOT, check=True, capture_output=True).stdout.decode().splitlines()
    observed = sorted(v.relative_to(ROOT).as_posix() for v in (ROOT/'MIPP').rglob('*') if v.is_file())
    require(sorted(committed) == observed and len(committed) == 16, 'Changed transitive MIPP member set')
    for path in committed:
        original = subprocess.run(['git', 'show', revision+':'+path], cwd=ROOT, check=True, capture_output=True).stdout
        require((ROOT/path).read_bytes() == original, 'MIPP bytes differ from frozen commit: '+path)
    return dict(passed=1, public_build_sources=len(public['source_sha256']), committed_mipp_files=16, protocol_sha256=PROTOCOL_SHA, image_member_reads=0, image_decodes=0, matcher_calls=0)


def selected_keys(schedule, mode):
    require(mode in ('pilot', 'development', 'timing'), 'Unknown padding mode')
    chosen = [v for v in schedule['frames'] if mode == 'development' or v['pilot' if mode == 'pilot' else 'timing']]
    require(len(chosen) == {'pilot': 8, 'development': 400, 'timing': 64}[mode], 'Changed schedule count')
    keys = {(v['scene_id'], v['image_id']) for v in chosen}
    require(len(keys) == len(chosen), 'Duplicate schedule key')
    return keys


def prepare(mode):
    validate_sources()
    spec = importlib.util.spec_from_file_location('frozen_raw_provenance', BASE_VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.Verifier().verify(ROOT/'datasets/tless_expanded', ROOT/'datasets/tless_expanded_obj8_f32_train', ROOT/'datasets/tless_expanded_obj8_f32_development', ROOT/'artifacts/quality_coverage/COVERAGE_PROTOCOL.json')
    require(result['target_objects'] == [8] and len(result['frames']) == 400 and result['training']['successful_templates'] == 3456, 'Baseline bank/frame scope changed')
    schedule = json.loads((HERE/'frame_schedule.json').read_text())
    keys = selected_keys(schedule, mode)
    selected = [v for v in result['frames'] if (v['scene_id'], v['image_id']) in keys]
    require(len(selected) == len(keys), 'Baseline missing planned frame')
    require(all(v['width'] == 720 and v['height'] == 540 and v['padding'] == [64, 64, 64, 68] for v in selected), 'Baseline input dimensions changed')
    result['baseline_verified_total_frames'] = 400
    result['frames'] = sorted(selected, key=lambda v: (v['scene_id'], v['image_id']))
    result['padding_mode'] = mode
    result['padding_protocol_version'] = 'obj8_full_bank_minimum_padding_development_v1'
    result['padding_protocol_file'] = (HERE/'PROTOCOL.json').as_posix()
    result['padding_protocol_sha256'] = PROTOCOL_SHA
    result['padding_schedule_file'] = (HERE/'frame_schedule.json').as_posix()
    result['padding_schedule_sha256'] = sha(HERE/'frame_schedule.json')
    result['padding_verifier_sha256'] = sha(Path(__file__))
    existing = {v['path'] for v in result['input_sha256']}
    for path in (HERE/'PROTOCOL.json', HERE/'frame_schedule.json', HERE/'preflight_plan.json', Path(__file__)):
        if path.as_posix() not in existing:
            result['input_sha256'].append(dict(path=path.as_posix(), sha256=sha(path), bytes=path.stat().st_size, roles=['padding_frozen_recipe']))
    for item in result['input_sha256']:
        require(sha(Path(item['path'])) == item['sha256'], 'Input changed during padding verification')
    return result


def self_test():
    schedule = {'frames': [dict(scene_id=i//50, image_id=i%50, pilot=int(i%50 == 0), timing=int(i%50 in (0, 7, 14, 21, 28, 35, 42, 49))) for i in range(400)]}
    require([len(selected_keys(schedule, mode)) for mode in ('pilot', 'development', 'timing')] == [8, 400, 64], 'Literal selection failure')
    rejected = []
    for mode, frames in [('pilot', schedule['frames'][:-50]), ('development', schedule['frames'][:-1]), ('timing', [dict(v, timing=0) for v in schedule['frames']])]:
        try:
            selected_keys({'frames': frames}, mode)
        except ValueError:
            rejected.append(mode)
        else:
            raise AssertionError('Missing schedule not rejected')
    duplicate = [dict(v) for v in schedule['frames']]
    duplicate[-1] = dict(duplicate[-2])
    try:
        selected_keys({'frames': duplicate}, 'development')
    except ValueError:
        rejected.append('duplicate')
    else:
        raise AssertionError('Duplicate frame not rejected')
    with tempfile.TemporaryDirectory(prefix='padding-source-provenance-') as directory:
        path = Path(directory)/'source.cpp'
        path.write_bytes(b'synthetic source bytes\n')
        require_hash(path, sha(path))
        try:
            require_hash(path, '0'*64)
        except ValueError:
            rejected.append('source_sha')
        else:
            raise AssertionError('Changed source accepted')
    return dict(passed=1, selections=[8, 400, 64], rejected=rejected, dataset_member_reads=0, image_decodes=0, matcher_calls=0, script_sha256=sha(Path(__file__)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['pilot', 'development', 'timing'])
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--check-protocol', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Output must be fresh')
    require(args.self_test or args.check_protocol or args.mode, 'Select self-test, source check or a mode')
    result = self_test() if args.self_test else validate_sources() if args.check_protocol else prepare(args.mode)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(verified=result.get('verified', result.get('passed', 0)), frames=len(result.get('frames', [])), image_decodes=0, matcher_calls=0)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print('PADDING INPUT AUDIT FAILED: '+str(error), file=sys.stderr)
        raise SystemExit(1)
