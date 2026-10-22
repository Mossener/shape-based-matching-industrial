"""Reject narrowly weakened successor copies using only tiny synthetic fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SOURCES = ("verify_selection.py", "test_publication.py", "verify_public_selection.py",
           "test_public_selection.py", "run_public_tests.py", "run_public_mutations.py")
MUTATIONS = {
    "ignore_selected_manifest_binding": [(
        '''if (manifest_row is None
            or {key: manifest_row.get(key) for key in ("bytes", "sha256")}
            != {key: trusted[key] for key in ("bytes", "sha256")}):''',
        "if False:")],
    "ignore_manifest_bytes_pin": [(
        '''if (len(raw) >= MAX_BYTES or len(raw) != trusted["bytes"]
            or hashlib.sha256(raw).hexdigest() != trusted["sha256"]):''',
        "if False:")],
    "ignore_export_schema": [(
        '''or manifest.get("schema") != "rgb_stratified_lossless_training_export_v1"''',
        "or False")],
    "ignore_encoding_field": [(
        'encoding = member.get("encoding")', 'encoding = "identity"')],
    "ignore_original_pin": [
        ('if encoding == "identity" and before != saved:', 'if False:'),
        ('or stored != original or encoding != "identity" or before != saved):',
         'or stored != original or encoding != "identity"):')],
    "allow_arbitrary_bin_gzip_name": [(
        're.fullmatch(r"pools_[0-9]{6}\\.bin\\.gz", original)',
        're.fullmatch(r".+\\.bin\\.gz", original)')],
    "omit_export_members": [(
        '''if (selected_member is None
                or {key: selected_member.get(key) for key in ("bytes", "sha256")} != saved):''',
        '''if (selected_member is not None
                and {key: selected_member.get(key) for key in ("bytes", "sha256")} != saved):''')],
    "rebind_pool_to_selected_pin": [
        ('''if (selected_member is None
                or {key: selected_member.get(key) for key in ("bytes", "sha256")} != saved):''',
         "if selected_member is None:"),
        ('allowed[target_rel] = saved',
         'allowed[target_rel] = {key: selected_member.get(key) for key in ("bytes", "sha256")}')],
    "disable_outer_suffix_gate": [(
        '''if forbidden and not (forbidden == {".bin"} and path.suffixes == [".bin", ".gz"]
                              and pool_pins.get(rel) == {key: row.get(key) for key in ("bytes", "sha256")}):''',
        "if False:")],
}


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(HERE):
        raise SystemExit("fresh contained mutation output required")
    output.mkdir(parents=True)
    before = [pin(HERE / name) for name in SOURCES]
    original = (HERE / "verify_public_selection.py").read_text(encoding="utf-8")
    results = []
    for name, changes in MUTATIONS.items():
        directory = output / name
        source = directory / "source"
        source.mkdir(parents=True)
        for member in SOURCES:
            (source / member).write_bytes((HERE / member).read_bytes())
        mutated = original
        for old, new in changes:
            if mutated.count(old) != 1:
                raise SystemExit("mutation anchor must occur exactly once: " + name)
            mutated = mutated.replace(old, new)
        (source / "verify_public_selection.py").write_text(mutated, encoding="utf-8")
        command = [sys.executable, "-B", "-m", "unittest", "discover",
                   "-s", str(source), "-p", "test_public_selection.py", "-v"]
        process = subprocess.run(command, cwd=HERE,
                                 env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                 capture_output=True, timeout=120)
        (directory / "stdout.txt").write_bytes(process.stdout)
        (directory / "stderr.txt").write_bytes(process.stderr)
        counts = re.findall(rb"Ran (\d+) tests?", process.stderr)
        result = dict(name=name, rejected=process.returncode != 0,
                      exit_code=process.returncode, tests=int(counts[-1]) if counts else None,
                      command=command, changes=[dict(before=a, after=b) for a, b in changes],
                      mutant_pin=pin(source / "verify_public_selection.py"),
                      outputs=[pin(directory / member) for member in ("stdout.txt", "stderr.txt")])
        (directory / "receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        results.append(result)
    unchanged = before == [pin(HERE / name) for name in SOURCES]
    passed = unchanged and all(row["rejected"] and row["tests"] == 20 for row in results)
    receipt = dict(schema="v31_public_selection_targeted_mutations_v1", passed=passed,
                   mutants=results, source_pins=before, source_unchanged=unchanged,
                   synthetic_only=True, real_git_commands_run=0, real_index_reads=0,
                   real_bank_reads=0, real_raw_archive_reads=0, real_image_reads=0,
                   native_runs=0, matcher_calls=0, final_selection_created=False,
                   limitation="Deliberate source mutants and temporary tiny fixtures only")
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(passed=passed, rejected=sum(row["rejected"] for row in results),
                          mutants=len(results), receipt=str(output / "receipt.json"))))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
