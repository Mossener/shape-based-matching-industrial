"""Synthetic joins reject passing receipts from a different training/geometry."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import accept_training_geometry as subject


class JoinedAcceptance(unittest.TestCase):
    def fixture(self):
        self.docs={};self.pins={}
        root=subject.HERE/'synthetic_join_not_on_disk'
        def pin(path):
            path=str(Path(path).resolve())
            self.pins[path]=dict(path=path,bytes=100,sha256='a'*64)
            return copy.deepcopy(self.pins[path])
        def doc(name,value):
            path=root/name
            self.docs[str(path)]=value
            return pin(path)
        source=pin(root/'source.py')
        pin(subject.__file__)
        numeric=dict(numeric_training_audit_passed=True,public_numeric_training_complete=True,
            comparison_feasible=True,literal_only=False,output_pins_before={'x':1},output_pins_after={'x':1})
        numeric_pin=doc('numeric.json',numeric)
        training=dict(schema='rgb_stratified_training_execution_acceptance_v1',
            real_training_accepted=True,source_runtime_accepted=True,numeric_audit_passed=True,
            production_promotion=False,independent_audit=numeric_pin)
        training_pin=doc('training.json',training)
        inputs=dict(schema='rgb_stratified_geometry_inputs_v1',production_promotion=False,
            training_execution_acceptance=training_pin,source_numeric_audit=numeric_pin,
            banks=[dict(object_id=obj,control_template_count=3,pooled_template_count=5,
                        stratified_template_count=5) for obj in (1,2,5,8,12,17)])
        input_pin=doc('inputs.json',inputs)
        plan=dict(width=848,height=832,loaded_layers=156)
        freeze=dict(schema='rgb_stratified_common_geometry_freeze_v1',exact_geometry_computed=True,
            independent_geometry_audit_required=True,numeric_audit_passed=False,
            production_promotion=False,training_freeze=input_pin,source_pins=[source],plan=plan)
        freeze_pin=doc('freeze.json',freeze)
        scan=dict(passed=True,scanned_banks=18,input_freeze=input_pin,source_numeric_audit=numeric_pin,
            geometry_freeze=freeze_pin,loaded_layers=156)
        scan_pin=doc('scan.json',scan)
        guard=dict(passed=True,exit_code=0,maximum_seconds=1800,command=['synthetic-only'])
        guard_pin=doc('scan_guard.json',guard)
        launch=doc('launch.json',dict(limits=dict(maximum_seconds=1800),command=['synthetic-only']))
        scanner=dict(schema='rgb_stratified_guarded_geometry_runner_v1',passed=True,guard=guard_pin,
            scanner_receipt=scan_pin,geometry_freeze=freeze_pin,source_pins=[source],launch=launch)
        scanner_pin=doc('scanner.json',scanner)
        geometry=dict(schema='rgb_stratified_independent_geometry_audit_v1',passed=True,
            accepted_independent_audit=True,numeric_audit_passed=True,scope='exact_geometry_only',
            production_promotion=False,training_freeze=input_pin,geometry_freeze=freeze_pin,
            source_numeric_audit=numeric_pin,input_pins_before=[input_pin,freeze_pin],
            input_pins_after=[input_pin,freeze_pin],computed_plan=copy.deepcopy(plan),
            auditor_sources_before=[source],auditor_sources_after=[source])
        geometry_pin=doc('independent_evidence/audit_output/INDEPENDENT_GEOMETRY_AUDIT.json',geometry)
        independent_guard=copy.deepcopy(guard)
        interpreter=pin(root/'synthetic_python.exe')
        command=[interpreter['path'],'-B',str(subject.HERE/'geometry/independent_geometry_audit.py')]
        for flag,value in (('inputs',input_pin),('scanner-freeze',freeze_pin)):
            command.extend(('--'+flag,value['path'],'--'+flag+'-bytes',str(value['bytes']),
                            '--'+flag+'-sha256',value['sha256']))
        command.extend(('--output',str(root/'independent_evidence/audit_output')))
        independent_guard['command']=command
        doc('independent_execution/guard_receipt.json',independent_guard)
        reservation=doc('independent_reserved.json',dict(execution=str(root/'independent_execution'),
            guard_limits=dict(maximum_seconds=1800),execution_source_pins=[source,interpreter],
            training_freeze=input_pin,geometry_freeze=freeze_pin,evidence=str(root/'independent_evidence')))
        marker=doc('independent_consumed.json',dict(consumed=True,reservation=reservation))
        independent=dict(schema='rgb_stratified_independent_geometry_runner_receipt_v1',passed=True,
            scope='exact_geometry_only',guard=independent_guard,audit_output=geometry_pin,
            reservation=reservation,consumed_marker=marker)
        independent_pin=doc('independent.json',independent)
        self.paths=[p['path'] for p in (training_pin,input_pin,scanner_pin,independent_pin)]
        return training,inputs,scanner,geometry,independent,numeric

    def build(self):
        def check(value):
            subject.p.require(self.pins.get(value['path'])==value,'synthetic pin changed')
        with patch.object(subject,'read',side_effect=lambda path:copy.deepcopy(self.docs[str(path)])), \
             patch.object(subject.p,'file_pin',side_effect=lambda path:copy.deepcopy(self.pins[str(path)])), \
             patch.object(subject.p,'check_pin',side_effect=check):
            return subject.build(*self.paths)

    def test_complete_join_retains_scope_and_both_freeze_pins(self):
        self.fixture();result=self.build()
        self.assertTrue(result['passed']);self.assertFalse(result['quality_tested'])
        self.assertFalse(result['production_promotion']);self.assertEqual(result['loaded_layers'],156)
        self.assertEqual(result['scope'],'training_and_exact_geometry')
        paths={p['path'] for p in result['input_pins']}
        self.assertIn(self.paths[1],paths)
        self.assertIn(next(k for k in self.docs if k.endswith('freeze.json')),paths)

    def test_failed_unrelated_changed_or_incomplete_evidence_rejected(self):
        for change in ('runtime','unrelated_training','numeric_changed','wrong_scope',
                       'wrong_freeze','plan','incomplete','sources','guard','pins',
                       'reservation_training','reservation_geometry','consumed','command'):
            training,inputs,scanner,geometry,independent,numeric=self.fixture()
            if change=='runtime': training['source_runtime_accepted']=False
            elif change=='unrelated_training': inputs['training_execution_acceptance']={}
            elif change=='numeric_changed': numeric['output_pins_after']={}
            elif change=='wrong_scope': geometry['scope']='training_only'
            elif change=='wrong_freeze': geometry['geometry_freeze']={}
            elif change=='plan': geometry['computed_plan']['width']=864
            elif change=='incomplete': inputs['banks'].pop()
            elif change=='sources': geometry['auditor_sources_after']=[]
            elif change=='guard': independent['guard']['maximum_seconds']=3600
            elif change=='pins': geometry['input_pins_after'][0]=dict(geometry['input_pins_after'][0],bytes=99)
            elif change=='reservation_training':
                self.docs[independent['reservation']['path']]['training_freeze']={}
            elif change=='reservation_geometry':
                self.docs[independent['reservation']['path']]['geometry_freeze']={}
            elif change=='consumed': self.docs[independent['consumed_marker']['path']]['consumed']=False
            elif change=='command': independent['guard']['command']=['wrong_worker.py']
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):
                self.build()


if __name__=='__main__':unittest.main(verbosity=2)
