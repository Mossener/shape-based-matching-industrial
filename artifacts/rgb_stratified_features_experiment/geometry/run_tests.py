"""Run the source-only geometry literal tests and write a pinned receipt."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import argparse
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent


def pin(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    name='source_tests_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    output = Path(args.output or os.environ.get("GEOMETRY_RECEIPT_DIR", HERE/name)).resolve()
    if not output.is_relative_to(HERE):
        raise ValueError("Receipt directory must be contained by geometry/")
    if output.exists():
        raise ValueError('Fresh receipt directory required; preserve all previous evidence')
    output.mkdir(parents=True, exist_ok=False)
    sources = [HERE / name for name in ('planner.py','test_geometry.py','run_geometry.py','test_run_geometry.py','run_tests.py')]
    sources.append(HERE.parent/'independent/strict_bank_reader.py')
    before=[pin(path) for path in sources]
    snapshot=output/'source';snapshot.mkdir()
    for path in sources:(snapshot/path.name).write_bytes(path.read_bytes())
    command = [sys.executable, "-B", '-m','unittest','discover','-s',str(HERE),'-p','test_*.py']
    run = subprocess.run(command, cwd=HERE, capture_output=True, text=True,
                         env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    (output / "stdout.txt").write_text(run.stdout, encoding="utf-8", newline="\n")
    (output / "stderr.txt").write_text(run.stderr, encoding="utf-8", newline="\n")
    unchanged=before==[pin(path) for path in sources]
    receipt = {
        "schema": "v31_source_only_geometry_literal_receipt_v2",
        "passed": run.returncode == 0 and unchanged,
        "command": command,
        "exit": run.returncode,
        "tests": "Planner literals and runner synthetic in-memory bank/numeric payloads only",
        "source_pins": before,
        "source_unchanged_during_execution": unchanged,
        "native_executions": 0,
        "image_decodes": 0,
        "bank_files_opened": 0,
        "synthetic_bank_payloads_only": True,
        "matcher_calls": 0,
        "quality_claim": False,
        "performance_claim": False,
        "scope": "Exact V30 padding helper arithmetic adapted to frozen V31 eighteen-bank geometry",
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")
    print(json.dumps({"passed": receipt["passed"], "exit": run.returncode,
                      "native_executions": 0, "bank_files_opened": 0}))
    return 0 if receipt['passed'] else (run.returncode or 1)


if __name__ == "__main__":
    raise SystemExit(main())

