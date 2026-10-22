"""Snapshot tiny synthetic tests, without loading real archives or native code."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    output = args.output.resolve()
    if not output.is_relative_to(here) or output.exists():
        raise ValueError('New contained synthetic evidence directory required')
    (output/'source').mkdir(parents=True)
    pins = []
    for path in sorted(here.glob('*.py'))+sorted(here.glob('*.md'))+sorted(here.glob('ORIGIN.json')):
        data = path.read_bytes()
        (output/'source'/path.name).write_bytes(data)
        pins.append(dict(name=path.name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)))
    command = [sys.executable, '-m', 'unittest', 'discover', '-p', 'test_*.py', '-v']
    process = subprocess.run(command, cwd=output/'source', capture_output=True)
    (output/'stdout.txt').write_bytes(process.stdout)
    (output/'stderr.txt').write_bytes(process.stderr)
    result = dict(passed=process.returncode == 0, timestamp=datetime.now(timezone.utc).isoformat(),
                  command=command, exit_code=process.returncode, source_pins=pins,
                  synthetic_only=True, image_files_opened=0, matcher_calls=0)
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(process.stderr.decode('utf-8', errors='replace'), end='')
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
