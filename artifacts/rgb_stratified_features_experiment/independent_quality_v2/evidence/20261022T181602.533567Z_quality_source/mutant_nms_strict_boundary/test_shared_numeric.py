"""Synthetic successor regression: only the inherited V30 closure may repeat."""
import ast
import copy
from pathlib import Path
import tempfile
import unittest
import contract as c
import run_audit as r


class SharedNumericTests(unittest.TestCase):
    def fixture(self,root):
        closure=dict(path=str((root/'artifacts/rgb_dilated_mask_experiment/INPUT_CLOSURE.json').resolve()),
                     bytes=123,sha256=c.INHERITED_CLOSURE_SHA)
        other=dict(path=str((root/'other.json').resolve()),bytes=13,sha256='a'*64)
        return dict(inherited_input_closure=closure,frozen_numeric_files=[other,closure,copy.deepcopy(closure)])

    def parse(self,inputs):
        if hasattr(c,'frozen_numeric_pin_map'):return c.frozen_numeric_pin_map(inputs)
        return c.pin_map(inputs['frozen_numeric_files'])

    def test_two_roles_share_identical_v30_closure(self):
        with tempfile.TemporaryDirectory() as t:
            inputs=self.fixture(Path(t))
            try:result=self.parse(inputs)
            except ValueError as error:self.fail('identical inherited/training closure role rejected: '+str(error))
            self.assertEqual(len(result),2)
            self.assertEqual(result[inputs['inherited_input_closure']['path']],inputs['inherited_input_closure'])

    def test_single_closure_stays_valid(self):
        with tempfile.TemporaryDirectory() as t:
            inputs=self.fixture(Path(t));inputs['frozen_numeric_files'].pop()
            self.assertEqual(len(self.parse(inputs)),2)

    def test_conflicting_hash_or_size_is_rejected(self):
        for field,value in (('sha256','f'*64),('bytes',124)):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as t:
                inputs=self.fixture(Path(t));inputs['frozen_numeric_files'][-1][field]=value
                with self.assertRaises(ValueError):self.parse(inputs)

    def test_only_exact_inherited_role_is_shared(self):
        for fault in ('other_pin','different_role','wrong_sha','wrong_name','noncanonical'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as t:
                inputs=self.fixture(Path(t))
                if fault=='other_pin':inputs['frozen_numeric_files'] += [copy.deepcopy(inputs['frozen_numeric_files'][0])]
                elif fault=='different_role':inputs['inherited_input_closure']=inputs['frozen_numeric_files'][0]
                else:
                    shared=inputs['inherited_input_closure']
                    if fault=='wrong_sha':shared['sha256']='e'*64
                    elif fault=='wrong_name':shared['path']=str(Path(t)/'other_closure.json')
                    else:shared['path']=str(Path(t))+'/artifacts/rgb_dilated_mask_experiment/../rgb_dilated_mask_experiment/INPUT_CLOSURE.json'
                    inputs['frozen_numeric_files'][-1]=copy.deepcopy(shared)
                with self.assertRaises(ValueError):self.parse(inputs)

    def test_three_occurrences_are_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            inputs=self.fixture(Path(t));inputs['frozen_numeric_files'].append(copy.deepcopy(inputs['inherited_input_closure']))
            with self.assertRaises(ValueError):self.parse(inputs)

    def test_bank_raw_stage_and_receipt_lists_remain_strict(self):
        with tempfile.TemporaryDirectory() as t:
            inputs=self.fixture(Path(t));shared=inputs['inherited_input_closure']
            for role in ('bank_input_files','raw_reference_files','stage_files','accepted_receipt'):
                with self.subTest(role=role),self.assertRaises(ValueError):c.pin_map([shared,copy.deepcopy(shared)])

    def test_both_bindings_calls_use_dedicated_gate(self):
        tree=ast.parse(Path(c.__file__).read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='bindings')
        calls=[n for n in ast.walk(function) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='frozen_numeric_pin_map']
        self.assertEqual(len(calls),2)

    def test_wrapper_uses_successor_registry_and_schemas(self):
        self.assertEqual(r.REGISTRY.name,'execution_reservations_v2')
        self.assertEqual(r.SCHEMA,'independent_three_arm_quality_reservation_v2')
        self.assertEqual(r.RUNNER_SCHEMA,'independent_three_arm_quality_runner_v2')


if __name__=='__main__':unittest.main(verbosity=2)
