"""Retain all eleven synthetic protocol/arithmetic/summary checks; no native/data access."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--red-evidence", type=Path, required=True)
    args = parser.parse_args()
    red_data = args.red_evidence.read_bytes()
    red = json.loads(red_data)
    if not (red["phase"] == "red" and red["accepted"] is True and red["exit_code"] == 1 and
            red["synthetic_only"] is True and red["matcher_calls"] == red["image_decodes"] == 0 and
            "AssertionError: ValueError not raised" in red["stderr"]):
        raise ValueError("The genuine identity/cache false-accept RED is required")
    contract_test = HERE / "tests/benchmark_contract_test.py"
    if digest(contract_test.read_bytes()) != red["source_sha256"][str(contract_test.resolve())]:
        raise ValueError("Protocol test source changed since genuine RED")
    paths = [HERE / path for path in ("benchmark_contract.py", "benchmark_statistics.py", "summarize_benchmark.py",
             "tests/benchmark_contract_test.py", "tests/benchmark_statistics_test.py", "tests/benchmark_summary_test.py",
             "run_summary_validator.py")]
    before = {str(path.resolve()): path.read_bytes() for path in paths}
    argv = [sys.executable, "-m", "unittest", "discover", "-s", str(HERE / "tests"),
            "-p", "benchmark*_test.py", "-v"]
    started = datetime.now(timezone.utc).isoformat()
    process = subprocess.run(argv, cwd=HERE, capture_output=True)
    output = process.stdout.decode("utf-8", "replace") + process.stderr.decode("utf-8", "replace")
    unchanged = (all(Path(path).read_bytes() == data for path, data in before.items()) and
                 args.red_evidence.read_bytes() == red_data)
    accepted = unchanged and process.returncode == 0 and "Ran 11 tests" in output and "\nOK\n" in output.replace("\r\n", "\n")
    result = dict(phase="green", accepted=accepted, started_at=started,
                  finished_at=datetime.now(timezone.utc).isoformat(), argv=argv, exit_code=process.returncode,
                  stdout=process.stdout.decode("utf-8", "replace"), stderr=process.stderr.decode("utf-8", "replace"),
                  source_unchanged=unchanged, source_sha256={path: digest(data) for path, data in before.items()},
                  source_base64={path: base64.b64encode(data).decode() for path, data in before.items()},
                  red_evidence=dict(path=str(args.red_evidence.resolve()), sha256=digest(red_data), size_bytes=len(red_data)),
                  synthetic_only=True, matcher_calls=0, image_decodes=0, expected_tests=11,
                  limitation="Synthetic protocol/arithmetic/summary checks only; no measured benchmark or accuracy result")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = HERE / ("summary_validator_green_" + stamp + ".json")
    with path.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(output, end="")
    print("Evidence: " + str(path))
    if not accepted:
        raise SystemExit("Synthetic summary validation failed; evidence retained")


if __name__ == "__main__":
    main()
