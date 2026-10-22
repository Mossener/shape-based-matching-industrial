"""Synthetic file integration regressions for the quality execution contract.

Fixtures are tiny UTF-8 text, never serialized detector banks or dataset
images.  No compiler, native executable, decoder or matcher is used.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

import prepare_quality_inputs as inputs
import quality_contract as contract
import quality_execution_inputs as execution

HERE = Path(__file__).resolve().parent


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    return inputs._pin(path)


class QualityRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='v31-quality-literals-')
        cls.root = Path(cls.temp.name).resolve()
        cls.real_pin = staticmethod(inputs._pin)
        cls.virtual = {}
        cls.exp = cls.root / 'experiment'
        cls.legacy = cls.root / 'legacy'
        cls.frozen = cls.root / 'inherited'
        cls.exp.mkdir();cls.legacy.mkdir();cls.frozen.mkdir()
        (cls.exp / 'PROTOCOL.json').write_text('{}\n', encoding='utf-8')
        cls.frames = []
        for ordinal in range(400):
            scene = [1, 4, 6, 7, 8, 10, 12, 13][ordinal // 50]
            image = ordinal % 50 + 1
            cls.frames.append(dict(scene_id=scene, image_id=image,
                rgb=f'test_primesense/{scene:06d}/rgb/{image:06d}.png',
                rgb_sha256='a' * 64, rgb_bytes=1, pilot=ordinal<8, timing=ordinal<64))
        cls.banks = [];old_banks = [];training_files = [];private = {};common_files = []
        for obj in inputs.OBJECTS:
            row = dict(object_id=obj)
            class_id = f'tless_object_{obj}'
            for arm, key in [('C0','control'), ('P','pooled'), ('B','stratified')]:
                directory = cls.frozen / f'obj{obj}' / 'rgb_training' if arm=='C0' else cls.exp / arm / f'obj{obj}'
                directory.mkdir(parents=True)
                row[key+'_training'] = str(directory)
                row[key+'_template_count'] = 1 if arm=='C0' else 2
                for name in ['template_metadata.json', f'templates_{class_id}.yml.gz']:
                    path = directory / name
                    path.write_text(f'synthetic text {obj} {arm} {name}\n', encoding='utf-8')
                    pin = inputs._pin(path)
                    if arm=='C0':private[path.relative_to(cls.frozen).as_posix()]={k:pin[k] for k in ['bytes','sha256']}
                    else:training_files.append(pin)
            old_raw = cls.frozen / f'obj{obj}' / 'original_pilot_raw';old_raw.mkdir()
            common_raw = cls.legacy / 'run_quality_development_v1/native' / f'obj{obj}/rgb_control';common_raw.mkdir(parents=True)
            for frame in cls.frames:
                for path_name in ['fallback','fused']:
                    prefix=f's{frame["scene_id"]}_i{frame["image_id"]}_{path_name}_raw'
                    for suffix in ['.csv.gz','_manifest.json']:
                        path=common_raw/(prefix+suffix);body=b'synthetic raw text\n'
                        pin=dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
                        cls.virtual[str(path)]=pin;common_files.append(pin)
                        if frame['pilot']:
                            path=old_raw/(prefix+suffix);body=b'synthetic historical text\n'
                            pin=dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest());cls.virtual[str(path)]=pin
                            private[path.relative_to(cls.frozen).as_posix()]={k:pin[k] for k in ['bytes','sha256']}
            cls.banks.append(row)
            old_banks.append(dict(object_id=obj,class_id=class_id,rgb_training=row['control_training'],
                rgb_template_count=1,original_pilot_raw=str(old_raw)))
        cls.training_pin=write_json(cls.exp/'training.json',dict(banks=cls.banks,files=training_files))
        cls.geometry_pin=write_json(cls.exp/'geometry.json',dict(plan=dict(width=848,height=832,padding_ltrb=[64,64,64,228],banks=18,geometry_feasible=True)))
        cls.audit_pin=write_json(cls.exp/'audit.json',dict(passed=True,
            schema='independent_stratified_training_geometry_audit_v1',
            scope='training_and_exact_geometry',
            input_pins=[cls.training_pin,cls.geometry_pin]))
        cls.acceptance_path=cls.exp/'acceptance.json'
        write_json(cls.acceptance_path,dict(schema='rgb_stratified_training_geometry_acceptance_v1',
            accepted_independent_audit=True,scope='training_and_exact_geometry',numeric_audit_passed=True,
            production_promotion=False,training_freeze=cls.training_pin,geometry_freeze=cls.geometry_pin,independent_audit=cls.audit_pin))
        cls.inherited_quality_pin=write_json(cls.legacy/'QUALITY_INPUT_FREEZE.json',dict(objects=inputs.OBJECTS,
            development=cls.frames,dataset_root=str(cls.root/'dataset'),rgb_banks=old_banks,total_matcher_call_budget=22176))
        cls.inherited_closure_pin=write_json(cls.legacy/'INPUT_CLOSURE.json',dict(objects=inputs.OBJECTS,
            inherited_frozen_root=str(cls.frozen),private_files=private))
        cls.common_stage_pin=write_json(cls.legacy/'run_quality_development_v1/QUALITY_STAGE_FREEZE.json',dict(
            completed=True,stage='development',native_exit_code=0,actual_matcher_calls=9600,files=common_files))
        cls.changed_bank=Path(cls.banks[0]['pooled_training'])/'template_metadata.json'
        cls.changed_old=Path(old_banks[0]['original_pilot_raw'])/'s1_i1_fallback_raw.csv.gz'
        cls.changed_common=cls.legacy/'run_quality_development_v1/native/obj1/rgb_control/s1_i1_fallback_raw.csv.gz'
        cls.changed_old.write_bytes(b'synthetic historical text\n')
        cls.changed_common.write_bytes(b'synthetic raw text\n')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        def fixture_pin(path):
            path=Path(path).resolve()
            return self.virtual[str(path)] if str(path) in self.virtual and not path.is_file() else self.real_pin(path)
        def fixture_check(pin):
            if fixture_pin(pin['path'])!=pin:raise ValueError('Pinned literal changed: '+pin['path'])
        self.patches=[mock.patch.object(inputs,'EXPERIMENT',self.exp),mock.patch.object(inputs,'INHERITED',self.legacy),
            mock.patch.object(inputs,'INHERITED_QUALITY_SHA256',self.inherited_quality_pin['sha256']),
            mock.patch.object(inputs,'INHERITED_CLOSURE_SHA256',self.inherited_closure_pin['sha256']),
            mock.patch.object(inputs,'INHERITED_DEVELOPMENT_SHA256',self.common_stage_pin['sha256'],create=True),
            mock.patch.object(inputs,'INHERITED_DEVELOPMENT_BYTES',self.common_stage_pin['bytes'],create=True),
            mock.patch.object(inputs,'_pin',fixture_pin),mock.patch.object(inputs,'_check_pin',fixture_check)]
        for patch in self.patches:patch.start()
        self.addCleanup(lambda:[patch.stop() for patch in reversed(self.patches)])

    def test_schema_matches_native(self):
        result=inputs.build(self.acceptance_path)
        native=(HERE/'quality_eval.cpp').read_text(encoding='utf-8')
        self.assertIn('str(inputs["version"])=="'+result['version']+'"',native,
                      'preparer and native quality schema disagree')

    def test_execution_uses_explicit_three_arm_count_fields(self):
        source=(HERE/'quality_execution_inputs.py').read_text(encoding='utf-8')
        self.assertNotIn('arm.replace("rgb_", "")',source,'pooled/stratified counts must use actual accepted field names')

    def test_old_gate_verifies_eight_pilot_frames(self):
        tree=ast.parse((HERE/'quality_execution_inputs.py').read_text(encoding='utf-8'))
        assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='use' for t in n.targets)]
        if assignments:
            expression=compile(ast.Expression(assignments[-1].value),'<literal-frame-selection>','eval')
            self.assertTrue(eval(expression,{},dict(mode='old_gate',frame={'pilot':True,'timing':False})),
                            'old_gate failed to select its pilot image bytes')
        else:
            self.assertTrue(callable(getattr(execution,'selected_frames',None)),'explicit frame selector required')
            self.assertEqual(len(execution.selected_frames('old_gate',self.frames)),8)

    def test_build_flags_support_frozen_v11(self):
        source=(HERE/'build_quality.py').read_text(encoding='utf-8')
        for token in ['"-std=c++17"','"-O3"','"-mssse3"','"-msse4.1"','"-fopenmp"']:
            self.assertIn(token,source,'frozen V11 compile flag missing: '+token)
        self.assertIn('control_v11',source)
        self.assertIn('MIPP',source,'frozen V11 MIPP include directory missing')

    def _reject_changed_accepted_payload(self,path):
        original=path.read_bytes()
        try:
            path.write_bytes(original+b'changed after acceptance\n')
            with self.assertRaises(ValueError,msg='changed accepted payload was silently re-frozen'):
                inputs.build(self.acceptance_path)
        finally:path.write_bytes(original)

    def test_changed_accepted_new_bank_is_rejected(self):self._reject_changed_accepted_payload(self.changed_bank)
    def test_changed_inherited_old_raw_is_rejected(self):self._reject_changed_accepted_payload(self.changed_old)
    def test_changed_v30_common_raw_is_rejected(self):self._reject_changed_accepted_payload(self.changed_common)

    def test_changed_v30_development_freeze_is_rejected(self):
        path=Path(self.common_stage_pin['path']);original=path.read_bytes()
        try:
            # Whitespace changes preserve all legacy completion fields.
            path.write_bytes(original+b' \n')
            with self.assertRaises(ValueError,msg='V30 accepted stage origin was silently re-frozen'):
                inputs.build(self.acceptance_path,check_payloads=False)
        finally:path.write_bytes(original)

    def test_imported_python_helpers_are_pinned(self):
        builder=(HERE/'build_quality.py').read_text(encoding='utf-8')
        runner=(HERE/'run_quality.py').read_text(encoding='utf-8')
        self.assertIn('EXPERIMENT / "native_provenance.py"',builder,'native provenance import missing from build pins')
        self.assertIn('EXPERIMENT / "native_provenance.py"',runner,'native provenance import missing from run pins')

    def test_selftest_payload_scope_is_empty(self):
        selector=getattr(execution,'required_payload_paths',None)
        self.assertTrue(callable(selector),'stage-specific payload allowlist missing')
        self.assertEqual(selector('selftest',{}),[],'literal selftest must not read banks or dataset payloads')

    def test_declaration_pins_acceptance_envelope(self):
        result=inputs.build(self.acceptance_path)
        self.assertIn(inputs._pin(self.acceptance_path),result['frozen_numeric_files'],
                      'acceptance envelope itself is not frozen')

    def test_outer_audit_must_bind_training_and_geometry(self):
        path=Path(self.audit_pin['path']);original=path.read_bytes()
        acceptance=self.acceptance_path;original_acceptance=acceptance.read_bytes()
        try:
            for mutation in [lambda a:a.pop('input_pins'),
                lambda a:a.update(schema='independent_stratified_training_audit_v1')]:
                audit=json.loads(original);mutation(audit);path.write_text(json.dumps(audit))
                a=json.loads(original_acceptance);a['independent_audit']=self.real_pin(path)
                acceptance.write_text(json.dumps(a))
                with self.assertRaises(ValueError,msg='Training-only or unbound audit accepted as combined geometry evidence'):
                    inputs._acceptance(acceptance)
        finally:path.write_bytes(original);acceptance.write_bytes(original_acceptance)

    def test_combined_report_uses_finalized_schema_and_scope(self):
        path=Path(self.audit_pin['path']);original=path.read_bytes()
        acceptance=self.acceptance_path;original_acceptance=acceptance.read_bytes()
        try:
            for key,value in [('schema','unknown'),('scope','training_only')]:
                audit=json.loads(original);audit[key]=value;path.write_text(json.dumps(audit))
                a=json.loads(original_acceptance);a['independent_audit']=self.real_pin(path)
                acceptance.write_text(json.dumps(a))
                with self.assertRaises(ValueError,msg='Nonfinal combined schema or scope accepted'):
                    inputs._acceptance(acceptance)
        finally:path.write_bytes(original);acceptance.write_bytes(original_acceptance)

    def test_geometry_input_bank_files_are_consumed_without_inventing_files(self):
        old=json.loads(Path(self.training_pin['path']).read_text())
        revised=copy.deepcopy(old);revised.pop('files')
        revised['schema']='rgb_stratified_geometry_inputs_v1'
        revised['bank_files']=[]
        for row in revised['banks']:
            for arm,key in [('C0','control'),('P','pooled'),('B','stratified')]:
                directory=Path(row[key+'_training'])
                revised['bank_files'].append(dict(arm=arm,object_id=row['object_id'],
                    bank=self.real_pin(directory/f'templates_tless_object_{row["object_id"]}.yml.gz'),
                    metadata=self.real_pin(directory/'template_metadata.json')))
        revised.update(source_numeric_audit=self.audit_pin,training_execution_acceptance=self.audit_pin,
            inherited_control_closure=self.inherited_closure_pin,source=self.audit_pin,
            original_attempts=[],production_promotion=False)
        # This test targets exact 18 bank_files parsing, separate from the
        # outer independent acceptance and root joined-evidence gate.
        parser=getattr(inputs,'_training_file_pins',None)
        self.assertTrue(callable(parser),'Accepted geometry bank_files parser is missing')
        pins=parser(revised,revised['banks'])
        self.assertEqual(len(pins),36)
        bad=copy.deepcopy(revised);bad['bank_files'].pop()
        with self.assertRaises(ValueError):parser(bad,bad['banks'])

    def test_stage_payload_paths_match_exact_schedules(self):
        data=inputs.build(self.acceptance_path,check_payloads=False)
        for mode,count in [('old_gate',204),('pilot',228),('development',9636),('timing',36)]:
            self.assertEqual(len(execution.required_payload_paths(mode,data)),count)
        self.assertEqual(execution.selected_frames('selftest',[]),[])
        self.assertEqual(len(execution.selected_frames('development',self.frames)),400)
        self.assertEqual(len(execution.selected_frames('timing',self.frames)),64)

    def test_verify_rejects_count_schedule_and_allowlist_rewrites(self):
        with tempfile.TemporaryDirectory(prefix='v31-declaration-literal-') as directory:
            root=Path(directory);data=inputs.build(self.acceptance_path,check_payloads=False)
            plan=root/'COMMON_PADDING_FREEZE.json';write_json(plan,data['common_padding_plan'])
            data['common_padding_json']=str(plan);data['frozen_numeric_files'].append(inputs._pin(plan))
            path=root/'QUALITY_INPUT_FREEZE.json';write_json(path,data);inputs.verify(path)
            mutations=[lambda d:d['banks'][0].update(pooled_template_count=100),
                lambda d:d['development'][0].update(rgb_bytes=2),
                lambda d:d['raw_reference_files'][0].update(sha256='b'*64)]
            for mutation in mutations:
                changed=copy.deepcopy(data);mutation(changed);write_json(path,changed)
                with self.assertRaises(ValueError):inputs.verify(path)


if __name__=='__main__':unittest.main()
