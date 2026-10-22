"""Tiny, independent fixtures for timing execution and stage provenance gates.

No real evidence, images, native programs or Git are accessed by these tests.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import timing_audit as audit


class TimingProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.experiment = self.root / "experiment"
        self.run = self.experiment / "run_timing"
        self.native = self.run / "native"
        self.native.mkdir(parents=True)
        patch = mock.patch.object(audit, "EXPERIMENT", self.experiment)
        patch.start()
        self.addCleanup(patch.stop)
        self.stage_path = self.run / "QUALITY_STAGE_FREEZE.json"
        self.execution_path = self.run / "execution_provenance.json"
        self.before_path = self.run / "verified_before.json"
        self.after_path = self.run / "verified_after.json"
        self.pins = {}
        for name in ("build_manifest", "quality_inputs", "selftest", "development"):
            path = self.root / "references" / (name + ".json")
            self.write_json(path, {"synthetic": name})
            self.pins[name] = self.pin(path)
        script_pins = []
        for name in ("run_quality.py", "quality_contract.py", "prepare_quality_inputs.py",
                     "prepare_input_closure.py", "native_provenance.py", "freeze_private_sources.py",
                     "source_contract.py", "quality_execution_inputs.py"):
            path = self.experiment / name
            path.write_text("# synthetic source\n", encoding="utf-8")
            script_pins.append(self.pin(path))
        self.reservation_path = self.experiment / "reservations" / "timing.json"
        self.reservation = {
            "stage": "timing", "run": str(self.run), "maximum_calls": 12288,
            "previous_stage": "development", "previous_freeze": self.pins["development"],
            "total_protocol_maximum": 22176,
            "policy": "One attempt per fixed stage; reservation survives failure; missing frames are never negatives",
        }
        self.write_json(self.reservation_path, self.reservation)
        self.stage = {
            "stage": "timing", "completed": True, "native_exit_code": 0,
            "actual_matcher_calls": 12288, "maximum_matcher_calls": 12288,
            "post_verification_passed": True, "heldout_images_allowed": False,
            "missing_frames_are_not_negatives": True,
            "build_manifest": self.pins["build_manifest"],
            "quality_inputs": self.pins["quality_inputs"],
            "selftest": self.pins["selftest"], "previous_stage": self.pins["development"],
            "reservation": self.pin(self.reservation_path),
        }
        self.execution = {
            "command": [str(self.experiment / "build_quality_v1/quality_eval.exe"),
                        "--mode", "timing", "--output", str(self.native), "--inputs",
                        self.pins["quality_inputs"]["path"], "--previous",
                        str(Path(self.pins["development"]["path"]).parent / "native")],
            "mode": "timing", "native_exit_code": 0, "maximum_matcher_calls": 12288,
            "script_pins": script_pins,
        }
        for name in ("build_manifest", "quality_inputs", "selftest", "previous_stage", "reservation"):
            self.execution[name] = self.stage[name]
        self.write_json(self.execution_path, self.execution)
        self.verification = {
            "inputs": {"passed": True, "quality_input_freeze": self.pins["quality_inputs"]},
            "images": {"passed": True, "stage": "timing", "image_byte_files_checked": 64,
                       "image_decodes": 0, "matcher_calls": 0,
                       "training_image_files_checked": 0, "heldout_image_files_checked": 0},
        }
        self.write_json(self.before_path, self.verification)
        self.write_json(self.after_path, self.verification)
        (self.run / "native.stdout").write_bytes(b"synthetic native log\n")
        (self.run / "native.stderr").write_bytes(b"")
        for name in ("bank_load_timings.csv", "stage_summary.json", "timing_samples.csv"):
            (self.native / name).write_bytes(b"synthetic numeric fixture\n")
        (self.native / ".gitignore").write_text("*\n", encoding="utf-8")
        self.stage["files"] = [self.pin(path) for path in sorted(self.native.iterdir())
                               if path.name != ".gitignore"]
        self.stage["execution_files"] = [self.pin(path) for path in
                                         (self.execution_path, self.before_path, self.after_path,
                                          self.run / "native.stdout", self.run / "native.stderr")]
        self.write_json(self.stage_path, self.stage)

    @staticmethod
    def write_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def pin(path):
        data = path.read_bytes()
        return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    def execution_gate(self, stage=None):
        audit.validate_execution(audit.Reader(self.root), self.stage if stage is None else stage,
                                 self.stage_path, self.native, self.pins)

    def stage_gate(self, stage=None):
        if stage is not None:
            self.write_json(self.stage_path, stage)
        return audit._pin_stage(audit.Reader(self.root), self.stage_path, "timing", 12288)

    def test_minimal_valid_execution_and_stage_closure(self):
        self.execution_gate()
        stage, native = self.stage_gate()
        self.assertEqual(stage, self.stage)
        self.assertEqual(native, self.native)

    def test_stage_reference_pins_are_bound_to_reviewed_pins(self):
        for field in ("build_manifest", "quality_inputs", "selftest", "previous_stage"):
            changed = copy.deepcopy(self.stage)
            changed[field]["sha256"] = "0" * 64
            with self.subTest(field=field), self.assertRaisesRegex(audit.AuditError, "reviewed source/reference"):
                self.execution_gate(changed)

    def test_execution_reference_pins_are_bound_to_stage(self):
        for field in ("build_manifest", "quality_inputs", "selftest", "previous_stage", "reservation"):
            changed = copy.deepcopy(self.execution)
            changed[field]["sha256"] = "0" * 64
            self.write_json(self.execution_path, changed)
            with self.subTest(field=field), self.assertRaisesRegex(audit.AuditError, "execution stage binding"):
                self.execution_gate()

    def test_execution_command_mode_exit_and_count_mutations(self):
        mutations = {"command": self.execution["command"][:-2], "mode": "development",
                     "native_exit_code": 1, "maximum_matcher_calls": 12287}
        for field, value in mutations.items():
            changed = copy.deepcopy(self.execution)
            changed[field] = value
            self.write_json(self.execution_path, changed)
            with self.subTest(field=field), self.assertRaisesRegex(audit.AuditError, "command/mode/count"):
                self.execution_gate()

    def test_execution_script_scope_and_frozen_sha(self):
        changed = copy.deepcopy(self.execution)
        changed["script_pins"] = changed["script_pins"][::-1]
        self.write_json(self.execution_path, changed)
        with self.assertRaisesRegex(audit.AuditError, "script scope"):
            self.execution_gate()
        self.write_json(self.execution_path, self.execution)
        Path(self.execution["script_pins"][0]["path"]).write_text("# changed\n", encoding="utf-8")
        with self.assertRaisesRegex(audit.AuditError, "SHA/size mismatch"):
            self.execution_gate()

    def test_reservation_mutations_even_after_repinning(self):
        mutations = {"stage": "development", "run": str(self.run / "other"),
                     "maximum_calls": 12287, "previous_stage": "pilot",
                     "previous_freeze": self.pins["selftest"], "total_protocol_maximum": 99999,
                     "policy": "retry allowed"}
        for field, value in mutations.items():
            reservation = copy.deepcopy(self.reservation)
            reservation[field] = value
            self.write_json(self.reservation_path, reservation)
            stage, execution = copy.deepcopy(self.stage), copy.deepcopy(self.execution)
            stage["reservation"] = self.pin(self.reservation_path)
            execution["reservation"] = stage["reservation"]
            self.write_json(self.execution_path, execution)
            with self.subTest(field=field), self.assertRaisesRegex(audit.AuditError, "reservation differs"):
                self.execution_gate(stage)

    def test_pre_and_post_verification_must_match(self):
        changed = copy.deepcopy(self.verification)
        changed["images"]["image_byte_files_checked"] = 63
        self.write_json(self.after_path, changed)
        with self.assertRaisesRegex(audit.AuditError, "pre/post verification"):
            self.execution_gate()

    def test_matching_failed_or_wrong_scope_verification_is_rejected(self):
        for section, field, value in (("inputs", "passed", False), ("images", "passed", False),
                                      ("images", "stage", "heldout"),
                                      ("images", "image_byte_files_checked", 63)):
            changed = copy.deepcopy(self.verification)
            changed[section][field] = value
            self.write_json(self.before_path, changed)
            self.write_json(self.after_path, changed)
            with self.subTest(field=field), self.assertRaisesRegex(audit.AuditError, "pre/post verification"):
                self.execution_gate()

    def test_failed_or_incomplete_stage_closure_is_rejected(self):
        mutations = {"stage": "development", "completed": False, "native_exit_code": 1,
                     "actual_matcher_calls": 12287, "maximum_matcher_calls": 12289,
                     "post_verification_passed": False, "heldout_images_allowed": True,
                     "missing_frames_are_not_negatives": False}
        for field, value in mutations.items():
            changed = copy.deepcopy(self.stage)
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(audit.AuditError, "stage closure"):
                self.stage_gate(changed)

    def test_added_native_or_execution_output_is_rejected(self):
        for path in (self.native / "failure.json", self.native / "nested" / "extra.csv",
                     self.run / "unexpected_receipt.json"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
            with self.subTest(path=path.name), self.assertRaisesRegex(audit.AuditError, "output inventory"):
                self.stage_gate()
            path.unlink()

    def test_changed_frozen_output_bytes_are_rejected(self):
        (self.native / "timing_samples.csv").write_bytes(b"different bytes\n")
        with self.assertRaisesRegex(audit.AuditError, "SHA/size mismatch"):
            self.stage_gate()

    def test_repinned_root_failure_or_extra_execution_output_is_rejected(self):
        for name in ("failure.json", "unexpected_receipt.json"):
            path = self.run / name
            path.write_text("{}\n", encoding="utf-8")
            changed = copy.deepcopy(self.stage)
            changed["execution_files"].append(self.pin(path))
            with self.subTest(name=name), self.assertRaisesRegex(audit.AuditError, "exactly five"):
                self.stage_gate(changed)
            path.unlink()

    def test_duplicate_or_outside_native_pin_is_rejected(self):
        changed = copy.deepcopy(self.stage)
        changed["files"].append(changed["files"][0])
        with self.assertRaisesRegex(audit.AuditError, "duplicate/outside"):
            self.stage_gate(changed)
        changed = copy.deepcopy(self.stage)
        changed["files"][0] = self.pins["quality_inputs"]
        with self.assertRaisesRegex(audit.AuditError, "duplicate/outside"):
            self.stage_gate(changed)

    def test_exact_three_file_gate_rejects_even_pinned_nested_or_failed_output(self):
        audit.validate_timing_output_files(self.native)
        for path in (self.native / "failure.json", self.native / "nested" / "extra.csv"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
            changed = copy.deepcopy(self.stage)
            changed["files"].append(self.pin(path))
            # A complete but overbroad manifest passes the generic pin gate;
            # the timing-specific exact three-file gate must reject it.
            self.stage_gate(changed)
            with self.subTest(path=str(path)), self.assertRaisesRegex(audit.AuditError, "exactly three"):
                audit.validate_timing_output_files(self.native)
            path.unlink()
        (self.native / "timing_samples.csv").unlink()
        with self.assertRaisesRegex(audit.AuditError, "exactly three"):
            audit.validate_timing_output_files(self.native)

    def test_zero_image_identifier_is_valid_in_frozen_schedule_and_development_counts(self):
        development = [{"scene_id": 4, "image_id": image, "timing": image < 64}
                       for image in range(400)]
        frames = audit.expected_timing_frames({"development": development})
        self.assertEqual(len(frames), 64)
        self.assertEqual(frames[0], (4, 0))
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=audit.PER_FRAME_HEADER, lineterminator="\n")
        writer.writeheader()
        for obj in audit.OBJECTS:
            for image in range(400):
                for arm in audit.ARMS:
                    row = dict.fromkeys(audit.PER_FRAME_HEADER, "0")
                    row.update(object_id=str(obj), scene="4", image=str(image), arm=arm,
                               raw="5", selected="2")
                    writer.writerow(row)
        counts = audit.parse_development_counts(buffer.getvalue().encode("utf-8"))
        self.assertEqual(counts[(1, 4, 0, "rgb_control")], (5, 2))


if __name__ == "__main__":
    unittest.main()

