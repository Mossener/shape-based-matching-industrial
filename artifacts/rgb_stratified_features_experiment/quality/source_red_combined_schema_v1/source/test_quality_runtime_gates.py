"""Literal-only regression checks for source and execution evidence gates."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import build_quality as builder
import run_quality as runner
import quality_contract as contract
import run_source_tests as source_tests
import subprocess
import sys


class LiteralProvenance:
    @staticmethod
    def file_pin(path):
        import hashlib
        path=Path(path).resolve();data=path.read_bytes()
        return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

    @classmethod
    def check_pin(cls,pin):
        if cls.file_pin(pin['path'])!=pin:raise ValueError('Literal pin changed')


class RuntimeGatesTest(unittest.TestCase):
    def test_source_gate_rejects_wrong_revision_and_extra_member(self):
        with tempfile.TemporaryDirectory() as directory:
            exp=Path(directory);core=exp/'control_v11';helpers=exp/'frozen_helpers'
            core.mkdir();helpers.mkdir()
            for name in ['line2Dup.cpp']+[f'f{i}.h' for i in range(22)]:
                (core/name).write_text('literal core\n')
            for i in range(3):(helpers/f'h{i}.hpp').write_text('literal helper\n')
            members=lambda root:{p.name:{k:v for k,v in LiteralProvenance.file_pin(p).items() if k!='path'} for p in root.iterdir()}
            data=dict(schema='rgb_stratified_exact_v11_training_source_v1',
                git_revision='b25df46f6ddf9c24fb43f5836f1414dc38c8caed',sole_core_delta=None,
                core_translation_unit=str(core/'line2Dup.cpp'),files=members(core),helpers=members(helpers))
            file=exp/'TRAINING_SOURCE_FREEZE.json'
            with mock.patch.object(builder,'EXPERIMENT',exp),mock.patch.object(builder,'_load_local',return_value=LiteralProvenance):
                file.write_text(json.dumps(data));builder._source_manifest()
                bad=copy.deepcopy(data);bad['git_revision']='changed';file.write_text(json.dumps(bad))
                with self.assertRaises(ValueError,msg='Wrong original revision accepted'):builder._source_manifest()
                file.write_text(json.dumps(data));(core/'extra.h').write_text('extra')
                with self.assertRaises(ValueError,msg='Unlisted source member accepted'):builder._source_manifest()

    def test_build_has_bounded_compiler_and_preserves_timeout_diagnostics(self):
        text=(Path(builder.__file__)).read_text()
        self.assertIn('timeout=300',text,'Compiler has no wall-time bound')
        self.assertIn('except subprocess.TimeoutExpired',text,'Compiler timeout drops diagnostic bytes')

    def test_failed_input_gate_keeps_created_build_directory_for_receipt(self):
        text=Path(builder.__file__).read_text()
        self.assertIn('out = _new_output(args)',text,'Output handle is lost if input gate rejects')

    def _audit_fixture(self,root):
        dev=LiteralProvenance.file_pin(root/'development.json')
        report=root/'audit.json'
        report.write_text(json.dumps(dict(passed=True,numeric_audit_passed=True,
            scope='quality_all_three_arms',development_stage=dev)))
        acceptance=root/'acceptance.json'
        data=dict(accepted_independent_audit=True,scope='quality_all_three_arms',development_stage=dev,
            independent_audit=LiteralProvenance.file_pin(report),numeric_audit_passed=True,
            primary_accuracy_hypothesis_passed=False,production_promotion=False)
        acceptance.write_text(json.dumps(data));return dev,report,acceptance

    def test_quality_audit_gate_byte_checks_report_and_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'development.json').write_text('literal development')
            dev,report,acceptance=self._audit_fixture(root)
            try:result=runner._quality_audit_gate(acceptance,dev,contract,LiteralProvenance)
            except TypeError:self.fail('Quality audit gate cannot verify report/envelope file pins')
            self.assertEqual(result['acceptance'],LiteralProvenance.file_pin(acceptance))
            self.assertEqual(result['independent_audit'],LiteralProvenance.file_pin(report))
            report.write_text(report.read_text()+'changed')
            with self.assertRaises(ValueError):runner._quality_audit_gate(acceptance,dev,contract,LiteralProvenance)

    def test_quality_audit_report_must_bind_same_development(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'development.json').write_text('literal development')
            dev,report,acceptance=self._audit_fixture(root)
            data=json.loads(report.read_text());data['development_stage']['sha256']='b'*64
            report.write_text(json.dumps(data));a=json.loads(acceptance.read_text())
            a['independent_audit']=LiteralProvenance.file_pin(report);acceptance.write_text(json.dumps(a))
            try:
                with self.assertRaises(ValueError):runner._quality_audit_gate(acceptance,dev,contract,LiteralProvenance)
            except TypeError:self.fail('Quality audit gate cannot check independent report development binding')

    def test_watchdog_creates_fresh_siblings_and_preserves_exception(self):
        method=getattr(runner,'_run_native',None)
        self.assertTrue(callable(method),'Native stage lacks a resource watchdog')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            guard=mock.Mock();guard.run_guarded.side_effect=RuntimeError('literal guard exception')
            with self.assertRaises(RuntimeError):method('pilot',['literal-native'],{},root,guard,contract)
            self.assertTrue((root/'watchdog_failure.json').is_file())
            call=guard.run_guarded.call_args
            self.assertEqual(call.kwargs['native_output'],root/'native')
            self.assertEqual(call.kwargs['execution'],root/'guard')
            self.assertEqual(call.kwargs['maximum_seconds'],1800)
            self.assertEqual(call.kwargs['maximum_rss_bytes'],1610612736)
            self.assertEqual(call.kwargs['maximum_output_bytes'],4294967296)
            self.assertEqual(call.kwargs['maximum_execution_bytes'],67108864)

    def test_watchdog_rejects_missing_parent_or_existing_native_before_dispatch(self):
        method=getattr(runner,'_run_native',None)
        self.assertTrue(callable(method),'Native stage lacks a resource watchdog')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);guard=mock.Mock()
            with self.assertRaises(ValueError):method('pilot',[],{},root/'missing',guard,contract)
            (root/'native').mkdir()
            with self.assertRaises(ValueError):method('pilot',[],{},root,guard,contract)
            guard.run_guarded.assert_not_called()

    def test_source_test_timeout_retains_a_failed_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'literal.py').write_text('# literal\n');out=root/'receipt'
            failure=subprocess.TimeoutExpired(['literal'],60,output=b'literal stdout',stderr=b'literal stderr')
            with mock.patch.object(source_tests,'HERE',root),mock.patch.object(sys,'argv',['runner','--output',str(out)]),\
                 mock.patch.object(source_tests.subprocess,'run',side_effect=failure):
                try:
                    with self.assertRaises(SystemExit):source_tests.main()
                except subprocess.TimeoutExpired:self.fail('Source test timeout lost its failure receipt')
            result=json.loads((out/'receipt.json').read_text())
            self.assertFalse(result['passed']);self.assertTrue(result['timed_out'])
            self.assertEqual((out/'stdout.txt').read_bytes(),b'literal stdout')
            self.assertEqual((out/'stderr.txt').read_bytes(),b'literal stderr')


if __name__=='__main__':unittest.main()
