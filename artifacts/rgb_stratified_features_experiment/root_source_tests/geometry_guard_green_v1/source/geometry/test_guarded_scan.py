"""Synthetic process-launch checks; the real watchdog is never started here."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_guarded_scan as subject


class GuardedScan(unittest.TestCase):
    def fixture(self, base):
        source=base/'synthetic_source.py';source.write_text('# synthetic\n')
        inputs=base/'inputs.json';inputs.write_text('{}\n')
        audit=base/'audit.json';audit.write_text('{}\n')
        reservation=base/'reservation.json'
        output=base/'output'
        subject.fresh_json(reservation,dict(schema='rgb_stratified_geometry_reservation_v1',
            reserved=True,stage='all_eighteen_bank_geometry',output=str(output),
            source_pins=[subject.pins.file_pin(source)],input_freeze=subject.pins.file_pin(inputs),
            source_numeric_audit=subject.pins.file_pin(audit)))
        return reservation,base/'execution',base/'runner.json',output,source

    def guard(self, success):
        def fake(command,env,cwd,output,execution,**limits):
            reservation=Path(command[-1])
            self.assertTrue(reservation.with_name(reservation.name+'.guard_launch.json').is_file())
            self.assertEqual(limits,subject.LIMITS)
            output.mkdir();execution.mkdir()
            result=dict(passed=success,started=True,exit_code=0 if success else 2)
            subject.fresh_json(execution/'guard_receipt.json',result)
            if success:
                pins={}
                for key in ('geometry_freeze','geometry_report','common_padding_plan'):
                    path=output/(key+'.json');path.write_text('{}\n');pins[key]=subject.pins.file_pin(path)
                subject.fresh_json(output/'receipt.json',dict(passed=True,scanned_banks=18,
                    reservation=subject.pins.file_pin(reservation),**pins))
            return result
        return fake

    def test_complete_scanner_is_bound_to_guard_and_single_launch(self):
        with tempfile.TemporaryDirectory() as path:
            reservation,execution,receipt,output,_=self.fixture(Path(path))
            with patch.object(subject.execution_guard,'run_guarded',side_effect=self.guard(True)) as guard:
                result=subject.launch(reservation,execution,receipt)
                self.assertTrue(result['passed']);self.assertEqual(guard.call_count,1)
                self.assertEqual(result['scanner_receipt'],subject.pins.file_pin(output/'receipt.json'))
                with self.assertRaises(ValueError): subject.launch(reservation,execution,receipt)
                self.assertEqual(guard.call_count,1)

    def test_failed_child_preserves_failure_and_cannot_retry(self):
        with tempfile.TemporaryDirectory() as path:
            reservation,execution,receipt,_,_=self.fixture(Path(path))
            with patch.object(subject.execution_guard,'run_guarded',side_effect=self.guard(False)) as guard:
                result=subject.launch(reservation,execution,receipt)
                self.assertFalse(result['passed']);self.assertTrue(result['failure_preserved'])
                self.assertTrue(receipt.exists())
                with self.assertRaises(ValueError): subject.launch(reservation,execution,receipt)
                self.assertEqual(guard.call_count,1)

    def test_changed_source_stops_before_process_creation(self):
        with tempfile.TemporaryDirectory() as path:
            reservation,execution,receipt,_,source=self.fixture(Path(path))
            source.write_text('# changed\n')
            with patch.object(subject.execution_guard,'run_guarded') as guard:
                with self.assertRaises(ValueError): subject.launch(reservation,execution,receipt)
                guard.assert_not_called()


if __name__=='__main__': unittest.main(verbosity=2)
