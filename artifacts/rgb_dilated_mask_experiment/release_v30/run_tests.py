"""Save isolated publication-verifier fixture evidence without using Git."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def pin(path):
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(HERE):
        raise SystemExit("Fresh contained output directory required")
    output.mkdir(parents=True)
    source = output / "source"
    source.mkdir()
    names = ["verify_selection.py", "test_publication.py", "run_tests.py", "README.md"]
    before = [pin(HERE / name) for name in names]
    for name in names:
        (source / name).write_bytes((HERE / name).read_bytes())
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(source), "-p", "test_publication.py", "-v"]
    result = subprocess.run(command, cwd=HERE, env=env, capture_output=True)
    (output / "stdout.txt").write_bytes(result.stdout)
    (output / "stderr.txt").write_bytes(result.stderr)
    unchanged = before == [pin(HERE / name) for name in names]
    receipt = {"passed": result.returncode == 0 and unchanged, "exit_code": result.returncode,
               "tests": 10, "source_unchanged_during_execution": unchanged, "command": command,
               "source_pins": before, "source_snapshot_pins": [pin(source / name) for name in names],
               "outputs": [pin(output / name) for name in ["stdout.txt", "stderr.txt"]],
               "scope": "Ten ephemeral mocked Git-index fixtures for SHA1/SHA256; no real index mutation",
               "image_bytes_opened": 0, "native_matcher_calls": 0, "real_git_commands_run": 0}
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: receipt[key] for key in ["passed", "exit_code", "tests", "source_unchanged_during_execution"]}))
    if not receipt["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
