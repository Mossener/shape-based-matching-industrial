"""Literal numeric evidence gates and a mocked foreground watchdog."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import evidence as e
import audit as replay
import run_audit as runner


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8');return runner.pin(path)


class EvidenceTests(unittest.TestCase):
    def test_reader_bounds_and_refuses_images_banks_gzip_and_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);reader=e.Reader(root)
            for name in ['image.png','templates_obj1.yml.gz','s1_i1_fallback_raw.csv.gz','native.exe']:
                path=root/name;path.write_bytes(b'literal forbidden text')
                with self.subTest(name=name),self.assertRaises(e.a.AuditError):reader.read(path)
            path=root/'a.json';path.write_text('{}');reader.read(path);path.write_text('[]')
            with self.assertRaises(e.a.AuditError):reader.read(path)
            with mock.patch.object(e,'MAX_BYTES',1),self.assertRaises(e.a.AuditError):e.Reader(root).read(path)
            with self.assertRaises(e.a.AuditError):e.loads(b'{"x":1,"x":2}')
            with self.assertRaises(e.a.AuditError):e.loads(b'{"x":NaN}')

    def test_duplicate_noncanonical_and_boolean_pins_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            pin=write(Path(directory)/'a.json',{})
            with self.assertRaises(e.a.AuditError):e.pin_map([pin,pin])
            for key,value in [('bytes',True),('sha256','x'*64),('path','relative.json')]:
                bad=dict(pin);bad[key]=value
                with self.assertRaises(e.a.AuditError):e.pin_schema(bad)

    def _stage(self,root):
        run=root/'run';native=run/'native';native.mkdir(parents=True)
        for name in ('bank_load_timings.csv','stage_summary.json','timing_samples.csv','timing_pairs.csv'):
            (native/name).write_text('literal numeric\n')
        for name in ('execution_provenance.json','verified_before.json','verified_after.json',
                'guard/stdout.txt','guard/stderr.txt','guard/guard_reservation.json','guard/guard_latest.json',
                'guard/guard_telemetry.jsonl','guard/guard_receipt.json'):
            path=run/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')
        stage=dict(completed=True,stage='timing',native_exit_code=0,actual_matcher_calls=29952,maximum_matcher_calls=29952,
            post_verification_passed=True,heldout_images_allowed=False,missing_frames_are_not_negatives=True,
            files=[runner.pin(p) for p in native.iterdir()],execution_files=[runner.pin(p) for p in run.rglob('*')
                if p.is_file() and not p.is_relative_to(native)])
        path=run/'QUALITY_STAGE_FREEZE.json';return path,stage,native

    def test_exact_four_native_files_and_nested_execution_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,stage,native=self._stage(root);pin=write(path,stage)
            e.stage_gate(e.Reader(root),pin,'timing',29952,True)
            extra=native/'extra.csv';extra.write_text('extra');bad=copy.deepcopy(stage);bad['files'].append(runner.pin(extra))
            with self.assertRaisesRegex(e.a.AuditError,'four'):e.stage_gate(e.Reader(root),write(path,bad),'timing',29952)
            extra.unlink();extra=path.parent/'guard/extra.txt';extra.write_text('extra')
            with self.assertRaisesRegex(e.a.AuditError,'inventory'):e.stage_gate(e.Reader(root),write(path,stage),'timing',29952)
            extra.unlink();(native/'timing_samples.csv').write_text('changed')
            with self.assertRaisesRegex(e.a.AuditError,'SHA/size'):e.stage_gate(e.Reader(root),write(path,stage),'timing',29952,True)

    def test_acceptance_false_accuracy_allows_measurement_but_wrong_arm_or_audit_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);dev=write(root/'dev.json',{});prior=dict(schema='independent_three_arm_quality_audit_v1',
                passed=True,numeric_audit_passed=True,scope='quality_all_three_arms',development_stage=dev,arms=list(e.a.ARMS),
                object_frame_pairs=2400,production_promotion=False,common_padding_C0_full_raw_exact=True,
                pilot_overlap_full_raw_exact=True,primary_accuracy_hypothesis_passed=False,input_pins=[dev])
            prior_pin=write(root/'audit.json',prior)
            accepted=dict(accepted_independent_audit=True,numeric_audit_passed=True,scope='quality_all_three_arms',
                production_promotion=False,primary_accuracy_hypothesis_passed=False,development_stage=dev,independent_audit=prior_pin)
            acceptance=write(root/'acceptance.json',accepted);pins=dict(development_stage=dev,development_audit=prior_pin,quality_acceptance=acceptance)
            timing=dict(quality_audit=dict(acceptance=acceptance,independent_audit=prior_pin,development_stage=dev,
                primary_accuracy_hypothesis_passed=False))
            replay.acceptance_gate(e.Reader(root),pins,timing)
            for field,value in [('scope','training_only'),('arms',list(e.a.ARMS[:2])),('numeric_audit_passed',False)]:
                bad=copy.deepcopy(prior);bad[field]=value;pins['development_audit']=write(root/'audit.json',bad)
                with self.assertRaises(e.a.AuditError):replay.acceptance_gate(e.Reader(root),pins,timing)

    def test_watchdog_parent_freshness_and_exact_resource_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);guard=mock.Mock();guard.run_guarded.return_value={'passed':False}
            with self.assertRaises(e.a.AuditError):runner.dispatch([],{},root/'missing/out',root/'missing/guard',guard)
            guard.run_guarded.assert_not_called()
            runner.dispatch(['literal'],{},root/'out',root/'guard',guard)
            call=guard.run_guarded.call_args
            self.assertEqual(call.args[3:],(root/'out',root/'guard'))
            self.assertEqual(call.kwargs['maximum_seconds'],5400)
            self.assertEqual(call.kwargs['maximum_output_bytes'],4294967296)
            (root/'out').mkdir()
            with self.assertRaises(e.a.AuditError):runner.dispatch([],{},root/'out',root/'guard',guard)

    def test_reservation_single_attempt_and_exception_failure_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);here=root/'review';here.mkdir();ref=write(root/'reference.json',{})
            spec=dict(schema='rgb_stratified_independent_timing_inputs_v1',**{k:ref for k in replay.REFS})
            input_pin=write(root/'inputs.json',spec);reservation=here/'reservation.json';output=here/'nested/out'
            with mock.patch.object(runner,'HERE',here),mock.patch.object(e,'ROOT',root),\
                 mock.patch.object(runner,'source_pins',return_value=[]):
                runner.reserve(input_pin,output,reservation)
                self.assertTrue(output.parent.is_dir())
                with self.assertRaises(e.a.AuditError):runner.reserve(input_pin,here/'other',here/'second.json')
                guard=mock.Mock();guard.run_guarded.side_effect=RuntimeError('literal guard failure')
                result=runner.execute(reservation,guard)
                self.assertFalse(result['passed']);self.assertIn('literal guard failure',result['reason'])
                self.assertTrue(output.with_name('out_RUNNER.json').is_file())
                with self.assertRaises(FileExistsError):runner.execute(reservation,guard)


if __name__=='__main__':unittest.main()
