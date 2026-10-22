"""Capture small synthetic quality-auditor tests with exact source pins."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(HERE) or output.exists():
        raise ValueError('Fresh contained output required')
    output.mkdir()
    pins = []
    source = output / 'source'; source.mkdir()
    for name in ('audit.py', 'numeric.py', 'identity_strata.py', 'experiment_contract.py', 'test_audit.py', 'test_successor.py', 'run_synthetic.py', 'ORIGIN.json'):
        data = (HERE / name).read_bytes()
        (source / name).write_bytes(data)
        pins.append(dict(name=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-p', 'test_*.py', '-v'], cwd=source,
                            text=True, capture_output=True)
    (output / 'stdout.txt').write_text(result.stdout, encoding='utf-8')
    (output / 'stderr.txt').write_text(result.stderr, encoding='utf-8')
    unchanged = all((HERE/p['name']).read_bytes() == (source/p['name']).read_bytes() for p in pins)
    report = dict(passed=result.returncode == 0 and unchanged, exit_code=result.returncode, sources_unchanged_after=unchanged,
                  source_pins=pins, matcher_calls=0, dataset_image_reads=0, real_quality_output_reads=0,
                  command=[sys.executable, '-B', '-m', 'unittest', 'discover', '-p', 'test_*.py', '-v'],
                  scope='Literal numeric oracles and adversarial synthetic mutations only')
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
