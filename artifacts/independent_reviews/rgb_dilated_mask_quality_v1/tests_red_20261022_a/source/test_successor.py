"""Successor-specific literal oracles; temporary numeric files only."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import audit
import identity_strata


def contract_module():
    path = Path(__file__).with_name('experiment_contract.py')
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('experiment_contract', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SuccessorRequirements(unittest.TestCase):
    def contract(self):
        module = contract_module()
        self.assertIsNotNone(module, 'Explicit dilation/acceptance contract is missing')
        return module

    def test_exact_new_arm_and_retention_schema(self):
        self.assertEqual(audit.ARMS, ('rgb_control', 'rgb_dilated_mask'))
        self.assertIn('rgb_dilated_mask_detected', audit.RETENTION_HEADER)

    def test_only_the_exact_single_mask_operator_may_change(self):
        c = self.contract()
        old = b'prefix\n'+c.OLD+b'\nsuffix\n'
        new = old.replace(c.OLD, c.NEW)
        c.check_core_delta(old, new)
        for wrong in [old, new+b'extra', new.replace(b'prefix',b'changed'), new+c.NEW]:
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                c.check_core_delta(old, wrong)

    def test_quality_gate_is_fixed_and_separate_from_arithmetic_pass(self):
        c = self.contract()
        pool = {'rgb_control':{'allGT':{'tp':215,'fp':42112}},
                'rgb_dilated_mask':{'allGT':{'tp':215,'fp':42111}}}
        self.assertTrue(c.quality_gate(pool)['passed'])
        for tp,fp in [(214,1),(215,42112),(216,42113)]:
            changed=copy.deepcopy(pool);changed['rgb_dilated_mask']['allGT'].update(tp=tp,fp=fp)
            self.assertFalse(c.quality_gate(changed)['passed'])
        changed=copy.deepcopy(pool);changed['rgb_control']['allGT']['tp']=214
        with self.assertRaises(ValueError):c.quality_gate(changed)

    def test_accepted_marker_must_bind_original_freezes_and_receipt(self):
        c = self.contract()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);train=root/'BANK_FREEZE.json';plan=root/'COMMON_PADDING_FREEZE.json'
            train.write_text('{}');plan.write_text('{}');reader=audit.Reader(root)
            t,p=reader.pin(train),reader.pin(plan)
            receipt=root/'receipt.json';receipt.write_text(json.dumps({'passed':True,'input_pins':{t['path']:t,p['path']:p}}))
            marker={'schema':'rgb_dilated_mask_independent_audit_acceptance_v1',
                    'accepted_independent_audit':True,'scope':'training_and_exact_geometry',
                    'training_freeze':t,'plan_freeze':p,'independent_audit':reader.pin(receipt)}
            c.check_acceptance(reader,marker,train,plan)
            for section,field,value in [('scope',None,'other'),('accepted_independent_audit',None,False),
                                        ('training_freeze','sha256','0'*64)]:
                wrong=copy.deepcopy(marker)
                if field:wrong[section][field]=value
                else:wrong[section]=value
                with self.subTest(section=section),self.assertRaises(ValueError):
                    c.check_acceptance(reader,wrong,train,plan)

    def test_acceptance_cannot_substitute_a_passed_unbound_receipt(self):
        c = self.contract()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);train=root/'BANK_FREEZE.json';plan=root/'COMMON_PADDING_FREEZE.json'
            train.write_text('{}');plan.write_text('{}');reader=audit.Reader(root)
            receipt=root/'receipt.json';receipt.write_text('{"passed":true,"input_pins":{}}')
            marker={'schema':'rgb_dilated_mask_independent_audit_acceptance_v1','accepted_independent_audit':True,
                    'scope':'training_and_exact_geometry','training_freeze':reader.pin(train),
                    'plan_freeze':reader.pin(plan),'independent_audit':reader.pin(receipt)}
            with self.assertRaises(ValueError):c.check_acceptance(reader,marker,train,plan)

    def test_macro_includes_all_six_objects_and_zero_denominators(self):
        function=getattr(audit,'macro_metrics',None)
        self.assertTrue(callable(function),'Independent object macro calculation is missing')
        counts={'tp':1,'fp':0,'fn':0,'gt':1,'ignored':0,'matched_iou_sum':1.}
        zero={k:0 for k in counts}
        objects={obj:{arm:{'allGT':dict(counts if obj==1 else zero),'eligible':dict(counts if obj==1 else zero)}
                      for arm in audit.ARMS} for obj in audit.OBJECTS}
        result=function(objects)
        self.assertEqual(result['rgb_control']['allGT']['precision'],1/6)
        self.assertEqual(result['rgb_dilated_mask']['eligible']['recall'],1/6)

    def test_historical_v27_cross_groups_are_not_replaced_by_v22_groups(self):
        function=getattr(identity_strata,'summarize_three',None)
        self.assertTrue(callable(function),'V22/V27/current identity crossing is missing')
        old,previous,current={},{},{}
        for metric,counts in {'allGT':[148,67,59,126],'eligible':[147,62,56,109]}.items():
            identity=0
            for (rgb,binary),count in zip([(1,1),(1,0),(0,1),(0,0)],counts):
                for _ in range(count):
                    key=(1,4,9,metric,identity);identity+=1
                    old[key]=(rgb,binary,0 if rgb and binary else -1)
                    # 156 retained / 59 lost / 27 gained / 158 neither for allGT.
                    detected=int((rgb and identity<=156) or (not rgb and 215<identity<=242))
                    previous[key]=(rgb,detected,1 if rgb and detected else -1)
                    current[key]=(rgb,rgb,1 if rgb else -1)
        report,records=function(old,previous,current)
        self.assertEqual(len(records),774)
        self.assertEqual(report['v27_group_counts']['allGT'],{'retained':156,'lost':59,'gained':27,'neither':158})
        self.assertTrue(any(r['v27_group']=='lost' for r in records))
        self.assertIn('v22_v27_cross_groups',report)
        wrong=dict(previous);key=next(iter(wrong));wrong[key]=(0,0,-1)
        with self.assertRaises(ValueError):function(old,wrong,current)
        wrong=dict(current);wrong.pop(next(iter(wrong)))
        with self.assertRaises(ValueError):function(old,previous,wrong)


if __name__=='__main__':unittest.main()
