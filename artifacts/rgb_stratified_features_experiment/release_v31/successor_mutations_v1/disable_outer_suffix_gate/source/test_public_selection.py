"""Tiny synthetic accepted-export fixtures; every Git command is mocked."""
import contextlib
import copy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_publication as legacy

SPEC = importlib.util.spec_from_file_location(
    "public_selection_under_test", Path(__file__).with_name("verify_public_selection.py"))
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)
legacy.VERIFY = VERIFY


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


class InheritedPolicyTests(legacy.PublicationTests):
    """Run the unchanged path/size/index tests against the successor."""


class NumericPoolTests(unittest.TestCase):
    def save(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def selected(self, path, root):
        value = pin(path)
        value["path"] = path.relative_to(root).as_posix()
        return value

    def fixture(self, root):
        export = root / "public_export_v1"
        export.mkdir()
        pool = export / "pools_000000.bin.gz"
        pool.write_bytes(gzip.compress(b"synthetic complete numeric pool", mtime=0))
        text = export / "records.jsonl"
        text.write_bytes(b'{"numeric":1}\n')
        rows = []
        for path in (pool, text):
            bare = {key: value for key, value in pin(path).items() if key != "path"}
            rows.append(dict(original_path=path.name, stored_path=path.name,
                             encoding="identity", original=bare, stored=dict(bare)))
        ref = dict(path=str((root / "trusted_root_receipt.json").resolve()),
                   bytes=2, sha256=hashlib.sha256(b"{}").hexdigest())
        manifest = dict(schema="rgb_stratified_lossless_training_export_v1", passed=True,
                        files=rows, file_count=2,
                        stored_bytes=sum(row["stored"]["bytes"] for row in rows),
                        original_physical_bytes=sum(row["original"]["bytes"] for row in rows),
                        training_provenance=ref, training_acceptance=ref, source=ref,
                        native_calls=0, image_decodes=0, heldout_image_reads=0)
        manifest_path = export / "EXPORT_MANIFEST.json"
        self.save(manifest_path, manifest)
        selection_path = root / "selection.json"
        selection = dict(accepted_training_export=pin(manifest_path))
        self.refresh(root, selection_path, selection, (pool, text, manifest_path))
        return selection_path, selection, manifest_path, manifest, pool, text

    def refresh(self, root, selection_path, selection, paths):
        selection["files"] = [self.selected(path, root) for path in paths]
        selection["file_count"] = len(selection["files"])
        selection["selected_bytes"] = sum(row["bytes"] for row in selection["files"])
        self.save(selection_path, selection)

    def repin(self, root, selection_path, selection, manifest_path, manifest):
        self.save(manifest_path, manifest)
        selection["accepted_training_export"] = pin(manifest_path)
        self.refresh(root, selection_path, selection,
                     [root / row["path"] for row in selection["files"]])

    def verify(self, root, selection_path, staged=False, git=None):
        command = ["verify_public", "--selection", str(selection_path)]
        if staged:
            command.append("--staged")
        captured = io.StringIO()
        with patch.object(VERIFY, "HERE", root), patch.object(sys, "argv", command), \
                contextlib.redirect_stdout(captured), patch.object(
                    VERIFY.subprocess, "run",
                    side_effect=git or AssertionError("offline verifier invoked Git")):
            VERIFY.main()
        return json.loads(captured.getvalue())

    def test_exact_accepted_identity_pool_is_allowed_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, _, _, _, _, _ = self.fixture(root)
            self.assertTrue(self.verify(root, path)["passed"])

    def test_absent_or_unselected_or_noncanonical_manifest_pin_is_rejected(self):
        for fault in ("absent", "unselected", "wrong_sha", "wrong_bytes",
                      "relative", "extra_pin_field", "not_manifest_name"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path, selected, manifest_path, _, pool, text = self.fixture(root)
                if fault == "absent":
                    del selected["accepted_training_export"]
                elif fault == "unselected":
                    self.refresh(root, path, selected, (pool, text))
                elif fault == "wrong_sha":
                    selected["accepted_training_export"]["sha256"] = "0" * 64
                elif fault == "wrong_bytes":
                    selected["accepted_training_export"]["bytes"] += 1
                elif fault == "relative":
                    selected["accepted_training_export"]["path"] = "public_export_v1/EXPORT_MANIFEST.json"
                elif fault == "extra_pin_field":
                    selected["accepted_training_export"]["trusted"] = True
                else:
                    renamed = manifest_path.with_name("pretend.json")
                    manifest_path.rename(renamed)
                    selected["accepted_training_export"] = pin(renamed)
                    self.refresh(root, path, selected, (pool, text, renamed))
                self.save(path, selected)
                with self.assertRaises(SystemExit):
                    self.verify(root, path)

    def test_bad_export_schema_status_accounting_and_duplicates_are_rejected(self):
        changes = (
            ("schema", "unrelated_export"),
            ("passed", False),
            ("passed", 1),
            ("file_count", True),
            ("file_count", 3),
            ("stored_bytes", 0),
            ("original_physical_bytes", 0),
            ("duplicate", None),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path, selected, manifest_path, manifest, _, _ = self.fixture(root)
                if field == "duplicate":
                    manifest["files"].append(copy.deepcopy(manifest["files"][0]))
                    manifest["file_count"] += 1
                    manifest["stored_bytes"] += manifest["files"][0]["stored"]["bytes"]
                    manifest["original_physical_bytes"] += manifest["files"][0]["original"]["bytes"]
                else:
                    manifest[field] = value
                self.repin(root, path, selected, manifest_path, manifest)
                with self.assertRaises(SystemExit):
                    self.verify(root, path)

    def test_pool_requires_identity_original_mapping_and_both_matching_pins(self):
        for fault in ("gzip", "different_original_name", "original_sha",
                      "original_bytes", "stored_sha", "stored_bytes", "boolean_bytes",
                      "bare_pin_extra_field"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path, selected, manifest_path, manifest, _, _ = self.fixture(root)
                row = manifest["files"][0]
                if fault == "gzip":
                    row["encoding"] = "gzip"
                elif fault == "different_original_name":
                    row["original_path"] = "pools_000001.bin.gz"
                elif fault == "original_sha":
                    row["original"]["sha256"] = "0" * 64
                elif fault == "original_bytes":
                    row["original"]["bytes"] += 1
                    manifest["original_physical_bytes"] += 1
                elif fault == "stored_sha":
                    row["stored"]["sha256"] = "0" * 64
                elif fault == "stored_bytes":
                    row["stored"]["bytes"] += 1
                    manifest["stored_bytes"] += 1
                elif fault == "boolean_bytes":
                    row["original"]["bytes"] = True
                else:
                    row["stored"]["path"] = "unexpected"
                self.repin(root, path, selected, manifest_path, manifest)
                with self.assertRaises(SystemExit):
                    self.verify(root, path)

    def test_forbidden_names_cannot_be_laundered_through_manifest(self):
        names = ("payload.bin", "payload.bin.gz", "pools_00000.bin.gz",
                 "pools_000000.BIN.gz", "pools_000000.bin.gz.exe",
                 "pools_000000.exe.bin.gz", "nested/pools_000000.bin.gz",
                 "../pools_000000.bin.gz", "pools_000000.bin.gz:stream")
        for name in names:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path, selected, manifest_path, manifest, pool, text = self.fixture(root)
                row = manifest["files"][0]
                row["original_path"] = row["stored_path"] = name
                if ".." not in name and ":" not in name:
                    target = pool.parent / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    pool.rename(target)
                    self.refresh(root, path, selected, (target, text, manifest_path))
                self.repin(root, path, selected, manifest_path, manifest)
                with self.assertRaises(SystemExit):
                    self.verify(root, path)

    def test_unbound_or_different_directory_pool_is_rejected_before_read(self):
        for fault in ("unbound", "path_mixing"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path, selected, manifest_path, _, pool, text = self.fixture(root)
                extra = root / ("pools_000000.bin.gz" if fault == "path_mixing" else "other.bin.gz")
                extra.write_bytes(pool.read_bytes())
                self.refresh(root, path, selected, (pool, text, manifest_path, extra))
                original_read = Path.read_bytes
                opened = []
                def read(member):
                    if member == extra:
                        opened.append(member)
                    return original_read(member)
                with patch.object(Path, "read_bytes", read), self.assertRaises(SystemExit):
                    self.verify(root, path)
                self.assertEqual(opened, [], "unbound binary was opened")

    def test_changed_selected_pool_pin_cannot_override_accepted_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, selected, manifest_path, _, pool, text = self.fixture(root)
            pool.write_bytes(b"changed synthetic numeric bytes")
            self.refresh(root, path, selected, (pool, text, manifest_path))
            with self.assertRaises(SystemExit):
                self.verify(root, path)

    def test_missing_export_member_is_not_a_complete_public_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, selected, manifest_path, _, pool, _ = self.fixture(root)
            self.refresh(root, path, selected, (pool, manifest_path))
            with self.assertRaises(SystemExit):
                self.verify(root, path)

    def test_manifest_duplicate_keys_and_changed_trusted_bytes_rejected(self):
        for fault in ("duplicate_key", "changed_bytes"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path, selected, manifest_path, manifest, pool, text = self.fixture(root)
                if fault == "duplicate_key":
                    data = json.dumps(manifest).replace('"passed": true', '"passed": false, "passed": true')
                    manifest_path.write_text(data)
                    selected["accepted_training_export"] = pin(manifest_path)
                else:
                    manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")
                self.refresh(root, path, selected, (pool, text, manifest_path))
                with self.assertRaises(SystemExit):
                    self.verify(root, path)

    def test_manifest_bytes_change_after_both_pins_were_fixed_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, _, manifest_path, _, _, _ = self.fixture(root)
            manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")
            with self.assertRaises(SystemExit):
                self.verify(root, path)

    def test_export_member_escape_duplicate_and_nonfinite_values_are_rejected(self):
        for fault in ("original_escape", "stored_escape", "duplicate_original",
                      "duplicate_stored", "nonfinite", "oversize_stored"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path, selected, manifest_path, manifest, pool, text = self.fixture(root)
                row = manifest["files"][1]
                if fault == "original_escape":
                    row["original_path"] = "../records.jsonl"
                elif fault == "stored_escape":
                    row["stored_path"] = "../records.jsonl"
                elif fault == "duplicate_original":
                    row["original_path"] = manifest["files"][0]["original_path"]
                elif fault == "duplicate_stored":
                    row["stored_path"] = manifest["files"][0]["stored_path"]
                elif fault == "nonfinite":
                    manifest["irrelevant_field"] = float("nan")
                else:
                    row["stored"]["bytes"] = row["original"]["bytes"] = 95 * 1024**2 + 1
                self.repin(root, path, selected, manifest_path, manifest)
                with self.assertRaises(SystemExit):
                    self.verify(root, path)

    def test_even_rebound_manifest_cannot_select_wrong_pool_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, selected, manifest_path, manifest, pool, text = self.fixture(root)
            extra = pool.with_name("arbitrary.bin.gz")
            pool.rename(extra)
            manifest["files"][0]["original_path"] = manifest["files"][0]["stored_path"] = extra.name
            self.refresh(root, path, selected, (extra, text, manifest_path))
            self.repin(root, path, selected, manifest_path, manifest)
            with self.assertRaises(SystemExit):
                self.verify(root, path)

    def test_exact_pool_and_manifest_index_blobs_remain_required(self):
        for fault in ("green", "pool", "manifest"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path, selected, manifest_path, _, pool, _ = self.fixture(root)
                paths = [root / row["path"] for row in selected["files"]] + [path]
                def oid(data):
                    return hashlib.sha256(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                def git(command, **kwargs):
                    args = command[1:]
                    if args == ["rev-parse", "--show-object-format"]:
                        return legacy.Result("sha256\n")
                    if args == ["diff", "--cached", "--name-only", "-z"]:
                        return legacy.Result(b"".join(p.relative_to(root).as_posix().encode() + b"\0" for p in paths))
                    if args == ["ls-tree", "-r", "--name-only", "-z", "HEAD"]:
                        return legacy.Result()
                    if args == ["ls-files", "--stage", "-z"]:
                        rows = []
                        for member in paths:
                            bad = (fault == "pool" and member == pool) or (fault == "manifest" and member == manifest_path)
                            value = "0" * 64 if bad else oid(member.read_bytes())
                            rows.append(f"100644 {value} 0\t{member.relative_to(root).as_posix()}\0")
                        return legacy.Result("".join(rows).encode())
                    if args == ["diff", "--cached", "--check"]:
                        return legacy.Result()
                    self.fail("unexpected Git command: " + repr(command))
                if fault == "green":
                    self.assertTrue(self.verify(root, path, True, git)["passed"])
                else:
                    with self.assertRaisesRegex(SystemExit, "index bytes differ"):
                        self.verify(root, path, True, git)


if __name__ == "__main__":
    unittest.main(verbosity=2)
