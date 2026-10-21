"""Recheck the recorded numeric audit closure without parsing any image."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DP = ROOT / 'artifacts/independent_reviews/capacity_dp'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    checked = {}

    def read(path):
        path = path.resolve()
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        if relative in checked:
            require(checked[relative] == sha(data), 'Input changed: '+relative)
        checked[relative] = sha(data)
        return data

    def load(path):
        return json.loads(read(path))

    try:
        run = HERE / 'run_six_objects_v1'
        independent = DP / 'run_six_objects_dp_v2'
        original = load(run / 'results.json')
        other = load(independent / 'results.json')
        require(other['passed'] and not other['root_code_imported'], 'Independent audit status')
        require(other['totals'] == original['totals'], 'Independent aggregate mismatch')
        require(other['object_frame_pairs'] == original['object_frame_pairs'] == 2400,
                'Independent frame scope')
        require(other['unique_development_frames'] == original['unique_development_frames'] == 400,
                'Unique development frame scope')
        for key in ('image_files_opened', 'matcher_calls', 'heldout_frames_processed'):
            require(other[key] == original[key] == 0, 'Unexpected image/matcher operation')
        require(read(run / 'per_frame.csv') == read(independent / 'per_frame.csv'),
                'Independent per-frame byte mismatch')
        require(sha(read(independent / 'per_frame.csv')) == other['per_frame_sha256']
                == original['per_frame_sha256'], 'Per-frame SHA mismatch')
        require(sha(read(independent / 'effective_tp_ids.csv')) == other['effective_tp_ids_sha256'],
                'Independent TP identity SHA mismatch')
        identities = list(csv.DictReader(io.StringIO(read(independent / 'effective_tp_ids.csv').decode())))
        require(len(identities) == other['effective_tp_ids'] == 215, 'TP identity count')
        require(len({tuple(row.values()) for row in identities}) == 215, 'Duplicate TP identities')
        require(other['protocol_sha256'] == sha(read(DP / 'PROTOCOL.json'))
                == sha(read(independent / 'PROTOCOL.json')), 'DP protocol mismatch')
        require(other['auditor_sha256'] == sha(read(DP / 'audit_capacity.py'))
                == sha(read(independent / 'auditor_source.py')), 'DP source snapshot mismatch')
        for relative, pin in other['input_sha256'].items():
            data = read(ROOT / relative)
            require(len(data) == pin['bytes'] and sha(data) == pin['sha256'],
                    'DP recorded input mismatch: '+relative)
        for folder in (run, HERE / 'run_size_coverage_v1'):
            result = load(folder / 'results.json')
            for name, expected in result['source_sha256'].items():
                require(sha(read(HERE / name)) == expected == sha(read(folder / 'source' / name)),
                        'Root source snapshot mismatch: '+name)
            for pin in result['input_sha256']:
                require(sha(read(ROOT / pin['path'])) == pin['sha256'], 'Root input mismatch')
        size = load(HERE / 'run_size_coverage_v1/results.json')
        require(sha(read(HERE / 'run_size_coverage_v1/per_gt.csv')) == size['per_gt_sha256'],
                'Size rows SHA mismatch')
        require(sum(row['gt'] for row in size['per_object']) == 400 and
                all(row['gt_without_geometrically_compatible_template'] == 0
                    for row in size['per_object']), 'Size diagnostic result')
        commands = [
            [sys.executable, '-m', 'unittest', 'discover', '-s', str(HERE), '-p', 'test_*.py'],
            [sys.executable, str(DP / 'audit_capacity.py'), '--self-test', '--output',
             str(args.output / 'dp_selftest.json')],
            [sys.executable, str(DP / 'test_selected_precision.py'), '--output',
             str(args.output / 'precision_fixtures')],
        ]
        tests = []
        for index, command in enumerate(commands):
            process = subprocess.run(command, cwd=ROOT, capture_output=True)
            (args.output / f'test_{index}_stdout.txt').write_bytes(process.stdout)
            (args.output / f'test_{index}_stderr.txt').write_bytes(process.stderr)
            tests.append(dict(command=command, exit_code=process.returncode))
            require(process.returncode == 0, 'Fresh synthetic verification failed')
        for relative, expected in list(checked.items()):
            require(sha((ROOT / relative).read_bytes()) == expected, 'Input changed during review')
        result = dict(passed=True, full_dp_rerun=False, matcher_calls=0,
                      image_files_opened=0, image_decodes=0, heldout_frames_processed=0,
                      same_per_frame_bytes=True, tests=tests, totals=original['totals'],
                      checked_sha256=checked, verifier_sha256=sha(Path(__file__).read_bytes()),
                      limitation='This checks the recorded closure and fresh synthetic behavior; '
                                 'the independent DP full-data run is preserved separately, '
                                 'not repeated or relabeled as this review.')
        (args.output / 'results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(dict(passed=True, checked_files=len(checked), fresh_test_commands=len(tests))))
    except Exception as error:
        (args.output / 'failure.json').write_text(json.dumps(dict(incomplete=True, reason=str(error)))+'\n')
        raise


if __name__ == '__main__':
    main()
