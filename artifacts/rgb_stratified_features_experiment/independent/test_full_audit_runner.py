"""Source-only tests for the guarded full-audit runner.

The tests use a temporary synthetic run and never open the real training
directory, image set, pools or banks.  Heavy audit execution remains outside
this selftest.
"""
import json
from pathlib import Path
import tempfile
import importlib.util


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("full_audit_runner", HERE / "run_full_audit.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def require(value, message):
    if not value:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix="full-audit-runner-") as name:
        root = Path(name)
        run = root / "run"
        run.mkdir()
        first = run / "training_summary.json"
        second = run / "pools.jsonl"
        first.write_text('{"complete":true}\n', encoding="utf-8")
        second.write_text('{"pool_id":0}\n', encoding="utf-8")
        pins = [runner.file_pin(first), runner.file_pin(second)]
        provenance = root / "runner.json"
        provenance.write_text(json.dumps({
            "mode": "train", "passed": True,
            "expected_shared_poses": 20736, "expected_matcher_calls": 0,
            "files": pins,
        }), encoding="utf-8")
        # The synthetic provenance intentionally lacks the full static set;
        # first exercise the relative conversion through a complete fixture.
        for name2 in ("shards.jsonl", "pool_observations.jsonl",
                      "layer_selections.jsonl", "attempts.jsonl",
                      "progress.jsonl", "loaded_modules.json"):
            path = run / name2
            path.write_text("{}\n", encoding="utf-8")
            pins.append(runner.file_pin(path))
        provenance.write_text(json.dumps({
            "mode": "train", "passed": True,
            "expected_shared_poses": 20736, "expected_matcher_calls": 0,
            "files": pins,
        }), encoding="utf-8")
        result = runner.derive_output_pins(run, provenance)
        require(set(result) == {
            "training_summary.json", "pools.jsonl", "shards.jsonl",
            "pool_observations.jsonl", "layer_selections.jsonl",
            "attempts.jsonl", "progress.jsonl", "loaded_modules.json",
        }, "relative output map differs")
        first.write_text('{"tampered":true}\n', encoding="utf-8")
        try:
            runner.derive_output_pins(run, provenance)
        except ValueError as error:
            require("changed" in str(error), "tamper failure was not targeted")
        else:
            raise AssertionError("tampered output pin was accepted")
    print("full_audit_runner source selftest: PASS")


if __name__ == "__main__":
    main()
