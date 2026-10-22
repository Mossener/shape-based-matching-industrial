"""Pure temporary numeric fixtures; no dataset/native/bank IO."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent


class AuditAcceptanceTests(unittest.TestCase):
    def load_module(self):
        path=HERE/'accept_training_audit.py'
        self.assertTrue(path.is_file(),'missing independent-audit acceptance implementation')
        spec=importlib.util.spec_from_file_location('accept_training_audit',path)
        item=importlib.util.module_from_spec(spec);spec.loader.exec_module(item)
        return item

    def test_acceptance_is_separate_and_requires_both_frozen_inputs(self):
        c=self.load_module()
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            root=Path(directory);train=root/'BANK_FREEZE.json';plan=root/'COMMON_PADDING_FREEZE.json';audit=root/'audit.json';dest=root/'AUDIT_ACCEPTANCE.json'
            train.write_text('{"complete":true}\n');plan.write_text('{"passed":true}\n')
            before=(train.read_bytes(),plan.read_bytes())
            audit.write_text(json.dumps({'passed':True,'input_pins':{str(train.resolve()):c.pin(train),str(plan.resolve()):c.pin(plan)}}))
            marker=c.accept(train,plan,audit,dest)
            self.assertTrue(marker['accepted_independent_audit'])
            self.assertEqual((train.read_bytes(),plan.read_bytes()),before)
            self.assertEqual(marker['independent_audit'],c.pin(audit))
            with self.assertRaises(ValueError): c.accept(train,plan,audit,dest)

    def test_unrelated_failed_or_stale_audit_is_rejected(self):
        c=self.load_module()
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            root=Path(directory);train=root/'BANK_FREEZE.json';plan=root/'COMMON_PADDING_FREEZE.json';audit=root/'audit.json'
            train.write_text('{}');plan.write_text('{}')
            variants=[{'passed':True,'input_pins':{}}, {'passed':False,'input_pins':{str(train.resolve()):c.pin(train),str(plan.resolve()):c.pin(plan)}},
                      {'passed':True,'input_pins':{str(train.resolve()):dict(c.pin(train),sha256='0'*64),str(plan.resolve()):c.pin(plan)}}]
            for i,value in enumerate(variants):
                audit.write_text(json.dumps(value));dest=root/f'accept{i}.json'
                with self.assertRaises(ValueError):c.accept(train,plan,audit,dest)
                self.assertFalse(dest.exists())


if __name__=='__main__':unittest.main(verbosity=2)
