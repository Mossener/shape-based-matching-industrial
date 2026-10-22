"""No native calls: authorization ordering and prior-pin scope/recheck failures."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_full_api as runner


class RunnerContract(unittest.TestCase):
    def test_cpu_and_dataset_gates_precede_output_or_source_reads(self):
        with patch.object(runner,"checked_output",side_effect=AssertionError("output touched")), \
             patch.object(runner,"verify_sources",side_effect=AssertionError("source touched")):
            with self.assertRaisesRegex(ValueError,"CPU"):
                runner.run(SimpleNamespace(cpu_slot_granted=False))
            with self.assertRaisesRegex(ValueError,"dataset"):
                runner.run(SimpleNamespace(cpu_slot_granted=True,phase="correctness",dataset_stage_granted=False))

    def prior(self,directory,items):
        value=dict(accepted=True,phase="build",binding=dict(source_manifest_sha256="a"*64,
                   source_manifest_path=str(runner.MANIFEST)),final_recheck_errors=[],
                   toolchain=dict(compiler_root="D:/whole_api_fixture_compiler",opencv_root="D:/opencv-4.12.0",
                                  python=runner.pin(sys.executable)),
                   input_pins=items,artifact_pins=[])
        target=directory/"stage_result.json"
        target.write_text(json.dumps(value),encoding="utf-8")
        return target

    def test_exact_current_python_pin_is_allowed_outside_native_toolchain(self):
        runner.BUILD_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="policy_test_",dir=runner.BUILD_ROOT) as temporary:
            directory=Path(temporary).resolve();item=runner.pin(sys.executable)
            receipt=self.prior(directory,[item]);tracked={}
            runner.verify_previous(receipt,"build","a"*64,tracked)
            self.assertEqual(tracked[str(Path(sys.executable).resolve())],item)

    def test_python_scope_does_not_admit_neighbor_files(self):
        runner.BUILD_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="policy_test_",dir=runner.BUILD_ROOT) as temporary:
            directory=Path(temporary).resolve()
            neighbor=Path(sys.executable).resolve().with_name("unapproved_python_neighbor.bin")
            item=dict(path=str(neighbor),bytes=1,sha256="0"*64)
            receipt=self.prior(directory,[runner.pin(sys.executable),item]);original=runner.pin;reads=[]
            def guarded(path):
                reads.append(Path(path).resolve())
                if Path(path).resolve()==neighbor:raise AssertionError("neighbor read")
                return original(path)
            with patch.object(runner,"pin",side_effect=guarded),self.assertRaisesRegex(ValueError,"scope"):
                runner.verify_previous(receipt,"build","a"*64,{})
            self.assertEqual(reads,[receipt])

    def test_forged_python_role_cannot_authorize_image_pin(self):
        runner.BUILD_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="policy_test_",dir=runner.BUILD_ROOT) as temporary:
            directory=Path(temporary).resolve();forbidden=(runner.ROOT/"LED/1.bmp").resolve()
            item=dict(path=str(forbidden),bytes=1,sha256="0"*64)
            receipt=self.prior(directory,[item]);value=runner.read_json(receipt)
            value["toolchain"]["python"]=item;receipt.write_text(json.dumps(value),encoding="utf-8")
            original=runner.pin;reads=[]
            def guarded(path):
                reads.append(Path(path).resolve())
                if Path(path).resolve()==forbidden:raise AssertionError("image read")
                return original(path)
            with patch.object(runner,"pin",side_effect=guarded),self.assertRaisesRegex(ValueError,"Python|scope"):
                runner.verify_previous(receipt,"build","a"*64,{})
            self.assertEqual(reads,[receipt])

    def test_every_prior_scope_is_checked_before_reading_any_prior_pin(self):
        runner.BUILD_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="policy_test_",dir=runner.BUILD_ROOT) as temporary:
            directory=Path(temporary).resolve()
            forbidden=runner.ROOT/"LED/1.bmp"
            item=dict(path=str(forbidden),bytes=1,sha256="0"*64)
            receipt=self.prior(directory,[item]);original=runner.pin;reads=[]
            def guarded(path):
                reads.append(Path(path).resolve())
                if Path(path).resolve()==forbidden.resolve():raise AssertionError("image read")
                return original(path)
            with patch.object(runner,"pin",side_effect=guarded),self.assertRaisesRegex(ValueError,"scope"):
                runner.verify_previous(receipt,"build","a"*64,{})
            self.assertEqual(reads,[receipt])

    def test_changed_prior_artifact_is_rejected_and_unchanged_is_retained(self):
        runner.BUILD_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="policy_test_",dir=runner.BUILD_ROOT) as temporary:
            directory=Path(temporary).resolve();artifact=directory/"numeric.log"
            artifact.write_bytes(b"accepted");item=runner.pin(artifact)
            receipt=self.prior(directory,[item]);tracked={}
            runner.verify_previous(receipt,"build","a"*64,tracked)
            self.assertIn(str(artifact),tracked)
            artifact.write_bytes(b"changed!")
            with self.assertRaisesRegex(ValueError,"changed"):
                runner.verify_previous(receipt,"build","a"*64,{})


if __name__=="__main__":unittest.main()
