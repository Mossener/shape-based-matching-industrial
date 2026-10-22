"""Independent binary reader and numeric V11 grouping for captured traces.

No imports from capture/prototype/evaluator implementations. No image reads,
native processes or timings. Zero-score traces are explicitly out of this
audit's bit-representative scope because C++ sort can choose either signed zero.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def require(value, message):
    if not value:
        raise ValueError(message)


def parse(data):
    require(len(data) >= 32 and len(data) <= 1_073_741_824, 'Invalid trace length')
    require(data[:8] == b'SBMHASH1', 'Wrong trace magic')
    version, endian, inputs, outputs = struct.unpack_from('<IIQQ', data, 8)
    require((version, endian) == (1, 0x01020304), 'Wrong version/endian')
    require(inputs <= 10_000_000 and outputs <= 10_000_000 and
            inputs+outputs <= (len(data)-32)//24, 'Invalid counts')
    position, vectors = 32, []
    for count in (inputs, outputs):
        records = []
        for _ in range(count):
            require(position+24 <= len(data), 'Truncated fields')
            x, y, template, score, length = struct.unpack_from('<iiiIQ', data, position)
            position += 24
            require(score & 0x7f800000 != 0x7f800000, 'Nonfinite score')
            require(length <= 1_048_576 and position+length <= len(data), 'Truncated class')
            records.append((x, y, template, score, data[position:position+length]))
            position += length
        vectors.append(records)
    require(position == len(data), 'Trailing bytes')
    return vectors


def number(bits):
    return struct.unpack('<f', struct.pack('<I', bits))[0]


def numeric_v11(records):
    groups = {}
    for x, y, template, score, cls in records:
        require(score & 0x7fffffff != 0, 'Signed-zero representative outside independent scope')
        require(score & 0x7f800000 != 0x7f800000, 'Nonfinite score')
        identity = (cls, x, y, score)
        if identity not in groups or template < groups[identity][2]:
            groups[identity] = (x, y, template, score, cls)
    return sorted(groups.values(), key=lambda r: (-number(r[3]), r[2], r[4], r[1], r[0]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-run', required=True, type=Path)
    parser.add_argument('--repo', default=Path.cwd(), type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Output must be fresh')
    root, run = args.repo.resolve(strict=True), args.capture_run.resolve(strict=True)
    require(run.is_relative_to(root), 'Capture run outside repo')
    pins = {}

    def read(path):
        path = path.resolve(strict=True)
        require(path.is_relative_to(root) and path.suffix.lower() in ('.json', '.bin'),
                'Only contained trace/numeric files allowed')
        data = path.read_bytes()
        pin = dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
        if str(path) in pins:
            require(pins[str(path)] == pin, 'Evidence changed while reading')
        pins[str(path)] = pin
        return data

    def load(path):
        return json.loads(read(path).decode('utf-8-sig'))

    result = load(run/'capture_result.json')
    frozen_pin = result['frozen_capture_protocol']
    protocol_path = root/frozen_pin['path']
    frozen = load(protocol_path)
    require(pins[str(protocol_path.resolve())] == {k:frozen_pin[k] for k in ('sha256', 'size_bytes')},
            'Capture protocol pin differs')
    require(result['passed'] is True and result['matcher_calls'] == 50 and
            result['performance_measurement'] is False and frozen['case_count'] == 25 and
            frozen['tiny_scenario'] == result['tiny_scenario'] == 'quality_actual85', 'Incomplete/wrong scope')
    reports, names = [], []
    for declared in result['verified_cases']:
        manifest_path = root/declared['path']
        manifest = load(manifest_path)
        require(pins[str(manifest_path.resolve())] == {k:declared[k] for k in ('sha256', 'size_bytes')},
                'Case manifest differs')
        config = manifest['case']
        name = config['case_id']
        names.append(name)
        require(manifest_path.parent == run/name and
                config['matcher_threshold'] == frozen['fixtures'][config['dataset']]['threshold'],
                'Wrong case/threshold')
        vectors = {}
        for label in ('trace', 'reference'):
            pin = manifest[label]
            require(pin['path'] == ('capture.bin' if label == 'trace' else 'reference.bin'),
                    'Unexpected trace filename')
            path = manifest_path.parent/pin['path']
            vectors[label] = parse(read(path))
            require(pins[str(path.resolve())] == {k:pin[k] for k in ('sha256', 'size_bytes')},
                    'Trace SHA/length differs')
            require(list(map(len, vectors[label])) == [pin['input_count'], pin['output_count']],
                    'Declared vector counts differ')
        before, after = vectors['trace']
        require(not vectors['reference'][0] and after == vectors['reference'][1],
                'Capture/reference ordered bits differ')
        require(numeric_v11(before) == after, 'Independent V11 grouping/order differs')
        reports.append(dict(case=name, input_count=len(before), output_count=len(after),
                            duplicates_removed=len(before)-len(after), all_ordered_records_equal=True))
    require(names == frozen['case_order'] and len(set(names)) == 25, 'Wrong/missing case order')
    for path, pin in pins.items():
        data = Path(path).read_bytes()
        require(dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data)) == pin,
                'Evidence changed during audit')
    report = dict(passed=True, cases=reports, case_count=25, pins=pins,
                  independent_grouping='min template per full class/x/y/nonzero finite binary32 identity; '
                  'final numerical score/template/classbytes/y/x order',
                  audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  image_files_opened=0, matcher_calls=0, performance_measurement=False,
                  limitation='Checks saved numeric traces and grouping only; does not establish whole '
                  'capture execution provenance, detection accuracy, speed or signed-zero representatives')
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'pins'}))


if __name__ == '__main__':
    main()
