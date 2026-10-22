"""Synthetic one-shot wrapper tests; the real guard and auditor never run."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import run_audit as r


class RunnerTests(unittest.TestCase):
    def fixture(self,root):
        stage=root/'native_run'/'QUALITY_STAGE_FREEZE.json'; stage.parent.mkdir()
        stage.write_text(json.dumps(dict(stage='development',completed=True,native_exit_code=0,
              actual_matcher_calls=14400,maximum_matcher_calls=14400,summary=dict(passed=1),
              files=[dict(path=str(root/'unopened_bank.yml.gz'),bytes=100,sha256='a'*64)])))
        source=root/'source.py'; source.write_bytes(b'# synthetic source\n')
        return r.file_pin(stage),source,root/'reservation.json',root/'audit_evidence'

    def test_reserve_reads_no_stage_members_and_refuses_second_reservation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); stage,source,reservation,evidence=self.fixture(root)
            with mock.patch.object(r,'REGISTRY',root/'registry'),mock.patch.object(r,'source_pins',return_value=[r.file_pin(source)]):
                record=r.reserve(stage,evidence,reservation,root)
                self.assertEqual(record['development_stage'],stage)
                self.assertFalse((root/'unopened_bank.yml.gz').exists())
                self.assertFalse(evidence.exists())
                with self.assertRaises(ValueError): r.reserve(stage,evidence,root/'another.json',root)

    def test_execute_one_guarded_child_and_no_retry(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); stage,source,reservation,evidence=self.fixture(root)
            def guard(command,output,execution):
                output.mkdir(); execution.mkdir()
                (output/'result.json').write_text(json.dumps(dict(passed=True,numeric_audit_passed=True,
                     development_stage=stage,production_promotion=False,primary_accuracy_hypothesis_passed=False)))
                return dict(passed=True,exit_code=0)
            with mock.patch.object(r,'REGISTRY',root/'registry'),mock.patch.object(r,'source_pins',side_effect=lambda:[r.file_pin(source)]), \
                 mock.patch.object(r,'run_guard',side_effect=guard) as child:
                r.reserve(stage,evidence,reservation,root)
                with self.assertRaises(ValueError): r.execute(reservation,False,root)
                result=r.execute(reservation,True,root)
                self.assertTrue(result['passed']); self.assertFalse(result['production_promotion'])
                self.assertFalse(result['primary_accuracy_hypothesis_passed'])
                self.assertEqual(child.call_count,1)
                command=child.call_args.args[0]
                self.assertIn(stage['sha256'],command); self.assertIn(str(stage['bytes']),command)
                self.assertTrue((evidence/'RUNNER_RECEIPT.json').is_file())
                with self.assertRaises(ValueError): r.execute(reservation,True,root)
                self.assertEqual(child.call_count,1)

    def test_source_change_consumes_attempt_without_running_child(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); stage,source,reservation,evidence=self.fixture(root)
            with mock.patch.object(r,'REGISTRY',root/'registry'),mock.patch.object(r,'source_pins',side_effect=lambda:[r.file_pin(source)]), \
                 mock.patch.object(r,'run_guard') as child:
                r.reserve(stage,evidence,reservation,root); source.write_bytes(b'# changed\n')
                result=r.execute(reservation,True,root)
                self.assertFalse(result['passed']); child.assert_not_called()
                self.assertTrue(result['failure_preserved'])
                self.assertTrue((evidence/'RUNNER_RECEIPT.json').is_file())
                with self.assertRaises(ValueError): r.execute(reservation,True,root)

    def test_child_failure_or_wrong_stage_preserved(self):
        for fault in ('guard','wrong_stage','missing_result'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as t:
                root=Path(t); stage,source,reservation,evidence=self.fixture(root)
                def guard(command,output,execution):
                    output.mkdir(); execution.mkdir()
                    if fault!='missing_result':
                        (output/'result.json').write_text(json.dumps(dict(passed=True,numeric_audit_passed=True,
                            development_stage=dict(stage,sha256='0'*64) if fault=='wrong_stage' else stage,
                            production_promotion=False,primary_accuracy_hypothesis_passed=True)))
                    return dict(passed=fault!='guard',exit_code=2 if fault=='guard' else 0)
                with mock.patch.object(r,'REGISTRY',root/'registry'),mock.patch.object(r,'source_pins',side_effect=lambda:[r.file_pin(source)]), \
                     mock.patch.object(r,'run_guard',side_effect=guard):
                    r.reserve(stage,evidence,reservation,root); result=r.execute(reservation,True,root)
                    self.assertFalse(result['passed']); self.assertTrue(result['failure_preserved'])
                    self.assertTrue((evidence/'RUNNER_RECEIPT.json').is_file())


if __name__=='__main__': unittest.main(verbosity=2)
