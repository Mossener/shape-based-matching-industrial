"""Run the source-only geometry literal tests and write a pinned receipt."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def pin(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main() -> int:
    output = Path(os.environ.get("GEOMETRY_RECEIPT_DIR", HERE / "tests_green_20261022_a")).resolve()
    if not output.is_relative_to(HERE):
        raise ValueError("Receipt directory must be contained by geometry/")
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-B", str(HERE / "test_geometry.py")]
    run = subprocess.run(command, cwd=HERE, capture_output=True, text=True,
                         env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    (output / "stdout.txt").write_text(run.stdout, encoding="utf-8", newline="\n")
    (output / "stderr.txt").write_text(run.stderr, encoding="utf-8", newline="\n")
    sources = [HERE / "planner.py", HERE / "test_geometry.py", HERE / "run_tests.py"]
    receipt = {
        "schema": "v31_source_only_geometry_literal_receipt_v1",
        "passed": run.returncode == 0,
        "command": command,
        "exit": run.returncode,
        "tests": "21 unittest cases; synthetic layers only",
        "source_pins": [pin(path) for path in sources],
        "native_executions": 0,
        "image_decodes": 0,
        "bank_files_opened": 0,
        "matcher_calls": 0,
        "quality_claim": False,
        "performance_claim": False,
        "scope": "Exact V30 padding helper arithmetic adapted to frozen V31 eighteen-bank geometry",
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")
    print(json.dumps({"passed": receipt["passed"], "exit": run.returncode,
                      "native_executions": 0, "bank_files_opened": 0}))
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())

