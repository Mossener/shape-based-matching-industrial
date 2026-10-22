"""Read-only audit of an immutable V11 capture and its uninstrumented output."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct

CORE_REVISION = 'b25df46f6ddf9c24fb43f5836f1414dc38c8caed'
MAX_TRACE_BYTES = 1_073_741_824


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    return type(value) is int and value >= 0


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def json_bytes(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key: '+key)
            result[key] = value
        return result
    value = json.loads(data.decode('utf-8-sig'), object_pairs_hook=unique)
    require(isinstance(value, dict), 'JSON object required')
    return value


def relative_path(root, text, direct_child=False):
    require(isinstance(text, str) and text and '\\' not in text and ':' not in text
            and '\x00' not in text, 'Unsafe relative path')
    pure = PurePosixPath(text)
    require(not pure.is_absolute() and all(p not in ('.', '..') for p in text.split('/'))
            and pure.as_posix() == text, 'Unsafe relative path')
    require(not direct_child or len(pure.parts) == 1, 'Trace must be a direct child')
    result = (root/text).resolve()
    require(result.is_relative_to(root), 'Path escapes audit root')
    return result


def check_file(path, metadata, label):
    require(isinstance(metadata, dict), label+' metadata required')
    expected = metadata['sha256']
    size = metadata['size_bytes']
    require(isinstance(expected, str) and re.fullmatch('[0-9a-fA-F]{64}', expected),
            label+' SHA256 required')
    require(integer(size), label+' size must be a nonnegative integer')
    try:
        require(path.is_file() and path.stat().st_size == size, label+' byte size differs')
        require(sha256(path) == expected.lower(), label+' SHA256 differs')
    except OSError as error:
        raise ValueError(label+' pinned file missing/unreadable') from error
    return expected.lower()


def read_trace(data, max_records=10_000_000, max_class_bytes=1_048_576,
               max_total_bytes=1_073_741_824):
    require(all(integer(v) for v in (max_records, max_class_bytes, max_total_bytes)),
            'Trace bounds must be nonnegative integers')
    require(isinstance(data, bytes) and len(data) <= max_total_bytes, 'Trace byte bound exceeded')
    require(len(data) >= 32, 'Truncated trace header')
    require(data[:8] == b'SBMHASH1', 'Trace magic differs')
    version, endian, inputs, outputs = struct.unpack_from('<IIQQ', data, 8)
    require(version == 1 and endian == 0x01020304, 'Trace version/endian differs')
    require(inputs <= max_records and outputs <= max_records and
            inputs+outputs <= (1 << 64)-1 and inputs+outputs <= (len(data)-32)//24,
            'Trace record count/minimum byte bound exceeded')
    position = 32
    result = {}
    for name, count in (('input', inputs), ('output', outputs)):
        records = []
        for _ in range(count):
            require(len(data)-position >= 24, 'Truncated trace record')
            x, y, template_id, score_bits, length = struct.unpack_from('<iiiIQ', data, position)
            position += 24
            require((score_bits & 0x7f800000) != 0x7f800000, 'Nonfinite trace score')
            require(length <= max_class_bytes and length <= len(data)-position,
                    'Trace class byte bound/truncation')
            class_bytes = data[position:position+length]
            position += length
            records.append((x, y, score_bits, class_bytes, template_id))
        result[name] = records
    require(position == len(data), 'Trace has trailing bytes')
    return result


def validate_case(case):
    require(isinstance(case, dict), 'Case object required')
    dataset = case['dataset']
    require(type(case['matcher_threshold']) in (int, float), 'Numeric matcher threshold required')
    if dataset == 'LED':
        require(re.fullmatch(r'LED_[1-8]', case['case_id']) and case['split'] == 'legacy'
                and case['scenario'] == 'legacy' and case['matcher_threshold'] == 75,
                'LED case outside frozen scope')
        return 'LED/'+case['case_id'].split('_')[1]+'.bmp', 'LED/ku.smd'
    if dataset == 'case1':
        require(case['case_id'] == 'case1' and case['split'] == 'legacy'
                and case['scenario'] == 'legacy' and case['matcher_threshold'] == 90,
                'case1 outside frozen scope')
        return 'test/case1/test.png', 'test/case1/test_templ.yaml'
    require(dataset == 'tless_tiny' and case['split'] == 'development'
            and case['object_id'] == 1 and type(case['object_id']) is int
            and re.fullmatch(r'tiny_s\d+_i\d+', case['case_id']),
            'Tiny case outside development scope')
    require((case['scenario'], case['matcher_threshold']) in
            (('quality_actual85', 85), ('stress_coarse50', 50)),
            'Tiny scenario/threshold differs from frozen scope')
    return None, 'datasets/tless_train_f32/templates_tless_object_1.yml.gz'


def audit_capture(manifest_path, protocol_path, repo_root):
    try:
        root = Path(repo_root).resolve(strict=True)
        manifest_path = Path(manifest_path).resolve(strict=True)
        protocol_path = Path(protocol_path).resolve(strict=True)
        require(manifest_path.is_relative_to(root) and protocol_path.is_relative_to(root),
                'Capture evidence must stay inside the repository')
        manifest_raw, protocol_raw = manifest_path.read_bytes(), protocol_path.read_bytes()
        manifest_hash, protocol_hash = (hashlib.sha256(b).hexdigest()
                                        for b in (manifest_raw, protocol_raw))
        manifest, protocol = json_bytes(manifest_raw), json_bytes(protocol_raw)
        require(type(manifest['schema_version']) is int and manifest['schema_version'] == 1
                and type(protocol['schema_version']) is int and protocol['schema_version'] == 1,
                'Unknown manifest/protocol schema')
        require(manifest['core_revision'] == protocol['core_revision'] == CORE_REVISION,
                'Capture core revision differs')
        require(manifest['protocol_sha256'].lower() == protocol_hash, 'Protocol SHA256 differs')
        require(protocol['capture_kind'] == 'exact_pre_consolidation_v11'
                and protocol['reference_kind'] == 'uninstrumented_same_core',
                'Capture/reference implementation kind differs')
        require(manifest['case'] == protocol['case'], 'Capture case identity differs')
        image_path, bank_path = validate_case(protocol['case'])
        pins, by_role = {}, {}
        required = {'source', 'image', 'bank', 'config', 'capture_build', 'reference_build'}
        require(isinstance(protocol['pins'], list), 'Pin list required')
        for pin in protocol['pins']:
            role, name = pin['role'], pin['path']
            require(role in required | {'index'}, 'Unknown capture pin role')
            path = relative_path(root, name)
            require(name not in pins, 'Duplicate source/input pin')
            pins[name] = (path, pin)
            by_role.setdefault(role, []).append(name)
        require(required <= set(by_role), 'Missing required capture pin role')
        require(all(len(by_role[r]) == 1 for r in
                    ('image', 'bank', 'capture_build', 'reference_build')),
                'Exactly one image/bank/capture/reference build required')
        if image_path is None:
            require(by_role.get('index') == ['datasets/tless_tiny/index.json'],
                    'Pinned tiny development index required')
            path, pin = pins[by_role['index'][0]]
            check_file(path, pin, 'index pin')
            index = json_bytes(path.read_bytes())
            scene, image = map(int, re.fullmatch(r'tiny_s(\d+)_i(\d+)',
                                                protocol['case']['case_id']).groups())
            # Metadata filtering occurs before using an RGB path. No heldout
            # image is opened, including for hashing, to verify development.
            development = [frame for frame in index['test'] if frame['split'] == 'development'
                           and (frame['scene_id'], frame['image_id']) == (scene, image)]
            require(len(development) == 1, 'Case absent/duplicated in development scope')
            image_path = 'datasets/tless_tiny/'+development[0]['rgb']
            relative_path(root, image_path)
        else:
            require('index' not in by_role, 'Legacy case has unexpected dataset index')
        require(by_role['image'] == [image_path], 'image identity outside development/frozen scope')
        require(by_role['bank'] == [bank_path], 'Bank identity outside frozen scope')
        for path, pin in pins.values():
            check_file(path, pin, pin['role']+' pin')
        loaded, trace_pins = {}, []
        require(manifest['trace']['path'] != manifest['reference']['path'],
                'Capture/reference trace identities must differ')
        for name in ('trace', 'reference'):
            metadata = manifest[name]
            path = relative_path(manifest_path.parent, metadata['path'], direct_child=True)
            require(integer(metadata['size_bytes']) and metadata['size_bytes'] <= MAX_TRACE_BYTES,
                    name+' trace byte bound exceeded')
            check_file(path, metadata, name+' trace')
            parsed = read_trace(path.read_bytes())
            require(integer(metadata['input_count']) and integer(metadata['output_count'])
                    and (len(parsed['input']), len(parsed['output'])) ==
                    (metadata['input_count'], metadata['output_count']), name+' count metadata differs')
            loaded[name] = parsed
            trace_pins.append((path, metadata, name+' trace'))
        require(not loaded['reference']['input'], 'Uninstrumented reference must contain only output')
        require(loaded['trace']['output'] == loaded['reference']['output'],
                'Captured/uninstrumented ordered output identity differs')
        for path, pin in pins.values():
            check_file(path, pin, pin['role']+' pin after read')
        for path, metadata, label in trace_pins:
            check_file(path, metadata, label+' after read')
        require(sha256(manifest_path) == manifest_hash and sha256(protocol_path) == protocol_hash,
                'Manifest/protocol changed during audit')
        return dict(verified=True, input_count=len(loaded['trace']['input']),
                    output_count=len(loaded['trace']['output']), protocol_sha256=protocol_hash,
                    manifest_sha256=manifest_hash, trace_sha256=manifest['trace']['sha256'].lower(),
                    reference_sha256=manifest['reference']['sha256'].lower(), pins_verified=len(pins),
                    case=protocol['case'], core_revision=CORE_REVISION,
                    image_decodes=0, matcher_calls=0, performance_measurement=False,
                    limitation='Encoded-byte and provenance audit, not detection accuracy or speed')
    except (OSError, KeyError, TypeError, AttributeError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid capture manifest or pinned input: '+str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit_capture(args.manifest, args.protocol, args.repo_root)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
