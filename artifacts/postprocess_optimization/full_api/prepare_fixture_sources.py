"""Prepare exact adapter source blocks and metadata-only fixture input pins.

Never opens image/SMD/bank input bytes, starts a compiler or runs a matcher.
Input SHA values are copied from prior frozen receipts; native runners must
verify the actual allowed bytes separately before/after their granted stage.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAPTURE = ROOT / 'artifacts/match_consolidation/hash_prototype/run_20261022_capture_actual85'
LED_SOURCE = ROOT / 'artifacts/match_consolidation/hash_prototype/build_20261022_capture_v1/snapshot/support/led_demo.cpp'
MAGNET_SOURCE = ROOT / 'artifacts/magnet_match/run_20261021_scale_coverage/source/magnet_demo.cpp'
LED_SHA = '3b6521e0d8edb6c2ce7ad49fb22b50ada76bda1cf5afda37549972042f491e13'
MAGNET_SHA = '89eece9c67248207eb9f94c6dc984e7e9c4c94959a503d3fb9445965a4f86839'
TINY_PAIRS = [(5, i) for i in (7,70,127,215,293,353,436,493)]
TINY_PAIRS += [(2, i) for i in (3,92,153,214,295,374,446,494)]
COMMON_NAMES = ['LED_' + str(i) for i in range(1, 9)] + ['case1']
COMMON_NAMES += ['tiny_s%d_i%d' % pair for pair in TINY_PAIRS]


def need(value, message):
    if not value:
        raise ValueError(message)


def extract(source, start, end, namespace):
    need(namespace in ('led', 'magnet'), 'Unknown fixture adapter namespace')
    need(source.count(start) == source.count(end) == 1, 'Source markers must be unique')
    first, last = source.index(start), source.index(end)
    need(first < last, 'Reversed source markers')
    block = source[first:last]
    need(b'#include' not in block and b'int main(' not in block, 'Unexpected source inclusion/entry point')
    return (b'#pragma once\nnamespace postprocess_fixture_sources { namespace ' + namespace.encode('ascii') +
            b' {\n' + block + b'\n} }\n')


def permitted_tiny(rows):
    result, seen = [], set()
    for row in rows:
        if row['split'] != 'development':
            continue
        pair = row['scene_id'], row['image_id']
        need(pair in TINY_PAIRS and pair not in seen, 'Unknown/duplicate development frame')
        expected = 'test_primesense/%06d/rgb/%06d.png' % pair
        need(row['rgb'] == expected, 'Unexpected development image path')
        seen.add(pair)
        result.append(row)
    return result


def merge_pins(records):
    result = {}
    for value in records:
        path = PurePosixPath(value['path'].replace('\\', '/'))
        need(not path.is_absolute() and ':' not in str(path) and '..' not in path.parts,
             'Only contained relative fixture paths are allowed')
        pin = dict(path=str(path), bytes=value.get('bytes', value.get('size_bytes')),
                   sha256=value['sha256'].lower(), role=value['role'])
        need(pin['bytes'] is not None and pin['bytes'] >= 0, 'Missing fixture byte count')
        need(str(path) not in result or result[str(path)] == pin, 'Conflicting fixture pins')
        result[str(path)] = pin
    return [result[key] for key in sorted(result)]


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def prepare(output):
    output = output.resolve()
    need(output.is_relative_to(HERE) and not output.exists(), 'Fresh contained fixture-source directory required')
    # All reads before output creation are source or numeric metadata only.
    led = LED_SOURCE.read_bytes()
    magnet = MAGNET_SOURCE.read_bytes()
    need(hashlib.sha256(led).hexdigest() == LED_SHA and hashlib.sha256(magnet).hexdigest() == MAGNET_SHA,
         'Pinned historical SMD adapter source changed')
    index_path = ROOT / 'datasets/tless_tiny/index.json'
    index = json.loads(index_path.read_bytes())
    tiny = permitted_tiny(index['test'])
    need([(row['scene_id'], row['image_id']) for row in tiny] == TINY_PAIRS,
         'Fixed development index membership/order changed')
    metadata = [pin(index_path)]
    common = []
    for name in COMMON_NAMES:
        protocol_path = CAPTURE / name / 'protocol.json'
        protocol = json.loads(protocol_path.read_bytes())
        need(protocol['case']['case_id'] == name and protocol['core_revision'] ==
             'b25df46f6ddf9c24fb43f5836f1414dc38c8caed', 'Historical capture identity differs')
        selected = [row for row in protocol['pins'] if row['role'] in ('bank', 'image')]
        need(len([row for row in selected if row['role'] == 'image']) == 1 and
             len([row for row in selected if row['role'] == 'bank']) == 1, 'Capture fixture input set differs')
        expected_image = ('LED/' + name[4:] + '.bmp' if name.startswith('LED_') else
                          'test/case1/test.png' if name == 'case1' else
                          'datasets/tless_tiny/' + tiny[COMMON_NAMES.index(name)-9]['rgb'])
        need(next(row['path'] for row in selected if row['role'] == 'image') == expected_image,
             'Historical fixture image path differs')
        common.extend(selected)
        metadata.append(pin(protocol_path))
    common.append(dict(path='datasets/tless_tiny/index.json', bytes=metadata[0]['bytes'],
                       sha256=metadata[0]['sha256'], role='metadata'))
    provenance_path = ROOT / 'artifacts/magnet_match/run_20261021_scale_coverage/provenance.json'
    provenance = json.loads(provenance_path.read_bytes())
    metadata.append(pin(provenance_path))
    private = []
    expected_names = ['M%02d.bmp' % i for i in range(1, 8)] + ['moban.smd']
    old = {Path(path).name: digest for path, digest in provenance['input_sha256'].items()
           if Path(path).name in expected_names}
    need(set(old) == set(expected_names) and old['moban.smd'].lower() ==
         '6335f11e6b3c806bbd2e0b4fd2ab5150c015d3e9d18908b78ef6e316aeb06166',
         'Private historical SHA set differs')
    for name in expected_names:
        for prefix in ('artifacts/magnet_match/build/input', '\u78c1\u7247'):
            relative = prefix + '/' + name
            # Stat is not a content read. Actual hashes are a later runner gate.
            private.append(dict(path=relative, bytes=(ROOT/relative).stat().st_size,
                                sha256=old[name].lower(), role='private_smd' if name.endswith('.smd') else 'private_image'))
    generated = {'led.hpp': extract(led, b'struct StoredPoint', b'int benchmarkPaired(', 'led'),
                 'magnet.hpp': extract(magnet, b'struct Point', b'cv::Rect2f featureBox(', 'magnet')}
    output.mkdir()
    for name, data in generated.items():
        (output/name).write_bytes(data)
    result = dict(source_only=True, compiler_invocations=0, matcher_calls=0, image_decodes=0,
                  image_smd_bank_bytes_opened=0, common_names=COMMON_NAMES,
                  common_input_pins=merge_pins(common), private_input_pins=merge_pins(private),
                  metadata_pins=metadata, adapter_source_pins=[pin(LED_SOURCE), pin(MAGNET_SOURCE)],
                  generated_headers=[pin(output/name) for name in generated], reader=pin(Path(__file__)),
                  input_hash_values='Copied from historical fixed receipts; not freshly verified in this source-only stage',
                  historical_origin='Exact marker-delimited blocks, namespace wrappers only; no production core includes or entry point')
    (output/'FIXTURE_SOURCE_MANIFEST.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, manifest=pin(output/'FIXTURE_SOURCE_MANIFEST.json'),
                          common_inputs=len(result['common_input_pins']), private_inputs=len(result['private_input_pins']))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE/'generated_fixtures')
    prepare(parser.parse_args().output)
