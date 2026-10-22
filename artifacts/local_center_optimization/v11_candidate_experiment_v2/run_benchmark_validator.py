"""Retain literal synthetic RED/GREEN evidence; no compiler/matcher/dataset reads."""
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
    parser.add_argument("--phase", required=True, choices=("red", "green"))
    args = parser.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    paths = [HERE / "benchmark_contract.py", HERE / "tests/benchmark_contract_test.py", Path(__file__)]
    before = {str(path.resolve()): path.read_bytes() for path in paths}
    argv = [sys.executable, str(paths[1])]
    if args.phase == "red":
        argv += ["BenchmarkContract.test_b_changed_variant_or_cache_cannot_hide_behind_case_name"]
    started = datetime.now(timezone.utc).isoformat()
    process = subprocess.run(argv, cwd=HERE, capture_output=True)
    output = process.stdout.decode("utf-8", "replace") + process.stderr.decode("utf-8", "replace")
    unchanged = all(Path(path).read_bytes() == data for path, data in before.items())
    accepted = unchanged and ((process.returncode == 1 and "AssertionError: ValueError not raised" in output)
                              if args.phase == "red" else process.returncode == 0)
    evidence = dict(phase=args.phase, accepted=accepted, started_at=started,
                    finished_at=datetime.now(timezone.utc).isoformat(), argv=argv,
                    exit_code=process.returncode, stdout=process.stdout.decode("utf-8", "replace"),
                    stderr=process.stderr.decode("utf-8", "replace"), source_unchanged=unchanged,
                    source_sha256={path: digest(data) for path, data in before.items()},
                    source_base64={path: base64.b64encode(data).decode() for path, data in before.items()},
                    synthetic_only=True, matcher_calls=0, image_decodes=0,
                    limitation="Synthetic identity/order/timing validator only; no native correctness or speed result")
    path = HERE / ("benchmark_validator_" + args.phase + "_" + stamp + ".json")
    with path.open("x", encoding="utf-8") as target:
        json.dump(evidence, target, indent=2)
        target.write("\n")
    print(output, end="")
    print("Evidence: " + str(path))
    if not accepted:
        raise SystemExit("Unexpected validator phase outcome; evidence retained")


if __name__ == "__main__":
    main()
