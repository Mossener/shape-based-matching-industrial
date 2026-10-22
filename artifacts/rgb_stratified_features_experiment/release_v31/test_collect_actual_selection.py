"""Tiny isolated collector contracts; never opens the real experiment tree."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "collect_actual_selection", Path(__file__).with_name("collect_actual_selection.py"))
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.c = collector.Collector(self.root)

    def put(self, name, data=b"evidence\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return dict(path=str(path.resolve()), bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest())

    def document(self, name, value):
        return self.put(name, (json.dumps(value) + "\n").encode())

    def test_union_is_idempotent_and_conflicting_pin_fails(self):
        pin = self.put("evidence.txt")
        self.c.add_pin(pin)
        self.c.add_pin(pin)
        self.assertEqual(len(self.c.rows), 1)
        with self.assertRaisesRegex(ValueError, "conflicting pin"):
            self.c.add_pin(dict(pin, sha256="0" * 64))

    def test_relative_traversal_and_external_fullpin_are_rejected(self):
        for name in ("../escape.txt", "a/../b.txt", "a\\b.txt", "/absolute.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.c.relative(name)
        with self.assertRaisesRegex(ValueError, "outside repository"):
            self.c.add_pin(dict(path=str(self.root.parent / "runtime.txt"),
                                bytes=1, sha256="0" * 64))

    def test_pin_does_not_read_payload_and_later_verifier_owns_hash_check(self):
        pin = self.put("raw.csv.gz", b"a" * 31)
        # Deliberately wrong hash is retained, not silently recomputed here.
        wrong = dict(pin, sha256="1" * 64)
        self.c.add_pin(wrong)
        self.assertEqual(self.c.rows["raw.csv.gz"]["sha256"], "1" * 64)
        self.assertEqual(self.c.payload_bytes_read, 0)

    def test_binary_and_materialized_restore_members_are_rejected(self):
        names = ("tool.exe", "model.bin.gz",
                 collector.BASE + "/public_training_restore_validation_v1/result.json")
        for name in names:
            with self.subTest(name=name):
                pin = self.put(name)
                with self.assertRaisesRegex(ValueError, "forbidden|materialized restore"):
                    self.c.add_pin(pin)

    def test_original_transport_pin_can_exceed_github_limit_but_selected_member_cannot(self):
        original = dict(bytes=collector.MAX_FILE + 1, sha256="3" * 64)
        self.assertEqual(collector.bare_pin(original), original)
        with self.assertRaisesRegex(ValueError, "GitHub limit"):
            self.c.add_pin(dict(path=str(self.root / "too-large.txt"), **original))

    def test_manifest_authorized_pool_is_the_only_binary_exception(self):
        pin = self.put("export/pools_000000.bin.gz")
        self.c.allowed_pools["export/pools_000000.bin.gz"] = collector.bare_pin(pin)
        self.c.add_pin(pin)
        self.assertEqual(set(self.c.rows), {"export/pools_000000.bin.gz"})
        with self.assertRaisesRegex(ValueError, "forbidden"):
            self.c.add_pin(self.put("export/pools_000001.bin.gz"))

    def test_local_metadata_is_hashed_and_duplicate_json_keys_fail(self):
        pin = self.document("small.json", {"passed": True})
        self.assertTrue(self.c.json_file("small.json")["passed"])
        self.assertEqual(self.c.rows["small.json"]["sha256"], pin["sha256"])
        self.put("duplicate.json", b'{"x":1,"x":2}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.c.json_file("duplicate.json")

    def test_historical_snapshot_uses_run_pin_not_current_source(self):
        old = self.put("run/source/a.py", b"old\n")
        current = self.put("a.py", b"new\n")
        historical = dict(old, path=current["path"])
        self.c.snapshot("run/source", [historical])
        self.assertEqual(self.c.rows["run/source/a.py"]["sha256"], old["sha256"])
        self.assertNotIn("a.py", self.c.rows)

    def test_mutant_override_keeps_all_finite_source_roles(self):
        old = self.put("base/a.py", b"original\n")
        helper = self.put("base/b.py", b"helper\n")
        mutant = self.put("mutant/a.py", b"changed\n")
        self.put("mutant/b.py", b"helper\n")
        self.c.snapshot("mutant", [old, helper], mutant)
        self.assertEqual(set(self.c.rows), {"mutant/a.py", "mutant/b.py"})
        self.assertEqual(self.c.rows["mutant/a.py"]["sha256"], mutant["sha256"])

    def test_sources_record_external_runtime_without_selecting_it(self):
        source = self.put("runner.py")
        external = dict(path=str(self.root.parent / "python.exe"),
                        bytes=12, sha256="2" * 64)
        self.c.source_pins([source, external])
        self.assertEqual(set(self.c.rows), {"runner.py"})
        self.assertEqual(self.c.external_sources, [external])

    def test_only_failed_v1_may_omit_after_source_pins(self):
        source = self.put("audit.py")
        failed = dict(passed=False, source_pins_before=[source], source_pins_after=None)
        self.c.quality_source_records(failed, failed_v1=True)
        self.assertEqual(set(self.c.rows), {"audit.py"})
        for receipt, historical in ((failed, False),
                                    (dict(failed, passed=True), True),
                                    (dict(failed, passed=True), False),
                                    (dict(failed, passed=True, source_pins_after=[]), False)):
            with self.subTest(receipt=receipt, historical=historical), self.assertRaises(ValueError):
                self.c.quality_source_records(receipt, failed_v1=historical)
        self.c.quality_source_records(dict(failed, passed=True, source_pins_after=[source]))

    def test_manifest_inventory_never_follows_unlisted_sibling(self):
        raw = self.put("stage/raw.csv.gz")
        self.put("stage/private.png")
        receipt = dict(completed=True, post_verification_passed=True,
                       native_exit_code=0, files=[raw], execution_files=[])
        self.document("stage/QUALITY_STAGE_FREEZE.json", receipt)
        self.c.stage("stage/QUALITY_STAGE_FREEZE.json")
        self.assertEqual(set(self.c.rows),
                         {"stage/QUALITY_STAGE_FREEZE.json", "stage/raw.csv.gz"})

    def test_incomplete_stage_does_not_produce_a_passing_selection(self):
        self.document("stage.json", dict(completed=False, files=[], execution_files=[]))
        with self.assertRaisesRegex(ValueError, "incomplete stage"):
            self.c.stage("stage.json")

    def test_pathspec_is_explicit_nul_separated_and_has_no_self_pin(self):
        self.c.add_pin(self.put("evidence.txt"))
        selection = self.c.selection(dict(path=str(self.root / "export.json"),
                                          bytes=0, sha256="0" * 64))
        self.assertEqual(selection["file_count"], 1)
        self.assertEqual(selection["selected_bytes"], len(b"evidence\n"))
        self.assertFalse(selection["production_promotion"])
        spec = self.c.pathspec()
        self.assertTrue(spec.endswith(b"\0"))
        self.assertIn(collector.SELECTION.encode(), spec.split(b"\0"))
        self.assertNotIn(collector.SELECTION, self.c.rows)


if __name__ == "__main__":
    unittest.main()
