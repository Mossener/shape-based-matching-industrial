"""Small isolated tests for the V30 Git publication verifier."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("v30_publication_under_test", Path(__file__).with_name("verify_selection.py"))
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class Result:
    def __init__(self, stdout=b"", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


class PublicationIndexTests(unittest.TestCase):
    def run_fixture(self, object_format, case):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            data = b"{}\n"
            (root / "evidence.json").write_bytes(data)
            selection = {"file_count": 1, "selected_bytes": len(data), "files": [
                {"path": "evidence.json", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            ]}
            selection_path = root / "selection.json"
            selection_path.write_text(json.dumps(selection), encoding="utf-8")
            inventory_data = selection_path.read_bytes()

            def oid(payload):
                return hashlib.new(object_format, b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()

            def run(command, **kwargs):
                self.assertEqual(command[0], "git")
                self.assertEqual(kwargs["cwd"], root)
                arguments = command[1:]
                if arguments == ["rev-parse", "--show-object-format"]:
                    return Result(object_format + "\n")
                if arguments == ["diff", "--cached", "--name-only", "-z"]:
                    extra = b"unrelated-deleted.json\0" if case == "extra_staged_deletion" else b""
                    return Result(b"evidence.json\0selection.json\0" + extra)
                if arguments == ["ls-tree", "-r", "--name-only", "HEAD"]:
                    return Result("")
                if arguments == ["ls-files", "--stage", "-z"]:
                    stage = "1" if case == "unmerged" else "0"
                    data_oid = "0" * len(oid(data)) if case == "wrong_index_bytes" else oid(data)
                    entry = "" if case == "missing_index" else f"100644 {data_oid} {stage}\tevidence.json\0"
                    entry += f"100644 {oid(inventory_data)} 0\tselection.json\0"
                    return Result(entry.encode())
                if arguments == ["diff", "--cached", "--check"]:
                    return Result()
                self.fail(f"Unexpected command: {command!r}")

            expected_error = {
                "wrong_index_bytes": "index bytes differ",
                "extra_staged_deletion": "staged path set mismatch",
                "missing_index": "selected path is absent",
                "unmerged": "unmerged index entry",
            }.get(case)
            captured = io.StringIO()
            with patch.object(VERIFY, "HERE", root), patch.object(VERIFY, "SELECTION", selection_path), \
                    patch.object(VERIFY, "INVENTORY", "selection.json"), \
                    patch.object(VERIFY.subprocess, "run", run), patch.object(sys, "argv", ["verify", "--staged"]), \
                    contextlib.redirect_stdout(captured):
                if expected_error:
                    with self.assertRaisesRegex(SystemExit, expected_error):
                        VERIFY.main()
                else:
                    VERIFY.main()
                    result = json.loads(captured.getvalue())
                    self.assertTrue(result["passed"])
                    self.assertTrue(result["staged"])
                    self.assertEqual(result["file_count"], 1)
                    self.assertEqual(result["selected_bytes"], len(data))


def make_test(object_format, case):
    def test(self):
        self.run_fixture(object_format, case)
    return test


for git_format in ("sha1", "sha256"):
    for fixture in ("green", "wrong_index_bytes", "extra_staged_deletion", "missing_index", "unmerged"):
        setattr(PublicationIndexTests, f"test_{git_format}_{fixture}", make_test(git_format, fixture))


if __name__ == "__main__":
    unittest.main()
