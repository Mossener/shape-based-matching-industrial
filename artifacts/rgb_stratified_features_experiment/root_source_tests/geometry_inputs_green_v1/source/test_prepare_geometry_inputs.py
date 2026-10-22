"""In-memory checks for binding geometry declarations to accepted training."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import prepare_geometry_inputs as subject


class GeometryInputs(unittest.TestCase):
    def fixture(self):
        root = subject.HERE / 'synthetic_not_on_disk'
        run = root / 'training'
        inherited = root / 'original'
        self.inventory = {}

        def pin(path):
            path = str(Path(path).resolve())
            result = dict(path=path, bytes=100, sha256='a' * 64)
            self.inventory[path] = result
            return result

        self.acceptance_path = root / 'accepted.json'
        audit_path = root / 'audit.json'
        provenance_path = root / 'provenance.json'
        acceptance = dict(schema='rgb_stratified_training_execution_acceptance_v1',
            real_training_accepted=True, source_runtime_accepted=True,
            numeric_audit_passed=True, production_promotion=False,
            independent_audit=pin(audit_path), training_provenance=pin(provenance_path))
        audit = dict(numeric_training_audit_passed=True,
            public_numeric_training_complete=True, comparison_feasible=True,
            literal_only=False, successful_templates={'P': [5]*6, 'B': [5]*6},
            input_pins={}, output_pins_before={}, output_pins_after={})
        training_pin = pin(subject.HERE / 'TRAINING_INPUT_FREEZE.json')
        provenance = dict(passed=True, mode='train', input_freeze=training_pin,
            command=['synthetic.exe', '--output', str(run)])
        self.inventory[str(subject.CLOSURE)] = dict(path=str(subject.CLOSURE),
            bytes=100, sha256=subject.CLOSURE_SHA)
        closure = dict(inherited_frozen_root=str(inherited),
            objects=subject.OBJECTS[:], rgb_banks=[], private_files={})
        training = dict(origin=copy.deepcopy(self.inventory[str(subject.CLOSURE)]),
            original_attempts=[])
        audit['input_pins'][training_pin['path']] = {k:training_pin[k] for k in ('bytes','sha256')}
        for obj in subject.OBJECTS:
            control = inherited / 'frozen_inputs' / ('obj'+str(obj)) / 'rgb_training'
            closure['rgb_banks'].append(dict(object_id=obj, rgb_training=str(control), rgb_template_count=3))
            for directory in (control, run/'rgb_pooled_features'/('obj'+str(obj)),
                              run/'rgb_stratified_features'/('obj'+str(obj))):
                for name in ('templates_tless_object_%s.yml.gz' % obj, 'template_metadata.json'):
                    value=pin(directory/name)
                    small={k:value[k] for k in ('bytes','sha256')}
                    if directory==control:
                        closure['private_files'][(directory/name).relative_to(inherited).as_posix()]=small
                    else:
                        audit['output_pins_before'][(directory/name).relative_to(run).as_posix()]=small
                        audit['output_pins_after'][(directory/name).relative_to(run).as_posix()]=small
            value=pin(root/('obj%s_original.csv' % obj))
            training['original_attempts'].append(dict(object_id=obj,pin=value))
            audit['input_pins'][value['path']]={k:value[k] for k in ('bytes','sha256')}
        pin(self.acceptance_path)
        pin(subject.__file__)
        self.documents={str(self.acceptance_path):acceptance, str(audit_path):audit,
            str(provenance_path):provenance, str(subject.CLOSURE):closure,
            str(subject.HERE/'TRAINING_INPUT_FREEZE.json'):training}
        return acceptance,audit,provenance,closure,training

    def build(self):
        def check(value):
            subject.p.require(value == self.inventory.get(value['path']), 'synthetic content pin changed')
        with patch.object(subject,'read',side_effect=lambda path: copy.deepcopy(self.documents[str(path)])), \
             patch.object(subject.p,'check_pin',side_effect=check), \
             patch.object(subject.p,'file_pin',side_effect=lambda path: copy.deepcopy(self.inventory[str(path)])):
            return subject.build(self.acceptance_path)

    def test_all_eighteen_banks_and_six_originals(self):
        self.fixture()
        result=self.build()
        self.assertEqual(len(result['bank_files']),18)
        self.assertEqual([r['object_id'] for r in result['banks']],subject.OBJECTS)
        self.assertEqual(len(result['original_attempts']),6)
        self.assertEqual([r['arm'] for r in result['bank_files'][:3]],['C0','P','B'])
        self.assertEqual([r['stratified_template_count'] for r in result['banks']],[5]*6)
        self.assertFalse(result['production_promotion'])

    def test_numeric_input_freeze_must_match_accepted_provenance(self):
        _,audit,provenance,_,_=self.fixture()
        audit['input_pins'][provenance['input_freeze']['path']]['sha256']='b'*64
        with self.assertRaises(ValueError):
            self.build()

    def test_failed_audit_changed_outputs_or_unbound_original_rejected(self):
        for change in ('failed','literal','changed','original','runtime','origin'):
            acceptance,audit,_,closure,_=self.fixture()
            if change=='failed': audit['numeric_training_audit_passed']=False
            elif change=='literal': audit['literal_only']=True
            elif change=='changed': audit['output_pins_after']['extra']={}
            elif change=='original': audit['input_pins'].pop(next(k for k in audit['input_pins'] if k.endswith('.csv')))
            elif change=='runtime': acceptance['source_runtime_accepted']=False
            else: self.inventory[str(subject.CLOSURE)]['sha256']='b'*64
            with self.subTest(change=change), self.assertRaises((ValueError,KeyError)):
                self.build()


if __name__=='__main__':
    unittest.main(verbosity=2)
