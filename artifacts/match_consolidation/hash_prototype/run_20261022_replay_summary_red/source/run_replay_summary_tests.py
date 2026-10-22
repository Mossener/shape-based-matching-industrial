"""Preserve small synthetic summary tests; never access images or native code."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    source = Path(__file__).resolve().parent
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output/'source'
    snapshot.mkdir()
    pins = []
    for name in ('summarize_replay.py', 'test_replay_summary.py', 'capture_manifest.py',
                 'run_replay_summary_tests.py'):
        data = (source/name).read_bytes()
        (snapshot/name).write_bytes(data)
        pins.append(dict(name=name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    command = [sys.executable, '-m', 'unittest', '-v', 'test_replay_summary']
    process = subprocess.run(command, cwd=snapshot, capture_output=True)
    (output/'stdout.txt').write_bytes(process.stdout)
    (output/'stderr.txt').write_bytes(process.stderr)
    result = dict(synthetic_only=True, image_decodes=0, matcher_calls=0,
                  timestamp=datetime.now(timezone.utc).isoformat(), command=command,
                  source_pins=pins, exit_code=process.returncode)
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(process.stdout.decode('utf-8', errors='replace'), end='')
    print(process.stderr.decode('utf-8', errors='replace'), end='')
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
