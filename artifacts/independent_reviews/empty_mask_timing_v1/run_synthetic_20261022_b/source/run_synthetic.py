"""Run only tiny synthetic timing-audit tests and preserve source evidence."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(HERE) or output.exists():
        raise ValueError('Fresh contained synthetic output required')
    output.mkdir(parents=True)
    (output / 'source').mkdir()
    pins = []
    for path in sorted(HERE.glob('*.py')) + sorted(HERE.glob('*.md')) + [HERE / 'ORIGIN.json']:
        data = path.read_bytes()
        pins.append(dict(name=path.name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
        (output / 'source' / path.name).write_bytes(data)
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        suite = unittest.defaultTestLoader.discover(str(HERE), pattern='test_timing*.py')
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (output / 'tests.txt').write_text(stream.getvalue(), encoding='utf-8', newline='\n')
    report = dict(passed=result.wasSuccessful(), tests=result.testsRun, failures=len(result.failures),
                  errors=len(result.errors), skipped=len(result.skipped), source_pins=pins,
                  dataset_image_bytes_opened=0, image_decodes=0, native_matcher_calls=0,
                  evidence_kind='Isolated tiny synthetic numeric/provenance tests; no real timing run audited')
    (output / 'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'source_pins'}))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
